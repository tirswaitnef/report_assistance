# Tạo dữ liệu nghiên cứu từ lab PostgreSQL/MySQL

Bạn có thể dùng lab này để tạo đầu vào cho trợ lý mà không cần dùng dữ liệu CSDL cá nhân hoặc doanh nghiệp. Lab khởi tạo các bản ghi nhỏ do dự án tự tạo, đặt một số cấu hình yếu có chủ đích và thu kết quả đọc từ CSDL đang chạy.

**Phân biệt ba loại dữ liệu:** các JSON trong `data/cases/` là mẫu tổng hợp; các JSON do collector tạo là quan sát được thu từ lab tại thời điểm chạy; nhãn trong `reference-candidates.json` là gợi ý tham chiếu cần chuyên gia duyệt. Chỉ việc có lab hoặc có nhãn dự kiến chưa tạo thành ground truth đã được xác nhận.

Việc thu dữ liệu lab không gọi Gemini và không cần Gemini key. Lỗi Gemini HTTP 400 đang được chẩn đoán riêng; chạy lab thành công không chứng minh rằng API sinh báo cáo đã hoạt động trên tài khoản của bạn.

## 1. Lab gồm những gì?

| Thành phần | Cấu hình yếu có chủ đích | Cấu hình đối chứng đã siết chặt |
|---|---|---|
| PostgreSQL | Role ứng dụng có quyền superuser; SSL tắt; quy tắc host dùng `trust`; tắt ghi log kết nối | Role ứng dụng giới hạn quyền đọc; bật SSL; host SSL dùng SCRAM; bật ghi log kết nối |
| MySQL | Role ứng dụng có quyền toàn cục rộng; không bắt buộc secure transport | Role ứng dụng chỉ có quyền đọc trong CSDL lab; bắt buộc secure transport |

Các cặp cấu hình chạy thành bốn container trong mạng Docker riêng. Compose không công bố cổng CSDL ra máy chủ, không dùng host networking và không cấp chế độ privileged. Collector chạy câu lệnh đọc bên trong các container thuộc project lab; nó không nhận địa chỉ hệ thống bên ngoài để quét.

Các yếu điểm ở đây là **cấu hình và phân quyền**, không phải một bộ khai thác CVE. Lab hiện không chứng minh SQL injection, đọc trộm lưu lượng, truy cập từ Internet hoặc khai thác thành công. Cấu hình đối chứng cũng không phải chứng nhận hệ thống đã an toàn toàn diện. Chứng chỉ TLS tự ký dùng cho lab và việc bật log kết nối không thay thế PKI production hoặc một cơ chế audit đầy đủ.

## 2. Chuẩn bị trên Windows

