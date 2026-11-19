# Nhật ký thay đổi

## 2026-11-19 – Rê chuột xem trước: đo trong pywebview thật + kho khung nhỏ trong RAM (ADR-0016 bản 2) - CHỜ NGƯỜI DỰNG THỬ bằng chuột thật
- Đo TRONG cửa sổ pywebview thật (tools/panel_do_luot.py, DaVinci giả + proxy thật): cách cũ chỉ 5,8 hình/giây khi kéo thanh lướt, trễ p50 0,9 giây; JS/Python xử lý mỗi sự kiện chưa tới 1 ms, nghẽn là Video Decode của GPU lên 99% (số Chromium đêm 18/11 không phản ánh panel thật).
- Thử từng nghi phạm: tắt WebGL LUT, tắt tải trước, 3 nhóm cờ WebView2 (kể cả giải mã CPU): không đổi gì. Hẹn giờ "dừng tay nhảy chính xác" làm sóng âm tệ hơn (p50 20 ms lên 1133 ms). Gỡ tải trước clip kế (bộ giải mã thứ hai).
- Thêm kho khung nhỏ trong RAM (troly_frames.py): ffmpeg ưu tiên thấp giải mã sẵn khung 640 px, 25 khung/giây, JPEG, giữ trong RAM (8 clip, 300 MB, LRU), không ghi đĩa, không tạo proxy. Rê chuột/kéo thanh/rê trên sóng âm vẽ từ RAM; thả hoặc dừng 0,25 s thì video nhảy chính xác.
- Sau: 58-60 hình/giây, trễ p50 0,1-0,5 ms, p95 dưới 8 ms, không đứng hình quá 31 ms. CHƯA ĐẠT hoàn toàn mục tiêu dưới 30 ms ở trường hợp xấu nhất (1-2 sự kiện đầu mỗi lần rê trễ 50-112 ms, chưa rõ nguyên nhân).
- Test: +26 (tests/test_troly_frames.py), 489 bài đạt.

## 2026-11-18 (đêm) – Đêm #4: chữ hiển thị gọi người dùng là "bạn" (ADR-0028) - CHỜ NGƯỜI DỰNG ĐỌC LẠI
- Đổi "anh/Anh" thành "bạn/Bạn" ở 39 chỗ hiển thị trong 10 file (nút, tooltip, hộp xác nhận, thông báo, trang báo cáo AI...), đọc lại từng câu. Giữ "tiếng Anh" (English).
- Test quét chuỗi hiển thị: "anh" đứng một mình = 0 chỗ (+3 test); 463 bài đạt. Xem 5 trang ở 1440x900: không còn sót, không tràn ngang; thu nút "Tự phân loại" cho vừa chữ.

## 2026-11-18 (đêm) – Đêm #3: đổi tên hiển thị thành FramePilot và icon (ADR-0027) - CHỜ NGƯỜI DỰNG XEM
- Tên hiển thị FramePilot: tiêu đề cửa sổ, trang web, hộp lỗi, menu DaVinci (`FramePilot.py`; mục cũ chỉ xóa khi `install.py --remove-old`). KHÔNG đổi tên thư mục/repo/khóa lưu/tên timeline.
- Icon framepilot.ico gắn lên cửa sổ (WM_SETICON) và AppUserModelID "FramePilot" cho taskbar. Đã mở panel thật ở 4K 150%: taskbar và titlebar đúng icon, nét rõ. Chưa chụp ở 100%.
- Test: +8 (tests/test_troly_framepilot.py); 460 bài đạt.

## 2026-11-18 (đêm) – Đêm #2: sửa lag khi lướt xem trước (ADR-0016) - CHỜ NGƯỜI DỰNG THỬ trong panel thật
- Đọc mã thấy hàng đợi một lệnh nhảy, nhảy keyframe khi kéo, dùng lại một thẻ video, màu Log WebGL đã có từ ADR-0023: không làm lại, đem đo.
- Thêm nút **Đo lướt** (chỉ khi `--debug`): kéo giả đầu tới cuối clip, so cách cũ / keyframe / chính xác. Đo trên proxy thật: cách cũ 2-3 hình/giây, đứng hình tới 1,2 giây; hiện tại 27 hình/giây, đứng tối đa 55 ms (Chromium, chưa đo trong pywebview).
- Kéo mà dừng tay ~0,22 giây thì nhảy chính xác tới hình đó; tải trước phần đầu clip kế (thẻ video ẩn, chỉ đọc). Ghi nhận GPU (RTX 3060, giải mã H.264 phần cứng).
- Test: +8 (tests/test_troly_luot.py), sửa 1 test cũ (hai thẻ video); 452 bài đạt.

