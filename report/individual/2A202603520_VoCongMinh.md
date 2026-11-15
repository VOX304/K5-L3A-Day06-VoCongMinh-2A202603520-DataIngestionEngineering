# Lab06 — Võ Công Minh — 2A202603520 — L3A

**Đã chạy thí nghiệm thật; phần audit của người chấm còn chờ.** Các bảng retrieval dưới đây lấy từ artifacts. Nhãn AI được ghi riêng, không trình bày như nhãn thủ công của học viên. Chưa push hoặc nộp bài qua kênh lớp.

## Dữ liệu và pipeline

Corpus là bản tiếng Anh *Alice's Adventures in Wonderland* của Lewis Carroll, [Project Gutenberg ebook 11](https://www.gutenberg.org/ebooks/11), Millennium Fulcrum Edition 3.0, header cập nhật 26/06/2025; tải ngày 15/11/2026 UTC. [Manifest](../../data/manifest.json) ghi SHA-256 của bản gốc, nguồn, thời điểm lấy và quy tắc tính. [Căn cứ sử dụng](../../docs/corpus-choice.md) đối chiếu catalog/tuổi tác giả và nguồn chính thức về thời hạn bảo hộ; giữ [thông báo nguồn](../../data/NOTICE.md), [license](../../data/LICENSE.gutenberg.txt) và toàn bộ bản gốc. Chỉ dùng văn xuôi gốc, không dùng ảnh hoặc bản dịch hiện đại.

Văn bản không có phân trang: lấy 12 chương thật, bỏ mục lục/phần ngoài nội dung truy xuất, gom các đoạn liên tiếp thành **82 đơn vị nguồn**, tổng **142.809 ký tự**, mỗi đơn vị **1.500–3.092 ký tự**. Không nhân bản nội dung để đạt số lượng. `page` là ID đơn vị nguồn, không phải số trang PDF. Mỗi đơn vị có vị trí ký tự `[start,end)` trong chương; test tái dựng kiểm tra không mất hoặc lặp nội dung. Chuẩn hóa NFC, xuống dòng LF, khoảng trắng ngang, giữ ranh giới đoạn và bỏ dấu gạch dưới dùng đánh dấu nhấn mạnh. Không cần OCR.

Model thật: `BAAI/bge-small-en-v1.5`, **384 chiều**, FastEmbed **0.9.1**, ONNX Runtime **1.32.0**, `CPUExecutionProvider`. FastEmbed phiên bản này ánh xạ model sang bản ONNX lượng tử hóa `Qdrant/bge-small-en-v1.5-onnx-Q`, revision `aa8f8b060edb00e03bfdd08813a2949946c8ba55`. Dùng `embed` cho document, `query_embed` cho câu hỏi; không thêm prefix ngoài thư viện. [Hash các file model/tokenizer](../../results/model-artifacts.json) được giữ để tái lập.

Store: Qdrant local **1.20.0**, metric cosine, tìm kiếm exact trong embedded local store, lưu ở `starter/.cache/qdrant`; mỗi chiến lược một collection. Python **3.12.2**, NumPy **2.5.4**. Không API key, Docker hoặc vector giả. Phí API bằng **0 USD**; không ước lượng điện/khấu hao máy.

Metadata bắt buộc: `document_id`, URL `source`, `page` kiểu integer. Trường lọc `chapter_roman` kiểu string lấy từ heading thật; `language=en` và `unit_chars`, `chapter_char_start/end` giúp kiểm chứng. 12 giá trị chương phân biệt được. Khi ingest lại, upsert ID xác định rồi xóa ID cũ không thuộc snapshot; runner nạp hai lần và kiểm tra số lượng. Thay tài liệu cần tạo snapshot mới và chạy dev lại, không giữ kết luận holdout của một corpus khác.

## Cấu hình và benchmark

