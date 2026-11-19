# ADR-0032: Bước 1 lấy nguồn từ timeline đã sync, mỗi track một máy (19/11/2026, bản thử)

## Bối cảnh
Người dựng quay nhiều máy và sync bằng tool riêng. Ngày giờ ghi trong file của các máy lệch nhau (đồng hồ máy), nên không dùng làm trục. Người dựng
bỏ hướng "chỉnh đồng hồ máy trong panel" của ADR-0031 và duyệt demo "A · Timeline nhiều track" (design/nhieu_camera).

## Quyết định
- **Nguồn dữ liệu**: panel đọc timeline đã sync trong DaVinci qua API (vị trí, độ dài, track của từng clip). Ô "Timeline" ở góc trên chọn timeline nguồn.
  Timeline chưa sync (nhiều track nhưng không chồng nhau về thời gian, hoặc không có clip) vẫn hiện, kèm nhãn "Chưa sync, đang dùng giờ trong file".
  Chưa chọn timeline = hành vi cũ (giờ trong file). Mỗi nguồn có BỘ GIAI ĐOẠN riêng vì trục khác nhau (giây từ đầu timeline hay giờ trong ngày).
- **Trục** tính từ đầu timeline (0:00:00, 0:30:00...), không dùng giờ quay.
- **Gộp máy**: mỗi track video có clip = một máy. Tên máy lấy theo tiền tố tên file, bỏ ngày ở đầu tên (20261114_HM2129 -> HM), không có chữ thì dùng "Máy N",
  không hiện "?". Khi nhóm máy BỎ QUA cờ xoay, chỉ dùng kích thước mã hoá gốc + tiền tố. Công tắt "Có máy quay dọc" (mặc định TẮT) mới tách nhóm theo hướng sau xoay.
  Không xoay hay sửa file.
- **Hàng âm thanh**: chỉ clip CHỈ có âm thanh (Tascam/Zoom, nhạc), không lấy âm thanh đi kèm clip video.
- **Một giao diện**: 1 máy thì thu gọn còn 1 hàng, nhiều máy thì thêm hàng. Hơn 1000 clip chỉ vẽ thanh màu, không vẽ thumbnail.
- **Giai đoạn**: thanh trắng hai mép để kéo, bám vào mép clip (công tắt), "Cắt giai đoạn tại con trỏ" (chỉ chia giai đoạn, KHÔNG cắt clip), vùng màu phủ mọi hàng.
- **Bin mẹ (sự kiện)**: chỉ là NHÓM trong panel (người dựng chọn 19/11). Bin giai đoạn vẫn tạo trong bin nguồn như cũ nên Bước 2 đến 5 không đổi.
  Mẫu có bin mẹ: "Cưới đầy đủ" (Lễ gia tiên + Tiệc nhà hàng), "Chỉ tiệc nhà hàng" (Đón khách / Làm lễ · Vows / Tiệc, một bin mẹ). Chọn timeline nguồn thì
  KHÔNG tự áp mẫu: người dựng chọn mẫu rồi bấm Gợi ý lại.
- **Không ghi marker lên timeline** (người dựng chọn 19/11): giai đoạn chỉ lưu trong kế hoạch của Trợ lý. Mở lại project vẫn còn giai đoạn, nhưng không có marker trên timeline DaVinci.

## An toàn
Chỉ ĐỌC DaVinci. DaVinci chỉ cho đọc item của timeline đang mở, nên khi timeline nguồn khác timeline đang mở, panel mở timeline cần đọc rồi TRẢ LẠI timeline cũ
(đổi timeline hiện tại là thay đổi hiển thị, không sửa nội dung). Không sửa timeline, clip, track hay marker.

## Cách thử
`tools\harness_cam.py --real "<tên project đang mở>"` mở giao diện trong trình duyệt, nối DaVinci thật (chỉ đọc), dữ liệu kế hoạch ghi vào thư mục tạm.
Đã thử trên 2026.11.14 (3 máy: DG, B_A, HM), timeline "test muliticam" (134 clip) và "multicam_01_footage" (1034 clip, 28 clip bin không nằm trên timeline).

## Chưa làm
Kéo thả giai đoạn giữa các bin mẹ. Trang 2 và 3 nhiều camera. Chưa thử cửa sổ pywebview thật với project này (dùng harness trình duyệt, cùng HTML/JS và cùng TrolyApi).