## 2026-11-18 (đêm) – Đêm #1: Tự phân loại chạy luôn ở Bước 2 và 3 (ADR-0026) - CHỜ NGƯỜI DỰNG THỬ
- Bỏ cặp nút "Tự phân loại | AI gợi ý" ở thanh trên. Bước 2: nút "Tự phân loại · N clip nhóm X" (khung cam, tiến độ a / b) gộp "Chạy lại AI" + "Gợi ý cho cả nhóm"; chỉ gán nhãn, không chuyển clip trong DaVinci.
- Ngưỡng tự xếp áp ngay khi kéo/gõ, không gọi AI lại; biểu đồ 10 cột độ chắc + vạch ngưỡng + hai số "tự xếp" / "chờ bạn duyệt"; clip dưới ngưỡng viền cam đứt.
- Bước 3: nút "Tự phân loại In/Out · N clip sao" dời xuống ngay dưới bảng quy tắc từng bin, có ô "Giữ nguyên clip bạn đã đặt tay" (mặc định bật). Cột trái chỉ còn cây clip sao.
- Sửa lỗi nặng bắt được khi làm: `$("segMode")` còn trong app.js sau khi bỏ nút làm panel đứng; thêm test quét mọi id JS.
- Test: +11 (API ai_auto_apply/ai_group_scores, keep_manual, giao diện, quét id); 444 bài đạt.

## 2026-11-18 (khuya) – Bước 5 bản 3: TIMELINE KÉO THẢ (ADR-0013) - CHỜ NGƯỜI DỰNG THỬ
- Trang Bước 5 thành timeline: thước 0:00 → mục tiêu, V2/V1, khung cụm mẹ + khối con, A1/A2 (vạch chéo = tắt tiếng), bảng thứ tự cụm đang chọn, cột phải + gợi ý. Kéo thả (pointer events): dời cả cụm, đổi thứ tự khối con / sang cụm khác / lên V2, mép phải đổi thời lượng (không vượt Có), kéo dòng bảng; "Xếp lại theo giờ quay" (hỏi xác nhận nếu đã xếp tay). Ổ khóa chỉ khóa thời lượng.
- Mọi khối (mẹ lẫn con) có Tốc độ (100% / Slow mượt tự tính = fps timeline ÷ fps source từng clip / gõ số; con thắng mẹ) và Tiếng (bật/tắt; con thắng mẹ). Số liệu tính theo RA TIMELINE (= In/Out gốc ÷ tốc độ); khối V2 không cộng vào Hiện Tại. Mục tiêu chỉ là con số nhắm tới: dư/thiếu; nút Đưa lên Timeline mới luôn bấm được, hộp xác nhận ghi dư/thiếu, Slow, tắt tiếng. Gợi ý mới: Đưa khối Slow về 100%, Bỏ clip ít ưu tiên cho vừa (chỉ khi anh bấm).
- Tạo timeline mới có V1 + V2, Slow giữ In/Out (SetSpeed ripple True từng clip, V1 liền nhau), V2 bằng recordFrame (Slow ở V2 khóa V1/A1 rồi mở), tắt tiếng bằng SetClipEnabled (A1 cho V1, A2 cho V2; không đụng A3+), đọc lại vị trí để kiểm. ĐÃ THỬ THẬT trên project thử (không chạm project thật): kết quả trong ADR-0013.
- Test: +38 (tests/test_troly_tl.py, test_troly_tl_api.py gồm DaVinci giả bám số đo thật, web); 433 bài đạt. Bàn thử trình duyệt (Media Pool giả) kéo chuột thật 1440x900, 1100x700, 1707x960; chưa mở cửa sổ pywebview thật.