| Strategy | Chunking | Filter |
|---|---|---|
| A | Cửa sổ 500 ký tự, overlap 50 | Không lọc |
| B | Gom theo đoạn, tối đa 500 ký tự; cắt cứng đoạn dài | Không lọc |
| C | Chính xác chunk và vector của B | `chapter_roman` do ngữ cảnh người đọc cung cấp trước retrieval |

Giữ nguyên corpus, model, store, query vector và metric. A–B thay chính sách chunk; B–C chỉ thay filter. Vector document B/C được tính một lần rồi dùng lại; verifier so sánh cả payload và vector lưu của hai collection.

[20 câu và gold](../../benchmark/questions.json): q01–q15 dev, q16–q20 test, giữ split từ bản nháp trước thí nghiệm. Cả 20 câu có chương được cung cấp trước, đáp ứng tối thiểu 3 câu filter và 1 câu test filter; chưa đại diện tình huống không biết chương. Trước retrieval, kiểm tra lần đầu có 11 quote sai trong 20 câu. Đã đọc nguồn để sửa wording, chương sai, evidence thiếu, câu hỏi mơ hồ và nhầm lời Queen/Alice ở q20. [Source review](../../benchmark/source_review.json) ghi lý do từng câu và người thực hiện là AI; [validation](../../benchmark/validation.json) xác nhận **20/20** quote tồn tại đúng đơn vị/chương. Human sign-off của review này còn chờ.

[Quy tắc chọn](../../starter/config.json) được chốt trước: dev Evidence Hit@3 cao nhất, rồi dev Hit@1, rồi ít chunk hơn; còn hòa thì thứ tự A/B/C. [Freeze](../../benchmark/freeze.json) và [selection](../../results/selection.json) ghi hash/thời điểm. Chọn **C** sau dev, trước khi test chạy. Dev có câu ở chương IX và XI trùng phạm vi test, nên đây chỉ là holdout câu hỏi nhỏ, không phải chương/chủ đề hoàn toàn mới.

## Kết quả

Lần chạy hiện hành: [dev](../../results/dev-20261115T041747197624Z/metrics.json) và [test](../../results/test-20261115T041850787763Z/metrics.json), ngày 15/11/2026 UTC. Dev tổng 57,146 giây; test tổng 2,829 giây và dùng index đã lưu, không embedding/ingest lại tài liệu. Download model đã diễn ra ở bước smoke check riêng.

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk | Phí API |
|---|---|---|---|---|---|
| A | dev | 4/15 | 7/15 | 350 | 0 USD |
| B | dev | 4/15 | 6/15 | 408 | 0 USD |
| C | dev | 5/15 | 9/15 | 408 | 0 USD |
| A | test | 1/5 | 5/5 | 350 | 0 USD |
| B | test | 0/5 | 3/5 | 408 | 0 USD |
| C | test | 3/5 | 4/5 | 408 | 0 USD |

Hit cần đúng nguồn/đơn vị và có trọn quote đã chuẩn hóa trong **một** chunk. Các vị trí hợp lệ khác được ghi ở `alternative_evidence`. Ghép các mảnh giữa nhiều chunk không tính vào chỉ số chính. Đây là evidence retrieval, không phải độ chính xác câu trả lời LLM.

| Strategy | Tổng ký tự indexed | Min / median / max ký tự | Dev ingest + re-ingest | Test retrieval trung bình/câu |
|---|---|---|---|---|
| A | 156.209 | 96 / 500 / 500 | 23,011 giây | 1,915 ms |
| B | 142.267 | 4 / 392 / 500 | 26,409 giây | 1,837 ms |
| C | 142.267 | 4 / 392 / 500 | 5,115 giây | 9,210 ms |

Nguồn: [chunk statistics](../../results/dev-20261115T041747197624Z/chunk_statistics.json), [resource summary](../../results/resource-summary.json). Dev timing gồm chia chunk, embedding nếu cần, hai lượt ghi và reload/fingerprint. C dùng lại embedding B nên 5,115 giây không thể diễn giải là embedding C nhanh hơn. Retrieval timing gồm search và đánh giá trace, không gồm embedding query. Đây là một lần đo trên máy hiện tại, không phải benchmark latency lặp nhiều lần. B/C bỏ các separator giữa chunk nên tổng ký tự khác corpus; A lặp ký tự do overlap.

