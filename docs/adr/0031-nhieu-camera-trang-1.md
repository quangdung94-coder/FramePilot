# ADR-0031: Nhiều camera, trang 1: nhận máy, tên máy, máy chuẩn, chỉnh đồng hồ (19/11/2026, bản thử)

## Quyết định (người dựng chốt 19/11, xem demo design/nhieu_camera)
- Tối đa 4 máy, chữ cái A-D, tên do người dựng đặt (không trống, không trùng, tối đa 20 ký tự, dùng chung 3 trang).
- Nhận máy từ metadata (`Camera Type`/`Camera Serial #`...) rồi mới tới tên file; không giả định tiền tố tên file. Nhóm không có model/seri,
  hoặc có clip chồng giờ nhau trong cùng nhóm (có thể là 2 máy cùng đời bị gộp), được ĐÁNH DẤU nhập nhằng; người dựng gán tay từng nhóm vào
  chữ A-D (hai nhóm cùng chữ = gộp một máy). Nhóm thứ 5 trở đi không tự gán, báo rõ trên giao diện.
- Giờ chung = giờ máy chuẩn (mặc định A). Độ lệch chỉnh bằng MỘT KHOẢNH KHẮC CHUNG (lướt hai clip tới cùng một cảnh, bấm Lấy khung này) hoặc gõ tay
  ±giờ:phút:giây. Cảnh báo trên 3 giờ, CHẶN trên 12 giờ. Khoảnh khắc cho hai clip không chồng nhau sau khi chỉnh: cảnh báo.
- Đổi máy chuẩn: độ lệch các máy ĐÃ chỉnh tính lại theo máy mới (off'(x) = off(x) - off(máy mới)); máy chưa chỉnh vẫn chưa chỉnh.
- Lưu trong kế hoạch project (`plan["cams"]`: map nhóm->chữ, names, ref, shift, moment). Độ lệch hiệu lực ghi vào `plan["offsets"]` theo khóa nhóm
  (chỗ `clip_minutes` đọc), nên giai đoạn, đếm clip, thanh thời gian đều theo giờ chung.
- KHÔNG ghi gì vào DaVinci, không đụng file gốc. Project 1 máy chạy y như cũ: không chạm `plan["offsets"]` nếu người dựng chưa chỉnh gì.
- Không làm trong bản thử: chia ô khung xem, dựng timeline sau sync (chỉ ghi chú trên giao diện), đoán giờ bằng sóng âm.

## Cách làm
- `app/troly_cams.py` (logic thuần), `TrolyApi.cams_*` (assign, rename, set_ref, apply, moment, apply_moment, reset), `state()["cams"]`,
  giao diện `app/troly_web/cam.js` + `cam.css` (bản sao từ design/nhieu_camera/cam.css).
- Khoảnh khắc chung xem bằng proxy (thẻ video, lướt bằng thanh trượt); clip không có proxy thì hiện thumbnail tĩnh.
- Thử bằng `tools/harness_cam.py` (DaVinci giả, dữ liệu tạm, mở bằng trình duyệt), không cần DaVinci thật.

## Chưa làm / chưa thử
- Chưa thử trên project thật nhiều máy trong DaVinci. Tên thuộc tính metadata máy (`Camera Type`...) là dự đoán theo DaVinci; nếu thật khác,
  nhóm sẽ rơi về nhận theo tên file và bị đánh dấu nhập nhằng.
- Trang 2 (bin nhiều máy, làn ngang) và trang 3 (In/Out nhiều máy) làm sau, mỗi trang một điểm dừng chờ người dựng.
