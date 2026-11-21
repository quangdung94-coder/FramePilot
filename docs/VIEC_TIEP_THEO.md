# Việc tiếp theo (tờ bàn giao sống, cập nhật 21/11/2026)

File này chỉ ghi phần HIỆN TẠI. Lịch sử ở `TRANG_THAI.md`, `CHANGELOG.md`, `docs/adr/`. Quy tắc ở `CLAUDE.md`.
Ai làm xong việc gì thì sửa file này (xem `AGENTS.md` mục 5). Đầu mỗi phiên: chạy `git status` và `git log -5` để biết nhánh/commit thật, vì file này có thể cũ hơn mã.

## Hướng đã chốt (20/11/2026)
- KHÔNG dùng con số cố định. HỌC từ lựa chọn của người dựng trong các project cũ; panel chỉ GỢI Ý, người dựng quyết.
- Thứ tự học: (1) In/Out (tốn thời gian dựng nhất) → (2) sao ★ (clip nào lên timeline; timeline cũ là đáp án) → (3) điểm chuyển sự kiện (giờ quay đứt, trong nhà ra sân, âm thanh đổi) để hỗ trợ chia giai đoạn. Người dựng trước giờ không chia sự kiện khi dựng.
- Tài liệu đề xuất thêm đặc trưng độ nét (Laplacian) và độ rung (optical flow) cho gợi ý In/Out; nụ cười/cỡ cảnh chỉ làm điểm cộng; bỏ ngưỡng cứng. CHƯA ghi vào kế hoạch: chờ người dùng quyết sau khi xem kết quả học từ project cũ.

## Công cụ học từ project cũ
- `tools/hoc_tu_cu.py` (+ `hoc_tu_cu_phan_tich.py`) đọc 5 project cũ qua bản sao .drp, CHỈ ĐỌC. Cấu hình local có tên khách nằm trong `hoc_tu_cu.local.json` (không lên git).
- Lệnh: `& C:\VideoAI_venv\Scripts\python.exe tools\hoc_tu_cu.py` (gõ Y để chạy; bị ngắt thì chạy lại làm tiếp; `--thu <tên> --mau-toi-da 20` để thử nhỏ). Cần mở DaVinci.
- Người dùng đã chạy đêm 20/11. Kết quả (chỉ số liệu): `D:\VideoAI\data\hoc_tu_cu\tong_hop.json`. TÓM TẮT KẾT QUẢ: **chưa có** — chờ người dùng đọc/dán. Khi có, ghi tóm tắt số liệu (không tên khách) vào đây rồi hỏi người dùng muốn gợi ý In/Out theo hướng nào.

## Việc tiếp theo, theo thứ tự
1. Đọc kết quả `tong_hop.json` cùng người dùng → đề xuất cách học In/Out (chỉ bàn, chưa làm khi chưa được bảo).
2. Nhiều camera: trang 1 (chọn mốc bằng thumbnail, Phần 1) đã làm và người dùng thử OK. Còn: trang 2 (làn ngang, mỗi máy một làn) và trang 3 (In/Out nhiều máy). Demo duyệt: `design/nhieu_camera/` (nếu có) hoặc bản trong project Claude. Mỗi trang dừng chờ người dùng duyệt. Quyết định: tối đa 4 máy (A–D, chữ cái trong ô màu), chia khung xem làm trong DaVinci không làm trong panel, timeline sync máy 1 lên V1/A1, tô màu clip chỉ khi bấm Áp dụng, gợi ý In/Out theo giờ chung là công tắc mặc định TẮT. "Pin" trong kế hoạch nghĩa là BIN. Project nhiều máy: giai đoạn liền nhau, không khoảng trống (CHƯA làm).
3. Trang 1 Phần 2 (đóng gói exe, B10–B19): CHỜ người dùng nói. Exe không làm panel mượt hơn, chỉ lợi cài đặt; có rủi ro Windows Defender.
4. Lời nói/Whisper: model đáng thử (cần người dùng DUYỆT trước khi tải): whisper large-v3-turbo, Qwen3-ASR-1.7B, PANNs/YAMNet, SigLIP so với OpenCLIP. Không dùng InsightFace (cần giấy phép thương mại). Tài liệu: `nghien_cuu/` trong project Claude (slide FramePilot_nghien_cuu).

## Đang chờ người dùng thử / quyết (đừng tự đặt "Xong")
- **21/11 (Antigravity làm 3 giai đoạn, 584 test đạt):**
  - Giai đoạn 1: Gợi ý In/Out bằng Hình ảnh (độ nét + độ rung, bỏ ~1.3s đầu) + VAD (`troly_vision_io.py`), thanh Zoom ảnh Page 1/2, Hover Scrub không cần giữ chuột, cụm `J-K-L` tua / `I-O` tại con trỏ chuột (cả Bước 2 & 3), `P` gắn sao ★, quét chuột chọn nhiều clip.
  - Giai đoạn 2: SigLIP (`ViT-B-16-SigLIP`) đã tải về `D:\VideoAI\data\models\siglip_vitb16` và nối vào `troly_ai.py` (đã thử chạy GPU thật, chờ anh bấm Tự phân loại trên project thật).
  - Giai đoạn 3: Nhiều camera Trang 2 (làn ngang + lọc máy) & Trang 3 (Các máy khác lúc này + công tắc giờ chung mặc định TẮT) trong `multicam.js` — mới kiểm thử tự động, CHƯA thử trên DaVinci + pywebview thật.
- B7: Space phát/dừng clip ở Bước 2 (đã commit d93de1f). Phát khi không có proxy cần mở rộng máy chủ phát sang file gốc: chưa làm, chờ quyết.
- Tự phân loại AI Bước 2 xếp 0 clip: đã sửa (bỏ ràng buộc proxy), chờ người dùng bấm Tự phân loại lại.
- Bước 1 chọn mốc với NHIỀU máy THẬT trên panel pywebview: mới thử bằng DaVinci giả.
- Các mục "CHƯA CHẠY THẬT" trong `docs/RA_SOAT_19_11.md`.

## Việc KHÔNG được làm khi chưa có lệnh rõ của người dùng
- Ghi In/Out vào Media Pool (chỉ khi người dùng đồng ý và đã sao lưu In/Out cũ). Tải model/thư viện. Xóa bất cứ gì. Gộp nhánh vào main (nếu gộp nhiều nhánh thì báo trước MỘT lần). Push lên GitHub nếu người dùng chưa bảo.
- Mở rộng quyền ghi của panel vào DaVinci ngoài danh sách trong `CLAUDE.md`.

## Chỗ khác với Claude Code
- Không có Notion: ghi tạm vào `TRANG_THAI.md` (xem `AGENTS.md` mục 5). Claude đồng bộ lại sau.
- Trạng thái Notion dùng: Chưa làm / Đang làm / Chờ anh thử / Xong / Đã đóng. Nhóm việc: A Nhiều camera, B Tinh chỉnh panel, C Lời nói/Whisper, D Kiểm thử thật, E Dọn dung lượng. Dùng cùng nghĩa này khi ghi tạm.
