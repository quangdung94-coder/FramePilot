# Nhật ký thay đổi

## 2026-11-22 – Sửa triệt để lỗi cụm cuối bị đứng 1 tấm hình (DaVinci `CreateTimelineFromClips` lệch offset âm khi 1 clip cắt 2 khúc `Shift+I/O`), XONG (anh đã thử OK)
- `troly_resolve.py`: tách danh sách đoạn `V1` thành từng lô không trùng `mediaPoolItem` trong cùng 1 lời gọi `CreateTimelineFromClips` / `AppendToTimeline` (tránh lỗi C++ trong DaVinci Resolve 21.1.1 làm lệch toàn bộ clip sau khúc lặp `Shift+I/O` với `LeftOffset` âm hàng nghìn frame khiến mọi clip phía sau bị đứng thành 1 tấm hình).
- `troly_resolve.py`: bổ sung bước kiểm tra `GetLeftOffset() < 0` ngay sau khi tạo timeline trong `_finish_layout` để cảnh báo ngay nếu DaVinci sinh offset âm.

## 2026-11-22 – Sửa lỗi DaVinci bỏ rơi đoạn sau khi 1 clip có 2 khúc `Shift+I/O` (`do_create_cut_timeline`), XONG (anh đã thử OK)
- `troly_resolve.py`: sau `CreateTimelineFromClips`, kiểm tra ngay số clip thực tế trên `V1`; nếu DaVinci dừng giữa chừng (ví dụ 1 clip cắt 2 khúc `Shift+I/O` liên tiếp hoặc `endFrame` sát mép cuối file 59.94fps) thì tự động chèn bù từng đoạn còn thiếu bằng `AppendToTimeline` (có thử lùi 2 frame nếu sát mép cuối) thay vì im lặng rớt cả cụm cuối.
- `troly_tl.py`: bật kiểm đếm đủ số clip `V1` trong `verify_readback` để không bao giờ bỏ sót clip rớt.

## 2026-11-22 – Bước 5 mặc định gom gọn từng bin con + kéo thả tự do bin con & đồng bộ A1, XONG (anh đã thử OK)
- **Bước 5 (`troly_tl.py`, `index.html`, `step5.js`):**
  - Chuyển mặc định `#d5SortMode` sang **`Gom theo bin (kéo thả tự do)`** cho cả Truyền thống lẫn Phóng sự để mỗi bin con (`Decor`, `Gia đình`, `Khách`...) luôn là 1 khối liền mạch (không bị xé vụn chen vào nhau), trong khi clip bên trong mỗi bin con vẫn giữ đúng thứ tự giờ quay thật.
  - Khi kéo thả bin con (`move_block`) trong lúc đang chọn `Đan theo giờ quay (tách bin)`, hệ thống tự chuyển về `Gom theo bin` để thứ tự kéo thả có tác dụng ngay lập tức.
  - Đồng bộ lại thanh âm thanh `A1` bên dưới cho khớp với từng mảnh màu trên `V1` ở cả 2 chế độ.

## 2026-11-22 – Bước 5 xếp theo giờ quay (Truyền thống) & Bước 4 tắt tiếng A1 từng clip (phím M), XONG (anh đã thử OK)
- **Bước 5 · Không đảo thứ tự khi dựng Truyền thống (`troly_dur.py`, `troly_tl.py`, `troly_api.py`, `index.html`, `step5.js`):**
  - Thêm công tắc `#d5SortMode`: **`Theo giờ quay (TT)`** ↔ **`Gom theo bin (PSC)`** (tự động bật `Theo giờ quay` khi Kiểu quay = `Truyền thống`). Ở chế độ `Theo giờ quay`, mọi clip V1 trong từng giai đoạn giữ nguyên đúng trình tự thời gian thực, không bị gom dính theo bin (vẫn giữ linh hoạt đẩy khối B-roll lên `V2`).
- **Bước 4 · Bật/tắt tiếng A1 cho từng clip (`troly_core.py`, `troly_dur.py`, `troly_tl.py`, `troly_api.py`, `index.html`, `speech.js`, `step5.js`):**
  - Thêm nút **`🔊 Giữ A1 (M)` / `🔇 Đã tắt A1 (M)`** và phím tắt **`M`** (`event.code === "KeyM"`, hỗ trợ chọn 1 hoặc nhiều clip), hiện nhãn **`🔇 A1`** ngay trên danh sách clip Bước 4 để nhìn tổng quan lúc lướt text. Khi đưa lên timeline DaVinci ở Bước 5, các clip đánh dấu tắt A1 tự động tắt track tiếng `A1` (`SetClipEnabled(False)`) và vẫn giữ nguyên hình `V1`.

