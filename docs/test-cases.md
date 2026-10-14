# Bộ kiểm thử Mission 2

Core loop: **transcript → hiểu diễn biến → trích xuất có cấu trúc → gắn bằng chứng**.

7 tình huống dưới đây gồm 3 tình huống sản phẩm làm tốt, 2 tình huống khó/dữ liệu không rõ ràng và 2 tình huống thất bại.

Tài liệu ghi lại hai vòng:
- **Vòng 1:** chạy bộ đánh giá, phân tích từng tình huống thất bại để tìm nguyên nhân gốc.
- **Vòng 2:** sửa hai nguyên nhân gốc bằng code (không đổi prompt, không đổi model), rồi chạy lại.

Mỗi tình huống ghi kết quả của vòng 1. Các tình huống được sửa có thêm phần **Sau khi sửa**.

## Cách chạy

- **Ngày chạy:** 14/10/2026.
- **Lệnh:** `cd backend && PYTHONPATH=.. uv run python -m evals.runners.run_pipeline`.
- **Model:** `gpt-4o-mini` cho các agent, `gpt-5-mini` cho bước phân xử. Đây là cấu hình đang deploy, để chi phí thấp.
- **Kết quả thô** (toàn bộ mục trích xuất và điểm của từng cuộc họp):
  - Vòng 1: [`evals/results/2026-10-14-gpt-4o-mini-before-fix.json`](../evals/results/2026-10-14-gpt-4o-mini-before-fix.json).
  - Vòng 2, chạy 2 lần vì LLM trả lời khác nhau giữa các lần: [`…-after-fix-run1.json`](../evals/results/2026-10-14-gpt-4o-mini-after-fix-run1.json) và [`…-after-fix-run2.json`](../evals/results/2026-10-14-gpt-4o-mini-after-fix-run2.json).
- **Dữ liệu:**
  - Transcript nằm trong `evals/datasets/`.
  - Đáp án (kỳ vọng do người viết) nằm trong `evals/golden/`.
  - Bộ dữ liệu có 15 cuộc họp: 10 kịch bản bẫy và 5 cuộc họp thực tế.

Kết quả tổng hợp trên cả 15 cuộc họp:

| Chỉ số | Vòng 1 (trước khi sửa) | Vòng 2 (sau khi sửa, 2 lần chạy) | Ngưỡng |
|---|---|---|---|
| Bằng chứng đúng nguyên văn (evidence faithfulness) | **1.00** | **1.00** | 1.00 |
| Kịch bản bẫy ra đúng trạng thái cuối | 0.70 (7/10) | **0.80 – 0.90** | 1.00 |
| Quyết định cuối đúng | 0.73 | **0.85 – 0.88** | 0.90 |
| Người phụ trách và hạn đúng | 0.78 | **0.85 – 0.89** | 0.85 |
| Precision | 0.61 | 0.69 | 0.85 |
| Recall | 0.63 | 0.66 | 0.75 |

Sau khi sửa, cả hai lần chạy của vòng 2 đều qua TC5, TC6 và phần hạn của TC7. Tình huống bẫy còn trượt:
- Lần 1 trượt `reject_decided` (TC2). Chạy riêng tình huống này thêm 3 lần thì cả 3 đều đúng, nên đây là dao động của LLM, không phải do luật mới.
- Lần 2 chỉ trượt `relative_deadlines` (TC7), do cách diễn đạt nhãn quyết định.

**Bằng chứng luôn chính xác.** Mọi trích dẫn đều khớp nguyên văn transcript: 100% trên 103 trích dẫn. Lý do là code kiểm tra từng trích dẫn với transcript gốc, không tin LLM.

**Sai nằm ở bước LLM gán nhãn câu nói.** Khi model nhỏ gán nhầm một câu thành "chốt", máy trạng thái phía sau làm đúng logic nhưng nhận đầu vào sai.

---

## TC1 · Ý kiến đổi qua lại nhiều lần → giữ đúng kết luận cuối (tình huống bắt buộc)

**Loại:** sản phẩm làm tốt.

**Dữ liệu:** `b_back_to_a`.

```
[00:00:30] Bảo: Em đề xuất React, vì cả team đã dùng ở dự án cũ.
[00:00:55] Ngọc: Ok, chốt React.
[00:01:55] Ngọc: Cũng được, vậy chốt Vue luôn.
[00:02:40] Bảo: Khoan chị, ... mở lại chuyện này đi.
[00:03:35] Ngọc: Ok, vậy quay lại React, chốt React, quên Vue đi.
[00:04:00] Ngọc: Quân dựng khung dự án React và cấu hình lint giúp chị, xong trước thứ Sáu tuần này.
```

