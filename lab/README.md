# Database research lab

Lab gồm cặp PostgreSQL và MySQL có cấu hình yếu/đối chứng, chạy trong mạng Docker riêng và không công bố cổng CSDL ra host. Collector đọc cấu hình đang chạy rồi xuất case JSON cho trợ lý báo cáo; không cần dữ liệu CSDL cá nhân hoặc Gemini key để thu evidence.

Từ thư mục dự án có `lab.py`:

```powershell
py -3.12 run.py --install-only
py -3.12 lab.py up
py -3.12 lab.py collect --output outputs/lab-001
py -3.12 lab.py down
```

Cần Python 3.12 và Docker Desktop dùng Linux containers. Mật khẩu local nằm trong `.local/lab.env`, không chia sẻ. `down` giữ volume. Dùng đường dẫn output mới mỗi lần thu.

Đọc [hướng dẫn đầy đủ](../docs/LAB_RESEARCH_GUIDE.vi.md) trước khi dùng dữ liệu cho nghiên cứu. `cases/*.json` là đầu vào model; reference candidates và mapping trạng thái phải giữ riêng để tránh rò rỉ đáp án. Nhãn dự kiến cần chuyên gia duyệt, bốn case chỉ phù hợp làm pilot.