## 2026-11-22 – Thêm mẫu sự kiện Lễ mừng thọ (Cụ ông / Cụ bà thay Cô dâu / Chú rể), XONG (anh đã thử OK)
- `troly_core.py`: thêm 2 mẫu `Lễ mừng thọ (đầy đủ)` và `Lễ mừng thọ (chỉ tiệc)` trong `BUILTIN_TEMPLATES` & `TEMPLATE_EVENTS` (Chuẩn bị, Đón khách, Nghi lễ mừng thọ, Văn nghệ · Tiệc; dùng bin `Cụ ông`, `Cụ bà`, `Cụ ông cụ bà`, `Chúc thọ · Phát biểu`, `Trao quà · Mừng thọ`, `Văn nghệ`, `Chụp hình`), cùng quy tắc gợi ý In/Out Bước 3 tương ứng trong `BUILTIN_RULES`.
- `troly_ai.py`: bổ sung 4 thẻ cảnh chuẩn nhóm **Mừng thọ** (`cu_ong_cu_ba`, `cu_ong`, `cu_ba`, `chuc_tho`) kèm prompt SigLIP/CLIP nhận diện cụ ông/cụ bà và trao quà mừng thọ.
- `wedding_phrases.json`: bổ sung nhóm từ khóa `mung_tho` (mừng thọ, thượng thọ, cụ ông, cụ bà, sống lâu trăm tuổi, tứ đại đồng đường, khánh vàng...) để Bước 4 tự bôi sáng câu đắt giá.
- `app.js`: cập nhật `shortTplName` trong hộp Cài đặt `⚙` giữ nguyên tên mẫu `Lễ mừng thọ`.

## 2026-11-22 – Bộ công cụ Kiểm thử Xuyên Đêm (`tools/overnight_qa`) & Vá 6 lỗi thật trên bản `FramePilot.exe`, XONG
- **Công cụ kiểm thử xuyên đêm 100% local/offline (`tools/overnight_qa/`, `tests/test_overnight_qa.py`):**
  - Kết nối thẳng Edge WebView2 bên trong `FramePilot.exe` qua CDP (`cdp_client.py`, không cần thư viện ngoài), cách ly dữ liệu bằng `TROLY_CONFIG` + `TROLY_NO_SHUTDOWN=1` + junction thư mục `models` (`safety.py`), khóa cứng tên project `FP_TEST_*` khi chạy chế độ ghi (`sandbox_write`).
  - Hỗ trợ xoay vòng nhiều project (`--projects`), tự nhận diện nguồn 4K 10-bit chưa proxy (`--heavy-source`), watchdog đo RAM/Handles/VRAM riêng từng project + bắt tiến trình xác sống (`watchdog.py`), 4 bộ kịch bản `smoke_e2e`, `ai_gpu`, `chaos_race`, `sandbox_write` (`scenarios.py`), báo cáo `report.md`/`report.html` (`reporter.py`) và file bấm đúp `run_overnight.bat`.
- **Sửa 6 lỗi thật phát hiện qua phiên chạy xuyên đêm 3 tiếng (160 vòng trên 2 project 400 clip & 1.062 clip 3 cam):**
  - `troly_api.py`: tách đúng tuple 3 phần tử từ `_media_src(c)` trong `audio_events()` (CLAP Bước 3) và `speech_diarize()` (WavLM Bước 4).
  - `troly_vad_worker.py`, `troly_speech.py`, `troly_vision_io.py`, `build_exe.py`: bổ sung worker chạy `silero-vad` qua Python venv cho bản `.exe` (loại `torch`), đóng gói đủ `wedding_phrases.json`, `troly_ai.py` và 5 module phụ thuộc (`troly_thumbs/core/env/proc/src`), ghi log `stderr` của `AiJob` thay vì `DEVNULL`.
  - `troly_proc.py`, `troly_speech_run.py`, `troly_api.py`: thêm `kill_tree` + `huy_nhom("speech")` và kiểm tra `self.stop` ngay trong vòng quét `file_sig` & vòng 6 clip để bấm Dừng ngắt ngay worker (0 xác sống).
  - `index.html`, `app.js`: khóa nút `#loadBtn` khi bin đang đọc `(đang đọc bin...)` + kiểm tra `api().load`, thêm `<link rel="icon" href="data:,">` bỏ lỗi 404 `/favicon.ico`, đặt trần 40 ảnh cho cache `bigs`.

