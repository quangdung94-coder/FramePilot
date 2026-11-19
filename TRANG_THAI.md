# Trạng thái FramePilot, trước đây "Trợ lý File Quay" (cập nhật 19/11/2026)

Bàn giao cho project mới: đọc docs/BAN_GIAO.md trước.

## Nhiều camera, trang 1 làm lại (nhánh nhieu-camera-giao-dien, 19/11/2026, CHƯA gộp main, tag sao lưu truoc-nhieu-camera-ui) - 556 test đạt
- Trang 1 đọc thẳng timeline đã sync trong DaVinci (ADR-0032, thay ADR-0031): mỗi track video = một máy, tên máy theo tiền tố tên file (bỏ ngày ở đầu), trục từ đầu timeline, hàng giai đoạn kéo được + hàng máy + hàng âm thanh, con trỏ đỏ, cắt giai đoạn tại con trỏ, bám mép clip, bin mẹ (chỉ nhóm trong panel), mẫu "Chỉ tiệc nhà hàng". Bỏ panel chỉnh đồng hồ và thẻ máy cũ.
- Đã thử trên DaVinci THẬT (chỉ đọc) qua tools/harness_cam.py --real: project 2026.11.14, timeline "test muliticam" (3 máy, 134 clip) và "multicam_01_footage" (3 máy, 1034 clip). CHƯA mở bằng cửa sổ pywebview thật, CHƯA ghi marker (người dựng chọn không ghi).
- Còn: duyệt trang 1; trang 2 (làn ngang theo máy) và trang 3 (In/Out mỗi máy) làm sau, mỗi trang dừng chờ người dựng.

## Sửa lỗi Bước 3 và Khung xem trước (nhánh sua-loi-p3pad-showimg, 19/11/2026) - 526 test đạt
- Đã sửa 2 lỗi phát hiện qua review:
  1. `p3Pad` (app/troly_web/step3.js): đồng bộ giá trị đệm đã lưu từ kế hoạch lên ô nhập giao diện Bước 3 (`g.pad != null`). Trước đó mở lại panel luôn hiện 0.3 dù kế hoạch lưu số khác. Test: `tests/test_sua_loi_p3pad.py`.
  2. `showImg` (app/troly_web/app.js): cập nhật hình xem trước bằng cách cập nhật/thêm thẻ `img` thay vì gán `preview.innerHTML` (trước đó việc gán innerHTML làm tháo thẻ video khỏi DOM gây khựng/reset và xóa mất `canvas.pv-frame` của kho khung RAM). Test: `tests/test_sua_loi_showimg.py`.
- 526 bài test đạt (thêm 2 bài test mới).


## Kiểm tài nguyên git + dọn rác 19/11 (nhánh kiem-git-19-11, ĐÃ GỘP main: commit gộp 26d0fa9, tag truoc-gop-kiem-git-19-11)
- Đã thêm config.example.json, requirements_speech.txt, bảng tài nguyên ở docs/BAN_GIAO.md mục 2b; clone sạch chạy được test, install thử và panel với DaVinci giả. 524 bài test. Chi tiết: CHANGELOG.md.

## Tổng duyệt 19/11 + S1-S6: ĐÃ GỘP main 19/11 (commit gộp e08fff5, tag sao lưu truoc-gop-ra-soat-19-11 = 67bfa7d) - 520 test đạt; các mục CHƯA CHẠY THẬT vẫn chờ bạn thử tay
- 19 phát hiện: 4 nghiêm trọng / 7 trung bình / 8 nhẹ; đã sửa 11 (4 nghiêm trọng, 5 trung bình, 2 nhẹ), chưa sửa 8, mỗi lỗi một commit + test (tests/test_ra_soat_19_11.py). Chi tiết, danh sách CHƯA CHẠY THẬT và câu hỏi cho bạn: docs/RA_SOAT_19_11.md.
- 506 bài test đạt lúc rà soát; sau quyết định 19/11 09:03: **520 bài đạt** (trừ 2 test bản xem nhẹ, thêm 16). Đo lướt không đổi so với main. Chưa thử bằng chuột thật / DaVinci thật cho các sửa đổi này.
- Đã làm theo quyết định của bạn (docs/RA_SOAT_19_11.md mục 5, ADR-0029): S1 bỏ hẳn bản xem nhẹ; S2 "+ Bin mới" và Đổi tên bin dùng chung một hàm kiểm tên, KHÔNG chặn `&`; S3 mở lần hai thì đưa cửa sổ cũ lên trước (CHƯA CHẠY THẬT qua menu DaVinci); S4 ba lỗi nhẹ; S5 không làm (khóa clip trùng, cắt chữ 1100x680, e.key) và ghi ở docs/BAN_GIAO.md mục 8.
- Thay đổi hành vi bạn sẽ thấy: mở FramePilot lần hai cho cùng project sẽ đưa cửa sổ cũ lên trước (không đưa được thì báo "đang mở ở cửa sổ khác"); proxy không phát được chỉ báo rõ, không còn bản xem nhẹ; đổi bin nguồn rồi quay lại lấy lại giai đoạn cũ; clip trùng đường dẫn có cảnh báo vàng khi đọc clip.