| Strategy | Metadata tự động khớp nguồn (n/N) | Top-3 tuân thủ chương, test (n/N) | Human coherence / test audit |
|---|---|---|---|
| A | 15/15 | 1/5 | Chờ người chấm |
| B | 15/15 | 2/5 | Chờ người chấm |
| C | 15/15 | 5/5 | Chờ người chấm |

Metadata đúng vị trí không có nghĩa là retrieval đúng câu hỏi. Verifier đối chiếu toàn bộ trường với đơn vị nguồn và xác nhận text thực sự nằm tại đó; đây là kiểm tra tự động, chưa phải audit của người chấm. A/B không áp filter nhưng vẫn đo mức tuân thủ phạm vi đã yêu cầu để so sánh. Mọi câu hiện tại có filter; nếu không có thì phải báo N/A.

**Các nhãn sau là đề xuất của AI, chưa tính là nhãn thủ công bắt buộc.** AI đã đọc toàn văn các chunk mẫu và 15 top-3 test sau khi thấy điểm retrieval, nên không blind và có nguy cơ thiên lệch. Lý do từng trường hợp có trong [AI coherence review](../../results/test-20261115T041850787763Z/ai_coherence_review.json) và [AI test review](../../results/test-20261115T041850787763Z/ai_test_review.json).

| Strategy | AI coherence mức 0/1/2 (10 vị trí), mean /2 | AI grounding mức 0/1/2 (5 câu), mean /2 |
|---|---|---|
| A | 0 / 10 / 0; 1,00 | 0 / 0 / 5; 2,00 |
| B | 0 / 6 / 4; 1,40 | 1 / 1 / 3; 1,40 |
| C | 0 / 6 / 4; 1,40 | 0 / 1 / 4; 1,80 |

Coherence dùng cùng đơn vị nguồn 1–10 đã sắp xếp, vị trí 0, mỗi strategy 10 mẫu. C dùng chunk giống B nên nhãn đề xuất coherence cũng giống B. [Gói để người chấm đọc](../../results/test-20261115T041850787763Z/HUMAN_REVIEW.md) chứa đầy đủ văn bản. Hiện có **0/30** dòng human coherence, **0/15** dòng human grounding/test audit và 45 kiểm tra metadata thủ công chưa được điền. [Form coherence](../../results/test-20261115T041850787763Z/coherence_review.json), [form test](../../results/test-20261115T041850787763Z/test_review.json) giữ nguyên trống; không sao chép nhãn AI sang đó.

## Phân tích và kết luận

A–B: paragraph packing tăng từ 350 lên 408 chunk nhưng dev Hit@3 giảm 7/15 xuống 6/15 và test giảm 5/5 xuống 3/5. Nhãn AI gợi ý một số đoạn ngắn trọn ý hơn, nhưng đoạn dài vẫn bị cắt cứng; chunk chỉ có heading hoặc phần kết dài thiếu từ khóa có thể truy xuất kém. Không có cơ sở gọi B là semantic chunking hoặc kết luận chia theo đoạn luôn tốt hơn.

B–C: giữ nguyên dữ liệu/vector, filter tăng dev Hit@3 6/15 lên 9/15, test 3/5 lên 4/5, test Hit@1 0/5 lên 3/5. Filter loại nhiễu khác chương nhưng không sửa được thứ hạng evidence trong cùng chương. Trên lần đo này filter cũng tốn thêm thời gian search; cần so sánh với lợi ích theo nhu cầu sử dụng.

Hai thất bại cụ thể từ [test traces](../../results/test-20261115T041850787763Z/traces.json):