## 2026-11-21 – Tổng kiểm tra & Sửa lỗi Nhóm A/B/C + Nâng cấp giao diện Mục 5, CHỜ ANH THỬ
- **Sửa lỗi chức năng (Nhóm A):**
  - `player.js`: sửa lỗi bấm `Space` không dừng được video đang phát (do `plJkl("k")` tạm dừng trước khi `plToggle()` chạy); sửa `plNudge` và kéo mép `ioBar` trên nhiều khúc `Shift+I/O` lấy đúng khúc đang chọn (`plCurRange()`) thay vì ghi đè khúc đầu.
  - `troly_vision_io.py` & `troly_api.py`: đổi `troly_proc.run` -> `troly_proc.chay_an` để chạy VAD không crash `inout_suggest_start`; `big()` dùng `_effective_lut(c)` áp LUT theo tiền tố; `speech_set_inout` xóa `inouts` cũ khi về 1 khúc; không cho gợi ý Hình ảnh 3.5s đè kiểu quay `Truyền thống`.
  - `troly_dur.py`, `step5.js`, `step3.js`: bổ sung `stage_name` và `name` vào `items` của `dur_state()` và thêm `p3SelectUid(uid)` để xổ khúc clip Page 5 hiện đúng tên và bấm nhảy thẳng sang Bước 3.
  - `speech.js`, `app.js`, `multicam.js`, `troly_ai.py`: tách `pollWave` để Page 4 không tạo lại `<video>` liên tục khi sóng âm đang chờ; hiện nút `undoBtn1/2` khi có lịch sử chuyển; `mc-apply-sug` nạp lại `api().state()` đầy đủ; `AiJob.available()` nhận diện thêm SigLIP; chặn phím nền & hỗ trợ `Esc` đóng `#settingsModal`.
- **Đồng bộ giao diện & phím tắt (Nhóm B & C + Mục 5):**
  - Bổ sung `J-K-L`, `←/→` từng frame và `Delete` (xóa được cả khúc đơn) đồng nhất trên Page 2, 3, 4; gắn nhãn `nghi sai` (HALLU) cho câu Whisper ở Page 3; giữ vùng chọn nhiều clip khi hover lưới Page 2.
  - Sửa các chỗ sót `phím J` -> `phím P` và bỏ dòng ghi chú thừa Page 1; chuẩn hóa `style.css` & `index.html` theo bảng màu 3 lớp DaVinci (`Segoe UI`, `tabular-nums`, thanh đầu `52px`, sửa `--fg`, xóa selector trùng). Thêm phác thảo `design/framepilot_v2_demo.html`.

## 2026-11-21 – Nâng cấp 3 giai đoạn (In/Out Hình+Tiếng, Thao tác chuẩn DaVinci, SigLIP, Nhiều Camera Trang 2-3), CHỜ ANH THỬ
- **Cải tiến Page 5 (`5 · Thời lượng`) (`index.html`, `style.css`, `step5.js`):**
  - Thêm nút **`Vừa khung`** (phím tắt **`Shift + Z`** giống DaVinci) để phóng timeline vừa khít theo tổng độ dài clip đang có, tăng mức Zoom tối đa lên `2000%` và hỗ trợ `Alt / Shift + Lăn chuột` để cuộn ngang.
  - Thu gọn khoảng trống giữa vùng timeline trên và hai khung dưới (`.tl-bot`), căn hai cột dưới cao đều nhau.
  - Thêm nút mũi tên `▸` / `▾` ở bảng *Thứ tự trong cụm* để xổ xem chi tiết từng khúc clip In–Out bên trong mỗi bin con (bấm vào khúc clip sẽ nhảy thẳng sang Bước 3 để xem/chỉnh).
- **Nhiều khúc In/Out trên 1 clip (`Shift+I/O`), Sửa LUT Page 4 & Lọc câu Whisper bịa (`troly_core.py`, `troly_dur.py`, `troly_api.py`, `troly_speech.py`, `index.html`, `player.js`, `speech.js`):**
  - Thêm `v.crossOrigin = "anonymous"` cho thẻ `<video>` ở Page 4 (`#lnThumb`) để WebGL LUT đọc được khung hình từ máy chủ nội bộ (hết nhấp nháy rồi mất màu khi Play/tua).
  - Mở rộng `HALLU` trong `troly_speech.py` để tự đánh dấu vàng `có thể sai` thêm các câu YouTube hay bịa (*"cảm ơn các bạn đã xem video"*, *"hẹn gặp lại ở những video"*, *"bấm chuông"*, *"like/share"*, biến thể `subrisb`), kèm nút **`Ẩn câu sai`** trên Page 4.
  - Hỗ trợ đặt nhiều khúc In/Out trong cùng 1 clip bằng **`Shift + I` / `Shift + O`** (khúc đầu vẫn dùng `I` / `O`, bấm chọn từng khúc trên `#ioBar`, `Delete`/`Backspace` xóa khúc thừa). Không đụng Media Pool hay tạo Subclip; khi tạo **Timeline mới ở Bước 5**, toàn bộ các khúc được đưa lên timeline theo từng cặp `startFrame`/`endFrame` đã trim sẵn.
