# Nhật ký thay đổi

## 2026-11-18 – Bước 3 In/Out làm lại (ADR-0024) - CHỜ NGƯỜI DỰNG THỬ
- Cột trái cây clip sao (sao/tổng, công tắc mặc định BẬT); nút "Gợi ý In/Out cho clip sao" chạy nền, hai mức (quy tắc bin; lời nói + đệm 0,3 s); phím A nhận gợi ý rồi sang clip kế (chỉ Bước 3); khung chữ Whisper (bấm câu, Shift nối dài, chưa chép lời, không tiếng nói); ghi nhận nhận nguyên/chỉnh (plan["inout_stats"]); tools/sug_accuracy.py. 24 bài test mới (340 bài).
- Đo mức 1 trên project cũ: lệch < 1 s: 9% / 25%; mức 2 chưa đo được (chưa có chữ).

## 2026-11-18 – LUT trong khung xem, lướt mượt, AI tự xếp (ADR-0023) - CHỜ NGƯỜI DỰNG THỬ
- Khung xem áp LUT .cube bằng WebGL2 (nút LUT, không tạo file mới); lướt mượt: lệnh nhảy tuần tự, kéo theo keyframe (ffprobe chỉ đọc), thả chính xác, một thẻ video (đo trên cửa sổ thật: 13 -> 63 khung hiện khi kéo); AI tự xếp theo ngưỡng (mặc định 50%, dấu "AI xếp", không vào dữ liệu học, Hoàn tác). 33 bài test mới (316 bài).
- Độ đúng của AI tự xếp ở cảnh mới chỉ 43-59% từ ngưỡng 50% (chia theo giờ): xem ADR-0023.

## 2026-11-18 – Bước 5 Thời lượng (ADR-0013) - CHỜ NGƯỜI DỰNG THỬ; số mặc định là ĐỀ XUẤT
- Ô Video mục tiêu (12 phút), thanh chia tỉ lệ giai đoạn kéo được (tổng luôn khớp), bảng Min-Max TỔNG từng bin (Decor 10-20 s, Beauty 20-30 s, bin khác tự suy ra từ bảng quy tắc Bước 3), cảnh báo bin thiếu/dư, "Cắt gọt cho vừa" (chỉ kế hoạch trong panel), "Đưa lên Timeline mới" (hộp xác nhận, nhật ký trước, chỉ tạo timeline MỚI bằng clip con theo In/Out, không SetMarkInOut lên clip gốc, kiểm lại số timeline).
- Lưu plan["durations"] (chỉ khi anh sửa, có .bak). Đo thật 1 timeline thử trên DaVinci: độ dài = endFrame - startFrame (đã sửa công thức frame). Mã mới: app/troly_dur.py, step5.js, do_create_cut_timeline.
- 37 bài test mới (283 bài). Demo: design/4_thoi_luong (bản tĩnh dựng lại: design/4_thoi_luong_tinh).

## 2026-11-18 – Rà soát lỗi toàn bộ (chỉ sửa lỗi, không thêm tính năng)
- Sửa 7 lỗi (mỗi lỗi có bài test đỏ trước, xanh sau, tests/test_ra_soat.py): (1) tạo bin lỗi giữa chừng làm mất nhật ký các clip đã chuyển (không Hoàn tác được); (2) việc ghi DaVinci không kiểm đang mở đúng project; (3) Huỷ tắt máy bấm lúc lưu lần cuối vẫn bị tắt; (4) thumbnail ném lỗi làm kẹt hàng đợi; (5) Dừng chép lời vẫn chạy hết cả lô; (6) ffmpeg/Whisper/AI mồ côi khi đóng cửa sổ (Job Object) và AI nền nhận cờ dừng khi đóng; (7) chữ lỗi thời "AI gợi ý · chưa có dữ liệu".
- Kiểm chứng không có lỗi: máy chủ phát proxy (junction, UNC, ổ khác, URL kép, Range), kế hoạch cũ đọc-ghi vòng (4 file thật trên bản sao). 242 bài test đạt.

## 2026-11-18 – Áp bảng quy tắc In/Out mới (ADR-0021, anh đã duyệt)
- Số mặc định theo bin đổi theo số đo thật: Nghi lễ 2,5–5, Chào bàn 3–4, Khách 2,5–4, Gia đình 3–4, Nhà trai đến 3–4,5, Cô dâu chú rể 2–3, Phỏng vấn 4–8,5 (không còn trọn câu). Quy tắc anh tự sửa vẫn thắng. 231 bài test đạt.

