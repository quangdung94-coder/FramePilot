# ADR-0021: Thống kê In/Out thật từ project đã dựng để chỉnh bảng quy tắc

Ngày 18/11/2026. Trạng thái: đã đo, CHỈ ĐỀ XUẤT; chưa áp vào panel, chờ người dựng duyệt.

## Cách đo
- Đọc bằng `tools/inout_dump.py` (chỉ ĐỌC DaVinci: không SetMarkInOut, không ghi/xóa, không tạo timeline, không render). Việc duy nhất ngoài đọc: SaveProject project đang mở,
  LoadProject lần lượt P1, P2, rồi mở lại ĐÚNG project gốc (đã xác nhận trả về đúng tên). Trước khi mở: ExportProject từng project ra `D:\VideoAI\backup\drp_<ngày-giờ>\` (P1 12,5 MB, P2 1,6 MB, dưới ngưỡng 500 MB)
  cùng file dump In/Out (JSON cục bộ, có tên clip, không lên Git).
- Chỉ 2 project: P1 (973 clip, 11 timeline) và P2 (406 clip, 2 timeline). Media đều online (P1 972/973, P2 406/406). Các project khác không mở.
- Mẫu "thật" = đoạn nguồn đã dùng trên timeline thành phẩm (`full`, `Intro`/`intro`, `sameday`; bỏ timeline multicam/bản sao), tốc độ ≈1 (bỏ slow-motion: tỉ lệ đoạn nguồn/đoạn dựng ngoài 0,9–1,1),
  bỏ trùng (clip, vào, ra). Số frame nguồn lấy từ `GetSourceStartFrame/EndFrame` (đã đối chiếu: trùng In/Out Media Pool ở các clip có cả hai), quy giây bằng fps của clip.
  Phụ: In/Out đặt trong Media Pool (P1 94 clip, P2 9 clip).
- Chỉ lưu SỐ: `D:\VideoAI\data\troly\inout_stats\` (by_bin.csv, vs_rules.csv, inout_stats.json, index.html).
- Chưa biết kiểu quay Truyền thống/PSC của P1, P2 (kế hoạch panel chưa chọn) nên chưa tách.

## Bảng ghép tên bin (xin anh duyệt)
Bỏ số thứ tự đầu tên, gộp theo từ khóa: "Nghi lễ" (Lễ nhà hàng/Nghi lễ + Đón dâu về nhà trai/Nghi lễ), "Cô dâu chú rể" (2 giai đoạn), "Khách" (2 giai đoạn), "Gia đình" (Gia đình cô dâu),
"Chào bàn" (bin giai đoạn không có bin con), Decor, Phỏng vấn, Nhà trai đến, Khác. P1 không có bin con (bin theo buổi/camera) nên chỉ thống kê chung.

## Số đo (giây)
P2 (150 đoạn dùng): Giữ (trung vị; p25–p75) / điểm vào cách đầu clip (trung vị) / so với quy tắc hiện có.

| Bin | n | Giữ tv (p25–p75) | Vào tv | Quy tắc hiện có | Vào trúng ±0,5s | Ra trúng ±0,5s | Lệch giữ (tv) |
|---|---|---|---|---|---|---|---|
| Nghi lễ | 61 | 3,5 (2,6–4,8) | 3,3 | giữ 3–7 | 26% | 21% | −2,3 (anh giữ ngắn hơn) |
| Chào bàn | 22 | 3,3 (2,9–4,1) | 0 | mặc định (vào 1,2, giữ 3) | 32% | 36% | −0,6 |
| Khách | 16 | 3,5 (2,6–3,9) | 0 | mặc định | 25% | 31% | +0,5 |
| Phỏng vấn | 15 | 7,0 (4,2–8,5) | 38 | trọn câu | 0% | 7% | clip dài ~200s, anh chỉ lấy ~7s |
| Gia đình | 10 | 3,6 (3,0–4,1) | 0 | mặc định | 40% | 80% | +0,6 |
| Nhà trai đến | 9 | 3,4 (3,0–4,4) | 0,3 | mặc định | 44% | 44% | +0,4 |
| Cô dâu chú rể | 8 | 2,6 (1,8–3,0) | 1,6 | giữ 4 | 38% | 50% | −1,4 |
| Decor | 4 | 3,5 | 0 | giữ 3 | 50% | 75% | +0,5 (mẫu quá ít) |
| Tất cả | 150 | 3,7 (2,8–4,8) | 1,1 | — | 23% | 26% | IoU trung vị 0,45 |

P1 (245 đoạn, không có bin con): giữ trung vị 3,4 (2,2–4,8); điểm vào trung vị 14 s (clip nguồn dài trung vị 47 s); quy tắc mặc định trúng vào 14%, ra 8%, IoU 0,0. In/Out đặt trong Media Pool: giữ 2,5 s, vào 1,3 s (94 clip).

Nhận xét: độ dài đoạn giữ khá đều quanh 3–4 s ở mọi bin (không phải 4 s cho cô dâu/chú rể, cũng không phải 5–7 s cho nghi lễ); anh hay cắt ngay từ đầu clip (vào = 0) ở clip ngắn;
clip dài (Nghi lễ, Phỏng vấn, P1) thì điểm vào rất xa đầu clip nên quy tắc "vào +1,2s" hầu như không trúng. Phỏng vấn: thực tế giữ ~7 s trích, không giữ trọn câu/clip.

## Giá trị ĐỀ XUẤT cho bảng quy tắc (chưa áp; min–max = p25–p75 làm tròn 0,5 s, bin có n ≥ 8)
Nghi lễ 2,5–5 · Chào bàn 3–4 · Khách 2,5–4 · Gia đình 3–4 · Nhà trai đến 3–4,5 · Cô dâu chú rể 2–3 · Phỏng vấn 4–8,5 (bỏ "trọn câu"). Decor, Khác: chưa đủ mẫu (Decor ≈ 3,5 s).
Điểm vào: quy tắc theo vị trí cố định không bắt được thói quen; nên gợi ý theo nội dung (bước sau), không chỉnh số.

## OpenCLIP: clip giống nhau về hình có cắt giống nhau không? (P2, 143 đoạn, sai số tuyệt đối trung bình, giây, leave-one-out)
- Độ dài giữ: đoán bằng trung vị chung 1,79 · cùng bin 1,57 · 5 clip giống nhất về hình 1,73.
- Điểm vào: chung 11,1 · cùng bin 9,95 · 5 clip giống nhất 10,6.
→ Giống nhau về hình gần như không giúp đoán cách cắt (kém hơn dùng bin một chút). Không dùng vector hình để gợi ý In/Out.

## Giới hạn
- Chỉ 2 project; P1 không có bin con; chỉ 8–61 mẫu mỗi bin. Mẫu là đoạn người dựng DÙNG (có thiên lệch: clip bị bỏ không có mặt).
- Đoạn dùng trên timeline có thể đã chỉnh sau khi cắt (trượt/trim trên timeline), không hẳn là In/Out ban đầu.
- Chưa tách Truyền thống/PSC.