- **LUT xem trước theo tiền tố máy & Áp LUT WebGL cho Page 4 (`troly_env.py`, `troly_api.py`, `troly_thumbs.py`, `panel_troly_web.py`, `index.html`, `app.js`, `player.js`, `speech.js`):**
  - Thêm mục cấu hình **LUT theo tiền tố tên file** (ví dụ `C`, `DG`, `DJI_`) trong Setting bánh răng `⚙` (lưu vào `camera_luts` trong `config.json` để dùng chung cho các đám sau), tự gợi ý các tiền tố máy có trong project hiện tại và hỗ trợ hộp thoại chọn file `.cube`/`.3dl`.
  - Quy tắc ưu tiên: **Input LUT đã gắn trong DaVinci luôn thắng trước**; chỉ khi clip chưa có Input LUT trong DaVinci mới lấy LUT từ Setting theo tiền tố dài nhất khớp đầu tên file (chỉ đọc để xem trước, không ghi vào Media Pool).
  - Thêm nút **Làm mới thumbnail** trong Setting `⚙`: xóa cache thumbnail của **riêng project đang mở** và tạo lại theo LUT mới.
  - Bổ sung áp LUT bằng WebGL lên trình phát video của **Page 4 (`4 · Lời nói`)** (`#lnThumb`) đồng bộ với Page 2 & Page 3.
- **Tinh chỉnh Page 2, 3, 4 theo 4 ảnh phản hồi (`index.html`, `style.css`, `app.js`, `step3.js`, `speech.js`):**
  - Page 2 & Page 3: Cây bin dùng mũi tên `▾`/`▸` cho phép thu gọn/mở riêng từng bin mẹ tùy ý, đồng thời khi mở bin dưới thì các bin đã mở ở trên **không bị đóng lại** (không khóa cứng phải xổ hết toàn bộ).
  - Page 3: Trả bảng *Quy tắc gợi ý từng bin* về dạng bảng dọc thẳng hàng từ trên xuống (1 dòng 1 bin), và ẩn hộp *Kiểu quay (PSC / Truyền thống)* thừa vì đã chọn trong Setting.
  - Page 4: Thêm bộ lọc theo **Bin con** (`#lnSub`) và nút **`Chỉ clip sao ★`** (`#lnStarOnly`), xác nhận gắn sao `★`/`In-Out` từ Page 4 đồng bộ ngay sang Page 2 & 3; thêm trình phát video/thumbnail (`#lnPlayBtn` / `Space`) + **Sóng âm** (`#lnWaveCv`) ngay trên thanh In/Out, bấm câu chữ nhảy thẳng tới đoạn đó nghe kiểm tra.
- **Tổng rà soát & đồng bộ toàn bộ Page 1–5 theo 8 ảnh thật (`troly_env.py`, `troly_core.py`, `troly_api.py`, `index.html`, `style.css`, `app.js`, `ai.js`, `step3.js`, `speech.js`, `step5.js`):**
  - Page 1: ẩn dòng chú thích giờ quay mặc định, nâng nút `Lưu mẫu cho đám sau` to ngang `Tạo bin`, tích hợp tùy chọn đường dẫn lưu file mẫu (`templates.json`) trong cả modal Lưu mẫu và Setting bánh răng `⚙`.
  - Page 2 & 3: giữ nguyên toàn bộ các bin mẹ/con đang mở (không tự đóng nhóm trên khi chọn nhóm khác giống DaVinci), bỏ chú thích thừa của hộp AI / Page 3; sửa sạch các chỗ sót nhãn `(J)` -> `(P)` ở Bước 3 và Bước 4.
  - Page 3: phóng to khung video/thumbnail (`clamp(500px, 48vw, 760px)`), gom bảng quy tắc gợi ý thành thẻ ngang gọn, tinh gọn hàng nút dưới (ẩn nút `Nhận gợi ý (A)` và `Hoàn tác` vì đã có `Ctrl+Z`).
  - Page 4: thêm khung ảnh thumbnail `#lnThumb` bên trên thông tin file & lời nói cột phải.
  - Page 5: thêm thanh Zoom In/Out timeline (`100%–500%` + `Ctrl + Lăn chuột`) để phóng to xem rõ các bin con bên trong từng cụm bin mẹ.
