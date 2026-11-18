# Trạng thái Trợ lý File Quay (cập nhật 17/11/2026, khuya)

## Đã chạy được
- Bước 1: đọc giờ quay thật, chia giai đoạn bằng thanh thời gian kéo được, mẫu giai đoạn, tạo bin giai đoạn trong
  Media Pool (đã áp dụng thật trên project 17/10: 533 clip, 0,8 giây, 0 lỗi, timeline không đổi).
- Bước 2: lưới thumbnail (proxy + LUT), xếp clip vào bin con:
  - Phím 1-9 = bin con của giai đoạn đang xem; 0 = bỏ nhãn.
  - Shift+số = chuyển clip sang giai đoạn đó rồi CHỜ bấm số bin con (không giới hạn thời gian; Esc hoặc bấm chỗ khác để thôi).
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
- Bảng quy tắc lưu theo project (plan["bin_rules"], plan["trad_trim_s"]); chưa sửa = gợi ý y hệt bản cũ (kiểm thử 31 tổ hợp), không có khóa mới trong file kế hoạch. Kiểm hợp lệ: số dương, min <= max. Sóng âm: ffmpeg đọc proxy (chỉ đọc), cache D:\VideoAI\data\cache	roly_wave\<project>\, nền, giới hạn 90 giây, không proxy thì báo "Chưa có proxy".
- Kiểm thử: 202 bài đạt (thêm 30: test_troly_rules_wave, test_troly_step3_web). Đã thử bằng bàn thử trình duyệt (giao diện + TrolyApi THẬT, Media Pool giả, proxy tự tạo): chọn clip, sóng âm, I/O/mũi tên/J/số, sửa bảng (số sai bị chặn), đổi bước 2 <-> 3 (trình phát chuyển chỗ); không lẹm mép ở 1440x900, 1100x700, 2560x1440 (4K 150%).
- CHƯA thử: trong cửa sổ panel pywebview thật (chưa mở panel thật, chưa chụp màn hình panel thật), proxy thật ở F:\, DaVinci thật, ghi In/Out. PSC vẫn giống mặc định về số (chỉnh bảng nếu muốn khác).
- Anh cần làm: mở panel, vào Bước 3, thử sóng âm + kéo mép + sửa bảng; xem demo design/3_inout và cho biết sửa bố cục gì.

## Bước 6 AI (18/11/2026, nhánh buoc6) - CHỜ ANH XEM, chưa có giao diện trong panel
- Model OpenCLIP ViT-B/32 laion2B: D:\VideoAI\data\models\openclip_vitb32_laion2b\open_clip_model.safetensors (605 MB). Venv riêng: C:\VideoAI_ai_venv.
- Chạy: `C:\VideoAI_ai_venv\Scripts\python.exe app	roly_ai.py all --project "<tên project>"` (embed | suggest | review; --stop để dừng, chạy lại làm tiếp).
- Kết quả: D:\VideoAI\data	rolyi_suggest\<project>.json; trang xem D:\VideoAI\data	rolyi_review\<project>\index.html (mở bằng trình duyệt).
- Đã chạy 4 project có cache thumbnail. Chỉ 1 project có đủ nhãn tay (324): gợi ý theo mô tả trùng 17% hạng 1, 58% trong 3 đầu => yếu, chỉ tham khảo. Học từ nhãn tay thử nhanh ~81%.
- Một project không còn proxy nên thumbnail không ghép được tên clip.
- Chưa làm: giao diện trong panel, học từ nhãn (few-shot), dùng giai đoạn/giờ quay để thu hẹp bin.

## Việc tiếp theo (theo thứ tự)
1. Bước 3 In/Out: XONG phần code (ADR-0019), chờ anh thử và duyệt demo. Còn: quy tắc tự tính In/Out nâng cao (hoãn), sửa bố cục theo ý anh.
2. Bước 5 Thời lượng: ô "Video mục tiêu" (10-15 phút), biểu đồ chia tỉ lệ giai đoạn, Min-Max tổng thời lượng từng bin
   (Decor 10-20s, Beauty 20-30s), "Cắt gọt cho vừa", đưa lên timeline MỚI (không sửa timeline cũ).
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
- Bộ kiểm thử: tests/ (202 bài, `& $py -m unittest discover -s tests -q`; trên Windows đặt PYTHONUTF8=1). ADR trong docs/adr/ (0009, 0010, 0011, 0014 đến 0019).
- Số ADR sắp tới: Bước 3 trang riêng = ADR-0019 (đã làm), Bước 5 chia thời lượng = ADR-0013 (ADR-0011 = timeline mới, ADR-0014 = Lời nói A, đã có).