## Gộp main 19/11
- main (commit gộp 10d4d18, 19/11/2026) đã chứa mọi việc của chuỗi nhánh: Bước 5 bản 3 timeline (ADR-0013), Tự phân loại B2/B3 (ADR-0026), lag lướt + kho khung RAM (ADR-0016 bản 1, 2), FramePilot (ADR-0027), "bạn" (ADR-0028), K3. Tag sao lưu: truoc-gop-19-11 (đầu nhánh sua-lag-luot-2). Các nhánh cũ còn nguyên, không xóa. 493 test đạt.
- Còn dở: rê chuột thật có sự kiện đầu trễ 50-112 ms ở trường hợp xấu (người dựng chấp nhận); chưa kiểm bằng mắt K3 (cmd chớp); chạy `install.py` để menu hiện "FramePilot".

## Đêm 18/11 (4 dòng Notion [Đêm #1]-[Đêm #4]), nhánh xếp chồng, KHÔNG gộp main
- #1 xong code (nhánh tu-phan-loai-b2-b3, ADR-0026): Tự phân loại chạy luôn ở Bước 2 và 3. Chờ thử bằng chuột thật và AI thật.
- #2 xong code (nhánh sua-lag-luot, ADR-0016): đo lướt + dừng tay thì nhảy chính xác + tải trước clip kế. CHƯA đo trong panel pywebview thật (chạy panel với --debug, bấm Đo lướt).
- #3 xong code (nhánh doi-ten-framepilot, ADR-0027): đổi tên FramePilot + icon; đã mở panel thật 4K 150% thấy icon đúng. Chạy `install.py` để menu DaVinci hiện "FramePilot" (mục cũ xóa bằng `--remove-old`).
- #4 xong code (nhánh doi-ten-framepilot, ADR-0028): chữ hiển thị gọi người dùng là "bạn" (39 chỗ), có test quét. Chờ bạn đọc lại.
- 19/11 (nhánh sua-lag-luot-2, ADR-0016 bản 2): rê chuột xem trước đã đo trong pywebview thật và làm kho khung nhỏ trong RAM (58-60 hình/giây, trễ p95 dưới 8 ms). Còn: rê thử bằng chuột thật; sự kiện đầu mỗi lần rê vẫn có lúc trễ 50-112 ms (chưa đạt hẳn "dưới 30 ms"); so màu bằng mắt.
- K3 xong code: tiến trình con chạy ẩn qua troly_proc (thủ phạm cửa sổ cmd chớp theo mã: nạp sóng âm). Chờ bạn mở liên tiếp nhiều clip xem còn chớp không.


## Đã chạy được
- Bước 1: đọc giờ quay thật, chia giai đoạn bằng thanh thời gian kéo được, mẫu giai đoạn, tạo bin giai đoạn trong
  Media Pool (đã áp dụng thật trên project 17/10: 533 clip, 0,8 giây, 0 lỗi, timeline không đổi).
- Bước 2: lưới thumbnail (proxy + LUT), xếp clip vào bin con:
  - Phím 1-9 = bin con của giai đoạn đang xem; 0 = bỏ nhãn.
  - F1–F12 (từ 19/11, ADR-0030; trước đây Shift+số) = chuyển clip sang giai đoạn đó rồi CHỜ bấm số bin con (không giới hạn thời gian; Esc hoặc bấm chỗ khác để thôi).
  - Kéo thả thumbnail vào bin, menu chuột phải, Ctrl+A, Shift/Ctrl + bấm chọn nhiều, mũi tên di chuyển, Enter mở trong DaVinci.
  - Bấm bin trong cây Media Pool chỉ để XEM (như mở thư mục con), không đổi nhãn clip.
  - Giai đoạn chọn tay cho từng clip thắng giai đoạn tính theo giờ.
- Panel nhớ project khi tắt/mở lại DaVinci (lưu ngay, bản .bak, khôi phục bước/bin/thu phóng).
- Cột phải: thanh In/Out xem được (cam = đã đặt trong DaVinci, xanh = gợi ý theo nhãn bin: Decor 3s, Beauty 4s,
  Nghi lễ 5-7s, Phỏng vấn giữ trọn câu, mặc định vào +1,2s giữ 3s). Chỉ xem, chưa kéo chỉnh, chưa ghi vào DaVinci.
- Dấu sao ★: phím J gắn/bỏ sao (chọn nhiều thì đặt đồng loạt), nút gắn/bỏ sao ở cột phải, ô lọc "Chỉ clip có sao".
- Nút "★ Đưa clip sao lên Timeline": chỉ tạo timeline MỚI (ADR-0011); người dựng đã thử trên DaVinci thật, chạy đúng.