- **Page 5 Timeline lớn & Đồng nhất (`index.html`, `style.css`, `step5.js`):** Tăng chiều cao timeline V2/V1/A1/A2 ở trên (`72/132/34/34 px`), đẩy bảng thứ tự cụm/bin xuống sát dưới, ẩn các dòng chú thích dài thừa (`.tl-lg`, `.tl-note`) và thêm phím `←`/`→` chuyển mượt giữa các cụm sự kiện.
- **Gom Cài đặt Project mới, Ctrl+Z hoàn tác & Dọn chú thích (`index.html`, `app.js`):** Gom lựa chọn kiểu sự kiện (1 dòng: *Lễ sáng + Tiệc tối* / *Chỉ tiệc*) và kiểu quay vào chung hộp Setting bánh răng `⚙`; đặt `Ctrl + Z` làm phím tắt hoàn tác mặc định cho toàn panel (ẩn nút chữ dài); lược bỏ các hộp/dòng chú thích nhỏ thừa thãi ở Page 1, 2, 3.
- **Page 1 Đồng bộ Bin con & Thu gọn Thông tin clip (`index.html`, `style.css`, `app.js`):** Hiển thị toàn bộ bin con thành từng hàng riêng (ô màu + tên + phím `1–9`) bên dưới mỗi giai đoạn (bin mẹ) đồng bộ với Page 2; khi sửa cho phép thêm/xóa từng hàng bin con thay vì gộp chung bằng dấu phẩy. Bỏ cột phải trống, thu gọn Thông tin clip thành thanh ngang sát dưới lưới `Source` gồm 6 mục cần thiết (`File`, `Giờ quay`, `Dài`, `FPS / TC`, `LUT`, `Máy / Mốc`).
- **Page 3 Bố cục 2 cột & 4 phím mũi tên (`index.html`, `style.css`, `app.js`, `player.js`):** Dời khối thông tin clip, bảng quy tắc từng bin và Tự phân loại In/Out từ cột phải xuống dưới sóng âm thành 3 cột ngang; mở rộng cột trái (`clamp(320px, 26vw, 440px)`) cho lưới Thumbnail 2–3 cột; đổi tên nút chuyển thành `List | Thumbnail` kèm icon giống DaVinci; bật 4 phím mũi tên (`↑`, `↓`, `←`, `→`) di chuyển giữa các source trong `#p3List` (bấm vào video/sóng âm thì `←`/`→` lại chỉnh từng frame).
- **Page 3 Thumbnail (`index.html`, `style.css`, `step3.js`):** Thêm nút chuyển `Chữ | Ảnh` ở cột trái Bước 3 để xem lưới 2 cột thumbnail nhỏ kèm chấm trạng thái In/Out; cho phép xuống dòng gọn ở `.p3-keys`, `.p3-txh` để không bị cắt chữ mép phải.
- **Không phụ thuộc proxy & Sửa lẹm chữ cột phải (`troly_api.py`, `player.js`, `style.css`):**
  - Bỏ `margin-top: -8px` ở `.player`, bật `flex-wrap` và co gọn thanh `.top` ở màn vừa để hết tràn viền/lẹm nửa chữ dưới khung xem trước.
  - Mở fallback chỉ-đọc sang file gốc `c.path` khi clip chưa tạo proxy cho toàn bộ 5 chỗ: Kho khung RAM (`frames_open` / rê chuột lướt hình Page 2), Sóng âm Bước 3 (`wave`), Phát video (`play_info`), Keyframe (`keyframes`) và Gợi ý In/Out Hình+Tiếng (`inout_suggest_start`). Proxy nay chỉ là yếu tố phụ trợ giúp nhẹ/mượt hơn.
- **Cài đặt Cache & SRT (`troly_env.py`, `troly_api.py`, `index.html`, `app.js`):** Thêm nút bánh răng `⚙` trên thanh trên cùng để tùy chọn thư mục chứa Cache (thumbnail, sóng âm, keyframe, khung RAM) và thư mục mặc định xuất/chứa file SRT cho toàn bộ panel (lưu vào `config.json`, chặn lưu nhầm vào thư mục git).
- **Giai đoạn 1 (`troly_vision_io.py`, `troly_core.py`, `troly_api.py`, `app.js`, `player.js`, `index.html`, `style.css`):**
  - Kiểm chứng 30 clip thật của LV_A: 88.5% bỏ >1s đầu (trung vị 1.42s), 63.3% đoạn giữ êm/nét hơn đoạn bỏ.
  - Tích hợp phân tích Hình ảnh (Laplacian Sharpness + Farneback Optical Flow) và Silero VAD vào `compute_sug` / `inout_suggest_start` (chỉ gợi ý, không ghi DaVinci).
  - Giao diện: thêm thanh Zoom thumbnail Page 1 & Page 2 (`Ctrl + Lăn chuột`), Live Hover Scrub không cần giữ chuột trái trên `waveBox`, `ioBar`, `#preview`, `#plSeek` và trực tiếp trên thumbnail lưới Page 2 (`#grid`, dừng nhẹ 120ms tự mở clip và lướt theo con trỏ), đặt `I`/`O` ngay tại vị trí con trỏ chuột ở Bước 2 & 3, trả lại cụm `J-K-L` tua, đổi phím gắn sao sang `P`, kéo quét vùng chọn nhiều clip.
- **Giai đoạn 2 (`troly_ai.py`):** Tải model `ViT-B-16-SigLIP` về `D:\VideoAI\data\models\siglip_vitb16` (cài `transformers`, `sentencepiece` vào venv AI `C:\VideoAI_ai_venv`), tách cache `troly_embed_siglip`, tự fallback OpenCLIP nếu thiếu. Đã thử nạp chạy trên GPU RTX 3060.
- **Giai đoạn 3 (`multicam.js`, `index.html`, `style.css`):** Bổ sung Trang 2 nhiều camera (lọc theo máy A–D, chế độ Làn ngang) và Trang 3 (khung "Các máy khác lúc này" + công tắc gợi ý theo giờ chung mặc định TẮT).
- Kiểm thử: 584 bài test đạt (`test_giai_doan_1_moi.py`, `test_giai_doan_2_va_3.py` và toàn bộ bộ test nền). Chưa mở kiểm tra trực tiếp trong cửa sổ pywebview thật với DaVinci thật.