**Kỳ vọng:**
- Có đúng một quyết định: **React**. Vue bị đánh dấu là phương án đã bị thay thế.
- Có việc cần làm cho Quân, hạn là thứ Sáu.

**Kết quả thực tế:**
- Quyết định "Chọn framework cho trang quản trị? → React", người chốt Ngọc, độ tin cậy 1.0. Bằng chứng gồm câu 00:03:35 (lần chốt cuối) và 00:00:30 (đề xuất gốc). Vue nằm trong danh sách "thay cho".
- Việc cần làm "dựng khung dự án React và cấu hình lint", phụ trách Quân, hạn 09/10/2026. Hạn này đúng: ngày họp là thứ Ba 06/10, nên "thứ Sáu tuần này" là 09/10.

**Đánh giá: Đạt.**

**Điều học được:**
- Có hai lần chốt mâu thuẫn và một lần mở lại, nhưng kết quả vẫn đúng. Lý do là LLM chỉ gán nhãn từng câu (đề xuất / chốt / mở lại), còn **máy trạng thái bằng code** quyết định phương án nào thắng.
- Hạn tương đối như "thứ Sáu tuần này" cũng do code tính, không để LLM đoán.
- Lỗi nhỏ phát hiện được: danh sách "thay cho" có một phần tử rỗng (`['', 'Vue']`). Cần lọc nhãn rỗng khi dựng danh sách phương án bị thay thế. Đã sửa ở vòng 2: nhãn `null`/rỗng mà LLM trả về được coi là "không có phương án" (`decide_guard`), và lần chạy sau ra đúng `['Vue']`.

## TC2 · Đã chốt rồi bị bác → không còn quyết định

**Loại:** sản phẩm làm tốt (tình huống khó).

**Dữ liệu:** `reject_decided`.

```
[00:00:55] Đức: Ok, vậy chốt tách giỏ hàng thành dịch vụ riêng.
[00:01:40] Thịnh: ... team chỉ có bốn người, em nghĩ không kham nổi.
[00:02:20] Đức: Ừ, em nói đúng. Vậy thôi, không tách giỏ hàng nữa, quyết định lúc nãy huỷ.
[00:03:00] Đức: Ừ, vấn đề tải của giỏ hàng vẫn còn để ngỏ.
```

**Kỳ vọng:** không có quyết định nào. Vấn đề trở thành **câu hỏi mở**.

**Kết quả thực tế:**
- Không sinh quyết định.
- Câu hỏi mở "Tách module giỏ hàng ra thành dịch vụ riêng?" có trạng thái `open` và cờ "cần xác nhận".
- Có thêm 2 mục thừa:
  - Vướng mắc "vấn đề tải của giỏ hàng vẫn còn để ngỏ". Mục này chấp nhận được.
  - Tri thức "Dạ, em hiểu rồi.". Đây là nhiễu.

**Đánh giá: Đạt** về trạng thái cuối. Precision giảm vì có mục thừa.

**Điều học được:**
- Câu "quyết định lúc nãy huỷ" được nhận là hành vi *bác bỏ*, và máy trạng thái gỡ đúng quyết định trước đó.
- Model nhỏ hay biến câu xã giao ("Dạ, em hiểu rồi") thành mục tri thức. Cách khắc phục là lọc các câu quá ngắn hoặc không có nội dung trước khi tạo mục, hoặc thêm ví dụ phủ định vào prompt.

## TC3 · Câu đùa và giả định không được thành quyết định

**Loại:** sản phẩm làm tốt.

**Dữ liệu:** `joke_hypothetical`.

```
[00:00:55] Mai: Hay mình tự viết bộ tìm kiếm bằng Rust luôn cho ngầu, đùa thôi chứ ai rảnh.
[00:01:45] Phúc: Giả sử ngân sách gấp đôi thì mình thuê dịch vụ Algolia, nhưng năm nay thì không có đâu.
[00:02:30] Phúc: Ok, chốt Elasticsearch.
```

**Kỳ vọng:**
- Chỉ có quyết định **Elasticsearch**.
- Rust và Algolia không xuất hiện thành phương án hay quyết định.
- Có việc cần làm cho Dũng, hạn cuối tuần.