## 2026-11-18 (tối) – Bước 5 sửa thành THANH KÉO (ADR-0013, demo bản 2 đã duyệt) - CHỜ NGƯỜI DỰNG THỬ
- Mỗi giai đoạn/bin một thanh cố định, đầu phải = toàn bộ clip sao ("Thanh đầy"), phần màu = số LẤY kết thúc ở chấm 28 px kéo được (pointer events, cảm ứng, bám 1 giây, Shift tinh chỉnh, phím ← →); gõ phút:giây vẫn được; không vượt Có. Chữ hàng: "Thanh đầy = X · lấy Y", "Bỏ Z (N clip ít ưu tiên nhất)", "Kéo hết cỡ rồi · muốn dài hơn phải gắn thêm sao". Thiếu chỉ ở thanh tổng ("Hiện Tại", đoạn nét đứt "thiếu X").
- Mặc định KHÔNG giới hạn Max (bỏ Decor 10-20 s, Beauty 20-30 s... làm tụt tổng); Min–Max chuyển vào "Giới hạn nâng cao", chỉ có tác dụng khi anh đặt. Kéo bin con (plan["durations"]["bin_s"]) cập nhật tổng giai đoạn. Gợi ý: Tự kéo thêm cho đủ / Hạ mục tiêu xuống số Hiện Tại / Quay lại Bước 3.
- Sửa nguồn hụt tổng (29:11 thay vì 30:00): rút ngắn clip không còn hụt 0,1 s mỗi clip (dồn phần lẻ), bù lại clip đã bỏ ở Truyền thống (trong giai đoạn và toàn cục, không vượt mục tiêu quá 10 s). Ca mẫu 34:40 clip sao, mục tiêu 30:00 -> Hiện Tại 30:00 ±10 s.
- Test: +12 (tests/test_troly_dur_moi.py viết lại, API kéo bin con/kẹp ở Có/đổi tên bin_s, web), sửa test cũ theo mặc định mới; 395 bài đạt. Thử bằng chuột/pointer thật ở bàn thử trình duyệt (Media Pool giả) 1100x700, 1440x900, 1707x960; chưa mở cửa sổ pywebview thật.

## 2026-11-18 – Bước 5 Thời lượng làm lại (ADR-0013, theo demo đã duyệt) - CHỜ NGƯỜI DỰNG THỬ
- Mỗi giai đoạn MỘT hàng (mũi tên xổ, ổ khóa, ô gõ phút:giây, thanh màu giữ/bỏ/thiếu, dòng "Có X, được chia Y, phải bỏ Z"); "Video mục tiêu" gõ phút:giây; thanh tổng "Đang giữ X, thiếu/dư Y". Bỏ vạch kéo tỉ lệ, bỏ nút "Cắt gọt cho vừa": mọi sửa tính lại ngay (gõ dở chưa tính, kết quả cũ bị bỏ, không vẽ lại khi đang giữ chuột).
- Khóa/gõ số làm giai đoạn khác co giãn theo tỉ lệ clip sao có, không vượt quá số có (thiếu thì báo thiếu, không bịa clip). Lưu plan["durations"]["stage_s"] và ["locked"]; khóa cũ stage_share bỏ qua; đổi tên giai đoạn đổi theo. Min mặc định co theo số chia; Min anh sửa là cứng. Truyền thống chỉ bỏ nguyên clip, "clip sao có thể cho" tính theo nguyên clip, số dư được bù lại.
- Bin con xổ ra (Có/Giữ/Bỏ/Min-Max), chip clip sẽ bỏ, xem trước timeline, cột phải "Chưa đạt mục tiêu" + 3 gợi ý (Chia lại cho đủ / Hạ mục tiêu / Quay lại Bước 3 mở đúng bin còn clip chưa sao). "Đưa lên Timeline mới" luôn bấm được, hộp xác nhận ghi số thiếu; tên "Rough Cut sao <project> <ngày giờ>" (không có `:`). Ô Kiểu quay hiện ở Bước 5.
- Test: +23 (tests/test_troly_dur_moi.py, API, web), sửa test cũ theo hành vi mới; 383 bài đạt. Đã thử bằng chuột/phím thật ở bàn thử trình duyệt (Media Pool giả, dữ liệu tạm) 1440x900, 1100x700, 1707x960; chưa mở cửa sổ pywebview thật.

## 2026-11-18 – Bước 3 sửa 3 điểm (ADR-0025) - CHỜ NGƯỜI DỰNG THỬ
- Cây clip thu gọn/mở (▸/▾, cả giai đoạn mặc định thu gọn); nút "Chạy gợi ý cho N clip sao" nổi bật, tiến độ trên nút, "Chạy lại", lỗi hiện rõ; Truyền thống cắt đầu/đuôi riêng theo bin (plan["trad_trim"]) và mặc định chung tách đầu/đuôi, giữ khóa cũ trad_trim_s. 18 bài test mới (358 bài).

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
