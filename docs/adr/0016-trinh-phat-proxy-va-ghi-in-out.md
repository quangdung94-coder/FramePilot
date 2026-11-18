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