## Lời nói A (đề bài docs/de_bai_loi_noi_A.md)
- Xong bước 1 (đo) và bước 2 (kho dữ liệu + chạy cả bin, thử trên bản sao 5 clip: đối chiếu khớp, chạy tiếp đúng). Chưa thử chạy cả bin thật 318 clip trong DaVinci.
- Xong bước 3 của đề bài (giao diện tab "4 · Lời nói" tầng 1: bản đồ, lọc, tìm chữ, cột phải, J gắn sao, kéo mép khung In/Out, Đặt In/Out lưu vào kế hoạch panel; đã đổi nhãn tab: 4 Lời nói, 5 Thời lượng). Đã mở trong cửa sổ pywebview thật (17/11 tối): hiển thị đúng, hộp chọn thư mục chạy được, kho giả 376 clip hiện đủ bản đồ; phím J, kéo mép khung, tìm chữ đã thử ở khung trình duyệt, CHƯA thử bằng tay trong cửa sổ thật. Lưu ý: đã chọn thư mục kho GIẢ cho project đang mở, nhớ chọn lại thư mục kho thật trước khi chép lời.
- Xong mục A4 (xuất SRT): nút "Xuất SRT theo giai đoạn" (mỗi giai đoạn một file, giờ nối tiếp liên tục, mã `[clip#số dòng]` trong dòng chữ), "SRT clip này", "SRT phần đã chọn" (Ctrl/Shift + bấm chọn nhiều clip). Có kiểm thử vòng đủ (xuất, đọc lại kể cả sau khi dịch, ghép đúng clip và giờ gốc). Đã thử ở khung trình duyệt với dữ liệu giả; CHƯA thử trong cửa sổ pywebview thật (hộp chọn thư mục xuất) và chưa xuất từ kho chép lời thật.
- ADR-0014 đã viết (docs/adr/0014-loi-noi-kho-du-lieu-va-xuat-srt.md).
- Việc kế (cần người dựng): chọn thư mục kho THẬT, bấm "Chép lời cả bin" (ước ~1 giờ cho 318 clip), thử xuất SRT; đưa 1-2 clip tiếng nhỏ để chốt mức kéo tối đa. Sau đó: tầng 2 đọc kỹ, nhập bản dịch về (hàm đọc lại đã có).
- Chưa chắc: tự nhận ngôn ngữ vi/en chỉ là đoán theo chữ (Whisper Const-me không có chế độ auto), chưa thử với clip tiếng Anh thật; ngưỡng kéo âm lượng chờ clip tiếng nhỏ.

## Đổi tên giai đoạn / bin con (đề bài 17/11 23:25, đổi kế hoạch 17/11 khuya) - XONG
- Kế hoạch (người dựng chốt): bin chỉ là NHÃN trong panel, bin thật chỉ tạo khi bấm Áp dụng, nên chỉ đổi tên TRONG KẾ HOẠCH của panel: không đổi tên trong Media Pool, không mô hình id, không nâng cấp file project. Chi tiết và lý do: docs/adr/0015.
- Đã sao lưu D:\VideoAI\data\troly\projects sang projects_backup_20261117-232355 (7 file) trước khi làm. Không ghi file project thật khi thử.
- Cách dùng: bấm ĐÚP tên giai đoạn (bước 1 hoặc cột Media Pool bước 2) hoặc tên bin con (cột Media Pool), gõ tên mới, Enter đổi, Esc hoặc bấm ra ngoài thì hủy. Tên rỗng, có ký tự cấm : & / \ * ? " < > |, trùng tên cùng cấp, quá 60 ký tự thì báo lỗi rõ. Nhãn clip đi theo tên mới; phím 1-9 giữ nguyên theo vị trí bin.
- Nếu đã Áp dụng rồi mới đổi tên: hộp xác nhận Áp dụng liệt kê bin cũ trong Media Pool sẽ còn lại RỖNG, Trợ lý không tự xóa.
- Kiểm thử: 114 bài đạt (thêm test_troly_rename, test_troly_rename_api, test_troly_rename_web). Đã thử bằng chuột/phím thật ở khung trình duyệt với Media Pool giả: đổi tên giai đoạn, đổi tên bin con, gõ số và J trong ô sửa không bị coi là phím tắt, tên sai bị chặn, Esc hủy, hộp Áp dụng có nhắc; không lẹm mép ở 1100, 1440, 2560 px.
- Người dựng đã thử trong cửa sổ Trợ lý thật và báo "ok" (17/11/2026). Chưa làm: menu chuột phải "Đổi tên" (bấm đúp đủ dùng).

