# Dùng Gemini để thu thập dữ liệu nghiên cứu

Tài liệu này hướng dẫn **tạo và lưu đầu ra model để đánh giá**, không thay thế việc thu thập findings, xây dựng ground truth hay chấm chuyên gia. Ba RQ vẫn là ba câu hỏi do người dùng đề xuất: chất lượng báo cáo (RQ1), chất lượng remediation đối chiếu OWASP (RQ2), và tác động của Grounding/RAG (RQ3).

## 1. Mở ứng dụng bằng Gemini

Làm theo [hướng dẫn cài đặt](../HUONG_DAN_SU_DUNG.md): giải nén ZIP, cài Python 3.12, lấy key tại [Google AI Studio](https://aistudio.google.com/apikey), rồi chạy:

```powershell
py -3.12 run.py --configure-gemini
```

macOS/Linux dùng `python3.12 run.py --configure-gemini`. Nhập key ở terminal ẩn; không đưa vào hồ sơ JSON hoặc chia sẻ trong chat. Khi server chạy, mở `http://127.0.0.1:8000` **trên máy đang chạy chương trình**. Giữ Terminal mở. Cấu hình lưu ở `.local/settings.json`, là file local chứa key dạng văn bản; bảo vệ file và không chia sẻ.

Lần sau chạy `py -3.12 run.py` hoặc `python3.12 run.py`. Thay key/model bằng cách chạy lại `--configure-gemini`. Biến môi trường `GEMINI_API_KEY`, `GEMINI_MODEL` và `AI_PROVIDER=gemini` có thể thay file local; biến môi trường có ưu tiên cao hơn, kể cả khi rỗng.

Gemini gửi yêu cầu HTTPS đến Google. Người dùng phải tự kiểm tra hạn mức, điều khoản và chi phí của tài khoản. Chỉ dữ liệu đã khử thông tin nhạy cảm và được phép gửi ra ngoài mới được đưa vào model. Tính năng redaction tự động là best-effort, không bảo đảm xóa mọi secret/PII.

## 2. Chọn và cố định model trước nghiên cứu

`gemini-flash-latest` là gợi ý khởi đầu nhưng là **alias có thể thay đổi**. Với pilot, dùng model đang khả dụng để kiểm tra luồng. Với nghiên cứu chính thức:

1. Chọn model ID cố định được tài khoản hỗ trợ và có đầu ra JSON có schema.
2. Giữ nguyên ID, provider, decoding parameters, corpus OWASP và code trong toàn bộ các điều kiện.
3. Ghi model ID yêu cầu và `modelVersion` thực trả về, thời gian chạy cùng phiên bản code. Nếu provider không cung cấp một trường, ghi là thiếu, không tự suy đoán.
4. Nếu modelVersion thay đổi giữa đợt chạy, đánh dấu batch; không gộp như cùng một model mà không phân tích ảnh hưởng.

Seed dùng để tái lập thứ tự chạy của ứng dụng, **không bảo đảm** API sinh cùng câu trả lời. Repetition vẫn cần thiết. Token và metadata được lưu khi provider trả về; token không tự quy đổi thành chi phí nếu chưa có bảng giá và quy tắc tính phù hợp.

Trong phiên triển khai chưa có Gemini key thật, nên chưa xác minh API/quota/model cụ thể. Mocks và kiểm thử phần mềm không phải bằng chứng về chất lượng Gemini.

## 3. Chuẩn bị một case đầu vào

Hệ thống **không tự quét CSDL**. Bạn thu findings và evidence trong lab được phép, sau đó chuẩn hóa thành JSON. Ví dụ nguồn bằng chứng phù hợp:

| Loại case | Nguồn bằng chứng gợi ý | Không được suy diễn |
|---|---|---|
| PostgreSQL quyền quá rộng | Kết quả đọc `pg_roles`, role grants, mô tả chức năng tài khoản | Superuser tự động chứng minh đã bị khai thác |
| PostgreSQL TLS | `SHOW ssl`, chính sách client, kết quả kiểm tra phiên kết nối có phạm vi rõ | `ssl=on` tự động chứng minh mọi client xác minh chứng chỉ |
| MySQL quyền tài khoản | `SHOW GRANTS` của tài khoản lab và nhu cầu nghiệp vụ | Quyền rộng luôn là lỗ hổng đã xác nhận, không cần xét chức năng |
| SQL injection | Đoạn mã truy vấn, luồng đầu vào, quan sát kiểm thử có ủy quyền | Nối chuỗi tự động chứng minh truy cập trái phép thành công |
| Audit | Cấu hình audit, sự kiện thử và log đã che thông tin | Không có một file log đồng nghĩa toàn hệ thống không logging |

Chỉ dùng câu lệnh đọc cấu hình trong phạm vi cho phép. Không thực hiện thay đổi CSDL hoặc thử khai thác trên hệ thống bên ngoài để tạo dữ liệu cho ứng dụng.

Mở `data/cases/postgres-config.json` hoặc `mysql-query.json`, sao chép thành file mới, giữ đúng schema và điền **quan sát thực**. Ví dụ tối thiểu:

```json
{
  "title": "LAB-PG-001",
  "database": "PostgreSQL",
  "findings": [
    {
      "id": "F-001",
      "title": "Role ứng dụng cần rà soát quyền",
      "category": "excessive_privileges",
      "severity": "high",
      "description": "Mô tả giả thuyết finding và giới hạn đã biết, dựa trên quan sát thực của bạn.",
      "asset": "lab-postgres/app_role",
      "evidence_ids": ["E-001"]
    }
  ],
  "evidence": [
    {
      "id": "E-001",
      "source": "Ghi rõ lệnh/nguồn đọc cấu hình được phép",
      "content": "Thay bằng kết quả thực đã che thông tin nhạy cảm; không coi đoạn mẫu này là evidence nghiên cứu.",
      "collected_at": null
    }
  ]
}
```

Đây chỉ là **schema minh họa**, chưa phải case nghiên cứu hợp lệ. Thay cả severity bằng đánh giá có căn cứ của người kiểm thử. Nếu không có bằng chứng, để `evidence_ids=[]`; không tự tạo quan sát. Nếu không biết thời gian thu thập, dùng `null`, không bịa timestamp. Các ID evidence phải duy nhất và tồn tại. Schema hiện chỉ nhận các mức `critical`, `high`, `medium`, `low`, `info`; nếu severity chưa xác định, ghi rõ trạng thái đó trong mô tả và sổ chú giải bên ngoài, không coi giá trị placeholder là nhãn chuẩn của chuyên gia.

Mỗi case cần hồ sơ nghiên cứu riêng ghi nguồn, quyền sử dụng, DBMS/version, cluster/scenario, split development/held-out, nhãn chất lượng evidence và checksum của artifact. Trang nghiên cứu có trường **Case ID**, **Cluster ID**, **Nhóm dữ liệu** và **Phiên bản DBMS** để lưu vào manifest của batch. Dùng mã ổn định, ví dụ case `PG-001-A`, cluster `SCENARIO-001`, split `pilot`/`development`/`test`; các biến thể cùng scenario phải cùng cluster và split. Không giữ `case-current`/`cluster-current` cho các case khác nhau. Các trường này nằm trong metadata nghiên cứu, không phải schema JSON findings: lưu sổ mapping bên cạnh dataset và không thêm tùy ý vào JSON case.

## 4. Pilot qua web

1. Trên trang báo cáo, chọn **Nhập findings từ JSON**, tải case bạn chuẩn bị.
2. Kiểm tra danh sách findings, bằng chứng và asset. Chọn bộ sinh Gemini.
3. Sinh một báo cáo Grounding+RAG để kiểm tra API và schema. Xem model, cảnh báo, claims, citations và remediation; tải JSON nếu cần kiểm tra metadata.
4. Một lượt thành công chưa đủ xác nhận model đúng; mở evidence và đoạn OWASP để kiểm tra thủ công. “Có liên kết bằng chứng” chỉ nói có ID trích dẫn hợp lệ, không xác nhận bằng chứng hỗ trợ kết luận.

Dùng pilot thuộc tập development để chỉnh prompt/format. Sau khi mở held-out, không sửa prompt để tối ưu riêng cho lỗi của các case test mà vẫn tuyên bố đánh giá sạch.

## 5. Chạy bốn cấu hình từ trang nghiên cứu

Mở **Thiết kế nghiên cứu**, kiểm tra case hiện tại, điền Case ID/Cluster ID/split/DBMS version, chọn số lần lặp và seed. Dùng `pilot` để thử, `development` để phát triển và `test` cho dữ liệu giữ riêng đánh giá. Cùng một case được chạy qua:

| Điều kiện | Grounding | OWASP RAG | Ngữ cảnh model nhận |
|---|---|---|---|
| G0R0 | Tắt | Tắt | Metadata finding |
| G1R0 | Bật | Tắt | Metadata + evidence và yêu cầu trích dẫn/abstain |
| G0R1 | Tắt | Bật | Metadata + đoạn OWASP truy xuất |
| G1R1 | Bật | Bật | Metadata + evidence + đoạn OWASP |

G0 không có evidence content/IDs trong ngữ cảnh sinh. R0 không có OWASP context. Truy xuất dùng cùng metadata ở G0R1 và G1R1. Vì G bật thay đổi cả **thông tin được cấp và chính sách grounding**, kết quả không chứng minh riêng tác động của một câu prompt. Tương tự, hiệu ứng R gồm cả context và hướng dẫn trích nguồn.

Với **3 lần lặp**, một case tạo **12 lượt gọi API**. Có thể phát sinh phí, quota hoặc thời gian chờ; kiểm tra số lượt trước khi bấm chạy. Web phù hợp cho pilot/từng case, không nên mở nhiều batch cùng lúc. Chờ trạng thái kết thúc, kể cả có lượt lỗi, rồi tải ZIP. Lỗi quota, chặn nội dung hoặc schema/citation đều phải giữ trong tỷ lệ thành công; không được chỉ chọn các kết quả đẹp để đánh giá.

Ứng dụng không tự retry đến khi ra kết quả “tốt”. Nếu outage buộc chạy lại, đặt một batch ID mới, lưu lý do và quy tắc xử lý được xác định trước. Không ghép kết quả tốt nhất của nhiều lần lặp thành một lượt duy nhất.

## 6. Đọc và lưu gói dữ liệu xuất

Gói kết quả gồm các artifact phục vụ kiểm toán và chấm, tùy trạng thái thành công/lỗi:

| Artifact | Dùng để làm gì |
|---|---|
| `manifest.json` | Cấu hình batch, study metadata (case/cluster/split/DBMS version), case/hash, seed, repeats, model/corpus và thông tin tái lập được ghi nhận |
| `runs.jsonl` | Mỗi dòng là một lần chạy: điều kiện, lần lặp, thành công/lỗi, thời gian và metadata có sẵn |
| Báo cáo JSON/Markdown | Đầu ra được chấp nhận, evidence và OWASP citations; metadata model/token khi có |
| `expert-review.csv` | Phiếu chấm trống cho người đánh giá, không phải điểm Gemini tự chấm |
| Case đã che dữ liệu | Đối chiếu đầu vào đã được xử lý, không thay cho archive evidence gốc được bảo vệ riêng |

Giữ nguyên gói xuất, tạo bản làm việc riêng để annotate. Bản JSON có thể lộ điều kiện qua metadata và citations: **blind ID không tự tạo đánh giá mù**. Chuẩn bị bản dành cho reviewer có định dạng tương đương, ẩn nhãn provider/condition nhưng giữ nguồn cần thiết để chấm entailment; ghi giới hạn vì citations có thể làm reviewer đoán điều kiện.

Ứng dụng không lưu nội dung raw bị provider/schema từ chối để tránh giữ response nhạy cảm ngoài ý muốn; log vẫn giữ trạng thái lỗi an toàn. Đây là giới hạn so với kế hoạch lưu raw output trong protocol, cần khai báo trong phương pháp và thống kê lỗi. Không tuyên bố đã audit đầy đủ mọi lỗi ngữ nghĩa của những response không được lưu.

## 7. Chấm và trả lời ba RQ

### RQ1 — Chất lượng báo cáo

Hai chuyên gia nên xây dựng reference độc lập **trước khi xem đầu ra model**: sự kiện được evidence hỗ trợ, sự kiện mâu thuẫn, phần chưa thể kết luận và tập fact tối thiểu báo cáo phải có. Sau đó tách toàn bộ output thành claim nguyên tử, gồm cả đoạn analysis chứ không chỉ mảng `claims`.

Trong hàng `row_type=finding` của CSV, điền `supported`, `contradicted`, `unsupported`, `essential_covered`, `essential_total` và các tử số/mẫu số citation theo protocol. Công thức chính:

- Supported claim precision = `supported / (supported + contradicted + unsupported)`.
- Fact coverage = `essential_covered / essential_total`.
- Citation support cần đọc evidence thực sự hỗ trợ claim hay không, không chỉ kiểm tra ID tồn tại.

Không có claim có thể kiểm chứng thì precision **không xác định**, không phải 100%; ghi abstention riêng. Thiếu reference facts thì không tự thay fact coverage bằng string overlap.

### RQ2 — Chất lượng remediation

Trong từng hàng `row_type=remediation`, chuyên gia chấm riêng sáu chiều **0–3**:

1. Đúng kỹ thuật.
2. Phù hợp với finding/evidence/engine.
3. Được đoạn OWASP hỗ trợ.
4. Có thể thực hiện và có phạm vi rõ.
5. Cách xác minh thành công có ý nghĩa.
6. Nhận biết rủi ro, phụ thuộc và điều kiện triển khai.

Ghi lý do, nguồn và cảnh báo unsafe advice. Lệnh cấu hình DBMS cụ thể phải đối chiếu tài liệu vendor; OWASP chung không đủ xác nhận cú pháp đúng. Model tự đánh giá đầu ra của nó không phải ground truth độc lập.

### RQ3 — Hiệu ứng Grounding/RAG

Chạy cùng case, cùng model và cùng budget qua bốn điều kiện. Gộp repeats trong case rồi case trong **cluster scenario/environment**; không coi từng claim hoặc repeat là mẫu độc lập. Các biến thể từ cùng lab/scenario phải ở cùng split, không được xuất hiện cả development và held-out.

Sau khi chấm đủ dữ liệu, so sánh theo cặp các điều kiện và tương tác `(G1R1 − G0R1) − (G1R0 − G0R0)`, báo cáo effect size và khoảng tin cậy bootstrap theo cluster. Protocol có kế hoạch cluster bootstrap 10.000 resamples và điều chỉnh multiple testing nếu dùng kiểm định; đây là công việc phân tích sau annotation, không phải kết quả tự sinh bởi web.

## 8. Dataset và kế hoạch phân tích

Ba case đi kèm chỉ là fixtures, không đủ để trả lời RQ. Mục tiêu 120 cases/40 clusters trong proposal là **kế hoạch**, không phải dataset đã có. Trước nghiên cứu chính thức, pilot để ước lượng công sức annotation và độ chính xác CI, chốt cỡ mẫu, split, rubric, exclusion rules và protocol version. Ghi nhận cả evidence thiếu, mâu thuẫn và case âm/không đủ căn cứ; không chỉ chọn findings dễ.

Với nhiều case có thể dùng CLI sau khi đã cấu hình Gemini:

```powershell
.venv\Scripts\python.exe scripts/run_experiment.py --provider llm --cases dataset/heldout --repeats 3 --seed 491 --output outputs/study-001
```

macOS/Linux thay executable bằng `.venv/bin/python`. `dataset/heldout` là thư mục bạn tự tạo với các JSON hợp lệ; `study-001` phải là output mới. Dataset cần sổ mapping cluster/split riêng theo schema đang hỗ trợ. Chạy từng batch phù hợp quota; `--provider template` chỉ kiểm tra phần mềm, không đưa vào bảng kết quả LLM như Gemini.

Kết luận luận văn chỉ được viết sau khi có model thật, dataset hold-out, reference chuyên gia, scores hoàn chỉnh, thống kê lỗi và phân tích phù hợp. Không dùng “100% citation-ID validity” để khẳng định AI chính xác 100%, OWASP-compliant hoặc remediation đã thành công trên hệ thống thực.