## 2026-11-18 – Gợi ý AI trong Bước 2 của panel (ADR-0022) - CHỜ NGƯỜI DỰNG THỬ, giao diện/demo CHƯA được duyệt
- Hộp "Gợi ý AI" cột phải Bước 2: hạng 1-3 + điểm, Nhận (gán nhãn, như xếp tay; không chạm DaVinci), Bỏ qua, gợi ý cho cả nhóm (thẻ viền đứt trên lưới, Nhận cả nhóm qua hộp xác nhận), phím A/X, Chạy/Dừng AI nền. Demo design/6_ai_goi_y.
- Gợi ý chỉ xét bin của giai đoạn clip đang ở; đủ 20 nhãn tay thì học từ nhãn (kNN trên vector OpenCLIP), không thì theo mô tả. Đo (project 324 nhãn): mô tả 47%/86% (hạng 1/trong 3), học từ nhãn 85%/97% (LOO, lạc quan), chia theo giờ 53%/90%.
- tools/ai_cross.py (đo + đề xuất ghép tên bin, chưa áp; chưa đo chéo project vì chỉ 1 project đủ nhãn). Hai nút Áp dụng dính đáy cột phải Bước 2.
- 16 bài test mới (230 bài).

## 2026-11-18 – Thống kê In/Out thật từ project đã dựng (ADR-0021) - CHỜ NGƯỜI DỰNG DUYỆT ĐỀ XUẤT
- tools/inout_dump.py (chỉ đọc DaVinci; sao lưu .drp trước; đổi project rồi mở lại đúng project gốc) + tools/inout_stats.py (số liệu, không tên khách). 2 project (P1, P2), 245 + 150 đoạn dùng trên timeline.
- Kết quả: độ dài giữ ~3-4 s ở mọi bin; quy tắc hiện có trúng điểm vào 23%, ra 26% (P2); Phỏng vấn thực tế giữ ~7 s trích, không trọn câu. Đề xuất bảng mới trong ADR, CHƯA áp. Hình giống nhau không giúp đoán cách cắt (OpenCLIP).
- 5 bài test mới (214 bài đạt).

## 2026-11-18 – Bước 6 AI: OpenCLIP nhúng ảnh, gợi ý bin theo mô tả (ADR-0020) - CHỜ NGƯỜI DỰNG XEM
- Đã tải (đúng danh sách được duyệt): model OpenCLIP ViT-B/32 laion2B (605 MB, .safetensors, MIT) vào D:\VideoAI\data\models\openclip_vitb32_laion2b\; thư viện trong venv RIÊNG C:\VideoAI_ai_venv (~3,1 GB). Venv panel không đụng.
- app/troly_ai.py: ghép thumbnail với clip (dựng lại mã băm từ proxy), nhúng nền có dừng/làm tiếp, gợi ý bin theo mô tả (hạng 1-2-3 + điểm), đo độ khớp với nhãn tay (từ 20 clip), trang báo cáo tĩnh. Chỉ gợi ý, không ghi DaVinci/kế hoạch.
- Số đo: 350-530 clip nhúng trong 4-9 giây; project có nhãn: hạng 1 trùng 17%, trong 3 đầu 58% (lần viết lại mô tả đã nhìn nhãn nên không độc lập). Học từ nhãn tay (kNN) ~81%.
- CLAUDE.md thêm quy tắc tải model/thư viện; requirements_ai.txt; 7 bài test mới (209 bài đạt, 1 bỏ qua).

## 2026-11-18 – Trang Bước 3 In/Out riêng (ADR-0019)
- Demo design/3_inout (CHƯA được người dựng duyệt) + trang Bước 3: clip theo bin, trình phát, sóng âm từ proxy (app/troly_wave.py, cache, chỉ đọc), thanh In/Out kéo tay, bảng quy tắc gợi ý từng bin chỉnh được (lưu theo project, chưa sửa = như cũ), số giây cắt Truyền thống chỉnh được. Bước 2 không còn thanh In/Out. 30 bài kiểm thử mới, tổng 202.

## 2026-11-18 – Danh sách clip "có thể sai" (mục D)
- app/troly_speech_review.py: gộp tối đa 50 clip có thể sai (chỉ đọc kho) thành CSV + SRT trong thư mục dữ liệu (không vào Git/Notion). 5 bài kiểm thử mới. Đã chạy trên kho thật: 50 clip, 94 dòng. Không có lỗi chính tả "Quy quy tắc" trong kho.

## 2026-11-18 – Kiểu quay PSC / Truyền thống (ADR-0018)
- Ô chọn kiểu quay theo project (mặc định chưa chọn, không đổi gì). Truyền thống: gợi ý giữ dài, cắt 1,5 giây đầu/đuôi; PSC: bộ tham số 3-7 giây theo bin. Chỉ đổi gợi ý màu xanh, In/Out đặt tay luôn thắng. 9 bài kiểm thử mới, tổng 172.

