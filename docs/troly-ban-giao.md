# Bàn giao: Trợ lý File Quay (15/11/2026, phiên chat → tab Code)

Hướng mới đã chốt: project doc "huong-di-moi-tro-ly-file-quay.md" trên claude.ai. Làm Phần 1 + 2 trước:
chia giai đoạn theo giờ quay, thumbnail (proxy + LUT), phân loại vào bin con bằng phím 1–9, lưu nhãn để AI học sau.

## Đã có (chưa commit, chưa ghi CHANGELOG/ADR)
- `src/troly_core.py`: giờ quay, máy quay, chia giai đoạn, mẫu sự kiện, kế hoạch + nhãn. Không gọi DaVinci.
- `src/troly_thumbs.py`: thumbnail bằng ffmpeg, ưu tiên proxy, áp "Input LUT" của Media Pool, cache.
- `src/troly_resolve.py`: luồng nền gọi DaVinci: đọc bin/clip, tạo bin con + MoveClips, hoàn tác, mở clip.
- `tests/test_troly.py`: 19 bài, đạt (chạy trên Linux có ffmpeg; Media Pool giả).

## Số đo thật (project 2026.10.17, 1 máy, 533 clip, bin Master/01_footage/01_SELECTED)
- "Date Created" = lúc bấm quay, "Date Modified" = lúc dừng; created ≈ modified − độ dài (lệch ≤ vài giây).
  Start TC của máy KHÔNG phải giờ thật (lệch nhiều giờ). Sáng 06:25–09:27, tối 16:57–21:38.
- Chuỗi ngày DaVinci: "Sat Oct 17 2026 06:25:28" (Created), "Sat Oct 17 06:25:33 2026" (Modified). Không dùng strptime %b
  (Tk đổi locale) → `parse_resolve_date` tự đọc.
- Cả 533 clip có proxy 1920x1080 .mov ở `F:\02_Proxy Media\<project>\ProxyMedia\...` (thuộc tính "Proxy Media Path").
- "Input LUT" = `Sony\SLog3SGamut3.CineToLC-709TypeA` (không đuôi) → file
  `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\Sony\SLog3SGamut3.CineToLC-709TypeA.cube`.
- ffmpeg 9.0.2 có trên PATH (winget). Venv Python 3.10 có tkinter, PIL, cv2, numpy, customtkinter, torch.

## Việc còn lại
1. `src/panel_troly.py` (CustomTkinter, bảng màu Fluent Blue như panel_ctk.py):
   - Đầu: chọn bin nguồn, nút "Đọc clip", trạng thái.
   - Thẻ 1 Giai đoạn: chọn mẫu, "Gợi ý theo khoảng nghỉ quay" (`suggest_stages`), thanh thời gian (vạch = clip, khối màu =
     giai đoạn, kéo hai mép/kéo cả khối, lăn chuột để phóng), danh sách giai đoạn sửa tên/giờ, lệch giờ theo máy (giây),
     "Lưu thành mẫu", "Áp dụng vào Media Pool" (hỏi xác nhận, `target_folder` → worker `apply`), "Hoàn tác lần chuyển gần nhất".
   - Thẻ 2 Phân loại: chọn giai đoạn, lưới thumbnail theo giờ, phím 1–9 xếp vào bin con (`keymap`), 0 bỏ nhãn, mũi tên,
     Ctrl/Shift chọn nhiều, Enter mở clip trong DaVinci (`reveal`), lọc "chỉ chưa xếp", thêm bin con, xem lớn bên phải.
     Mỗi lần xếp ghi nhãn (`set_label`) vào `<data_root>\troly\projects\<project>.json`.
   - Thẻ 3 In/Out, 4 Thời lượng: để trống "sắp có".
   - Thumbnail: `ThumbMaker(<data_root>\cache\troly_thumbs\<project>)`, 4 luồng, làm giai đoạn đang xem trước.
2. `scripts/install_troly.py`: mục menu "VideoAI Trợ lý File Quay" (dùng LAUNCHER/MARKER của install_panel.py).
3. ADR-0009: thêm quyền GHI mới vào DaVinci: tạo bin con trong bin nguồn + MoveClips; có nhật ký và hoàn tác,
   không xóa clip, không đổi in/out, màu, file.
4. Chạy thử trên project thật (chỉ đọc trước), xem thumbnail có đúng màu LUT, rồi CHANGELOG, commit, push, cài menu.