## 2026-11-20 – Tool học từ 5 project cũ (tools/hoc_tu_cu.py), CHỜ ANH CHẠY
- Một lệnh, hỏi Y trước khi chạy. Chỉ đọc: xuất .drp bản gốc, nhập project tạm _hoc_tu_cu_*, đọc timeline+clip, lấy mẫu thưa bằng ffmpeg (âm thanh + khung nhỏ, không chạy model), phân tích ra số (In/Out, "sao" = clip có trên timeline chính, điểm chuyển, lệch đồng hồ giữa máy). Nhớ tiến độ, chạy lại là làm tiếp.
- Tên khách thật chỉ ở hoc_tu_cu.local.json (đã vào .gitignore); mã và báo cáo dùng LV_A..LV_E. Test: tests/test_hoc_tu_cu.py. Chưa chạy thật trên DaVinci và ổ đĩa của anh.

## 2026-11-19 – B7: Space ở Bước 2 phát/dừng clip, chưa có proxy thì báo rõ (CHỜ ANH THỬ, CHƯA commit)
- Gốc: phím Space đã được bắt (event.code) ở Bước 2 và 3, nhưng chưa có proxy thì plToggle thoát im lặng nên anh thấy "không phát". Nay Space báo lý do trên thanh trạng thái (chưa có proxy / proxy chưa mở xong / chưa chọn clip), chữ trong khung phải rút gọn "Chưa có proxy, chỉ xem hình tĩnh". Thêm chặn nhả Space (keyup) để nút đang focus như "Tự phân loại" không bị bấm lại. Chưa làm: phát từ file gốc khi không có proxy (máy chủ phát chỉ đọc trong proxy_root).
- Thử panel thật (cửa sổ pywebview, phím Space thật) trên bản sao dữ liệu: đúng thông báo. Test mới tests/test_space_buoc2.py. 577 bài test đạt. Ảnh chụp lần cuối không dùng được nên chưa có ảnh chữ rút gọn.

## 2026-11-19 – Lỗi "Tự phân loại AI ở Bước 2 xếp 0 clip" (đang ở nhánh main, CHƯA commit, CHỜ ANH THỬ)
- Nguyên nhân gốc: thư mục proxy của project (thư mục proxy_root/<project>) rỗng, nên AI chỉ nhúng được thumbnail "mồ côi" (khóa thumb:<mã>, không có tên clip); gợi ý lưu 1 mục "(không ghép được clip)" và không clip nào của kế hoạch khớp, Tự phân loại xếp 0 mà không báo vì sao. Không do thay đổi trang 1 (troly_ai.py và ai.js không đổi trong các commit trang 1). Đã tái hiện trên bản sao dữ liệu project 2026.10.25.PHK_Baoluan&KimNga (nhóm 115 clip) bằng DaVinci thật (chỉ đọc).
- Sửa: troly_ai.is_orphan_key, TrolyApi._ai_nomatch; ai_info có thêm trường no_match; ai_auto_apply/ai_auto_run trả lỗi nói rõ lý do và không ghi nhãn; ai.js hiện lý do trong hộp Gợi ý AI và trên thanh trạng thái. Test mới tests/test_troly_ai_khong_ghep.py. 574 bài test đạt.
- Theo ý anh 19/11: BỎ ràng buộc proxy. Panel ghi clips.json (danh sách clip + thumbnail của panel, làm từ proxy hoặc file gốc) vào thư mục embed trước khi chạy AI; troly_ai.match_thumbs dùng nó nếu có, không còn lệ thuộc thư mục proxy (troly_ai.write_manifest/load_manifest, TrolyApi.ai_run). Thử trên bản sao dữ liệu + DaVinci thật, proxy rỗng: 400/400 clip có vector, Tự phân loại xếp 73 clip nhóm 01 (ngưỡng 50%). Còn 41 clip nhóm đó không có gợi ý vì điểm theo mô tả của các bin trong giai đoạn bằng 0 (ảnh giống bin của giai đoạn khác); chưa sửa, báo anh quyết. Chưa chụp cửa sổ panel thật.

## 2026-11-19 – Bước 1 chọn mốc giai đoạn bằng thumbnail (nhánh nhieu-camera-giao-dien, CHƯA gộp main, ADR-0033)
- Giao diện Bước 1 theo demo design/trang1_chon_moc: danh sách giai đoạn có mốc đầu/cuối, timeline thấp, cây Media bin, lưới thumbnail, thông tin clip; phím F1…F9 (đầu) và Shift+F (cuối) đọc bằng event.code; chặn mốc sai thứ tự; nhiều máy liền nhau, 1 máy có khoảng trống; tối đa 9 giai đoạn.
- Thêm TrolyApi.set_mark, tools/panel_probe.py (thử panel pywebview thật trên bản sao dữ liệu), biến môi trường TROLY_CONFIG, tools/harness_cam.py --tl. Test mới ở tests/test_nguon_timeline.py. Phần 2 (exe) chưa làm.

