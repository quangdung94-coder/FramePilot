# Trợ lý File Quay (panel DaVinci Resolve)

Thư mục này là dự án ĐỘC LẬP, tách từ repo VideoAI cũ ngày 17/11/2026. Mọi thứ cần biết nằm trong 2 file:
CLAUDE.md (file này: mục tiêu, quy tắc, cấu trúc) và TRANG_THAI.md (đã làm gì, đang dở gì, làm gì tiếp).
KHÔNG cần đọc repo VideoAI cũ, Notion cũ hay các phiên chat cũ.

## Mục tiêu
Trợ lý giúp người dựng phim cưới quản lý file quay TRƯỚC khi dựng, chạy trong DaVinci Resolve Studio 21.
Quy trình:
1. Đọc giờ quay thật của từng clip, xếp theo thời gian thực.
2. Chia ngày cưới thành giai đoạn (Chuẩn bị nhà gái, Rước dâu, Gia tiên, Đón dâu, Đón khách, Lễ nhà hàng, Chào bàn...)
   bằng thanh thời gian người dựng tự kéo; tạo bin giai đoạn trong Media Pool.
3. Xem thumbnail, xếp clip vào bin con (Decor, Beauty cô dâu, Chú rể, Gia đình, Phỏng vấn...). Người dựng xếp trước,
   AI học dần sau, người dựng chỉ duyệt cuối.
4. Đánh dấu sao ★ (phím J) clip muốn dùng, đưa toàn bộ clip có sao lên một timeline MỚI theo thứ tự giai đoạn + giờ quay.
   In/Out người dựng tự chỉnh trong DaVinci (panel chỉ gợi ý).
5. (Sau) chia thời lượng từng bin, AI tự phân loại.

## Người dùng
- Người dựng phim cưới, KHÔNG chuyên IT. Trả lời bằng tiếng Việt, giải thích thuật ngữ ngắn gọn như thầy giáo IT.
- Máy: Windows, DaVinci Resolve Studio 21.1.1 (Preferences > System > General > External scripting using = Local),
  RTX 3060. Python: C:\VideoAI_venv\Scripts\python.exe (gọi tắt `$py`). ffmpeg có sẵn trong PATH.

## Quy tắc làm việc
- Không cần hỏi lại từng bước nhỏ; hỏi trước khi XÓA, ghi đè dữ liệu người dùng, hay cài thứ gì lớn.
- Giao diện có demo đã duyệt (thư mục design/): code ra phải giống demo ít nhất 80-90% (bố cục, màu, chữ, nhãn).
  Code xong mở panel thật, chụp màn hình so với demo. Chưa so thì chưa báo xong. Không để lẹm mép ở mọi tỉ lệ DPI.
- Chữ hướng dẫn trên panel nói có chức năng nào thì chức năng đó phải chạy được.
- Phím tắt đọc bằng `event.code` (Digit1, KeyJ...), KHÔNG dùng `event.key` (Shift+3 ra "#", Unikey VNI dùng phím số).
  Bỏ qua phím khi đang gõ trong ô nhập chữ.
- Cuối mỗi buổi: cập nhật TRANG_THAI.md (đã làm / còn dở / bước tiếp) và CHANGELOG.md; nếu có Git thì commit + push.
- Báo trung thực: phần nào chưa chạy thử thật trên DaVinci thì nói rõ.
- Chỉ tải model/thư viện đã được anh duyệt trong chat; model chạy cục bộ, lưu D:\VideoAI\data\models\; Bước 6 chỉ GỢI Ý, không tự chuyển clip. Thư viện AI nằm trong venv RIÊNG C:\VideoAI_ai_venv (requirements_ai.txt), không cài vào venv của panel.

## Quy tắc với DaVinci (an toàn)
- Mặc định chỉ ĐỌC. Panel chỉ được GHI:
  a) tạo bin con + chuyển clip giữa các bin (AddSubFolder, MoveClips), có nhật ký và Hoàn tác;
  b) tạo timeline MỚI từ clip có sao (CreateTimelineFromClips, dự phòng CreateEmptyTimeline + AppendToTimeline).