**Kết quả thực tế:**
- Quyết định "→ Elasticsearch", người chốt Phúc, độ tin cậy 1.0.
- Việc cần làm "dựng cụm Elasticsearch thử nghiệm", phụ trách Dũng, hạn 16/10/2026, đúng.
- Không có mục nào về Rust hay Algolia.

**Đánh giá: Đạt.**

**Điều học được:**
- Prompt trích xuất có nhãn riêng cho câu giả định và câu đùa. Máy trạng thái bỏ qua các nhãn này, nên "giả sử…" không thể thành quyết định.
- Câu hỏi chủ đề do LLM đặt lại hơi sai ("Dùng **CSDL** nào cho giải pháp tìm kiếm"). Không ảnh hưởng kết quả, nhưng cho thấy phần diễn đạt vẫn cần người duyệt.

## TC4 · Cuộc họp thực tế nhiều chủ đề: đủ các nhóm thông tin

**Loại:** thực tế. Phần cốt lõi đạt, phần phụ bị thiếu.

**Dữ liệu:** `payment_v2`. Cuộc họp 7 phút, có Lan là người quyết định.

**Kỳ vọng:** 10 mục, gồm:
- 1 quyết định: PostgreSQL thay cho MongoDB.
- 4 việc cần làm, trong đó Minh dựng schema với hạn 16/10.
- 1 vướng mắc: staging hỏng.
- 1 yêu cầu: CS cần báo cáo.
- 1 câu hỏi mở: có cần replica đọc không.
- 1 tri thức: bắt buộc ACID.
- 1 góp ý: tài liệu API viết tốt.

**Kết quả thực tế:** 6 mục, cả 6 đều đúng.
- Quyết định "→ PostgreSQL", thay cho MongoDB. Bằng chứng 00:03:30 và 00:02:15.
- 3 việc cần làm, đúng người phụ trách. Hạn của Minh ra 16/10 (ngày họp 08/10, "thứ Sáu tuần sau" là 16/10).
- 1 vướng mắc (staging hỏng) và 1 yêu cầu (báo cáo giao dịch lỗi).
- **Thiếu 4 mục:**
  - câu hỏi mở về replica đọc;
  - việc "xin ý kiến anh Tuấn";
  - tri thức ACID;
  - góp ý về tài liệu API.

**Đánh giá: Chưa đạt.** Recall 6/10. Phần quyết định, việc cần làm và bằng chứng đúng hoàn toàn.

**Điều học được:**
- Model nhỏ bỏ sót các ý **nằm ghép trong cùng một câu**. Ví dụ, câu 00:03:30 vừa chốt Postgres vừa nêu "lưu ý chung: bắt buộc ACID", và model chỉ lấy phần chốt.
- Cách khắc phục:
  - cho phép một câu sinh nhiều nhãn;
  - hoặc tách câu dài trước khi gán nhãn;
  - hoặc dùng model mạnh hơn cho bước trích xuất (thiết kế gốc dùng Claude Sonnet).
- Nội dung mục còn lẫn động từ mô tả hành vi ("giao việc…", "nêu vật cản…"). Cần chuẩn hoá lại câu chữ.

## TC5 · "Ok chốt vậy nhé" mà không nói chốt phương án nào

**Loại:** tình huống khó / dữ liệu không rõ ràng.

**Dữ liệu:** `ambiguous_decide`.

```
[00:00:30] Kiên: Một là lưu thẳng vào S3, hai là lưu trên ổ đĩa server rồi đồng bộ lên S3 sau.
[00:00:50] Kiên: Em nghiêng về S3 nhưng cũng chưa chắc lắm.
[00:01:40] Vy: Ừm, cả hai đều có cái hay.
[00:02:05] Kiên: Vậy sao chị?
[00:02:15] Vy: Ok chốt vậy nhé.
```

**Kỳ vọng:**
- **Không** có quyết định, vì không ai nói chốt phương án nào.
- Hệ thống tạo câu hỏi mở "S3 hay ổ đĩa server?", hoặc ít nhất gắn cờ "cần xác nhận".

**Kết quả thực tế:**
- Quyết định "Lưu trữ file đính kèm ở đâu? → **Amazon S3**", độ tin cậy **0.95**, **không có cờ cảnh báo**.
- Bằng chứng là câu "Ok chốt vậy nhé." Câu này không hề nhắc tới S3.

**Đánh giá (vòng 1): Chưa đạt.**