1. **q17, B và C**, gold chương X, đơn vị 64: bước cuối là quay lại bờ. Top-3 chỉ có phần mở đầu/các bước đầu ở đơn vị 63 và đoạn nghĩ về điệu nhảy ở đơn vị 67. Chunk B `7fe233ca9bd46a7d76492bfda660b8b1` thực sự chứa gold nhưng không nằm top-3; đây là lỗi ranking/độ phủ top-3, không phải thiếu dữ liệu hoặc quote bị chia mất. A tìm thấy gold ở rank 2. Filter chương X không giúp vì cả ba kết quả nhiễu của B vốn cùng chương.
2. **q20, B**, gold chương XII, đơn vị 80: cần phản ứng của Alice trước đề nghị sentence-first của Queen. B trả lời truy xuất bằng các đoạn pardons/croquet ở đơn vị 59 (IX) và Hatter testimony ở 75 (XI), không có trao đổi cần thiết. C giới hạn XII đưa chunk `e2ea9d1bfff8afe089ba7809270839d5` chứa cả hai người nói lên rank 1; A có gold ở rank 3. AI đề xuất grounding B=0, C=2, kèm lý do, chưa phải nhãn human.

Ngoài ra, q19 B/C xếp chunk chỉ có heading “Who Stole the Tarts?” ở rank 1; evidence đầy đủ nằm rank 2. Điều này giải thích vì sao đủ Hit@3 vẫn có thể kém Hit@1. `chapter_roman` hữu ích cho giới hạn phạm vi, còn `page` và offsets giúp kiểm chứng; hạn chế là người đọc phải biết chương trước và heading không bảo đảm đầy đủ evidence.

Giữ lựa chọn **C theo dev** dù A đạt test Hit@3 cao hơn. Năm câu test rất nhỏ: một câu tương ứng 20 điểm phần trăm. Không đổi model, chunk size, filter hoặc gold sau khi thấy kết quả. Nếu cải tiến câu hỏi/heading packing/reranking, cần chọn trên dev và có bộ test mới; chưa triển khai các cải tiến đó trong kết quả này.

## Tái lập, lỗi kỹ thuật và AI hỗ trợ

Theo [RUN_LAB06.md](../../docs/RUN_LAB06.md), cài lockfile, chuẩn bị corpus, chạy dev rồi test và verifier. [Experiment log](../../artifacts/experiment_log.csv) chứa cấu hình/giả thuyết và số đo thật. [Artifact verification](../../results/artifact-verification.json) xác nhận 60 trace/180 hit, tính lại metric, đối chiếu source/text/metadata, model hash và snapshot B/C; **20 tests pass**, mypy/compileall pass.

Lần dev đầu thành công nhưng test đầu dừng trước truy vấn do fingerprint khác sau mở lại Qdrant. Qdrant local trả vector chuẩn hóa float32 ngay sau upsert và vector gốc sau reload. Đã tái hiện bằng regression test và sửa để fingerprint/search dùng trạng thái đọc từ đĩa; giữ hash chính xác, vẫn bắt thay đổi vector dù ID/count không đổi. Giữ nguyên [failed test](../../results/test-20261115T041602035125Z/failure.json), dev cũ và freeze cũ. Chạy lại dev rồi test sau sửa storage; không có điểm test trước sửa và không thay chiến lược dựa vào test. Log thiếu dữ liệu/DNS của phiên cũ nằm trong `results/history/`.

AI hỗ trợ được công khai: phiên triển khai trước có Codex chính, Luna phác thảo yêu cầu/câu hỏi và Sol viết adapter/test. Phiên tiếp tục dùng Codex chính để tải prerequisites, đọc nguồn sửa benchmark, xử lý lỗi thực thi, chạy/đối soát artifacts và đề xuất nhãn từ trace. Không mở thêm sub-agent trong phiên này. Các câu nháp sai chứng minh cần kiểm tra lại đầu ra AI; nhãn AI không được khai là do Võ Công Minh đã chấm. Học viên vẫn phải đọc, hiểu, sửa/xác nhận các form human và tự nộp bài theo yêu cầu lớp.
