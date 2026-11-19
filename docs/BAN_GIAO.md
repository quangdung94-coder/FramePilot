# Bàn giao FramePilot (trước 18/11/2026 tên "Trợ lý File Quay") — 19/11/2026

Đọc file này + `CLAUDE.md` + `TRANG_THAI.md` là đủ để làm tiếp trong project Claude mới. (`docs/troly-ban-giao.md` là bản bàn giao cũ 15/11, chỉ còn giá trị lịch sử.)

## 1. Sơ đồ code (module nào làm gì)

```
app/panel_troly_web.py   mở cửa sổ pywebview (WebView2), khóa 1 cửa sổ / project, icon
  └─ app/troly_api.py    lớp TrolyApi: MỌI hàm giao diện gọi (window.pywebview.api.<tên>); giữ kế hoạch project trong RAM, lưu ngay
       ├─ troly_core.py      logic thuần: giờ quay, giai đoạn, nhãn, sao, In/Out (đặt tay, gợi ý 2 mức), lưu kế hoạch nguyên tử (.tmp → đổi tên, .bak, .corrupt)
       ├─ troly_resolve.py   LUỒNG NỀN DUY NHẤT gọi DaVinci: đọc bin/clip; GHI: tạo bin con + MoveClips, hoàn tác, ghi In/Out (sao lưu trước), tạo timeline MỚI
       ├─ troly_thumbs.py    thumbnail ffmpeg (proxy + LUT, 4 luồng, cache)
       ├─ troly_play.py      máy chủ phát proxy 127.0.0.1 (vé ngẫu nhiên, Range, chỉ trong proxy_root) + /f/ khung RAM
       ├─ troly_frames.py    kho khung JPEG nhỏ trong RAM để rê chuột mượt (LRU 8 clip / 300 MB, không ghi đĩa)
       ├─ troly_kf.py        keyframe proxy bằng ffprobe (cache)      troly_lut.py  đọc .cube cho WebGL
       ├─ troly_wave.py      sóng âm từ proxy (cache)
       ├─ troly_dur.py + troly_tl.py   Bước 5: chia thời lượng, cắt gọt, bố cục timeline V1/V2, Slow, tắt tiếng
       ├─ troly_speech*.py   Bước 4: trích âm, VAD, Whisper, kho SQLite mỗi project, xuất SRT, danh sách nghi sai
       ├─ troly_batch.py     "Phân tích cả project" + tắt máy an toàn (lệnh tắt máy truyền vào, test dùng bản giả)
       ├─ troly_ai.py        Bước 6 AI (OpenCLIP, venv riêng C:\VideoAI_ai_venv) — chỉ gợi ý
       ├─ troly_proc.py      MỌI tiến trình con đi qua đây (ẩn cửa sổ cmd)
       └─ troly_env.py       config.json, kết nối DaVinci, hộp báo lỗi, Job Object (tắt con theo), khóa cửa sổ
app/troly_web/           index.html, style.css, app.js (Bước 1-2, phím), player.js (trình phát, I/O, Ghi In/Out),
                         step3.js, speech.js (Bước 4), step5.js, ai.js
tools/                   panel_do_luot.py + measure_seek.js (đo lướt), inout_dump/inout_stats (đọc In/Out project đã dựng), sug_accuracy, ai_cross
tests/                   unittest, DaVinci GIẢ trong tests/test_troly.py (FPool, FProject...), tests/test_ra_soat*.py = lỗi đã sửa
design/                  demo đã duyệt (mở bằng trình duyệt)
install.py               cài mục menu "FramePilot" vào Workspace > Scripts của DaVinci
```

## 2. Chạy

```powershell
$py = "C:\VideoAI_venv\Scripts\python.exe"
& $py app\panel_troly_web.py --project "<tên project đang mở trong DaVinci>"     # thêm --debug: F12 + nút Đo lướt
$env:PYTHONUTF8 = "1"; & $py -m unittest discover -s tests -q                    # 506 bài (19/11), ~25 giây
& $py install.py --check                                                           # kiểm menu DaVinci (bỏ --check để cài)
& $py tools\panel_do_luot.py --out kq.json                                         # đo lướt: pywebview thật + DaVinci giả + proxy thật (chỉ đọc)
```
Mốc đo lướt 19/11 (RTX 3060, 4K 150%): thanh lướt ~58 hình/giây, sóng âm ~59, trễ trung vị dưới 1 ms. So A/B với bản cũ: `--app <thư mục app của worktree cũ>`.

## 3. Quyết định (ADR, docs/adr/)

| ADR | Tóm tắt |
|---|---|
| 0009 | Chia giai đoạn theo giờ quay, phân loại vào bin con; quyền GHI: tạo bin + MoveClips, có nhật ký + Hoàn tác |
| 0010 | Giao diện HTML trong pywebview (WebView2) |
| 0011 | "Đưa clip sao lên Timeline" chỉ tạo timeline MỚI |
| 0013 | Bước 5 Thời lượng: chia, cắt gọt, timeline MỚI bằng clip con (kéo thả V1/V2, Slow ripple, tắt tiếng) |
| 0014 | Bước 4 Lời nói: kho SQLite mỗi project, xuất SRT theo giai đoạn |
| 0015 | Đổi tên giai đoạn/bin con chỉ trong kế hoạch panel |
| 0016 | Trình phát proxy, In/Out tay, ghi In/Out (sao lưu + đối chiếu + Hoàn tác); kho khung RAM |
| 0017 | Phân tích cả project + tắt máy an toàn (SaveProject chỉ khi tick tắt máy) |
| 0018 | Kiểu quay PSC / Truyền thống |
| 0019 | Trang Bước 3: sóng âm + bảng quy tắc từng bin |
| 0020 | Bước 6 AI OpenCLIP, chỉ gợi ý |
| 0021 | Thống kê In/Out thật làm bảng quy tắc mặc định |
| 0022 | Gợi ý AI trong Bước 2, học từ nhãn tay |
| 0023 | LUT WebGL, lướt mượt (không tạo proxy mới), AI tự xếp theo ngưỡng |
| 0024 | Bước 3 làm lại: cây clip sao, gợi ý hai mức, phím A |
| 0025 | Bước 3: cây thu gọn, nút Chạy gợi ý, Truyền thống cắt đầu/đuôi theo bin |
| 0026 | "Tự phân loại" chạy luôn ở Bước 2 và 3 |
| 0027 | Tên FramePilot + icon |
| 0028 | Chữ hiển thị gọi người dùng là "bạn" |