**Điều học được:**
- LLM tự điền phương án cho câu "chốt" mơ hồ, dựa vào câu "nghiêng về S3" trước đó. Đây là **lỗi nguy hiểm nhất**: kết quả sai nhưng trông rất chắc chắn.
- Bằng chứng trung thực chưa đủ. Cần thêm luật trong code: một hành vi "chốt" mà **câu trích dẫn không chứa tên phương án** thì không được tạo quyết định. Hệ thống phải chuyển thành câu hỏi mở kèm cờ "cần xác nhận", để người duyệt hỏi lại.
- Lớp kiểm tra này có thể làm bằng code thuần, giống cách kiểm tra trích dẫn, nên không phụ thuộc vào model.

**Sau khi sửa:**
- Đã thêm luật vào [`ai/domain/decide_guard.py`](../backend/app/ai/domain/decide_guard.py): câu chốt chỉ được tính cho một phương án khi **chính câu đó nhắc tên phương án**. So khớp không dấu và chấp nhận viết tắt, ví dụ "Postgres" khớp "PostgreSQL".
- "Ok chốt vậy nhé" mất phương án do LLM tự gán, rồi đi vào luồng "chốt không rõ phương án" đã có sẵn: chủ đề có hai phương án còn hiệu lực nên được đưa sang phân xử. Bên phân xử không tìm được câu chốt nào nêu tên, nên chủ đề thành câu hỏi mở.
- **Kết quả:** câu hỏi mở "Lưu trữ file đính kèm", có cờ "cần xác nhận", bằng chứng là câu "Ok chốt vậy nhé." Không còn quyết định S3. **Đạt** ở cả 2 lần chạy.

## TC6 · Phải chờ cấp trên duyệt → hệ thống tự chốt

**Loại:** thất bại.

**Dữ liệu:** `wait_for_boss`.

```
[00:00:08] Giang: Còn một việc nữa, có nên mua thêm năm license Figma cho team thiết kế không?
[00:00:55] Long: Em thấy mua thì tốt, nhưng ngân sách quý này do chị Thảo duyệt.
[00:01:25] Giang: Đúng, anh chưa quyết được khoản này.
[00:01:50] Long: Để em xin ý kiến chị Thảo rồi báo lại cả nhóm.
[00:02:10] Giang: Ok, Long nhận nhé.
[00:02:50] Giang: Ok, họp tới đây thôi.
```

**Kỳ vọng:**
- Câu hỏi mở "Có mua thêm license Figma không?".
- Việc cần làm cho Long: xin ý kiến chị Thảo.
- Không có quyết định.

**Kết quả thực tế:**
- Việc cần làm cho Long: đúng.
- **Quyết định sai:** "Có nên mua thêm năm license Figma…? → Figma", độ tin cậy 1.0. Bằng chứng chốt là câu **"Ok, họp tới đây thôi."**
- Câu "Dạ, vậy em chờ tin từ Long." bị biến thành việc cần làm của Nhi.

**Đánh giá (vòng 1): Chưa đạt.**

**Điều học được:**
- Model nhỏ hiểu "Ok, …" ở cuối buổi là chốt. Nó cũng bỏ qua câu "anh chưa quyết được khoản này", là tín hiệu rõ ràng của việc *hoãn chờ cấp trên*.
- Cách khắc phục giống TC5: chặn quyết định khi câu chốt không nêu phương án.
- Thêm luật: một chủ đề đã có hành vi "hoãn / chờ ý kiến" thì một câu "ok" chung chung sau đó không được gỡ trạng thái hoãn.
- Đây cũng là lý do sản phẩm **bắt buộc người duyệt** trước khi phát hành. Màn hình duyệt cho thấy ngay câu bằng chứng "Ok, họp tới đây thôi", nên người duyệt bác được mục sai trong vài giây.

**Sau khi sửa:**
- Xem lại nhãn LLM gán, nguyên nhân thật hơi khác dự đoán. LLM gán "Ok, họp tới đây thôi" là câu chốt **không nêu phương án**. Sau đó máy trạng thái tự gán câu này vào phương án duy nhất của chủ đề là Figma.
- Đã thêm luật vào [`ai/domain/state_machine.py`](../backend/app/ai/domain/state_machine.py): khi chủ đề đã được hoãn ("anh chưa quyết được khoản này"), câu chốt không nêu phương án **không được tự gán**. Chủ đề được chuyển sang xác nhận.
- **Kết quả:** câu hỏi mở "Có nên mua thêm năm license Figma…?", có cờ "cần xác nhận", và việc cần làm của Long. Không còn quyết định. **Đạt** ở cả 2 lần chạy.
- **Còn tồn tại:** model vẫn sinh thêm việc cần làm trùng lặp ("Chờ thông tin từ Long") và một lần gán sai người phụ trách là chị Thảo. Phần này kéo precision xuống, cần prompt tốt hơn hoặc model mạnh hơn.

