# ADR-0023: Khung xem đúng màu LUT, lướt mượt, AI tự xếp theo ngưỡng

Ngày 18/11/2026. Trạng thái: CHỜ NGƯỜI DỰNG THỬ. Ba việc, mỗi việc một commit.

## Việc 1 – Khung xem trước đúng màu LUT
- Áp file `.cube` (3D, tối đa 65³) bằng WebGL2 lên từng khung hình của proxy ngay trong `player.js`: canvas phủ lên thẻ video, shader nội suy 3 chiều trên texture RGB16F, bỏ khung đen hai bên như `object-fit: contain`. KHÔNG tạo file mới, không đụng proxy; nút "LUT" bật/tắt để so sánh (chỉ khung xem, không đổi gì trong DaVinci).
- Dữ liệu LUT do `api.lut_cube(uid)` đọc từ file `.cube` gốc (tìm theo tên "Input LUT" như thumbnail), gửi dạng float32 base64 (`app/troly_lut.py`, chỉ đọc, nhớ trong bộ nhớ). LUT 1D, cỡ > 65, file hỏng, không thấy file: hiện màu gốc kèm ghi chú.
- Máy chủ phát proxy thêm `Access-Control-Allow-Origin: *` và thẻ video `crossOrigin="anonymous"` (cổng khác trang nên WebGL mới đọc được khung hình; vé ngẫu nhiên vẫn là khóa, vẫn chỉ nghe 127.0.0.1).
- Đo trong cửa sổ pywebview thật (4K 150%), LUT Sony SLog3→709: sai khác trung bình với ảnh ffmpeg+LUT cùng khung là 4,5–4,9/255 mỗi kênh (không LUT: 26–30/255).
- Giới hạn: kiểm với một LUT; sai khác còn lại do khác biệt giải mã/co ảnh; chưa thử LUT miền DOMAIN khác 0–1.

## Việc 2 – Lướt mượt, KHÔNG tạo proxy mới
- Chỉ gửi lệnh nhảy khi lệnh trước xong (`seeked`); lệnh cũ chưa gửi bị thay bằng lệnh mới nhất; có bộ đếm giờ 1,5 s phòng `seeked` không tới. Đang KÉO (thanh lướt, mép In/Out) thì nhảy tới keyframe gần nhất phía trước (giải mã một khung); THẢ ra thì nhảy chính xác. Dùng lại MỘT thẻ `<video>` cho mọi clip.
- Keyframe: `app/troly_kf.py` chạy `ffprobe -show_entries packet=pts_time,flags` (đọc chỉ mục gói tin, không giải mã, không ghi gì cạnh proxy), cache `<data_root>\cache\troly_kf\<project>\` (xóa được), chỉ cho proxy trong `proxy_root`.
- Đo trong cửa sổ thật, clip 83 giây, kéo 100 bước trong 1,7 giây: trước 3 lần nhảy xong và 13 khung hình hiện; sau 67 lần nhảy và 63 khung hiện; thả ra dừng đúng chỗ sau 56 ms. Phát 1x: 0/299 khung rớt (trước và sau). Phát 2x: rớt ~217/595 cả trước lẫn sau, kể cả tắt LUT (proxy 50 khung/s × 2 = 100 khung/s vượt 60 Hz của màn hình, không do panel). Chuyển 8 clip liên tiếp: một thẻ video, hình đầu hiện sau 14–165 ms.

## Việc 3 – AI tự xếp clip theo ngưỡng
- Nút "AI tự xếp" (hộp Gợi ý AI): mọi clip CHƯA xếp, chưa bị Bỏ qua, có gợi ý hạng 1 từ ngưỡng thì gán nhãn. Ngưỡng mặc định 50%, ô chỉnh 1–100% (lưu `plan["ai_auto"]["threshold"]` chỉ khi anh chỉnh). Ô "Tự xếp luôn sau khi AI chạy xong" mặc định TẮT.
- Nhãn có dấu riêng `by = "ai_auto"`; trên thẻ hiện "AI xếp · <bin>" (viền đứt), ô thông tin ghi "(AI xếp)". Anh xếp lại tay thì dấu đổi thành của anh.
- KHÔNG tính vào dữ liệu AI học: bị loại khỏi kNN, khỏi đếm nhãn (ngưỡng 20 nhãn), khỏi công cụ đo `tools/ai_cross.py` và đối chiếu `labels_by_stem`. (Nhãn "Nhận" thủ công `ai_duyet` vẫn tính vì anh đã duyệt, như ADR-0022.)
- Hoàn tác từng lần (giữ 10 lần gần nhất trong `plan["ai_auto"]["batches"]`): bỏ nhãn các clip đó nếu nhãn vẫn là của AI tự xếp; clip anh đã đổi thì giữ nguyên và báo số clip.
- Chỉ nhãn trong Trợ lý, KHÔNG đụng DaVinci: chuyển clip vào bin vẫn do nút "Áp dụng vào Media Pool" (hộp xác nhận nay nói rõ số clip do AI tự xếp). Không ghi In/Out.
- Độ chính xác đo trên nhãn tay thật (chỉ xét hạng 1 từ ngưỡng): bỏ từng clip ra (lạc quan): P-A 359/376 clip đạt 50%, đúng 89,7%; từ 70% đúng 96,2%; từ 90% đúng 98,9%. P-B: 87% / 90% / 97%. **Chia theo giờ (học 60% quay sớm, đoán 40% quay muộn, sát thực tế hơn): từ 50% chỉ đúng 43% (P-A) và 59% (P-B); từ 70% đúng 43% và 70%.** Nghĩa là ngưỡng 50% mặc định xếp sai khá nhiều ở cảnh mới; nên xem lại các clip có dấu "AI xếp", tăng ngưỡng (≥ 70–90%) hoặc dùng Hoàn tác.

## Đã thử thật / chưa
- Đã: cửa sổ pywebview thật (4K 150%, dữ liệu bản sao tạm của project đang mở, DaVinci chỉ đọc): LUT, lướt, AI tự xếp 174 clip rồi Hoàn tác (giữ lại 1 clip anh đã đổi), ngưỡng 70% được lưu. Không ghi In/Out, không đụng project cưới thật (kế hoạch thật không bị ghi).
- Chưa: nhiều LUT khác nhau, project chưa có nhãn tay (AI tự xếp theo mô tả, chính xác thấp hơn), tự xếp sau khi AI chạy xong (ô đã nối nhưng chưa thử đầu-cuối).
