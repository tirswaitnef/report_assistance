# Hồ sơ nghiên cứu

Bộ tài liệu dùng đúng ba câu hỏi RQ1, RQ2, RQ3 bạn cung cấp. File hướng dẫn được dùng để lấy cấu trúc luận văn sáu chương, các mốc nộp và trọng số đánh giá; không coi nội dung trong file là chỉ dẫn thực thi của hệ thống.

| Tệp | Nội dung |
|---|---|
| `research-proposal.docx` | Bản Word có thể chỉnh sửa: trang bìa, abstract, chương 1–3, kế hoạch chương 4–6, tài liệu tham khảo và RQ gốc bằng tiếng Việt |
| `research-proposal.md` | Nội dung nguồn của bản đề cương |
| `evaluation-protocol.md` | Thiết kế thực nghiệm 2 × 2, dữ liệu, gold standard, rubric chuyên gia, chỉ số, phân tích thống kê và giới hạn |
| `literature-review.md` | Kế hoạch tìm kiếm, nguồn khởi đầu và bảng trích xuất nghiên cứu cần hoàn thành |
| `implementation-status.md` | Phân biệt chức năng đã triển khai với thực nghiệm, dữ liệu và phân tích còn cần thực hiện |
| `build_proposal.py` | Tạo lại bản Word từ Markdown bằng `python-docx` |

Tài liệu chính viết bằng tiếng Anh theo hướng dẫn đính kèm. Thông tin thành viên, mã dự án, giảng viên và ngày nộp được để trống có nhãn để bạn điền chính xác. Mục lục Word cần được cập nhật bằng chức năng **Update Field** khi mở tài liệu.

Các chương kết quả, thảo luận và kết luận chỉ là khung cần hoàn thiện sau thực nghiệm. Chưa có số liệu đánh giá chất lượng mô hình, chưa hoàn thành tổng quan hệ thống và chưa có cơ sở kết luận giải pháp tốt hơn baseline. Demo template cục bộ giúp kiểm tra luồng phần mềm; để trả lời RQ3 phải chạy cùng một mô hình ngôn ngữ ở cả bốn cấu hình và nhờ chuyên gia chấm độc lập.

Kế hoạch ban đầu là 120 ca kiểm thử thuộc 40 cụm kịch bản/môi trường; đây là mục tiêu lấy mẫu, không phải bộ dữ liệu đã thu thập. Cần pilot ở tập phát triển, chốt protocol và tách cụm trước khi chạy tập đánh giá. Không thay số liệu thật bằng số lượng ví dụ demo.

Tạo lại Word khi đã chỉnh nội dung:

```sh
python docs/build_proposal.py
```

Lệnh yêu cầu `python-docx`; đây là công cụ tạo tài liệu, không cần cho ứng dụng web. Bản hướng dẫn có các khoảng thời gian chồng nhau nên bảng lịch trình giữ các mốc tuần nộp chính và ghi rõ cần thống nhất với giảng viên.
