# ADR-0016: Trình phát proxy, đặt In/Out tay và ghi In/Out vào Media Pool

Ngày: 17-18/11/2026. Trạng thái: đã code, CHỜ NGƯỜI DỰNG THỬ.

## Bối cảnh
Bước 2 chỉ có thumbnail tĩnh. Người dựng cần xem clip chạy thật, đặt In/Out ngay lúc lọc source, rồi ghi vào Media Pool để
chỉnh tiếp bằng tay trong DaVinci.

## Quyết định
1. **Trình phát**: thẻ `<video>` của WebView2 phát file proxy qua máy chủ cục bộ `app/troly_play.py`.
   - Chỉ nghe `127.0.0.1`, cổng ngẫu nhiên, hỗ trợ Range (lướt). Mỗi clip một "vé" token ngẫu nhiên -> đường dẫn.
   - Chỉ phát đường dẫn nằm trong `proxy_root` (config.json, KHÔNG ghi cứng trong mã) hoặc thư mục cache `troly_play`.
     Chuẩn hóa + giải liên kết (symlink) trước khi so; kiểm lại lúc phát. Đường dẫn ngoài -> 403/None (có test).
   - Chỉ mở file để ĐỌC; không ghi/đổi tên/xóa trong thư mục proxy.
   - Phương án dự phòng: nếu thẻ video báo lỗi (ProRes/DNx...), `play_info(uid, transcode=True)` gọi ffmpeg tạo mp4 H.264 720p
     nhẹ (keyframe mỗi 12 frame) trong `<data_root>\cache\troly_play\<project>\` (xóa được), chỉ cho clip đang xem.
   - Clip không có proxy: hiện "Chưa có proxy - chỉ xem hình tĩnh", giữ thumbnail.
   - Phím: Space phát/dừng, I / O đặt điểm vào/ra tại vị trí đang xem, mũi tên chỉnh từng frame (Shift = 10) khi con trỏ đang ở
     cột phải. Đọc bằng `event.code`, bỏ qua khi đang gõ ô chữ.
2. **In/Out đặt tay**: lưu trong kế hoạch panel `plan["inout"][đường dẫn tương đối] = [in_s, out_s]` (giây từ đầu file; cùng chỗ
   với nút "Đặt In/Out" của tab Lời nói). **Đặt tay luôn thắng**: hiệu lực = đặt tay > In/Out đang có trong DaVinci > (chỉ hiển
   thị) gợi ý tự động. Gợi ý tự động KHÔNG bao giờ được ghi vào DaVinci. Màu: cam = đã đặt trong DaVinci, cam vằn = đặt tay chưa ghi,
   xanh = gợi ý.
3. **Ghi vào DaVinci** (chỉ khi bấm nút + hộp xác nhận nói rõ số clip; chỉ cho clip có sao hoặc clip đang chọn):
   đọc In/Out cũ -> ghi file sao lưu `<data_root>\troly\inout_backup\<project>_<ngày giờ>.json` (không ghi đè; lỗi ghi thì DỪNG, chưa
   đụng DaVinci) -> `SetMarkInOut(frame_in, frame_out, "all")` từng clip -> đọc lại `GetMarkInOut` đối chiếu. Báo khớp/lỗi/lệch theo
   từng clip, không báo thành công giả. **Hoàn tác** khôi phục đúng bản sao lưu gần nhất (trước đó trống thì `ClearMarkInOut`).
   Chỉ gọi SetMarkInOut/ClearMarkInOut: không xóa clip, không sửa timeline, không đụng file, không render.

## Kết quả đo thật trên DaVinci Resolve Studio 21.1.1.10 (đo 17/11/2026, project thử LV_Ten, clip DG7320, 50 fps, Start TC 00:42:38:24)
- `SetMarkInOut(10, 100, "all")` -> trả `True`; `GetMarkInOut()` -> `{video:{in:10,out:100}, audio:{in:10,out:100}}`.
  => **nhận SỐ FRAME tính từ ĐẦU FILE** (frame 0 = frame đầu clip), KHÔNG cộng Start TC (Start TC quy ra 127 924 frame; nếu cộng thì
  đã đọc lại khác đi).
- `SetMarkInOut("00:42:38:34", "00:42:43:24", "all")` (chuỗi timecode) -> trả `False`, không đổi gì. => phải dùng frame nguyên.
- `SetMarkInOut(127010, 127100)` (vượt 240 frame của clip) -> trả `True` và đọc lại đúng 127010/127100: **DaVinci KHÔNG kiểm vượt
  độ dài**, nên panel tự kẹp trong [0, frames-1] trước khi ghi.
- `ClearMarkInOut("all")` đưa về `{video:{}, audio:{}}` (trạng thái ban đầu của clip). Đo xong đã xóa về đúng trạng thái đầu,
  đối chiếu với bản dump (376 clip trong project thử đều chưa có In/Out; chỉ chạm 1 clip).
- Chuyển đổi hiển thị: timecode file = Start TC + frame (hàm `file_frame_to_tc`); frame ghi = timecode - Start TC (`tc_to_file_frame`).
  Panel lưu giây, ghi `round(giây × fps)`.
- Không bất ngờ so với cách tính đang dùng khi ĐỌC (`mark_in / fps`), nên không phải đổi cách tính.

## Kết quả đo proxy thật (18/11/2026, WebView2 = Edge 157, cùng động cơ với panel; CHỈ ĐỌC, không ghi vào F:\02_Proxy Media)
Lấy 5 file proxy ở 5 project khác nhau (ffprobe + cửa sổ WebView2 thử dùng đúng `troly_play.PlayServer`, tự đóng):

| Mẫu | Container | Hình | Kích thước, fps | Âm thanh | Phát trong WebView2 |
|---|---|---|---|---|---|
| 1, 3, 4 | MOV | H.264 High (avc1), ~42 Mbps | 1920x1080, 50 | PCM s16le 48 kHz stereo | ĐƯỢC, có hình + tiếng; ~124 khung / 2,4 s, 0 khung rớt; mở 16-30 ms; lướt 20-165 ms |
| 5 | MOV | H.264 High, ~41 Mbps | 1920x1080, 59,94 | PCM s16le | ĐƯỢC; 149 khung, 0 rớt; lướt 23-142 ms |
| 2 | MOV | **HEVC Main (hvc1)**, ~18,5 Mbps | 1920x1080, 50 | PCM s16le | **KHÔNG có hình**: `canPlayType` HEVC rỗng, `videoWidth` = 0, 0 khung; chỉ có tiếng; **không báo lỗi** |

- Proxy là `.mov`, thuần H.264 + PCM trong 4/5 mẫu (mẫu nhỏ, chưa đo hết ~3000 file). Không có ProRes/DNx trong 5 mẫu.
- **Lỗi tìm ra 1:** trình phát chỉ chuyển sang bản xem nhẹ khi có sự kiện `error`, nhưng proxy HEVC không báo lỗi (chỉ ra tiếng, hình đen).
  Đã sửa: ngay khi `loadedmetadata` mà `videoWidth` = 0 thì tự chuyển sang bản xem nhẹ (có bài kiểm thử tĩnh).
- **Lỗi tìm ra 2:** bản xem nhẹ ffmpeg KHÔNG BAO GIỜ tạo được: file tạm đuôi `.part` làm ffmpeg không chọn được định dạng, lệnh lỗi ngay
  và `ensure_play_mp4` trả `None`. Đã sửa: thêm `-f mp4`; đổi `-an` thành AAC 96 kbps để vẫn nghe tiếng khi duyệt.
- Bản xem nhẹ chạy thật trên mẫu HEVC (clip 1,9 s): 0,4 giây tạo, 0,39 MB (gốc 4,45 MB), H.264 720p + AAC; WebView2 phát được: 96 khung,
  0 rớt, lướt 3-11 ms. Clip dài chưa đo thời gian tạo.
- Âm thanh PCM trong MOV phát được trong WebView2 (đã giải mã, có byte âm thanh).
- **Chưa đo:** bấm phát trong CỬA SỔ PANEL thật (chỉ đo bằng cửa sổ WebView2 thử, cùng động cơ và cùng máy chủ phát); độ dài proxy so với bản
  gốc; clip dài nhiều phút; lướt nhiều clip liên tiếp.
- Người dựng thử xong trong panel thật thì ghi thêm kết quả vào đây.

## Hệ quả
- config.json cần thêm `"proxy_root": "F:\\02_Proxy Media"` (không đưa lên Git).
- Quy tắc ghi In/Out đã thêm vào CLAUDE.md. Ghi hàng loạt CHỈ do người dựng bấm nút.


## Đêm 18/11/2026: sửa lag khi lướt (nhánh sua-lag-luot) - CHỜ NGƯỜI DỰNG THỬ trong panel thật
**Phát hiện khi đọc mã:** E2 (một lệnh nhảy đang chạy, đợi `seeked`), E3 (kéo thì nhảy theo keyframe, thả thì chính xác, keyframe đọc MỘT lần bằng ffprobe rồi cache), E4 phần "dùng lại MỘT thẻ video" và E7 (màu Log bằng WebGL, file .cube đưa qua API) đã làm sẵn từ ADR-0023. Không làm lại; chỉ đo xem chúng có thật sự hết giật không, rồi bổ sung chỗ còn thiếu.

**Bổ sung:**
- Nút **Đo lướt** (E1, chỉ hiện khi panel chạy `--debug`, hàm `plMeasure()` gọi được từ F12): mô phỏng KÉO từ đầu tới cuối clip, 3 giây, 60 sự kiện/giây, ở 3 cách: `cu` (mỗi sự kiện gán thẳng `currentTime`, đúng như cách trước khi sửa), `keyframe` (cách hiện tại: hàng đợi một lệnh + nhảy keyframe, thả thì chính xác), `chinhxac` (hàng đợi một lệnh nhưng luôn nhảy chính xác). Đo số hình thật sự hiện ra (mỗi `seeked` là một hình), độ trễ mỗi lần nhảy, lần đứng hình lâu nhất, số khung rớt (`getVideoPlaybackQuality`), thời gian chờ hình chính xác sau khi thả. Chỉ đọc; số đo lưu ra `<data_root>	roly\debug\do_luot_*.json` (API `debug_save`, chỉ khi `--debug`, tên file chỉ chữ/số/_-).
- **Dừng tay giữa lúc kéo** (E6): kéo mà ngừng khoảng 0,22 giây (chưa thả chuột) thì nhảy CHÍNH XÁC tới hình đó thay vì kẹt ở keyframe phía trước (tới 1 giây); có lệnh mới thì hủy hẹn giờ.
- **Tải trước clip kế** (E4): một thẻ video ẩn `preload="metadata"`, tắt tiếng, chỉ nạp phần đầu và chỉ mục của clip kế tiếp. Chỉ đọc proxy qua máy chủ phát.

**Số đo (E1/E6), đo ngày 18/11/2026 trên proxy thật DG7500.mov của một project quay (H.264 High 1920x1080 50 hình/giây, 83,5 giây, 84 keyframe), máy RTX 3060, hai lượt giống nhau:**

| Cách | hình hiện ra/giây khi kéo | đứng hình lâu nhất | đứng hình trung bình | khung rớt | chờ hình chính xác sau thả |
|---|---|---|---|---|---|
| `cu` (cách cũ) | 2,2 - 2,9 | 0,72 - 1,20 giây | 393 - 523 ms | 0 | 157 - 169 ms |
| `keyframe` (hiện tại) | 27,2 - 27,3 | 55 ms | 37 ms | 0 | 146 - 153 ms |
| `chinhxac` | 17,4 - 19,0 | 151 - 154 ms | 54 - 59 ms | 0 | 191 - 192 ms |

Kết luận: cách cũ chỉ ra khoảng 2-3 hình mỗi giây và đứng hình tới hơn 1 giây (đúng cảm giác giật); cách hiện tại (hàng đợi + keyframe) ra khoảng 27 hình mỗi giây (gần như mọi keyframe), đứng tối đa 55 ms. Mở clip mới mất khoảng 25-55 ms với hoặc không tải trước (mẫu quá ít để thấy khác biệt; tải trước không gây hại và không có lợi đo được).
E5: WebGL báo NVIDIA GeForce RTX 3060 (Direct3D11); `mediaCapabilities` báo H.264 1080p50 40 Mbps `supported/smooth/powerEfficient = true` (thường nghĩa là giải mã bằng phần cứng). Không ép gì thêm.

**CHƯA ĐO THẬT trong panel pywebview (WebView2):** các số trên đo bằng trình duyệt Chromium trong ứng dụng Claude (cùng máy, cùng máy chủ phát proxy 127.0.0.1, API và proxy thật), không phải cửa sổ pywebview. Cần bấm Đo lướt (panel chạy `--debug`) trong panel thật và so lại. Cũng chưa kéo bằng chuột thật; sự kiện kéo là giả. Chưa đo clip bị hai card đồ họa chọn khác card.


## ADR-0016 bản 2 (19/11/2026): rê chuột vẫn lag trong panel thật, kho khung nhỏ trong RAM (nhánh sua-lag-luot-2) - CHỜ NGƯỜI DỰNG THỬ bằng chuột thật

**Vì sao làm bản 2:** số đo đêm 18/11 (27 hình/giây) đo bằng Chromium, không phải panel pywebview; người dựng thấy lag còn tệ hơn trước khi sửa. Lần này đo ĐÚNG trong cửa sổ pywebview thật (WebView2, Edge 157, RTX 3060).

**Cách đo (tools/panel_do_luot.py + tools/measure_seek.js):** mở đúng giao diện và TrolyApi của panel trong cửa sổ pywebview, nhưng với DaVinci GIẢ (dữ liệu giả LV_Ten, dữ liệu tạm), mỗi clip trỏ tới một proxy THẬT trong proxy_root (chỉ đọc, không tạo file proxy nào). Mô phỏng rê bằng sự kiện giả 60 lần/giây, 3 giây, từ đầu tới cuối clip, ở 3 chỗ: thanh lướt video, sóng âm, kéo mép In của thanh In/Out. Đo thời gian xử lý mỗi sự kiện, số lần gọi Python và fetch, longtask, số hình thật sự hiện ra, độ trễ từ sự kiện tới hình kế tiếp, lần đứng hình lâu nhất, khung rớt. Clip đo: proxy H.264 High 1920x1080 50p, có gán LUT Blackmagic 4.6K Film to Rec709 v3. File kết quả thô: docs/do_luot/.

### F1/F2: đo trong pywebview thật, lỗi nằm ở đâu
| (bản 63cf429, chưa sửa lần này) | hình/giây khi rê | trễ tới hình (p50 / p95 / lớn nhất) | đứng hình lâu nhất |
|---|---|---|---|
| thanh lướt video | 5,8 | 917 / 2290 / 2440 ms | 2450 ms |
| sóng âm (bấm liên tiếp) | 2,6 - 3,9 | 37-56 / 82-120 / 99-137 ms | 100-150 ms |
| kéo mép In/Out | 1,6 | 1400 / 2840 / 3000 ms | 3000 ms |
Số Chromium đêm 18/11 (27 hình/giây, đứng tối đa 55 ms) KHÔNG phản ánh panel thật.
- **Không phải JavaScript hay Python:** xử lý mỗi sự kiện rê trung bình 0,14-0,8 ms (p95 ≤ 1,3 ms); trong lúc rê gọi Python 0 lần (chỉ 1 lần `set_inout` khi thả mép In), fetch 0 lần; không có longtask đáng kể (một lần 81-94 ms lúc bắt đầu). F3 và F4 (gộp bằng requestAnimationFrame, tách lớp vẽ sóng âm) vì thế KHÔNG cần: F2 không chỉ ra chỗ đó. Sóng âm chỉ vẽ lại khi đổi clip hoặc đổi vùng In/Out, không vẽ lại khi rê.
- **Nghẽn ở giải mã GPU khi nhảy:** lấy mẫu `\GPU Engine` của tiến trình msedgewebview2 (H3) trong lúc rê bằng cách cũ: engine **Video Decode đạt 99,7%** theo từng đợt, 3D tối đa 9,2%, Copy tối đa 1,5%. Khớp với người dùng thấy GPU 57-60%: mỗi lần nhảy thẻ video bắt giải mã phần cứng lại từ keyframe (GOP 50 hình ở 40 Mbps).

### G1 (A/B) và H1, H2, H4: thử từng nghi phạm trong pywebview thật
| Bản | thanh lướt hình/giây | trễ p50 (thanh lướt) | sóng âm trễ p50 |
|---|---|---|---|
| trước sua-lag-luot (2e56563) | 0 - 5,8 | 917 - 1567 ms | 43 ms |
| hiện tại 63cf429 (chưa RAM) | 5,8 | 917 ms | **1133 ms** |
| hiện tại, tắt nhảy chính xác sau 0,22 s (nodwell) | 5,8 | 917 ms | 20 ms |
| hiện tại, tắt tải trước clip kế (preoff) | 5,8 | 917 ms | 1133 ms |
| hiện tại, tắt lớp WebGL LUT (H1: lutoff) | 5,8 | 917 ms | 1133 ms |
- Bản hiện tại KHÔNG tệ hơn bản trước ở thanh lướt (hai bản giống nhau); **tệ hơn ở sóng âm**: hẹn giờ "dừng tay thì nhảy chính xác sau 0,22 s" (nghi phạm (a)) chen thêm một lần nhảy vào dãy rê: p50 từ 20 ms lên 1133 ms. Tải trước clip kế (nghi phạm (b)) và lớp WebGL LUT (nghi phạm (c)) KHÔNG đổi số nào: không phải thủ phạm. Dù vậy đã GỠ tải trước clip kế (bộ giải mã thứ hai, không có lợi đo được, thay bằng nạp trước vào RAM ở dưới).
- H2: WebGL báo NVIDIA GeForce RTX 3060 (Direct3D11) trong pywebview thật, `mediaCapabilities` báo H.264 1080p50 40 Mbps supported/smooth/powerEfficient. Thử cờ WebView2: `--ignore-gpu-blocklist --enable-zero-copy`, `--disable-features=CalculateNativeWinOcclusion`, `--disable-accelerated-video-decode` (giải mã bằng CPU): thanh lướt vẫn 3,8-5,8 hình/giây, trễ p50 917-950 ms. KHÔNG cờ nào có hiệu quả, KHÔNG giữ cờ nào.
- H4: canvas/thẻ video trong khung xem không có backdrop-filter, blur hay box-shadow lớn đè lên (có test); canvas khung mới cũng không dùng.

### G2-G5: kho khung nhỏ trong RAM (đã làm)
- `app/troly_frames.py` (FrameStore) + `TrolyApi.frames_open/frames_stats` + đường `/f/<vé>/<n>` trên máy chủ phát cục bộ. Mở clip: MỘT tiến trình ffmpeg ưu tiên thấp (CPU, không dùng GPU nên không tranh NVDEC với trình phát) đọc proxy (chỉ ĐỌC) ra khung cạnh dài 640 px, mỗi 2 hình một khung (25 khung/giây với proxy 50p; clip dài hơn 120 giây thì 12,5), nén JPEG (q 6), GIỮ TRONG RAM. Không ghi file ra đĩa, không tạo proxy hay bản nhẹ (có test: lệnh ffmpeg ra stdout `-`, mã không có ghi file). Áp LUT của clip ngay lúc giải mã (cùng `lut3d` như thumbnail). Tiến dần từ đầu, giao diện hiện "Đang nạp khung xem nhanh x%".
- G4: tối đa 8 clip (LRU) và tổng 300 MB (hằng số MAX_CLIPS, MAX_BYTES), một clip không chiếm quá nửa kho; chỉ MỘT việc giải mã chạy một lúc; đổi clip thì hủy ngay việc cũ (và làm tiếp từ chỗ đã có khi quay lại); rảnh (không rê, clip hiện tại đã nạp xong) thì nạp trước tối đa 3 clip (clip kế và các clip cùng giờ của máy quay khác) (`frames_open(prefetch=True)`, bị bỏ qua nếu đang bận).
- G3: rê chuột (thanh lướt, kéo mép In/Out, bấm và rê trên sóng âm/thanh In/Out) vẽ khung từ RAM lên canvas NGAY (không đụng thẻ video, không gọi Python); khung chưa nạp tới thì hiện khung gần nhất đã có; gộp mousemove theo requestAnimationFrame. Thả chuột hoặc dừng ~0,25 s: thẻ video nhảy CHÍNH XÁC tới hình đó, rồi canvas ẩn. Chưa có kho khung hoặc lỗi: tự về cách cũ (nhảy keyframe).
- G5: lấy khung bằng `fetch` cục bộ + `createImageBitmap` (không qua cầu pywebview), giữ tối đa 160 ImageBitmap trong JS; khung đầu được nạp sẵn lúc khởi động. Chọn cách này vì mỗi khung 20-30 KB, đo mỗi lần lấy và vẽ vài mili giây; chưa cần gói nhiều khung mỗi lần.

### G6: số đo SAU trong pywebview thật (cùng clip, cùng cách rê, 3-5 lần chạy giống nhau)
| | hình/giây khi rê | trễ tới hình p50 / p95 | trễ lớn nhất | đứng hình lâu nhất |
|---|---|---|---|---|
| thanh lướt video: TRƯỚC | 5,8 | 917 / 2290 ms | 2440 ms | 2450 ms |
| thanh lướt video: SAU | **58-60** | **0,2-0,5 / 4,5-7,9 ms** | 50-112 ms | 19-26 ms |
| sóng âm bấm-rê: TRƯỚC (bản hiện tại) | 4,6 | 1133 / 2483 ms | 2636 ms | 100 ms |
| sóng âm bấm-rê: SAU | **58-60** | **0,1-0,2 / 4,6-7,6 ms** | 6-39 ms | 20-31 ms |
| kéo mép In: TRƯỚC | 1,6 | 1400 / 2840 ms | 3000 ms | 3000 ms |
| kéo mép In: SAU | (số hình đếm bị nhân đôi do móc đo, bỏ qua) | **0,5-0,6 / 1,1-3,5 ms** | 60-76 ms | 18-22 ms |
- Thời gian nạp: clip 17,8 giây 1,9 giây (444 khung, 11 MB); clip 83,5 giây (proxy 433 MB) 6,8 giây (2088 khung, 35 MB) khi đo riêng bằng Python. RAM: 35 MB cho clip 83 giây; kho giới hạn 300 MB.
- Thời gian chờ hình CHÍNH XÁC sau khi thả chuột: 70-350 ms (video vẫn nhảy một lần, nhưng canvas giữ hình đúng tới lúc đó nên không thấy giật).
- Màu (G3): khung RAM so với khung video chính xác ở cùng thời điểm (canvas LUT WebGL): lệch trung bình khoảng 2,8/255 ở 4 trong 5 điểm; một điểm lệch 14,5 chưa giải thích được (nghi khung video chưa kịp cập nhật lúc đo, không phải sai màu). Đối chiếu căn thời gian riêng: khung RAM chỉ số k khớp nhất với khung video ở giây k/25 (lệch 0 khung). So bằng mắt: CHƯA.

**MỤC TIÊU "rê chuột hiện hình dưới khoảng 30 ms": ĐẠT MỘT PHẦN.** Trung vị 0,1-0,5 ms và p95 dưới 8 ms ở cả ba kiểu rê, không đứng hình quá 31 ms, hình/giây ngang tốc độ màn hình (58-60). CHƯA ĐẠT ở trường hợp xấu nhất: 1-2 trong 180 sự kiện mỗi lần chạy (sự kiện đầu tiên của lúc bắt đầu rê) trễ 50-112 ms; chưa tìm ra nguyên nhân (đã thử khởi động sẵn canvas và 6 khung đầu, không bớt). Chờ người dựng rê thật bằng chuột để xem có thấy khựng không.

**CHƯA ĐO THẬT:** rê bằng chuột người thật (đây là sự kiện giả); màn hình/DPI khác 150%; project và proxy khác (đo 1-2 clip, chưa đo clip nhiều phút, proxy HEVC dùng bản xem nhẹ); LUT khác; hai card đồ họa (chỉ thấy RTX 3060); RAM khi mở nhiều clip liên tiếp trong panel thật; so màu bằng mắt.
**Chưa giải quyết:** phát liên tục (Space) vẫn là thẻ video như cũ (vốn mượt); mỗi lần thả chuột video vẫn nhảy chính xác một lần (70-350 ms).


### K3 (19/11): cửa sổ cmd đen chớp khi mở liên tiếp nhiều clip
Quét mọi lời gọi tiến trình con trong app\: thủ phạm tìm được là **nạp sóng âm** (`troly_wave.make_peaks` chạy ffmpeg KHÔNG có `creationflags`, panel chạy bằng pythonw nên Windows mở một console chớp). Kho khung RAM (troly_frames), thumbnail, keyframe (ffprobe), Whisper, tiến trình AI và lệnh tắt máy đã có cờ ẩn; bản xem nhẹ ffmpeg (`troly_play.ensure_play_mp4`) thiếu cờ giống sóng âm (chỉ chạy khi proxy HEVC). Chưa quan sát trực tiếp cửa sổ chớp (không bắt được bằng mã); kết luận dựa trên mã. Cách sửa: `app/troly_proc.py` có `chay_an` (như subprocess.run) và `mo_an` (như Popen), luôn thêm CREATE_NO_WINDOW và STARTUPINFO SW_HIDE, giữ cờ người gọi đặt (độ ưu tiên thấp của kho khung); thay hết các chỗ gọi; test quét không còn `subprocess.run/Popen/...` nào ngoài troly_proc.py. Không đổi hành vi khác. CHƯA kiểm bằng mắt trong panel thật (người dựng mở liên tiếp nhiều clip để xem còn chớp không).
