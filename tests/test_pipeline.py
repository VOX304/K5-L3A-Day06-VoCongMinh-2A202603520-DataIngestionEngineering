"""Behavioral checks; fixture text is not the lab's real corpus/benchmark."""
from starter.src.ingestion import normalize_text
from starter.src.chunking import fixed_size
from starter.src.models import DocumentPage
from starter.src.chunking import by_paragraph
from starter.src.evaluation import evaluate_query, summarize
import pytest


def test_fixed_chunks_preserve_source_and_overlap():
    page = DocumentPage('doc', 'source', 7, 'abcdefghij', {'chapter': 'I'})
    chunks = fixed_size(page, size=6, overlap=2)
    assert [c.text for c in chunks] == ['abcdef', 'efghij']
    assert all(c.page == 7 and c.metadata == {'chapter': 'I'} for c in chunks)
    assert len({c.chunk_id for c in chunks}) == 2
    assert fixed_size(page, 6, 2) == chunks


def test_normalization_preserves_paragraph_structure():
    assert normalize_text('Cafe\u0301  text\r\n\r\nnext\tword') == 'Caf\u00e9 text\n\nnext word'


def test_paragraph_chunks_keep_short_paragraphs_together_and_bound_long_ones():
    page = DocumentPage('doc', 'source', 1, 'one\n\ntwo\n\nabcdefghijk')
    assert [c.text for c in by_paragraph(page, 10)] == ['one\n\ntwo', 'abcdefghij', 'k']
    with pytest.raises(ValueError):
        fixed_size(page, 5, 5)


def test_hit_requires_location_and_sufficient_evidence():
    question = {'id': 'fixture', 'split': 'dev', 'gold_source_id': 'doc',
                'gold_page': 1, 'evidence_quote': 'the red door'}
    hits = [{'text': 'a red door', 'metadata': {'document_id': 'doc', 'page': 1}},
            {'text': 'behind the red door stood Alice', 'metadata': {'document_id': 'doc', 'page': 1}}]
    result = evaluate_query(question, hits)
    assert result['hit_at_1'] is False
    assert result['hit_at_3'] is True
    result['strategy'] = 'A'
    assert summarize([result])['A/dev']['hit_at_3'] == {'correct': 1, 'total': 1, 'rate': 1.0}
    hits[1]['metadata']['page'] = 2
    assert evaluate_query(question, hits)['hit_at_3'] is False


def test_alternative_gold_is_accepted_but_fragment_union_is_not():
    question = {'id': 'fixture', 'split': 'dev', 'gold_source_id': 'doc',
                'gold_page': 1, 'evidence_quote': 'the red door',
                'alternative_evidence': [{'source_id': 'other', 'page': 2, 'quote': 'a scarlet entrance'}]}
    hit = {'text': 'a scarlet entrance', 'metadata': {'document_id': 'other', 'page': 2}}
    assert evaluate_query(question, [hit])['hit_at_1'] is True
    fragments = [{'text': text, 'metadata': {'document_id': 'doc', 'page': 1}}
                 for text in ['the red', 'door']]
    assert evaluate_query(question, fragments)['hit_at_3'] is False


def test_corpus_loader_rejects_duplicate_source_locations(tmp_path):
    import json
    from starter.src.ingestion import load_corpus
    item = {'document_id': 'fixture', 'source': 'fixture-only', 'page': 1, 'text': 'one paragraph'}
    path = tmp_path / 'fixture.jsonl'
    path.write_text(json.dumps(item) + '\n' + json.dumps(item), encoding='utf-8')
    with pytest.raises(ValueError, match='Duplicate source location'):
        load_corpus(path)


def test_preparation_assigns_real_unit_location_only_after_quote_match():
    from starter.scripts.prepare_corpus import verify_questions
    pages = [DocumentPage('doc', 'fixture', 9, 'Alice found a brass key.', {'chapter_roman': 'I'})]
    seeds = [{'id': 'fixture', 'evidence_quote': 'a brass key', 'filter': {'chapter_roman': 'I'}}]
    questions, errors = verify_questions(seeds, pages)
    assert errors == []
    assert questions[0]['gold_page'] == 9
    seeds[0]['evidence_quote'] = 'a silver key'
    questions, errors = verify_questions(seeds, pages)
    assert not questions and errors[0]['id'] == 'fixture'


def test_source_units_reconstruct_chapters_without_duplication_or_gaps():
    from starter.scripts.prepare_corpus import source_units
    romans = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']
    chapters = [f'CHAPTER {roman}.\nFixture heading\n\n' + '\n\n'.join(
        f'{roman} paragraph {i}: ' + 'x' * 1000 for i in range(7)) for roman in romans]
    pages = source_units('\n\n'.join(chapters))
    assert len(pages) >= 30
    assert all(len(p.text) >= 1500 for p in pages)
    assert len({p.text for p in pages}) == len(pages)
    for roman, original in zip(romans, chapters):
        units = [p for p in pages if p.metadata['chapter_roman'] == roman]
        assert '\n\n'.join(p.text for p in units) == normalize_text(original)
        for p in units:
            assert original[p.metadata['chapter_char_start']:p.metadata['chapter_char_end']] == p.text