## TC7 · Hạn chót viết theo nhiều kiểu tương đối

**Loại:** thất bại một phần.

**Dữ liệu:** `relative_deadlines`. Ngày họp là thứ Sáu 16/10/2026.

| Câu trong transcript | Kỳ vọng | Thực tế |
|---|---|---|
| "xong ngày mai nhé" | 17/10 | 17/10 ✓ |
| "thứ Hai tuần sau" | 19/10 | 19/10 ✓ |
| "trong vòng 5 ngày nữa" | 21/10 | **trống**, có cờ "thiếu hạn chót" ✗ |
| "hạn là cuối tháng" | 31/10 | 31/10 ✓ |
| "hạn 20/10 nhé" | 20/10 | 20/10 ✓ |

Quyết định "giữ nguyên lịch phát hành bản 2.0" được trích xuất thành "→ phát hành bản 2.0". Nội dung này đúng về ý nhưng thiếu chữ "giữ nguyên", nên bộ chấm không khớp.

**Đánh giá (vòng 1): Chưa đạt.** 4/5 hạn đúng, quyết định bị diễn đạt mơ hồ.

**Điều học được:**
- Bộ tính hạn bằng code (`ai/domain/due_dates.py`) chưa nhận dạng mẫu "trong vòng N ngày (nữa)". Cần bổ sung mẫu này và một unit test.
- Khi không hiểu hạn, hệ thống **để trống và gắn cờ "thiếu hạn chót"**, không đoán. Như vậy là đúng hướng: người duyệt thấy cờ và tự điền.
- Với câu hỏi có/không ("có dời ngày phát hành không?"), nhãn phương án nên giữ nguyên ý phủ định ("giữ nguyên lịch"). Nếu không, quyết định đọc lên dễ hiểu sai.

**Sau khi sửa:**
- Đã thêm các mẫu "trong vòng N ngày (nữa)", "trong N ngày tới" và "N ngày tới" vào bộ tính hạn, kèm unit test. Riêng "5 ngày" đứng một mình vẫn không được tính, vì đó là khoảng thời gian chứ không phải hạn.
- **Kết quả:** "Việt gia hạn chứng chỉ SSL, trong vòng 5 ngày nữa" ra hạn 21/10. Đúng **5/5 hạn** ở cả 2 lần chạy.
- **Vẫn chưa đạt:** quyết định vẫn ra "→ phát hành bản 2.0", thiếu ý "giữ nguyên lịch". Đây là lỗi diễn đạt nhãn của LLM, luật code không sửa được. Đây là tình huống thất bại còn lại của bộ kiểm thử.

---

## Tổng kết

**Hệ thống làm tốt:**
- Theo dõi ý kiến thay đổi, mở lại, huỷ quyết định (TC1, TC2).
- Loại câu đùa và câu giả định (TC3).
- Gắn bằng chứng nguyên văn: 100%.
- Tính hạn tương đối bằng code.

**Đã sửa sau vòng 1** (bằng code, không đổi prompt hay model):
- Câu "chốt" mơ hồ không còn tạo ra quyết định sai. TC5 và TC6 chuyển sang Đạt.
- Mẫu hạn "trong vòng N ngày". Phần hạn của TC7 đạt 5/5.

**Hệ thống vẫn chưa làm tốt:**
- Ý phụ nằm ghép trong câu dài (TC4, recall).
- Mục thừa hoặc trùng lặp từ câu xã giao (TC2, TC6, precision).
- Nhãn phương án mất ý phủ định "giữ nguyên" (TC7).
- Kết quả dao động giữa các lần chạy với model nhỏ (TC2).

Các lỗi còn lại đều nằm ở chất lượng gán nhãn của LLM, không sửa được bằng luật code đơn giản.

**Hướng tiếp theo:** chạy lại bộ đánh giá với model mạnh hơn cho bước trích xuất (thiết kế gốc dùng Claude Sonnet), để tách lỗi do model khỏi lỗi do thiết kế. Sau đó cải thiện prompt với các ví dụ phủ định (câu xã giao, câu chào kết thúc buổi họp).