- KHÔNG BAO GIỜ: xóa clip, đổi tên file, đụng file trên ổ đĩa, sửa/xóa timeline đang có, render.
  c) ghi In/Out của clip nguồn (SetMarkInOut/ClearMarkInOut), CHỈ khi người dựng bấm nút trong panel + hộp xác nhận nói rõ số clip; TRƯỚC khi ghi phải sao lưu In/Out cũ của từng clip (file riêng có ngày giờ trong <data_root>\troly\inout_backup), ghi xong đọc lại đối chiếu, có nút Hoàn tác khôi phục đúng bản sao lưu. In/Out người dựng đặt tay luôn thắng gợi ý; gợi ý tự động không bao giờ được ghi. Chỉ ghi In/Out, không đụng gì khác (ADR-0016). Số frame tính từ đầu file, không cộng Start TC.
- Đã đo: MoveClips không làm đổi timeline (2 timeline, 338 clip giữ nguyên).
- Lưu project (SaveProject, ADR-0017): người dựng đã đồng ý (18/11/2026) cho panel gọi `ProjectManager.SaveProject()`, CHỈ trong "Phân tích cả project" khi ô "Tắt máy khi xong" được tick, trước khi đếm ngược và ngay trước khi tắt. Lưu lỗi thì KHÔNG tắt máy. Ô tắt máy mặc định TẮT; không bao giờ tắt máy nếu bị dừng giữa chừng, chép lời lỗi hoặc người dựng bấm Huỷ. Kiểm thử chỉ dùng lệnh tắt máy GIẢ (biến môi trường TROLY_NO_SHUTDOWN chặn lệnh thật).
- Tên timeline mới không chứa ký tự `: & / \ * ? " < > |`.

## Dữ liệu
- config.json (thư mục gốc, không đưa lên Git): data_root = D:\VideoAI\data (dùng chung với bản cũ để giữ nhãn đã xếp); proxy_root = F:\02_Proxy Media (thư mục duy nhất trình phát được đọc).
- Kế hoạch mỗi project: <data_root>\troly\projects\<tên project>.json (giai đoạn, nhãn bin con, chọn tay, sao,
  trạng thái giao diện, nhật ký chuyển). Ghi tự động qua file tạm, có bản .bak. Khóa clip = đường dẫn TƯƠNG ĐỐI
  (ví dụ 01_footage/DG4939.MP4), không dùng ổ đĩa.
- Cache thumbnail: <data_root>\cache\troly_thumbs\<project>\ (xóa được, tự tạo lại).
- Không đưa lên Git: video, config.json, thư mục data.

## Sự thật đã đo về dữ liệu DaVinci
- Giờ quay thật: thuộc tính "Date Created" (= lúc bấm quay). Dùng nó nếu khớp (Date Modified − độ dài) trong 15 giây,
  không thì dùng Date Modified − độ dài. Start TC KHÔNG phải giờ thật (lệch hàng giờ).
- Chuỗi ngày dạng "Sat Oct 17 2026 06:25:28" (Created) và "Sat Oct 17 06:25:33 2026" (Modified): tự phân tích, không dùng
  strptime %b (lỗi theo ngôn ngữ máy).
- Proxy ở F:\02_Proxy Media (thuộc tính "Proxy Media Path"); thumbnail ưu tiên proxy. LUT: thuộc tính "Input LUT",
  ffmpeg lut3d (chép LUT vào cache tên ngắn, chạy ffmpeg trong thư mục cache để tránh lỗi đường dẫn Windows).
- Project thử (tên ví dụ, project thật không ghi ở đây): 2026.10.17.LV_Ten (533 clip, 1 máy), 2026.10.25.LV_X&Y (tên có `&`).