1. Cài Python 3.12 như khi chạy ứng dụng báo cáo.
2. Cài [Docker Desktop](https://www.docker.com/products/docker-desktop/), bật backend WSL 2 và dùng **Linux containers**. Mở Docker Desktop, đợi engine sẵn sàng.
3. Giải nén bản mã nguồn có file `lab.py`. Mở PowerShell tại thư mục chứa `lab.py` và `run.py`.
4. Kiểm tra Docker:

```powershell
docker version
docker compose version
```

Lệnh đầu cần có thông tin cả Client và Server. Nếu chỉ có Client hoặc báo không kết nối được engine, xử lý Docker Desktop trước khi chạy lab. Có thể bắt đầu với khoảng 4 GB RAM cấp cho Docker và 8 GB đĩa trống; đây là khuyến nghị tài nguyên cho máy cá nhân, không phải số liệu benchmark.

Nếu đây là thư mục mã nguồn mới, chuẩn bị các thư viện dùng để kiểm tra JSON đầu ra trước:

```powershell
py -3.12 run.py --install-only
```

Lệnh này chỉ tạo `.venv` và cài thư viện, không yêu cầu Gemini key hoặc khởi động web. Khi cập nhật mã nguồn, chương trình có thể tạo lại môi trường; không cần chép `.venv` từ thư mục cũ.

## 3. Khởi động và thu dữ liệu

Chạy tại thư mục có `lab.py`:

```powershell
py -3.12 lab.py up
```

Lần đầu cần Internet để tải image CSDL. Helper tạo mật khẩu CSDL ngẫu nhiên trong `.local/lab.env`, rồi khởi động các service và kiểm tra trạng thái sẵn sàng. Không gửi file này hoặc toàn bộ `.local` lên GitHub, chat hay dịch vụ chia sẻ. Dữ liệu CSDL nằm trong Docker volumes của lab.

Khi các service đã sẵn sàng, thu một đợt dữ liệu mới:

```powershell
py -3.12 lab.py collect --output outputs/lab-001
```

Mỗi lần thu dùng một đường dẫn output mới, chẳng hạn `outputs/lab-002`. Collector giữ các mốc thời gian thu thập thật, nguồn câu lệnh và provenance có sẵn. Nếu đọc CSDL thất bại, phải giữ trạng thái lỗi và sửa prerequisite; không thay kết quả bằng nội dung giả để hoàn thành bộ dữ liệu.

macOS/Linux dùng `python3.12` thay cho `py -3.12`. Mọi lệnh còn lại được chạy tại cùng thư mục dự án.

## 4. Đọc bộ dữ liệu xuất

Một đợt thu thành công có các artifact sau:

| Artifact | Mục đích |
|---|---|
| `cases/*.json` | Bốn hồ sơ findings/evidence để nhập vào web; mã hồ sơ được làm trung tính |
| `manifest.json` | Mapping mã hồ sơ, cluster, thời gian, phiên bản/provenance và checksum được ghi nhận |
| `reference-candidates.json` | Trạng thái dự kiến và nhãn tham chiếu ban đầu, cần chuyên gia xác nhận |
| `health/statechecks.json` | Kết quả kiểm tra cấu hình quan sát được so với trạng thái dự kiến; chỉ là kiểm tra vận hành |
| `raw/*.txt` | Snapshot đọc cấu hình và grants để đối chiếu evidence và checksum |

Chỉ nhập **một file trong `cases/`** làm đầu vào model. Không gộp nội dung reference hoặc mapping trạng thái yếu/đối chứng vào JSON findings, prompt hoặc corpus RAG. Nếu model nhận sẵn nhãn đúng/sai, phép đánh giá dễ bị rò rỉ đáp án.

Collector không xuất các case nếu một truy vấn thất bại hoặc trạng thái quan sát không khớp cấu hình lab dự kiến. Khi đó xem artifact lỗi, sửa lab rồi thu một đợt mới; không chỉnh nhãn để làm lượt thu có vẻ hợp lệ. Kiểm tra trạng thái vận hành thành công vẫn không thay thế chuyên gia duyệt ngữ nghĩa.

Các finding là yêu cầu đánh giá hoặc giả thuyết cần kiểm chứng. Với cấu hình đối chứng, chuyên gia có thể kết luận giả thuyết yếu điểm bị bằng chứng bác bỏ. Không coi mọi finding đầu vào là lỗ hổng đã xác nhận hoặc ép model đề xuất sửa một vấn đề không tồn tại.

Ví dụ giới hạn diễn giải: `rolsuper=true` chứng minh thuộc tính role đang bật trong snapshot, chưa chứng minh có sự cố khai thác. `ssl=on` chưa chứng minh mọi client xác minh chứng chỉ. `require_secure_transport=ON` là một chính sách server, không phải bản chụp lưu lượng của mọi phiên kết nối. Log kết nối bật chưa chứng minh đủ mọi loại sự kiện audit cần có.

## 5. Nhập vào web và chạy thực nghiệm

1. Sau khi thu dữ liệu, mở một PowerShell khác tại thư mục dự án và chạy `py -3.12 run.py`.
2. Mở `http://127.0.0.1:8000` trên máy bạn. Trong **Báo cáo bảo mật**, chọn **Nhập findings từ JSON** và mở một file `outputs/lab-001/cases/*.json`.
3. Xem lại nguồn, timestamp và nội dung evidence. Khi API đã được kiểm tra thành công, chọn Gemini và model ID đã cố định cho nghiên cứu.
4. Mở **Thiết kế nghiên cứu**, điền Case ID, Cluster ID và phiên bản DBMS theo manifest. Chọn `pilot` cho các lượt thử.
5. Giữ cặp cấu hình yếu/đối chứng của cùng một engine/scenario trong **cùng cluster và cùng split**. Không chia một biến thể vào development rồi biến thể còn lại vào test.
6. Chọn 3 lần lặp để chạy bốn điều kiện Grounding/RAG: **12 lượt gọi API cho một case**. Bốn case tương ứng 48 lượt nếu đều chạy đủ; cần kiểm tra quota/chi phí trước.
7. Tải ZIP kết quả, giữ cả lượt lỗi và metadata. Giữ bản thu evidence ban đầu tách khỏi đầu ra model và bảng chấm.

Lab có thể dừng sau khi đã thu đủ evidence, vì web đọc các JSON đã xuất. Khi cần quan sát lại, khởi động và thu một batch mới; không ghi đè evidence gốc.

## 6. Dùng dữ liệu cho ba RQ

**Trước khi xem đầu ra Gemini**, nhờ hai người có chuyên môn đối chiếu cấu hình, lệnh thu và evidence; ghi các fact đúng, fact bị bác bỏ, thông tin còn thiếu và biện pháp khắc phục chấp nhận được. Dùng reference candidates làm điểm bắt đầu, không sao chép nguyên nhãn thành gold mà không kiểm tra. Ghi và giải quyết bất đồng theo [protocol](evaluation-protocol.md).

- **RQ1:** chấm độ đúng của claim, độ đầy đủ so với fact tối thiểu và evidence có thực sự hỗ trợ kết luận hay không. Bao gồm cả claim trong phần analysis, không chỉ mảng `claims`.
- **RQ2:** chấm riêng correctness, applicability, OWASP support, actionability, verification và risk awareness theo thang 0–3. Case đối chứng cần thưởng cho việc nhận biết không đủ căn cứ hoặc finding bị bác bỏ, không thưởng cho remediation nghe có vẻ chi tiết nhưng không cần thiết.
- **RQ3:** chạy cùng case/model qua bốn điều kiện, so sánh theo cặp sau khi chấm và gộp repeats trong case, rồi case trong cluster. Grounding thay đổi cả quyền truy cập evidence và hướng dẫn, nên không diễn giải hiệu ứng thành tác động của riêng một câu prompt.

Bốn hồ sơ từ lab là bộ khởi đầu cho pilot, không phải dataset đủ để kết luận đề tài. Thu lại cùng một lab nhiều lần không tự tạo nhiều scenario độc lập. Kế hoạch 120 cases/40 clusters trong đề cương vẫn cần được xây dựng, chốt split, annotation và phân tích độ chính xác khoảng tin cậy trước nghiên cứu chính thức.

Mã run/case thay đổi để theo dõi artifact từng đợt; cluster giữ cố định là `DBLAB-v1-PG-CONFIG` hoặc `DBLAB-v1-MY-CONFIG`. Thu lại cùng cấu hình lab ở đợt khác vẫn thuộc cùng scenario family và cùng split; mã run mới không tạo cluster độc lập. Lab ban đầu chỉ có hai họ cấu hình theo engine, không phải bốn mẫu độc lập.

Xem thêm [hướng dẫn nghiên cứu Gemini](GEMINI_RESEARCH_GUIDE.vi.md) và [protocol đánh giá](evaluation-protocol.md). Chỉ số citation-ID validity trên web không đo tính đúng đắn ngữ nghĩa.

## 7. Dừng lab và xử lý sự cố

```powershell
py -3.12 lab.py down
```

Lệnh này tắt lab và giữ dữ liệu volume để có thể khởi động lại. Không tự xóa volume hoặc dùng lệnh dọn toàn bộ Docker vì có thể ảnh hưởng project khác. Nếu mật khẩu trong `.local/lab.env` bị thay nhưng volume cũ còn giữ tài khoản đã khởi tạo, cấu hình và dữ liệu có thể không khớp; giữ bản dữ liệu và chẩn đoán trước khi reset.

Nếu service chưa healthy, kiểm tra Docker Desktop, tài nguyên, dung lượng và lỗi tải image. Không tắt TLS verification để tải image. Nếu chỉ collector thất bại, giữ output lỗi, kiểm tra đúng project lab và trạng thái service. Nếu chỉ Gemini lỗi, làm theo hướng dẫn API hiện có; không sửa evidence hoặc đổi sang template rồi ghi nhận như kết quả Gemini.

Trên Windows, Docker Desktop có thể cung cấp cả file `docker` không đuôi và `docker.exe`. Bản helper mới chọn rõ `docker.exe`, vì Python có thể chọn file không đuôi trong khi PowerShell gọi Docker thành công. Nếu bản cũ chỉ báo `Lab filesystem/process error`, cập nhật `lab.py` và `lab/collect.py` từ cùng phiên bản mã nguồn, giữ nguyên `.local` và `.venv`. Kiểm tra `docker version` có cả Client/Server rồi chạy lại `lab.py up`; chỉ thu dữ liệu sau thông báo `Lab ready`.

Xem trạng thái lab tại thư mục dự án bằng `py -3.12 lab.py status`.

Kết quả kiểm chứng phần mềm/lab trong môi trường phát triển được ghi tại [VALIDATION.md](../VALIDATION.md). Lần chạy trên máy bạn vẫn cần các service healthy và collector hoàn thành thành công; cấu hình Compose một mình không chứng minh bằng chứng đã được thu.
