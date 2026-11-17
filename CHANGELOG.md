# Nhật ký thay đổi

## 2026-11-17 (đêm, tiếp) – Lời nói A, bước 3: giao diện bản đồ lời nói
- Tab mới "4 · Lời nói" (tầng 1: bản đồ) theo demo 4a: thanh màu mỗi clip (xanh lá có cụm key, xanh dương có người nói, vàng có thể sai, trống im lặng, khung trắng gợi ý In/Out), câu tiêu biểu, cột Key và Ngữ, bộ lọc "Chỉ clip có cụm key", "Tiếng nói từ 20 giây", ô "Tìm chữ" cả project, dòng "Hiện X / Y clip", chọn giai đoạn, cột phải (thanh lớn, In/Out theo timecode file gốc, chữ clip, câu có key tô đậm).
- Gắn sao (phím J, event.code), kéo mép khung trắng, "Đặt In / Out" chỉ lưu vào kế hoạch panel (không ghi DaVinci). Nút "Chép lời cả bin", chọn thư mục kho, ngôn ngữ mặc định, đổi ngôn ngữ từng clip. "Xuất SRT", "Tầng 2", "Đọc kỹ từng câu" hiện mờ ghi "sắp có".
- Đổi số bước: 4 Lời nói (mới), 5 Thời lượng (trước là 4). API: speech_clips, speech_detail, speech_set_inout, speech_pick_dir. Kiểm thử 81 bài đạt.

## 2026-11-17 (đêm) – Lời nói A, bước 1-2: đo và kho dữ liệu
- Đo 5 clip thật: mức kéo cần +0,7 đến +5,5 dB (chưa có clip tiếng nhỏ), 21 câu, 1 câu nghi bịa; Whisper chạy gom nhiều file làm mất câu nên chép từng file, 2 tiến trình song song (~11 giây mỗi clip nhỏ).
- Mới: app/troly_speech.py (kéo âm lượng, VAD, Whisper, câu nghi bịa), troly_speech_store.py (kho SQLite một file mỗi project, đối chiếu, chạy tiếp, tìm chữ), troly_speech_run.py (chạy cả bin nền, nhật ký, giữ máy không ngủ, báo xong), do_loi_noi.py (đo). Hàm speech_* trong TrolyApi; Clip có thêm timecode bắt đầu `tc`.
- Sửa: làm tròn mức kéo xuống để đỉnh sóng không vượt trần. Kiểm thử 65 bài đạt. Chưa có giao diện (bước 3) và xuất SRT (bước 4).

## 2026-11-17 (tối) – Kho Git riêng
- Tạo kho riêng tư TroLyFileQuay; gỡ tên khách thật khỏi CLAUDE.md và lịch sử (amend + force-push); .gitignore thêm cache/, projects/*.json, *.bak, *.corrupt-*, *.log.
- Chép tests/ (47 bài), docs/adr (0009-0011), docs/troly-ban-giao.md từ kho cũ; đánh số ADR tiếp: 0012 = Bước 3, 0013 = Bước 4.

## 2026-11-17 (v0.2.5, đồng bộ với kho cũ commit b13c7fb)
- Sao ★ (phím J), lọc chỉ clip có sao, `suggest_inout`, nút "★ Đưa clip sao lên Timeline" chỉ tạo timeline MỚI (không sửa timeline có sẵn, không ghi In/Out). Quyết định ghi ở ADR-0011 (kho VideoAI cũ).
- Bản CustomTkinter `panel_troly.py` đã bỏ ở kho cũ; thư mục này chỉ có bản HTML.

## 2026-11-17
- Tách Trợ lý File Quay khỏi repo VideoAI sang thư mục độc lập TroLyFileQuay: app/troly_env.py thay các module dùng chung cũ (panel_common, analyze_project, extract_timelines); install.py riêng; CLAUDE.md và TRANG_THAI.md tự đủ.
