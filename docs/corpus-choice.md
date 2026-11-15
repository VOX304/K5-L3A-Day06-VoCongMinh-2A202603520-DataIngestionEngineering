# Corpus: *Alice's Adventures in Wonderland*

Verified snapshot: Lewis Carroll's original English text, [Project Gutenberg ebook 11](https://www.gutenberg.org/ebooks/11), Millennium Fulcrum Edition 3.0, updated June 26, 2025 according to the downloaded header. The raw file was downloaded on November 15, 2026 UTC. Its SHA-256 is `01b38ea4c710a84bc18d0bd41271a5a1a92b94e97b2812f4dece97d4a694725e`; preparation rejects a changed edition rather than silently changing gold locations.

The 12 actual chapter headings yield **82** non-overlapping source units, **142,809** normalized characters in total; each unit contains **1,500–3,092** characters. These are source locations for unpaginated text, not physical PDF pages. [The manifest](../data/manifest.json) records every unit's size and chapter-local `[start,end)` offsets. Consecutive units exclude only the two newline separators. A reconstruction test checks that segmentation preserves chapters without duplication or gaps. The cover, contents and Gutenberg license are excluded from retrieval; the complete raw source is retained.

## Source and reuse basis

The catalog identifies Carroll as 1832–1898 and lists this edition as public domain in the USA. The downloaded text has no special permission-only notice. The [Vietnamese Embassy's copyright overview](https://vietnamembassy-usa.org/basic-page/intellectual-property) describes a life-plus-50 term for literary works. Applying that term to this original author's 1898 death is the basis for treating the original prose as out of economic copyright in this local educational exercise; this is an inference from the cited sources, not a claim of permission from a modern publisher. Attribution is retained. No modern translation, editorial commentary or images are ingested. The [official consolidated law](https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-11-vbhn-vpqh-38786/43592.htm) is the legislative reference; local rights are separate from the US catalog status.

Preserve [data/NOTICE.md](../data/NOTICE.md), [the full Gutenberg terms](../data/LICENSE.gutenberg.txt) and [the unmodified raw text](../data/raw/alice.txt) alongside excerpts. The [Gutenberg license](https://www.gutenberg.org/policy/license.html) includes conditions on notices and its trademark. No public publishing or paid redistribution was performed by this task.

## Normalization and metadata

NFC Unicode normalization, CRLF-to-LF conversion, horizontal whitespace cleanup and line trimming preserve paragraph boundaries. Underscore emphasis markers are removed. The last occurrences of the 12 chapter headings identify body chapters rather than the table of contents. Short unit tails merge into the preceding unit within the same chapter. No OCR is needed.

`document_id` and `source` identify the ebook and exact download URL; integer `page` is the sequential source-unit ID. `chapter_roman` is a string parsed from the source heading; `language=en` comes from the English source. Integer `unit_chars`, `chapter_char_start` and `chapter_char_end` permit validation and traceability. All are copied into chunk metadata. Chapter filtering has 12 genuine scopes.

## Benchmark verification

The original draft split is unchanged: q01–q15 dev, q16–q20 test. Before retrieval, exact quote validation and AI-assisted source reading corrected nonexistent draft wording, wrong chapter assignments (q14 VI, q15 XI), insufficient answers/evidence (q08, q10), ambiguous q07/q11 and reversed speaker attribution in q20. [Source review](../benchmark/source_review.json) records each justification and its AI provenance; [validation](../benchmark/validation.json) reports 20 exact matches and no problems. Human sign-off is explicitly pending.

Every question assumes its listed chapter is supplied by the reader **before retrieval**. This is contextual input, not a chapter inferred from the answer. All 20 use this scenario, so effectiveness without supplied chapter context is not established. Dev includes chapters IX and XI also present in test; test is a small question holdout, not a disjoint chapter/domain test. [Freeze record](../benchmark/freeze.json) records code, corpus, question and configuration hashes before the current dev run. The first freeze is retained separately because a reload fingerprint defect required a code fix before any test query could run; no change used test scores.
