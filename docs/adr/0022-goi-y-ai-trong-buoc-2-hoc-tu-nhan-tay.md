# ADR-0022: Gợi ý AI trong Bước 2 của panel, học từ nhãn tay

Ngày 18/11/2026. Trạng thái: đã code + thử trong bàn thử trình duyệt với DaVinci thật (chỉ đọc); CHƯA mở cửa sổ pywebview thật; giao diện và demo CHƯA được người dùng duyệt (miễn duyệt trước lượt này).

## Quyết định
- AI chỉ GỢI Ý. "Nhận" chỉ gán NHÃN trong kế hoạch panel (`by = "ai_duyet"`), như người dựng xếp tay; chuyển clip vào bin trong DaVinci vẫn qua nút "Áp dụng vào Media Pool" (có nhật ký + Hoàn tác như cũ). AI không gọi DaVinci (có test chặn trong `troly_ai.py`, `ai.js` và các hàm `ai_*`).
- Nguồn gợi ý, chọn theo từng project:
  - từ 20 clip đã xếp tay (có vector) trở lên và ít nhất 3 clip đã xếp trong các bin của giai đoạn đang xét: học từ nhãn (kNN k=7 trên vector OpenCLIP, nhiệt độ 20), hiện "theo nhãn anh xếp";
  - ít hơn: theo mô tả bin (ADR-0020), hiện "theo mô tả".
- Thu hẹp theo giai đoạn: chỉ xét các bin của giai đoạn mà clip đang thuộc (giai đoạn đã tính theo giờ quay hoặc chọn tay). Điểm chuẩn hóa trong các bin đó, hạng 1-3.
- Giao diện (cột phải Bước 2, theo design/6_ai_goi_y): hộp "Gợi ý AI" ngay dưới trình phát: 3 hàng bin + thanh điểm + % + nút Nhận; Bỏ qua (phím X), Nhận hạng 1 (phím A), "Gợi ý cho cả nhóm" (thẻ viền đứt trên lưới + "Nhận hạng 1 cho N clip" từ 70%, có hộp xác nhận), Chạy AI / Chạy lại / Dừng (nền, venv AI, dừng bằng cờ STOP, chạy tiếp được). Chưa chạy AI: hiện "Chưa chạy AI" và nút chạy. Hai nút Áp dụng dính đáy cột phải để không bị đẩy khỏi màn hình thấp (cột phải vốn dài hơn 900 px).
- "Bỏ qua" lưu `plan["ai_skip"]` (chỉ trong kế hoạch panel). Gợi ý chỉ cho clip chưa xếp.

## Số đo (project có 324 clip đã xếp tay; chỉ xét bin trong giai đoạn của clip)
| Cách | hạng 1 | trong 3 đầu |
|---|---|---|
| Theo mô tả | 47% | 86% |
| Học từ nhãn, bỏ từng clip ra (LOO, lạc quan vì clip liền kề giống nhau) | 85% | 97% |
| Học từ nhãn, học 60% clip quay SỚM, đoán 40% quay MUỘN (sát thực tế) | 53% | 90% |

Nhận xét: tách theo giai đoạn đã nâng "theo mô tả" từ 17% lên 47% (ADR-0020 đo trên cả 13 bin). Học từ nhãn hơn mô tả rõ khi các clip cùng cảnh nằm cả hai phía; với cảnh mới (chia theo giờ) chỉ hơn ~6 điểm ở hạng 1, nhưng hạng 3 đạt 90%: nên dùng như danh sách 3 lựa chọn để duyệt nhanh, không tin tuyệt đối.
Chỉ 1/4 project có đủ nhãn tay (3 project còn lại 0, 0, 4 nhãn) nên CHƯA đo chéo project (học project này, đoán project kia); công cụ `tools/ai_cross.py` đã sẵn và sẽ tự đo khi có ≥ 2 project đủ nhãn.

## Bảng ghép tên bin giữa các project (ĐỀ XUẤT, chưa áp)
Cả 4 project dùng chung bộ tên bin mẫu (13 tên), nên hiện chưa cần ghép; file đề xuất `D:\VideoAI\data\troly\ai_suggest\bin_name_map_proposal.json` liệt kê các nhóm tên trùng chữ (không phân biệt dấu/hoa thường). Các cặp gần nghĩa cần anh duyệt trước khi gộp để học chung giữa project: "Gia đình cô dâu" ~ "Gia đình", "Beauty cô dâu" ~ "Cô dâu chú rể". Chưa tự áp; học từ nhãn hiện chỉ dùng nhãn của chính project đang mở.

## Đã thử thật / chưa
- Đã: bộ test (12 bài panel + 4 bài giao diện), bàn thử trình duyệt dùng giao diện + TrolyApi thật, đọc DaVinci thật (project đang mở, chỉ đọc), kế hoạch/AI là bản sao tạm: gợi ý hạng 1-3, thẻ AI trên lưới, A, X, Nhận cả nhóm (hộp xác nhận, 119 clip, chỉ ghi nhãn), chuyển từ "theo mô tả" sang "theo nhãn" sau khi đủ nhãn, chạy AI nền bằng venv AI (8 giây, thoát đúng), 1440x900, 1100x700, 1707x960 (4K 150%) không tràn ngang. Kế hoạch thật không bị thay đổi (so với bản sao lưu trước khi làm).
- Chưa: mở cửa sổ pywebview thật; nút Dừng khi đang nhúng dở (đã thử cờ STOP và làm tiếp ở dòng lệnh, ADR-0020); độ chính xác trên project mới chưa có nhãn (chỉ ~47% hạng 1, ~86% trong 3 đầu).