## Trình phát proxy + đặt/ghi In/Out (đề bài 18/11, nhánh inout-player, ADR-0016) - CHỜ NGƯỜI DỰNG THỬ
- Xong code: trình phát proxy ở cột phải Bước 2, kéo/phím I O/mũi tên đặt In/Out tay, nút Ghi In/Out vào DaVinci (clip sao hoặc đang chọn) có sao lưu + đối chiếu + Hoàn tác, nối nút ở tab Lời nói. 140 bài kiểm thử đạt. Đã thử giao diện thật bằng Chromium với Media Pool giả ở 1440x900 và 2560x1440.
- Sao lưu bước 0: .drp project thử xuất bằng ExportProject -> D:\VideoAI\backup\drp_20261118-0145\project_LV_Ten.drp (chưa kiểm file bằng mắt); dump In/Out 376 clip (đều trống) -> D:\VideoAI\backup\inout_before_20261118-0145\inout_before.json. Đã sao lưu 18/11/2026 06:29: kế hoạch project -> D:\VideoAI\backup\projects_20261118-062904\ (7 file); mã nguồn (bỏ .git) -> D:\VideoAI\backup\TroLyFileQuay_20261118-062904\.
- Đo DaVinci (1 clip, đã xóa về trống): SetMarkInOut nhận frame từ đầu file, không cộng Start TC; chuỗi timecode bị từ chối; không kiểm vượt độ dài. Chi tiết ADR-0016.
- Đã đo proxy thật 18/11 (chi tiết ADR-0016): 4/5 mẫu H.264 + PCM trong MOV, phát trực tiếp được trong WebView2 (0 khung rớt, lướt 20-165 ms); 1/5 mẫu HEVC không có hình mà KHÔNG báo lỗi. Đã sửa 2 lỗi: trình phát chỉ dự phòng khi có `error` (nay thêm videoWidth = 0), và bản xem nhẹ ffmpeg không bao giờ tạo được (thiếu -f mp4; nay chạy thật 0,4 s, phát được). config.json đã có proxy_root, đã pull tới ab3509f.
- ANH CẦN LÀM: (1) mở panel bản mới, thử phát proxy thật và lướt, ghi thêm vào ADR-0016; (2) thử đặt In/Out và bấm Ghi trên 2-3 clip rồi Hoàn tác (Claude KHÔNG tự ghi In/Out vào DaVinci). Không ghi hàng loạt cho tới khi anh thử xong.
- CHƯA chạy thật: bấm phát trong cửa sổ panel pywebview thật (mới đo bằng cửa sổ WebView2 thử cùng máy chủ phát), chụp màn hình panel thật, ghi In/Out vào DaVinci thật, proxy khác độ dài bản gốc.
- Chưa làm (đúng đề bài): công tắc PSC/Truyền thống, trang Bước 3 đầy đủ, quy tắc tự tính In/Out vẫn hoãn.

## Phân tích cả project + tắt máy an toàn (đề bài 18/11, ADR-0017) - CHỜ NGƯỜI DỰNG THỬ
- Đã làm: nút "Phân tích cả project" ở tab Lời nói (chép lời cả bin rồi chờ thumbnail mọi clip), ô "Tắt máy khi xong" mặc định TẮT; khi tick: lưu project DaVinci (SaveProject) -> đếm ngược 2 phút có nút Huỷ -> lưu lần cuối -> tắt. KHÔNG tắt nếu bị dừng, chép lời lỗi/lệch, thumbnail chưa xong, lưu lỗi, ngoại lệ, đóng cửa sổ hoặc bấm Huỷ. Quy tắc SaveProject đã ghi vào CLAUDE.md.
- Kiểm thử: 163 bài đạt, toàn bộ dùng lệnh tắt máy/lưu GIẢ; lệnh tắt máy thật bị chặn bằng biến TROLY_NO_SHUTDOWN. Đã thử giao diện bằng bản giả: tick, hộp xác nhận, đếm ngược, Huỷ (không tắt), để chạy hết (chỉ gọi bản giả).
- CHƯA thử thật: SaveProject trên DaVinci thật, lệnh shutdown thật, cả lượt chạy thật vài giờ. Anh nên thử lần đầu với tick tắt máy rồi bấm Huỷ lúc đếm ngược.

## Kiểu quay PSC / Truyền thống (đề bài 18/11, ADR-0018) - CHỜ NGƯỜI DỰNG THỬ
- Đã làm: ô "Kiểu quay: chưa chọn / Truyền thống / PSC" ở thanh trên bước 2, lưu theo project (plan["shoot_style"]). Chưa chọn = KHÔNG đổi gì (kiểm thử khớp 31 tổ hợp với bản cũ). Truyền thống: cắt 1,5 giây đầu và đuôi, giữ dài; PSC: bộ tham số 3-7 giây theo bin hiện có. Chỉ đổi gợi ý màu xanh; In/Out đặt tay luôn thắng; gợi ý không bao giờ được ghi vào DaVinci.
- Kiểm thử: 172 bài đạt (thêm 9). Đã thử đổi kiểu bằng giao diện (bản giả) và kiểm thanh trên không chật ở 1100 px.
- CHƯA thử: trong cửa sổ panel thật; PSC hiện chưa khác mặc định về số (chỉ thêm nhãn), cần anh cho biết con số PSC muốn.