## 2026-11-18 – Phân tích cả project + tắt máy an toàn (ADR-0017)
- Nút "Phân tích cả project" (chép lời cả bin rồi thumbnail), ô "Tắt máy khi xong" mặc định tắt, lưu project DaVinci rồi đếm ngược 2 phút có Huỷ, không tắt khi dừng/lỗi/lưu lỗi. Worker mới do_save_project; app/troly_batch.py. Quy tắc SaveProject trong CLAUDE.md. 23 bài kiểm thử mới (bản giả), tổng 163.

## 2026-11-18 – Đo proxy thật, sửa trình phát
- Đo 5 proxy ở 5 project (chỉ đọc): 4 mẫu H.264 + PCM trong MOV phát được trong WebView2 (0 khung rớt, lướt 20-165 ms); 1 mẫu HEVC không có hình mà không báo lỗi (ADR-0016).
- Sửa: trình phát tự chuyển sang bản xem nhẹ khi videoWidth = 0; bản xem nhẹ ffmpeg trước đây không bao giờ tạo được (file tạm .part thiếu -f mp4), nay chạy thật và giữ tiếng (AAC). Kiểm thử 140 bài đạt.
- Sao lưu trước khi làm: D:\VideoAI\backup\projects_20261118-062904 và TroLyFileQuay_20261118-062904.

## 2026-11-18 – Trình phát proxy + đặt/ghi In/Out (ADR-0016) - CHỜ NGƯỜI DỰNG THỬ
- Cột phải Bước 2: trình phát proxy (Space phát/dừng, thanh lướt, tốc độ 0.25-4×) qua máy chủ cục bộ 127.0.0.1 chỉ đọc trong proxy_root (config.json); không có proxy thì báo "Chưa có proxy" và giữ thumbnail; proxy WebView2 không phát được thì tự tạo mp4 H.264 nhẹ bằng ffmpeg trong cache (chưa chạy thật).
- Đặt In/Out bằng tay: kéo hai mép, phím I / O tại chỗ đang xem, mũi tên chỉnh từng frame; đặt tay luôn thắng DaVinci/gợi ý; lưu vào kế hoạch panel.
- Nút "Ghi In/Out clip sao" / "Ghi clip đang chọn" / "Hoàn tác" (cả ở tab Lời nói): hộp xác nhận nói rõ số clip, sao lưu In/Out cũ trước, đọc lại đối chiếu, báo clip lỗi/lệch, Hoàn tác khôi phục đúng bản sao lưu.
- Đo thật: SetMarkInOut nhận số frame từ đầu file (không cộng Start TC), chuỗi timecode bị từ chối, không kiểm vượt độ dài (panel tự kẹp).
- Kiểm thử 138 bài đạt (mới: test_troly_play, test_troly_inout). Phần chưa chạy thật: phát proxy thật trên WebView2, bản xem nhẹ ffmpeg, ghi hàng loạt trong panel thật.

## 2026-11-17 (khuya, tiếp) – Đổi tên giai đoạn và bin con trong kế hoạch (ADR-0015)
- Bấm đúp tên giai đoạn / bin con để sửa tại chỗ (Enter đổi, Esc hủy). Chỉ đổi trong kế hoạch của panel: nhãn, chọn tay, trạng thái giao diện đi theo tên mới; nhật ký chuyển giữ nguyên; phím 1-9 theo vị trí. Tên rỗng, ký tự cấm, trùng tên cùng cấp, quá 60 ký tự bị chặn.
- Hộp xác nhận Áp dụng nhắc các bin cũ trong Media Pool sẽ còn lại rỗng (không tự xóa).
- Đã thử rồi gỡ phương án đổi tên bin trong Media Pool (DaVinci 21.1.1 không có hàm đổi tên bin). Kiểm thử 114 bài đạt (sửa bài kiểm thư mục tạm để không bị ảnh hưởng khi đang chép lời thật).

## 2026-11-17 (khuya) – Lời nói A, mục A4: xuất SRT + ADR-0014
- Mới app/troly_speech_srt.py và TrolyApi.speech_export: SRT theo giai đoạn (mỗi giai đoạn một file, giờ nối tiếp liên tục qua các clip, mã [clip#số dòng] trong dòng chữ), theo phần đã chọn, hoặc một clip; dòng nghi bịa không xuất; không ghi đè file cũ; không xuất vào thư mục mã. Hàm read_back ghép SRT (kể cả đã dịch) về đúng clip và giờ gốc.
- Giao diện: nút "Xuất SRT theo giai đoạn" đã bật, thêm "SRT clip này" và "SRT phần đã chọn"; chọn nhiều clip bằng Ctrl/Shift + bấm, Ctrl+A.
- ADR-0014 (docs/adr). Dọn: TRANG_THAI bỏ mục đang dở (nút đưa clip sao lên timeline đã chạy đúng), đổi tên mẫu trong design/. Kiểm thử 94 bài đạt.

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