Số ADR kế tiếp: 0029 (0012 bị bỏ trống từ trước).

## 4. Quy tắc làm việc
- Việc giao qua bảng Notion "Trợ lý File Quay – Tiến độ": mỗi dòng có checklist mã (R1, B1...). Xong mục nào tick ngay mục đó; kẹt thì ghi "KẸT: ..." dưới mục và làm tiếp. Bắt đầu: Trạng thái "Đang làm"; xong: "Chờ anh thử" (người dùng tự đổi sang "Xong").
- Mỗi việc một nhánh mới tách từ main; không gộp main, không force push, không xóa nhánh — người dùng duyệt gộp.
- Sửa lỗi: viết test trước (thấy đỏ), sửa, thấy xanh; một lỗi một commit. Chạy cả bộ test trước khi commit.
- Quyết định mới → ADR mới; cuối buổi cập nhật CHANGELOG.md và TRANG_THAI.md; ghi rõ phần "CHƯA CHẠY THẬT".
- Giao diện: bám demo trong design/ ≥ 80-90%, mở panel thật chụp màn hình so demo; không lẹm mép; phím đọc `event.code`, bỏ qua khi gõ chữ.
- Không đưa tên khách thật vào mã, test, ADR, commit (dùng LV_Ten, LV_X&Y). Chữ trên panel gọi người dùng là "bạn".
- Chạy thử chỉ bằng DaVinci giả + dữ liệu tạm; không đụng footage, proxy, project thật (chỉ đọc khi cần đo).

## 5. Quyết định đã chốt, KHÔNG được đảo
- Mặc định chỉ ĐỌC DaVinci. Chỉ được ghi: tạo bin con + MoveClips; tạo timeline MỚI; In/Out clip nguồn khi người dựng bấm + xác nhận số clip (sao lưu trước, Hoàn tác); SaveProject chỉ trong luồng tắt máy (ADR-0017).
- KHÔNG BAO GIỜ: xóa clip, đổi tên/di chuyển/xóa file trên ổ, sửa/xóa timeline có sẵn, render, tạo proxy hay bản nhẹ mới trên đĩa (xem câu hỏi về "bản xem nhẹ" trong docs/RA_SOAT_19_11.md).
- Gợi ý tự động (In/Out, AI) không bao giờ tự ghi vào DaVinci; In/Out đặt tay luôn thắng gợi ý. "Nhận" gợi ý AI chỉ gán nhãn trong panel.
- Khóa clip trong kế hoạch = đường dẫn TƯƠNG ĐỐI từ thư mục project (năm.tháng.ngày.tên); giờ quay thật = Date Created (đối chiếu Modified − độ dài, 15 giây).
- Bin chỉ là nhãn trong panel cho tới khi bấm "Áp dụng vào Media Pool".
- Thư viện AI ở venv riêng; model chỉ tải khi người dùng duyệt, chạy cục bộ.

## 6. Việc còn mở
- Người dùng thử bằng chuột thật trong panel thật: Tự phân loại B2/B3, ghi In/Out 2-3 clip rồi Hoàn tác, Bước 5 tạo timeline có Slow + V2 trên project thật, Phân tích cả project với tick tắt máy rồi Huỷ.
- Chạy `install.py` để menu DaVinci hiện "FramePilot" (xóa mục cũ bằng `--remove-old`).
- Kiểm bằng mắt K3 (cửa sổ cmd chớp khi mở liên tiếp nhiều clip).
- Câu hỏi cho người dùng trong docs/RA_SOAT_19_11.md (mục "Câu hỏi").
- Ý tưởng chưa thiết kế: nhiều máy quay theo làn, sao nhiều mức, số thứ tự trước tên bin (TRANG_THAI.md, "Việc tiếp theo").

## 7. Giới hạn đã biết
- Clip dài: kho khung RAM chỉ giữ tối đa 150 MB một clip (clip 20 phút proxy thật chỉ có khung cho khoảng phần đầu; phần sau rê bằng thẻ video, chậm hơn).
- Proxy HEVC: WebView2 không hiện hình mà không báo lỗi; panel dự phòng bằng "bản xem nhẹ" ffmpeg (tạo file mp4 trong cache — đang chờ người dùng quyết có giữ không).
- DPI: đã chụp ở 150% (4K) với cửa sổ 1100x680 và 1440x900; DPI 100% và màn khác CHƯA thử. Ở cỡ nhỏ nhất 1100x680 vài nút Bước 3 và ô "Kiểu quay" bị cắt chữ.
- Rê chuột thật: sự kiện đầu mỗi lần rê có lúc trễ 50-112 ms (đã chấp nhận).
- Hai máy cùng thẻ nhớ đặt trong thư mục không theo tên project (vd. ...\CAM A\PRIVATE\M4ROOT\CLIP\C0001.MP4) thì trùng khóa: panel cảnh báo và không ghi In/Out cho các clip đó, nhưng nhãn/sao vẫn dùng chung.
- Tự nhận vi/en khi chép lời chỉ là đoán theo chữ.
