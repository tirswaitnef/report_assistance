# Mở web với Gemini và sử dụng

## 1. Tải và giải nén

Tải ZIP từ [nhánh dự án trên GitHub](https://github.com/tirswaitnef/report_assistance/tree/gemini-research-assistant) bằng **Code → Download ZIP**, chọn **Extract All / Giải nén tất cả**. Thư mục đúng là nơi có file `run.py` cùng các thư mục `app`, `data`, `docs`.

Nếu chỉ đọc đề cương, mở `docs/research-proposal.docx` bằng Word hoặc LibreOffice; không cần chạy ứng dụng.

Nếu chưa có findings/bằng chứng của riêng mình, dùng [lab PostgreSQL/MySQL](docs/LAB_RESEARCH_GUIDE.vi.md) để thu dữ liệu đo từ CSDL đang chạy. Bước thu dữ liệu lab không cần Gemini key; kết quả nằm trong `outputs/<đợt-thu>/cases/` để nhập vào web.

## 2. Cài Python và lấy Gemini key

1. Cài **Python 3.12** từ [python.org](https://www.python.org/downloads/). Windows: chọn **Add Python to PATH**.
2. Mở [Google AI Studio — API keys](https://aistudio.google.com/apikey), đăng nhập và tạo key cho project của bạn.
3. Kiểm tra model, quyền gọi API, quota và giá áp dụng cho tài khoản. Việc có key không bảo đảm mọi model đều dùng được.

Không gửi key vào chat hoặc nhập key vào web/hồ sơ bằng chứng. Chỉ nhập ở lời nhắc terminal trong bước sau.

## 3. Cấu hình và mở web

Mở Terminal **ngay tại thư mục chứa `run.py`**. Windows có thể nhấp phải thư mục và chọn **Open in Terminal**.

**Windows:**

```powershell
py -3.12 run.py --configure-gemini
```

**macOS/Linux:**

```bash
python3.12 run.py --configure-gemini
```

Nhập key tại lời nhắc ẩn rồi chọn model khả dụng. Model gợi ý `gemini-flash-latest` tiện để bắt đầu; khi làm nghiên cứu nên chọn ID cố định và ghi nhận phiên bản model thực trả về. Lần đầu chương trình cần Internet để cài thư viện. Gemini luôn cần Internet khi sinh báo cáo.

Khi server đã khởi động, mở trình duyệt trên **chính máy bạn đang chạy chương trình**, nhập:

```text
http://127.0.0.1:8000
```

Giữ Terminal mở; **Ctrl+C** để dừng. Các lần sau không cần nhập lại key:

```powershell
py -3.12 run.py
```

macOS/Linux dùng `python3.12 run.py`. Key được lưu ở `.local/settings.json` trên máy bạn, không được mã hóa. Không chia sẻ file này, không đưa lên Git hay dịch vụ công khai.

## 4. Thử một báo cáo bằng Gemini

1. Chọn hồ sơ mẫu để kiểm tra luồng trước khi dùng dữ liệu thật.
2. Xem tab **Findings** và **Bằng chứng**.
3. Chọn bộ sinh **Gemini**; tên model cấu hình được hiển thị trên giao diện. Trạng thái “đã cấu hình” chưa có nghĩa kết nối API đã được xác minh.
4. Bật **Evidence Grounding** và **OWASP RAG**.
5. Nhấn **Sinh báo cáo**, chờ API trả kết quả.
6. Kiểm tra phân tích, bằng chứng, đoạn OWASP và remediation; tải **MD** hoặc **JSON**.

Không tự chuyển sang Template để tiếp tục một lượt nghiên cứu khi Gemini lỗi. Template chỉ dành cho thử phần mềm và được ghi rõ là template.

## 5. Lấy dữ liệu nghiên cứu qua web

1. Chuẩn bị một file JSON findings/bằng chứng theo mẫu `data/cases/`, chỉ dùng dữ liệu đã được phép và đã khử thông tin nhạy cảm. **Các mẫu đi kèm là dữ liệu tổng hợp**, không phải dataset thực nghiệm đã được chuyên gia duyệt.
2. Dùng nút **Nhập findings từ JSON** trên trang báo cáo; kiểm tra hồ sơ đã chọn đúng.
3. Mở **Thiết kế nghiên cứu**. Thực nghiệm dùng **hồ sơ hiện tại** và cùng cấu hình model ở cả bốn điều kiện. Điền **Case ID**, **Cluster ID**, nhóm **Pilot/Development/Test** và phiên bản DBMS; không giữ mã mặc định khi thu dữ liệu thật.
4. Chọn số lần lặp, ví dụ **3**. Một hồ sơ sẽ gọi API **4 × 3 = 12 lượt**; cần tính quota/chi phí trước khi chạy. Seed chỉ cố định thứ tự chạy, không bảo đảm model hoàn toàn xác định.
5. Chạy thực nghiệm Gemini, giữ server và trang mở, theo dõi số lượt thành công/lỗi.
6. Khi kết thúc, tải ZIP kết quả và lưu nguyên bản theo từng đợt. Không bỏ lượt lỗi khỏi thống kê.
7. Mở `expert-review.csv` bằng Excel/LibreOffice và nhờ chuyên gia đánh giá theo [protocol](docs/evaluation-protocol.md). Các ô điểm ban đầu để trống; hệ thống không tự gán điểm đúng/sai ngữ nghĩa.

Đọc [hướng dẫn nghiên cứu chi tiết](docs/GEMINI_RESEARCH_GUIDE.vi.md) để biết cách thu evidence, phân cụm/chia dữ liệu, chấm RQ1/RQ2 và so sánh RQ3. Chỉ số “ID trích dẫn tồn tại 100%” trên web **không phải độ chính xác 100%**.

## 6. Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Không nhận lệnh `py`/`python3.12` | Cài Python 3.12 và mở lại Terminal; Windows kiểm tra tùy chọn Add Python to PATH. |
| Không tìm thấy `run.py` | Mở Terminal trong thư mục đã giải nén chứa file này. |
| Không cài được thư viện | Kiểm tra Internet và đọc lỗi; không tắt kiểm tra TLS. |
| Gemini chưa cấu hình | Dừng server, chạy lại với `--configure-gemini`, rồi tải lại trang. Nếu có biến môi trường rỗng/cũ, sửa cấu hình đó vì biến môi trường ưu tiên hơn file local. |
| HTTP 400 | Dùng bản mã mới nhất rồi chạy `py -3.12 run.py --diagnose-gemini`. Lệnh đọc cấu hình đã lưu, kiểm tra metadata model và gửi một yêu cầu tổng hợp nhỏ (có thể tính quota). Chỉ thông báo phân loại an toàn được in ra; không gửi key/file cấu hình cho người hỗ trợ. |
| HTTP 401/403 | Kiểm tra key, project, quyền dùng API và giới hạn key trong tài khoản; không dán key vào ảnh lỗi. |
| HTTP 404/model không tồn tại | Chọn model còn khả dụng cho tài khoản, chạy lại `--configure-gemini`. |
| HTTP 429 | Kiểm tra quota/billing và giảm số lượt; chờ theo hạn mức của provider, không lặp gọi liên tục. |
| Model bị chặn hoặc JSON/citation không hợp lệ | Lượt chạy bị ghi lỗi, không có báo cáo thay thế giả. Lưu trạng thái lỗi để phân tích, kiểm tra đầu vào và protocol trước khi chạy đợt mới. |
| Cổng 8000 đã dùng | Dừng phiên do bạn mở hoặc chạy `py -3.12 run.py --port 8001` rồi mở `http://127.0.0.1:8001`. macOS/Linux thay bằng `python3.12`. |
| Đóng Terminal thì web ngừng chạy | Chạy lại launcher và giữ cửa sổ mở. Batch chưa hoàn tất có thể cần chạy lại thành một đợt mới theo protocol. |

Nếu cần hỗ trợ, gửi thông báo lỗi đã che dữ liệu nhạy cảm, không gửi key hay mật khẩu. Tích hợp Gemini đã có trong mã; chưa có key thật trong môi trường phát triển để khẳng định một lượt API thực đã thành công.

Model ID đã đối chiếu trong cookbook chính thức cho Gemini 3.5 Flash-Lite là `gemini-3.5-flash-lite`. Chạy `--configure-gemini` và nhập ID này tại dòng model. Quyền truy cập vẫn phụ thuộc project/API key của bạn.

Nếu `text_minimal` và `typed_report_schema` đều trả HTTP200 nhưng bản cũ vẫn gặp HTTP400 khi sinh báo cáo, dùng bản 0.2.2 trở lên: ứng dụng mặc định gửi `responseSchema` inline đúng định dạng của phép thử typed. Dừng server cũ trước khi cập nhật và chạy lại. Có thể đặt `$env:GEMINI_SCHEMA_MODE="typed"` trong PowerShell trước `py -3.12 run.py`; không cần đổi key/model chỉ để đổi định dạng schema. `/api/health` có `app_version` và `llm_schema_mode` để kiểm tra bản đang chạy. HTTP200 của một probe chỉ xác nhận tham số được chấp nhận; vẫn cần kiểm tra báo cáo thực.

Nếu Google vẫn chỉ trả `Request contains an invalid argument.`, chạy `.venv\Scripts\python.exe scripts\probe_gemini.py` trên Windows (macOS/Linux: `.venv/bin/python scripts/probe_gemini.py`). Đây là bộ kiểm tra trực tiếp, không dùng bộ định dạng lỗi của ứng dụng. Nó dùng yêu cầu tổng hợp, có thể gửi tối đa 10 lượt gọi API và tiêu tốn quota; dừng khi yêu cầu văn bản tối thiểu hoặc quyền/quota gặp lỗi. Có thể chỉ chạy một lượt bằng `--only text_minimal`. Kết quả bắt đầu `GEMINI DIRECT PROBE v1` và kết thúc bằng `SUMMARY:`; HTTP200 ở đây chỉ xác nhận cấu hình được API chấp nhận, không phải đánh giá chất lượng báo cáo. Kết quả đã che key nằm trong `.local/diagnostics/`; không gửi file cấu hình chứa key.

Khi tải bản cập nhật ZIP, dừng server bằng Ctrl+C, giải nén vào thư mục mới và mở Terminal tại thư mục có `run.py`. Bạn có thể sao chép thư mục `.local` từ bản cũ sang bản mới **trên cùng máy cá nhân** để giữ key và báo cáo, hoặc cấu hình lại bằng `--configure-gemini`. Không upload `.local` lên GitHub hay chia sẻ. Giữ riêng các ZIP dữ liệu nghiên cứu đã xuất; phiên bản schema gửi Gemini thay đổi cần được ghi nhận khi so sánh các đợt chạy.