## 2026-11-19 – Nhiều camera, trang 1 làm lại theo timeline đã sync (nhánh nhieu-camera-giao-dien, CHƯA gộp main, tag sao lưu truoc-nhieu-camera-ui)
- Trang 1 đọc timeline DaVinci (chỉ đọc): máy = track video, tên theo tiền tố tên file, trục từ đầu timeline, hàng giai đoạn kéo được, con trỏ đỏ, cắt giai đoạn tại con trỏ, bám mép clip, bin mẹ (nhóm trong panel), mẫu "Chỉ tiệc nhà hàng", công tắt máy quay dọc. ADR-0032 (ADR-0031 đã bị thay thế).
- Thêm app/troly_src.py, worker tl_list/tl_read, TrolyApi add_event/rename_event/cut_stage/set_vertical, tools/harness_cam.py (--real). Bỏ troly_cams.py, cam.js, cam.css. 556 bài test đạt. Thử trên DaVinci thật project 2026.11.14, chưa ghi marker.

## 2026-11-19 – Bước 2: phím giai đoạn đổi sang F1–F12 (nhánh doi-phim-giai-doan-f, CHƯA gộp main, tag sao lưu truoc-doi-phim-f)
- F1–F12 chọn giai đoạn rồi chờ số bin con; Shift+số hết là phím giai đoạn. Đọc event.code, chặn mặc định F1/F5/F11/F12, cảnh báo trên giao diện khi quá 12 giai đoạn. ADR-0030.
- Cập nhật nhãn (Media Pool, dòng nhắc phím, menu chuột phải), TRANG_THAI, ADR-0009. 533 bài test đạt (thêm 7). Chưa thử trên panel thật.

## 2026-11-19 – Sửa lỗi đồng bộ đệm p3Pad và giữ DOM preview trong showImg (nhánh sua-loi-p3pad-showimg)
- Sửa lỗi Bước 3: `p3Pad` đồng bộ giá trị đệm đã lưu từ kế hoạch lên ô nhập trên giao diện (`tests/test_sua_loi_p3pad.py`).
- Sửa lỗi preview: `showImg` không còn gán `preview.innerHTML = ...` làm tháo thẻ video và xóa mất `canvas.pv-frame` (kho khung RAM), mà cập nhật thẻ `img` tại chỗ (`tests/test_sua_loi_showimg.py`).
- 526 bài test đạt (thêm 2 bài test).


## 2026-11-19 – Kiểm tài nguyên trên git + dọn rác (nhánh kiem-git-19-11, ĐÃ GỘP main: commit gộp 26d0fa9, tag sao lưu truoc-gop-kiem-git-19-11 = f8be717)
- Clone từ GitHub vào thư mục tạm: 520 test đạt, install.py cài thử vào APPDATA tạm đạt; panel mở bằng DaVinci giả từ bản clone (có config.json chép từ mẫu) chạy được: gõ "+ Bin mới", proxy HEVC báo rõ, mở lần hai đưa cửa sổ cũ lên trước. Thiếu config.json thì panel báo "Không đọc được config.json (data_root)".
- THIẾU và đã thêm: config.example.json (mẫu cấu hình, không nhạy cảm), requirements_speech.txt (numpy, silero-vad cho Bước 4), ghim phiên bản requirements.txt (pywebview 6.2.1, Pillow 12.3.0). docs/BAN_GIAO.md mục 2b: bảng tài nguyên (trên git / ngoài git có chủ ý và cách lấy), các bước cài máy mới.
- Bỏ tên khách thật khỏi test S3. Sửa ký tự tab/xóa lùi chen vào đường dẫn Windows trong BAN_GIAO, RA_SOAT, CHANGELOG, TRANG_THAI, ADR-0016. Thêm tests/test_repo_tai_nguyen.py (524 bài test).
- Dọn: xóa __pycache__ và thư mục tạm của lần kiểm; không có nhánh nào đã gộp còn lại; không file nào trong git bị xóa (mọi file đều còn được tham chiếu, chỉ docs/QUY_TRINH_DONG_BO.md không ai tham chiếu, chờ người dùng quyết).

## 2026-11-19 – GỘP ra-soat-19-11 vào main (commit gộp e08fff5, tag sao lưu truoc-gop-ra-soat-19-11 trên main cũ 67bfa7d)
- main giờ chứa tổng duyệt 19/11 (11 lỗi sửa) và S1-S6 theo quyết định của người dùng (bỏ bản xem nhẹ, tên bin dùng chung một hàm không chặn &, mở lần hai đưa cửa sổ cũ lên trước, 3 lỗi nhẹ). 21 commit, không xung đột. 520 bài test đạt trên main.