## Cấu trúc
- app/panel_troly_web.py: mở cửa sổ pywebview (WebView2) hiển thị app/troly_web/index.html.
- app/troly_web/: giao diện HTML/CSS/JS (index.html, style.css, app.js). JS gọi Python qua window.pywebview.api.
- app/troly_api.py: lớp TrolyApi, mọi hàm giao diện gọi (state, move, toggle_star, append_starred...).
- app/troly_core.py: logic thuần (giờ quay, giai đoạn, nhãn, sao, gợi ý In/Out suggest_inout, lưu kế hoạch).
- app/troly_resolve.py: luồng nền duy nhất gọi DaVinci (đọc clip, chuyển bin, hoàn tác, tạo timeline).
- app/troly_wave.py: sóng âm từ proxy bằng ffmpeg (chỉ đọc, cache <data_root>\cache\troly_wave). app/troly_web/step3.js: trang Bước 3 (danh sách clip, sóng âm, bảng quy tắc từng bin). Quyết định: docs/adr/0019. Demo: design/3_inout.
- app/troly_play.py: máy chủ phát proxy 127.0.0.1 (Range, chỉ trong proxy_root); app/troly_web/player.js: trình phát + kéo In/Out + nút Ghi In/Out (ADR-0016).
- app/troly_thumbs.py: làm thumbnail bằng ffmpeg (proxy + LUT, 4 luồng, cache).
- app/troly_speech.py (kéo âm lượng, VAD, Whisper, câu nghi bịa), troly_speech_store.py (kho SQLite mỗi project), troly_speech_run.py (chạy cả bin nền), troly_speech_srt.py (xuất/đọc lại SRT), do_loi_noi.py (đo). Giao diện bước 4: app/troly_web/speech.js. Quyết định: docs/adr/0014.
- app/troly_ai.py: Bước 6 AI (ADR-0020): nhúng thumbnail bằng OpenCLIP ViT-B/32, gợi ý bin theo mô tả, trang báo cáo tĩnh. Chạy bằng venv AI: `C:\VideoAI_ai_venv\Scripts\python.exe app\troly_ai.py all --project "<tên>"`. Giao diện gợi ý ở Bước 2 (app/troly_web/ai.js, ADR-0022; demo design/6_ai_goi_y). Chỉ gợi ý, Nhận chỉ gán nhãn.
- tools/inout_dump.py + tools/inout_stats.py: đọc In/Out thật từ project đã dựng (chỉ đọc DaVinci, đổi project rồi trả lại) và thống kê ra số (ADR-0021).
- app/troly_dur.py + app/troly_web/step5.js: Bước 5 Thời lượng (ADR-0013): chia thời lượng, cắt gọt, timeline mới bằng clip con. Số mặc định là ĐỀ XUẤT; demo design/4_thoi_luong (bản tĩnh design/4_thoi_luong_tinh).
- app/troly_lut.py (đọc .cube cho WebGL), app/troly_kf.py (keyframe proxy bằng ffprobe, chỉ đọc): khung xem đúng màu LUT + lướt mượt + AI tự xếp theo ngưỡng (ADR-0023).
- app/troly_env.py: đọc config.json, kết nối DaVinci, hộp báo lỗi.
- install.py: cài mục menu "VideoAI Trợ lý File Quay" vào Workspace > Scripts. Sửa code trong app\ không cần cài lại,
  chỉ đóng và mở lại cửa sổ Trợ lý.
- design/: demo đã duyệt (1_giai_doan, 2_phan_loai_inout, 4_thoi_luong = Bước 5 Thời lượng từ 17/11/2026) và loi_noi_demo/ (Bước 4 Lời nói: ảnh 4a, 4b + HTML). Mở bằng trình duyệt.
- Số bước: 1 Giai đoạn, 2 Phân loại bin, 3 In/Out, 4 Lời nói, 5 Thời lượng (đã làm, ADR-0013), 6 AI (gợi ý ở Bước 2, ADR-0020/0022). Bước Lời nói làm theo docs/de_bai_loi_noi_A.md.

## Chạy
- Cài thư viện: `& $py -m pip install -r requirements.txt`
- Cài menu: `& $py install.py` (kiểm: `--check`)
- Chạy tay không qua menu: `& $py app\panel_troly_web.py --project "<tên project đang mở>"` (thêm `--debug` để mở F12).