## Danh sách clip "có thể sai" để duyệt (mục D, 18/11) - XONG, chờ anh duyệt
- Công cụ app/troly_speech_review.py (chỉ ĐỌC kho SQLite ở chế độ read-only, kho không đổi một byte): gộp tối đa 50 clip có thể sai thành CSV + SRT trong thư mục dữ liệu, KHÔNG vào Git/Notion. SRT có mã [clip#số dòng] và nhãn [NGHI:lý do] ở dòng nghi.
- Đã chạy trên kho chép lời thật của project đang dùng (376 clip: 149 đã chép, 222 im lặng, 5 lỗi, 50 có thể sai): xuất 50 clip, 94 dòng -> D:\VideoAI\data\troly\review\co_the_sai_project_20261118-065721.csv và .srt. Lý do trong CSV: hallu (câu bịa quen thuộc), lap (lặp câu trước), ngoai (ngoài đoạn có tiếng), thua (quá ít chữ), keo (kéo âm lượng nhiều), khong_chu (có tiếng mà không ra chữ).
- Không tìm thấy lỗi chính tả "Quy quy tắc" trong tài liệu của kho (đã tìm hết .md/.py/.js/.html).
- Việc của anh: duyệt file trên và cho biết nhóm lý do nào hay sai để chỉnh bộ lọc.

## Trang Bước 3 In/Out: sóng âm + bảng quy tắc từng bin (đề bài 18/11, nhánh buoc3, ADR-0019) - CHỜ NGƯỜI DỰNG THỬ
- **DEMO VÀ GIAO DIỆN BƯỚC 3 CHƯA ĐƯỢC ANH DUYỆT.** Anh miễn duyệt trước cho lượt này; Code tự làm demo (design/3_inout: index.html + 3_inout_demo.png 1440x900), rồi làm giao diện thật bám demo. Anh xem sau và có thể yêu cầu sửa bố cục.
- Đã làm: trang Bước 3 riêng (cột trái clip theo bin có chấm cam/rỗng/xanh = đặt tay/có trong DaVinci/gợi ý; giữa trình phát proxy + sóng âm + thanh In/Out kéo tay + nút Ghi/Hoàn tác dùng lại ADR-0016; phải bảng quy tắc từng bin). Bước 2 vẫn xem clip nhưng không còn thanh In/Out. Phím: Space, I, O, mũi tên trái/phải (frame, Shift = 10), lên/xuống đổi clip, J sao; số KHÔNG xếp bin ở Bước 3.
- Bảng quy tắc lưu theo project (plan["bin_rules"], plan["trad_trim_s"]); chưa sửa = gợi ý y hệt bản cũ (kiểm thử 31 tổ hợp), không có khóa mới trong file kế hoạch. Kiểm hợp lệ: số dương, min <= max. Sóng âm: ffmpeg đọc proxy (chỉ đọc), cache D:\VideoAI\data\cache\troly_wave\<project>\, nền, giới hạn 90 giây, không proxy thì báo "Chưa có proxy".
- Kiểm thử: 202 bài đạt (thêm 30: test_troly_rules_wave, test_troly_step3_web). Đã thử bằng bàn thử trình duyệt (giao diện + TrolyApi THẬT, Media Pool giả, proxy tự tạo): chọn clip, sóng âm, I/O/mũi tên/J/số, sửa bảng (số sai bị chặn), đổi bước 2 <-> 3 (trình phát chuyển chỗ); không lẹm mép ở 1440x900, 1100x700, 2560x1440 (4K 150%).
- CHƯA thử: trong cửa sổ panel pywebview thật (chưa mở panel thật, chưa chụp màn hình panel thật), proxy thật ở F:\, DaVinci thật, ghi In/Out. PSC vẫn giống mặc định về số (chỉnh bảng nếu muốn khác).
- Anh cần làm: mở panel, vào Bước 3, thử sóng âm + kéo mép + sửa bảng; xem demo design/3_inout và cho biết sửa bố cục gì.

## Bước 6 AI (18/11/2026, nhánh buoc6) - CHỜ ANH XEM, chưa có giao diện trong panel
- Model OpenCLIP ViT-B/32 laion2B: D:\VideoAI\data\models\openclip_vitb32_laion2b\open_clip_model.safetensors (605 MB). Venv riêng: C:\VideoAI_ai_venv.
- Chạy: `C:\VideoAI_ai_venv\Scripts\python.exe app\troly_ai.py all --project "<tên project>"` (embed | suggest | review; --stop để dừng, chạy lại làm tiếp).
- Kết quả: D:\VideoAI\data\troly\ai_suggest\<project>.json; trang xem D:\VideoAI\data\troly\ai_review\<project>\index.html (mở bằng trình duyệt).
- Đã chạy 4 project có cache thumbnail. Chỉ 1 project có đủ nhãn tay (324): gợi ý theo mô tả trùng 17% hạng 1, 58% trong 3 đầu => yếu, chỉ tham khảo. Học từ nhãn tay thử nhanh ~81%.
- Một project không còn proxy nên thumbnail không ghép được tên clip.
- Chưa làm: giao diện trong panel, học từ nhãn (few-shot), dùng giai đoạn/giờ quay để thu hẹp bin.

## Thống kê In/Out thật (18/11/2026) - anh ĐÃ DUYỆT bảng, đã áp làm mặc định
- Đã đọc 2 project đã dựng (P1, P2; media online) bằng tools/inout_dump.py; sao lưu .drp ở D:\VideoAI\backup\drp_20261118-102823 (15 MB). Đã mở lại đúng project gốc.
- Số liệu: D:\VideoAI\data\troly\inout_stats\ (index.html, by_bin.csv, vs_rules.csv). Giải thích + bảng đề xuất: docs/adr/0021. Bảng giá trị ĐÃ ÁP vào BUILTIN_RULES (Nghi lễ 2,5–5, Chào bàn 3–4, Khách 2,5–4, Gia đình 3–4, Nhà trai đến 3–4,5, Cô dâu chú rể 2–3, Phỏng vấn 4–8,5). Bảng ghép tên bin giữa project vẫn chờ anh duyệt.
- Chưa tách Truyền thống/PSC (kế hoạch panel chưa chọn kiểu quay).

## Bước 6 AI nhúng vào panel (18/11/2026) - CHỜ ANH THỬ; demo + giao diện CHƯA được anh duyệt
- Bước 2 có hộp "Gợi ý AI" (hạng 1-3, Nhận, Bỏ qua, gợi ý cả nhóm, phím A/X, Chạy/Dừng AI nền). Nhận chỉ gán nhãn trong Trợ lý, KHÔNG chuyển clip trong DaVinci. Demo: design/6_ai_goi_y. Quyết định + số đo: docs/adr/0022.
- Đủ 20 nhãn tay thì học từ nhãn, không thì theo mô tả. Số đo: mô tả 47%/86% (hạng 1 / trong 3 đầu); học từ nhãn chia theo giờ 53%/90%.
- Đã thử: bộ test, bàn thử trình duyệt với giao diện + TrolyApi thật + DaVinci thật (chỉ đọc), 1440x900 / 1100x700 / 1707x960. CHƯA mở cửa sổ pywebview thật. Chưa đo chéo project (chỉ 1 project đủ nhãn). Bảng ghép tên bin giữa project: file đề xuất, chờ anh duyệt.

## Rà soát lỗi toàn bộ (18/11/2026) - CHỜ ANH THỬ
- Sửa 7 lỗi (xem CHANGELOG), test: tests/test_ra_soat.py. Máy chủ phát proxy và đọc-ghi vòng 4 kế hoạch thật (bản sao): không lỗi.
- Đã mở panel THẬT (pywebview/WebView2, 4K 150%) với DaVinci thật chỉ đọc, dữ liệu là bản sao tạm: Bước 1-5 chuyển qua lại 19-33 ms, console không có lỗi JS (chỉ favicon 404). Mở với 376 clip: clip nạp xong trong khoảng 15 giây kể từ lúc chạy lệnh (gồm khởi động Python/WebView2, không đo tách).
- Chưa làm/chưa đo: project 500+ clip (không đổi project DaVinci nên chỉ có 376 clip), chép lời thật rồi đóng cửa sổ (chỉ thử Job Object với AI nền và tiến trình mẫu), kiểm JS bằng node (máy không có node, kiểm cú pháp bằng trình duyệt).
- Lỗi nhẹ chưa sửa: trang tải font Inter từ Google Fonts (cần mạng, mất mạng thì dùng font hệ thống); favicon 404; mã vé của máy chủ phát proxy không hết hạn (chỉ trong bộ nhớ).

## Bước 5 bản 3: TIMELINE KÉO THẢ (18/11/2026 khuya, nhánh buoc5-timeline) - CHỜ NGƯỜI DỰNG THỬ (ADR-0013)
- Trang Bước 5 thành timeline kéo thả theo demo đã duyệt (design/5_timeline_keo_tha): cụm mẹ/khối con dời được (theo giờ quay là mặc định), V1/V2 chồng, A1/A2, Tốc độ (100% / Slow mượt tự tính theo fps / gõ số) và Tiếng cho mọi khối (con thắng mẹ), số liệu theo RA TIMELINE, V2 không cộng vào Hiện Tại, mục tiêu chỉ là con số nhắm tới (dư/thiếu), gợi ý một chạm, hộp xác nhận ghi dư/thiếu/Slow/tắt tiếng. Thanh kéo bản trước (Có/Lấy, không vượt Có, Min-Max nâng cao) giữ nguyên bên dưới.
- ĐÃ THỬ THẬT trên DaVinci (project thử ZZ_TEST_TlKeoTha, đã mở lại project gốc, 2 timeline như cũ): Slow đúng cách = SetSpeed ripple True từng clip (RippleTimeline False KHÔNG dùng được: giữ độ dài, cắt source); V2 = AppendToTimeline recordFrame, Slow ở V2 phải khóa V1/A1 (không khóa thì hỏng V1); tắt tiếng SetClipEnabled chỉ chạy trên timeline hiện tại; chạy thẳng mã thật: V1 liền nhau đúng 530 frame dự tính, V2 đúng chỗ, A1/A2 tắt đúng khối, không còn khóa. Chi tiết ADR-0013.
- Project thử `ZZ_TEST_TlKeoTha` (12 timeline thử) còn trong cơ sở dữ liệu DaVinci: anh xóa tay nếu không cần (Trợ lý không xóa). Media thử ở %TEMP%\tltest.
- CHƯA chạy thật: cửa sổ pywebview thật (kéo chuột trong panel thật, chụp panel thật cạnh demo); cảm ứng thật; tạo timeline có Slow và V2 trên project THẬT của anh; tiếng tắt trong DaVinci thật với clip thật; project 06/11 mục tiêu 30:00; kiểu nội suy (Optical Flow...) chưa có nút.
- Sao lưu kế hoạch trước khi làm: D:\VideoAI\backup\projects_20261118-225543.

## Bước 5 Thời lượng: THANH KÉO (18/11/2026 tối, nhánh buoc5-moi) - CHỜ NGƯỜI DỰNG THỬ (ADR-0013)
- Sửa tiếp bản "một hàng/giai đoạn" theo demo bản 2 đã duyệt (design/5_thoi_luong_keo): thanh cố định, đầu phải = toàn bộ clip sao (Có), phần màu = Lấy với chấm kéo được (chuột + cảm ứng), gõ phút:giây vẫn được, không vượt Có; bin con cùng kiểu thanh (kéo bin cập nhật tổng giai đoạn); mặc định KHÔNG giới hạn Max (Min–Max ở "Giới hạn nâng cao", chỉ có tác dụng khi anh đặt); thiếu chỉ báo ở thanh tổng ("Hiện Tại", đoạn nét đứt); gợi ý Tự kéo thêm / Hạ mục tiêu xuống số Hiện Tại / Quay lại Bước 3; ổ khóa, tự cắt gọt khi sửa, "Đưa lên Timeline mới" giữ nguyên.
- Lỗi tổng thấp: nguyên nhân chính là Max mặc định của bin (đã bỏ); thêm hai nguồn hụt nhỏ đã sửa (rút ngắn clip hụt 0,1 s mỗi clip; Truyền thống hụt nguyên clip mỗi bin, nay có bù). "29:11 thay vì 30:00" không phải lỗi chia (số chia luôn cộng đúng mục tiêu khi đủ clip); chưa tái hiện đúng bằng dữ liệu của anh vì máy này không có project đó.
- CÁC SỐ vẫn là ĐỀ XUẤT: mục tiêu 12 phút; đạt = chênh <= 10 giây.
- Đã thử bằng chuột/pointer thật ở BÀN THỬ trình duyệt (giao diện thật + TrolyApi thật + Media Pool GIẢ + dữ liệu tạm, không đụng DaVinci/dữ liệu thật): kéo chấm giai đoạn (kẹp ở cuối thanh), gõ, khóa, gợi ý, bin con; không lẹm mép ở 1100x700, 1440x900, 1707x960 (= 4K 150%); bố cục khớp demo ~90%.
- CHƯA chạy thật: cửa sổ pywebview thật (kéo chuột trong panel thật, chụp panel thật cạnh demo); cảm ứng thật; tạo timeline thật trên DaVinci sau bản này (mã tạo giữ nguyên, đã đo 1 timeline thử ở bản đầu); Truyền thống cắt đầu/đuôi theo bin bằng tay; bin Đón khách/Tiễn khách thật; project 06/11 thật của anh (mục tiêu 30:00).
- Timeline thử của bản đầu còn trong project đang mở ("Rough Cut thoi luong ..."): anh xóa tay nếu không cần. Sao lưu kế hoạch trước khi làm: D:\VideoAI\backup\projects_20261118-191720.

## Lượt 18/11 (nhánh lut-smooth-aiauto): LUT, lướt mượt, AI tự xếp (ADR-0023)
- Việc 1 XONG (CHỜ ANH THỬ): khung xem trước áp LUT .cube bằng WebGL2 (player.js, nút LUT bật/tắt), không tạo file mới; máy chủ phát thêm CORS để WebGL đọc khung. Đo trong cửa sổ pywebview thật (4K 150%): sai khác trung bình so với ảnh ffmpeg+LUT 4,5-4,9/255 (tắt LUT: 26-30/255). Chưa thử LUT khác ngoài Sony SLog3 ... TypeA; LUT 1D/ cỡ > 65 chưa hỗ trợ (hiện màu gốc).
- Việc 2 XONG (CHỜ ANH THỬ): lướt mượt, KHÔNG tạo proxy mới: chỉ gửi lệnh nhảy khi lệnh trước xong (seeked), lệnh cũ chưa gửi bị thay bằng lệnh mới nhất; kéo thanh/mép In/Out thì nhảy theo keyframe (ffprobe chỉ đọc chỉ mục gói tin, cache troly_kf), thả thì nhảy chính xác; dùng lại MỘT thẻ <video>. Đo trong cửa sổ pywebview thật, clip 83 giây, kéo 100 bước trong 1,7 s: TRƯỚC 3 lần nhảy xong, 13 khung hình hiện; SAU 67 lần nhảy, 63 khung hiện; thả ra dừng đúng chỗ (75,17 s) sau 56 ms. Phát 1x: 0/299 khung rớt (trước và sau). Phát 2x: rớt ~217/595 cả trước lẫn sau, kể cả tắt LUT (proxy 50 khung/s x2 = 100 khung/s > 60 Hz màn hình, không phải lỗi của panel). Chuyển 8 clip liên tiếp: 1 thẻ video, hình đầu hiện sau 14-165 ms.
- Việc 3 XONG (CHỜ ANH THỬ): nút "AI tự xếp" (ngưỡng mặc định 50%, ô chỉnh 1-100%, ô "tự xếp sau khi AI chạy xong" mặc định tắt), dấu riêng "AI xếp" trên thẻ, KHÔNG tính vào dữ liệu AI học, Hoàn tác từng lần (giữ 10 lần), chỉ nhãn trong Trợ lý (không đụng DaVinci, không In/Out). ĐỘ CHÍNH XÁC (nhãn tay thật): bỏ từng clip ra ~87-90% đúng từ ngưỡng 50%, nhưng chia theo giờ (cảnh mới) chỉ 43-59% đúng từ 50%: nên tăng ngưỡng hoặc duyệt lại các thẻ "AI xếp". Chưa thử: ô tự xếp sau khi AI chạy xong (đầu-cuối), project chưa có nhãn tay.
- Đề bài gốc "claude/de-bai-3-viec-18-11.md" nằm trong project doc, KHÔNG có trong máy: làm theo nội dung tóm tắt trong tin nhắn giao việc.

## Bước 3 In/Out làm lại (18/11/2026, nhánh buoc3-moi) - CHỜ ANH THỬ (ADR-0024)
- Làm theo canvas "Bước 3 In/Out (bản phác mới)" (bản sao design/3_inout_moi): cột trái cây giai đoạn > bin con + "sao / tổng", công tắc "Chỉ hiện clip có sao" (mặc định BẬT); nút "Gợi ý In/Out cho clip sao" chạy nền (mức 1 quy tắc bin, mức 2 theo lời nói, đệm 0,3 s chỉnh được; lưu plan["inout_sug"]); phím A / nút "Nhận gợi ý (A)" chỉ ở Bước 3 rồi sang clip kế; khung chữ Whisper (bấm câu, Shift nối dài, Đặt In/Out ở đây, chưa chép lời, không tiếng nói); chân trang đếm số.
- Panel ghi lại số clip anh nhận nguyên / chỉnh (plan["inout_stats"]) để có số đo thật. Đo trước trên project cũ: mức 1 lệch < 1 s: 9% (P1), 25% (P2); < 2 s: 26% / 56%; mức 2 CHƯA ĐO ĐƯỢC (project cũ chưa chép lời).
- CHƯA chạy thử thật: trạng thái "Chưa chép lời" (chỉ ép dữ liệu), nút Ghi In/Out từ trang mới (mã ghi giữ nguyên, đã có test), project rất nhiều clip sao. Đã mở cửa sổ pywebview thật (4K 150%, bản sao dữ liệu) và so với demo.

## Bước 3: sửa 3 điểm (18/11/2026, ADR-0025) - CHỜ ANH THỬ
- Cây cột trái thu gọn/mở bằng mũi tên ▸/▾ (cả giai đoạn mặc định thu gọn, chỉ hiện bin con; P3.fold nhớ). Nút "Chạy gợi ý cho N clip sao" là nút chính, tiến độ trên nút, xong thành "Chạy lại", lỗi hiện đỏ rõ. Quay Truyền thống: cắt ĐẦU/ĐUÔI riêng từng bin (plan["trad_trim"]) + hai ô chung (trad_trim_s số hoặc cặp), cache gợi ý đổi theo.
- Đã thử trong cửa sổ pywebview thật (bản sao dữ liệu): thu gọn/mở, bấm nút (cả khi chưa có sao), bảng hai cột, nhập sai, về mặc định. CHƯA thử: Bước 5 với Truyền thống theo bin bằng tay; bin Đón khách/Tiễn khách thật (chỉ thử bằng Decor).

## Việc tiếp theo (theo thứ tự)
1. Bước 3 In/Out: XONG phần code (ADR-0019), chờ anh thử và duyệt demo. Còn: quy tắc tự tính In/Out nâng cao (hoãn), sửa bố cục theo ý anh.
2. Bước 5 Thời lượng: XONG bản làm lại (ADR-0013), chờ anh thử bằng clip sao thật và cho biết số muốn đổi.
3. Ý tưởng người dựng đã nêu (chưa thiết kế):
   - Nhiều máy quay (2-4 camera): nghiên cứu layout dễ nhìn (mỗi máy một làn trên thanh thời gian, màu theo máy, lọc theo máy).
     Panel đã có khóa máy quay + ô lệch giờ theo máy, chưa có giao diện.
   - Cho đổi tên bin giai đoạn (đổi theo cả bin trong Media Pool, giữ nhãn clip).
   - Số thứ tự đặt TRƯỚC tên bin thay vì sau (cần người dựng chỉ chỗ đang sai).
   - Sao nhiều mức 1/2/3 như lọc ảnh (phím khác 1-9, ví dụ Alt+1/2/3); lên timeline ưu tiên nhiều sao.
4. AI tự phân loại clip, học từ nhãn người dựng đã xếp: nền đã có (ADR-0020, vector ảnh). Bước kế: phân loại few-shot từ nhãn tay + giai đoạn, rồi giao diện duyệt trong panel.

## Ghi chú kỹ thuật
- Khi sửa logic trong troly_core.py nên thêm test vào tests/ rồi chạy bộ kiểm thử.
- Code sao/In-Out gợi ý ban đầu do Antigravity viết, phần nối giao diện + tạo timeline do Claude viết (15/11).
- Kho Git riêng: https://github.com/quangdung94-coder/TroLyFileQuay (riêng tư). Lịch sử kho riêng bắt đầu ở commit 5e9090c (đã gỡ tên khách; mã cũ 8945cc9 không còn dùng). Lịch sử trước 17/11/2026 nằm ở kho cũ D:\VideoAI\repo (v0.2.5 = commit b13c7fb). Menu DaVinci trỏ vào thư mục này (app\), `install.py --check` đạt.
- Bộ kiểm thử: tests/ (506 bài ngày 19/11, `& $py -m unittest discover -s tests -q`; trên Windows đặt PYTHONUTF8=1). ADR trong docs/adr/ (0009-0011, 0013-0028; danh sách 1 dòng trong docs/BAN_GIAO.md).
- Số ADR kế tiếp: 0029.