## 2026-11-19 (sau tổng duyệt) – Quyết định của người dùng 09:03/09:05 (nhánh ra-soat-19-11) - CHỜ ANH THỬ
- S1: BỎ HẲN "bản xem nhẹ" (mp4 720p trong cache). Xóa mã tạo bản đó, nhánh giao diện và 2 test cũ (TranscodeCmd, PlayerFallback). Proxy không phát được thì chỉ báo rõ (clip nào, vì sao, nên tạo lại proxy H.264 trong DaVinci), không tạo file. Thư mục cache cũ cache\troly_play không bị xóa. ADR-0029.
- S2: "+ Bin mới" và Đổi tên bin dùng chung một hàm kiểm tên. BỎ `&` khỏi bộ ký tự chặn của cả hai chỗ (trước đây Đổi tên bin chặn `&`). Chặn `: / \ * ? " < > |`, ký tự điều khiển, tên kết thúc bằng dấu chấm.
- S3: mở FramePilot lần hai cho cùng project thì đưa cửa sổ cũ lên trước (khôi phục nếu thu nhỏ). CHƯA CHẠY THẬT qua menu DaVinci.
- S4: hai lần kế hoạch hỏng cùng giây không ghi đè .corrupt; trình phát không mượn độ dài clip trước ("chưa rõ độ dài"); Hoàn tác lỗi một phần cập nhật vị trí bin ngay.
- S5: không làm theo ý người dùng (khóa clip trùng, cắt chữ 1100x680, e.key Esc/Enter), ghi vào docs/BAN_GIAO.md mục 8.
- 520 bài test đạt (506 − 2 test bản xem nhẹ + 16 bài mới), chạy 3 lần không chập chờn.

## 2026-11-19 – Tổng duyệt toàn bộ panel (nhánh ra-soat-19-11) - CHỜ ANH THỬ
- Sửa 11 lỗi, mỗi lỗi một commit kèm test trong tests/test_ra_soat_19_11.py (báo cáo đầy đủ: docs/RA_SOAT_19_11.md):
  - Đọc bin nguồn khác rồi quay lại không còn mất giai đoạn đã kéo/đổi tên (giữ theo từng bin, plan["stages_by_bin"]).
  - Mỗi project chỉ một cửa sổ FramePilot (khóa file <data_root>\troly\locks, tự nhả khi đóng); trước đây hai cửa sổ ghi đè nhãn của nhau.
  - Tạo timeline (sao, Bước 5) chỉ AppendToTimeline khi chắc timeline hiện tại là timeline MỚI.
  - Hai clip trùng khóa đường dẫn tương đối: cảnh báo khi đọc, không ghi In/Out vào DaVinci cho các clip đó.
  - Hoàn tác In/Out không lấy nhầm sao lưu của project cùng tiền tố tên; không đánh dấu "đã khôi phục" khi còn clip bị bỏ qua.
  - Hoàn tác lần chuyển của bin khác: báo rõ thay vì im lặng.
  - Kho lời nói SQLite có khóa khi đọc/ghi (luồng chép lời + giao diện dùng chung kết nối: lỗi "cannot commit").
  - ffmpeg trích âm và Whisper có giới hạn thời gian (file hỏng không treo cả lượt).
  - Đọc lại bin sau Áp dụng/Hoàn tác không in đè câu "Đã kết nối" lên cảnh báo.
  - Bước 5 ở cửa sổ 1100 px: bảng khối không đè sang thẻ bên cạnh.
  - .gitignore chặn video/âm thanh/kho dữ liệu.
- Thêm docs/BAN_GIAO.md (bàn giao cho project mới). 506 bài test đạt, chạy 3 lần không chập chờn. Đo lướt bằng main (57,9 / 58,9 hình/giây), RAM 50 clip 21 → 39 MB, 0 ffmpeg mồ côi.

## 2026-11-19 – GỘP vào main (commit gộp 10d4d18, tag sao lưu truoc-gop-19-11 trên đầu nhánh sua-lag-luot-2 = b8fc195)
- main giờ chứa: Bước 5 bản 3 timeline kéo thả (ADR-0013, đã gộp từ trước), Tự phân loại Bước 2/3 (ADR-0026), sửa lag lướt + kho khung nhỏ trong RAM + nút Đo lướt (ADR-0016 bản 1 và 2), đổi tên FramePilot + icon (ADR-0027), xưng hô "bạn" (ADR-0028), K3 (tiến trình con chạy ẩn). 493 bài test đạt trên main. Không xung đột, không xóa nhánh nào.

## 2026-11-19 – K3: hết cửa sổ cmd chớp khi mở clip (ADR-0016 bản 2)
- Thủ phạm theo mã: nạp sóng âm (ffmpeg thiếu cờ ẩn console); bản xem nhẹ ffmpeg cũng thiếu. Thêm app/troly_proc.py (chay_an / mo_an: CREATE_NO_WINDOW + SW_HIDE), mọi lời gọi tiến trình con đi qua đó; test quét không còn lời gọi subprocess ngoài file này. 493 bài đạt. Chưa kiểm bằng mắt.

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
