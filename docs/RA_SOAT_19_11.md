# Tổng duyệt FramePilot 19/11/2026 (nhánh `ra-soat-19-11`, tách từ main 67bfa7d)

Chỉ rà soát và sửa lỗi, không thêm tính năng, không đổi bố cục. Mốc trước khi làm: 493 test đạt. Sau: **506 test đạt** (thêm 13 bài trong `tests/test_ra_soat_19_11.py`), chạy 3 lần liền không chập chờn.
Mọi lần chạy thử dùng DaVinci GIẢ và dữ liệu tự tạo trong thư mục tạm; proxy thật chỉ được ĐỌC khi đo lướt (R6). Không đụng footage, project DaVinci, file kế hoạch thật.

Mức độ: **Nghiêm trọng** = mất/hỏng dữ liệu, crash, ghi nhầm vào DaVinci · **Trung bình** = sai kết quả, kẹt, rò rỉ · **Nhẹ** = hiển thị, chữ.

## 1. Bảng phát hiện

### Đã sửa (11)

| # | Mức | Lỗi | Cách tái hiện | Commit |
|---|---|---|---|---|
| 1 | Nghiêm trọng | Chọn bin nguồn khác rồi bấm "Đọc clip": giai đoạn đã kéo/đổi tên bị thay bằng giai đoạn gợi ý và lưu ngay; quay lại bin cũ cũng không lấy lại được. | Đọc bin A, đổi tên/kéo giai đoạn, đọc bin B, đọc lại A. Nay giai đoạn giữ theo từng bin (`plan["stages_by_bin"]`). | 8a651be |
| 2 | Nghiêm trọng | Mở FramePilot hai lần cho cùng project: hai cửa sổ giữ hai bản kế hoạch, cửa sổ lưu sau ghi đè nhãn/sao của cửa sổ kia. | Bấm menu FramePilot hai lần. Nay cửa sổ thứ hai báo "đang mở ở cửa sổ khác" (khóa file, tự nhả khi đóng/chết). | dcbd867 |
| 3 | Nghiêm trọng (chưa thấy trên DaVinci thật) | Đường dự phòng tạo timeline (CreateEmptyTimeline + AppendToTimeline, cả nút sao lẫn Bước 5, và V2) thêm clip vào timeline HIỆN TẠI; nếu DaVinci không tự chuyển sang timeline mới thì clip chèn vào timeline đang dựng. | DaVinci giả: CreateTimelineFromClips trả rỗng, CreateEmptyTimeline không đổi timeline hiện tại. Nay chuyển + đọc lại xác nhận trước khi Append; không chắc thì dừng và báo. | f182839 |
| 4 | Nghiêm trọng | Hai clip khác nhau trùng khóa đường dẫn tương đối (vd. hai thẻ Sony trong thư mục không đặt theo tên project: `CLIP/C0001.MP4`) dùng chung In/Out đặt tay → Ghi In/Out ghi cả vào clip kia. | Đặt In/Out cho clip A, Ghi clip đang chọn gồm A và B. Nay cảnh báo khi đọc clip và không ghi In/Out cho các clip trùng khóa. Nhãn/sao vẫn dùng chung (xem câu hỏi 2). | 8020beb |
| 5 | Trung bình | Hoàn tác In/Out của project "X" lấy nhầm file sao lưu của project "X_B" (cùng tiền tố); khôi phục mà bỏ qua clip chưa đọc vẫn đánh dấu "đã khôi phục" → mất đường Hoàn tác. | Hai project tên lồng nhau / Hoàn tác khi đang xem bin khác. | 519399d |
| 6 | Trung bình | Hoàn tác "lần chuyển gần nhất" khi đang đọc bin khác: không có gì xảy ra, không báo gì. | Áp dụng ở bin A, đọc bin B, bấm Hoàn tác. Nay báo phải đọc lại bin A. | 4609f57 |
| 7 | Trung bình | Kho lời nói SQLite: luồng chép lời nền và giao diện dùng chung một kết nối không khóa → `cannot commit - no transaction is active`, có thể commit nửa giao dịch. | Đổi ngôn ngữ một clip trong lúc "Chép lời cả bin" (test căng tải tái hiện 3/3 lần). | fc46bca |
| 8 | Trung bình | ffmpeg trích âm và Whisper không có giới hạn thời gian: một file hỏng treo cả "Chép lời cả bin" và "Phân tích cả project" (không bao giờ tới bước tắt máy). | Nay 900 giây/file trích âm, 1800 giây/WAV Whisper, quá thì tính lỗi clip đó và chạy tiếp. | 8e7d01f |
| 9 | Trung bình | Sau Áp dụng/Hoàn tác panel đọc lại bin và in "Đã kết nối DaVinci. Chọn bin nguồn..." đè lên dòng trạng thái duy nhất → cảnh báo "N clip KHÔNG chuyển được" biến mất. | MoveClips thất bại một nhóm. | 3f8211a |
| 10 | Nhẹ | Bước 5 ở cửa sổ 1100 px: nút Bật/Tắt tiếng của bảng khối đè lên thẻ "Chưa đạt mục tiêu". | Chụp pywebview thật 1100x680, 150%. Nay bảng cuộn ngang trong thẻ. | ccdc432 |
| 11 | Nhẹ | `.gitignore` không chặn video/âm thanh/kho SQLite (chưa có file nào lọt, chỉ phòng ngừa). | | 13f79f8 |

### Chưa sửa (8) — lý do

| # | Mức | Phát hiện | Vì sao chưa sửa |
|---|---|---|---|
| 12 | Trung bình | Clip trùng khóa (lỗi 4) vẫn dùng chung nhãn và sao. | Sửa tận gốc phải đổi cách đặt khóa trong file kế hoạch (nâng cấp dữ liệu cũ) → câu hỏi 2. |
| 13 | Trung bình | "Bản xem nhẹ" (proxy HEVC không phát được) tạo file mp4 720p trong `<data_root>\cache\troly_play`, không bao giờ tự xóa; trái quy tắc "không tạo proxy hay bản nhẹ mới". | Có từ ADR-0016, gỡ là đổi hành vi đã duyệt → câu hỏi 1. |
| 14 | Nhẹ | Cửa sổ nhỏ nhất 1100x680 (150%): ô "Kiểu quay: chưa cl…", hàng nút Bước 3 ("Bỏ sao (", "Ghi clip đan…"), nút "Áp dụng vào Media P…" (cột phải Bước 2 phải cuộn ngang) bị cắt chữ. Ở 1440x900 và toàn màn hình thì đủ. | Sửa cần đổi bố cục (xuống dòng/thu chữ) → câu hỏi 3. |
| 15 | Nhẹ | Esc/Enter/mũi tên đọc bằng `e.key` (số và chữ đã dùng `event.code`). Các phím này không bị Unikey đổi nên không gây lỗi. | Không có tác hại thực tế; để nguyên cho khỏi đụng phím đã duyệt. |
| 16 | Nhẹ | File kế hoạch hỏng hai lần trong cùng một giây: bản `.corrupt-<giờ>` lần sau ghi đè bản lần trước. | Gần như không xảy ra (ghi đã nguyên tử). |
| 17 | Nhẹ | "+ Bin mới" chỉ thay `/`, cho phép `:` `*` `?`...; DaVinci có thể từ chối tạo bin khi Áp dụng (panel báo "không chuyển được"). | Đổi tên đã kiểm ký tự (ADR-0015); thêm kiểm ở đây là đổi hành vi nhập → ghi lại, chờ bạn. |
| 18 | Nhẹ | Trình phát: clip mới không có độ dài thì tạm dùng độ dài của clip trước cho thanh lướt. | Chỉ ảnh hưởng clip thiếu metadata; không tái hiện được với dữ liệu thật. |
| 19 | Nhẹ | Hoàn tác chuyển bin lỗi một phần: vị trí bin của các clip đã về đúng chỗ chỉ cập nhật trong panel sau lần "Đọc clip" kế. | Chỉ ảnh hưởng số "bin sẽ rỗng" trong hộp xác nhận lần sau. |

**Tổng: 19 phát hiện — 4 nghiêm trọng / 7 trung bình / 8 nhẹ; đã sửa 11, chưa sửa 8.**

## 2. Kết quả từng mục
- **R1 An toàn dữ liệu**: (a) mọi lệnh xóa/đổi tên file chỉ trong thư mục tạm/cache do panel tạo; không có đường nào ghi vào footage/proxy (xuất SRT chỉ tạo file mới, không ghi đè). (b) Mọi lệnh ghi DaVinci đi từ nút + hộp xác nhận; "Mở trong DaVinci" chỉ đổi bin đang mở/chọn clip; tạo timeline có chuyển timeline hiện tại sang timeline mới. (c) Hoàn tác: chồng nhật ký đúng thứ tự, lỗi giữ nhật ký; sửa lỗi 6. (d) Ghi nguyên tử + .bak + .corrupt, file rỗng/hỏng tải lại đúng .bak (thử ở R4). (e) Sửa lỗi 2.
- **R2 Rà code**: sửa lỗi 7, 8. Kho khung RAM: hủy/nạp tiếp có khóa, ffmpeg bị kill khi đổi clip và khi đóng. Trình phát: đã chặn kết quả trễ của clip cũ. Làm tròn frame (4 chữ số thập phân) đủ cho 23,976 / 25 / 50 / 59,94 / 120p. Chia cho 0 đã chặn ở các chỗ tính tốc độ/thời lượng/tỉ lệ.
- **R3 Tên Windows** (dữ liệu tự tạo): project `2026.11.06.LV_Ten&Ten2 (A) #1 %d 'x'`, bin `Bin & 'chọn' (#1) 100%`, file có dấu, `&`, `'`, `#`, `%`, đường dẫn 431 ký tự, proxy chỉ đọc, LUT trong thư mục có dấu: đọc clip, Áp dụng + Hoàn tác, thumbnail + LUT, sóng âm, keyframe, trình phát (206), kho khung RAM, LUT WebGL, In/Out, trích âm, Bước 5, lưu/tải kế hoạch — tất cả chạy.
- **R4 Tình huống biên** (hành vi thật): project rỗng / bin 0 clip / 1 clip: không sập, báo rõ. Thiếu proxy: "Chưa có proxy" ở mọi chỗ; proxy hỏng: "ffmpeg lỗi: Invalid data…", không treo. Clip không giờ quay: hiện `--:--:--`, nằm ngoài giai đoạn, có đếm trong thông báo. Hai clip cùng tên khác thư mục: tách đúng. Bin bị đổi tên/xóa khi đang mở: "Không thấy bin nguồn…". DaVinci đóng giữa chừng: báo lỗi, mở lại thì Áp dụng chạy. Đổi project: từ chối ghi. 450 clip: đọc 0,02 s, state 8 ms, kế hoạch 115 KB. Tắt đột ngột (file kế hoạch cụt): giữ bản hỏng, nạp .bak (mất thao tác cuối). Clip 20 phút: thumbnail 0,3 s, sóng âm 0,6 s, kho khung dừng ở 150 MB.
- **R5 Đi qua tab** (pywebview thật + DaVinci giả + proxy tự tạo): 5 tab chuyển qua lại không lỗi JS; Bước 2: 1, 0, J, Shift+2 rồi 1, Ctrl+A rồi J, gõ chữ trong ô thì bỏ qua, mô phỏng Unikey (`key` khác, `code` = Digit1) vẫn xếp; Bước 3: số không xếp bin, I/O, ←/→ chỉnh frame, ↓ đổi clip, Space phát; chuyển tab giữa chừng In/Out còn nguyên. Tự phân loại, ngưỡng, Slow Bước 5: dựa trên test đơn vị có sẵn (test_troly_ai_auto, test_troly_tl, test_troly_tl_api).
- **R6 Hiệu năng**: thanh lướt 57,8-57,9 hình/giây, sóng âm 58,8, trễ trung vị 0,2-0,6 ms; bản main đo cùng lúc 57,9 / 58,9 → **không hồi quy** (con số "58-60" ngày 19/11 là từ lần đo khác). 50 clip liên tiếp: RAM Python 21 → 39 MB, tối đa 5 ffmpeg con cùng lúc, **0 ffmpeg mồ côi** sau khi đóng.
- **R7 Chữ**: không còn "anh" trên panel (chỉ "tiếng Anh"; vài docstring trong mã còn "anh", không hiện ra). Không nhãn debug/demo. Chữ Latin còn lại là thuật ngữ (DaVinci, Media Pool, Timeline, LUT, proxy, Slow, Whisper, Rough Cut). 1100x680 và 1440x900 ở 150%: không thanh cuộn ngang toàn trang; sửa lỗi 10; còn mục 14.
- **R8 Kho mã**: 506 test x3 đạt; không khóa/token/email/đường dẫn cá nhân, không tên khách thật trong repo; install.py chạy khô trên APPDATA sạch: chưa cài → cài → "đã cài đúng bản này", file khởi chạy biên dịch được; TRANG_THAI/CHANGELOG/ADR đã khớp (ADR kế tiếp 0029).
- **R9**: docs/BAN_GIAO.md.

## 3. CHƯA CHẠY THẬT
- Mọi sửa đổi trên chưa thử trên DaVinci thật (chỉ DaVinci giả). Riêng lỗi 3 chưa tái hiện được trên DaVinci thật (không biết bản thật có tự chuyển sang timeline rỗng mới hay không; bản sửa an toàn cả hai trường hợp).
- Chuột/bàn phím người thật trong panel thật (R5 dùng sự kiện giả trong cửa sổ pywebview thật).
- DPI 100% và màn hình khác 4K 150%.
- Ổ mạng (UNC) với dữ liệu thật; file trên ổ chỉ đọc thật (mới thử thuộc tính chỉ đọc trên ổ cục bộ).
- K3: bằng mắt xem cửa sổ cmd còn chớp không.
- Khóa một cửa sổ khi mở từ menu DaVinci (mới thử bằng hai tiến trình Python).
- Chép lời Whisper thật với file hỏng (giới hạn thời gian mới thử bằng tiến trình giả).
- AI thật, Tự phân loại B2/B3 bằng giao diện; tạo timeline Slow + V2 trên project thật.

## 4. Câu hỏi cho bạn
1. "Bản xem nhẹ" (khi proxy HEVC không phát được): giữ (tạo mp4 720p trong cache, không bao giờ tự xóa) hay bỏ (chỉ hiện thumbnail + báo "proxy không phát được")? Nếu giữ: có cần nút xóa cache này không?
2. Footage của bạn có khi nào để thẻ nhớ nguyên cấu trúc (CAM A\PRIVATE\M4ROOT\CLIP\…) mà thư mục project KHÔNG đặt tên kiểu `năm.tháng.ngày.tên`? Nếu có, nên đổi khóa clip (cần nâng cấp file kế hoạch cũ) để nhãn/sao không bị dùng chung.
3. Ở cửa sổ nhỏ nhất (1100x680) vài nút bị cắt chữ. Bạn có dùng cửa sổ nhỏ không? Nếu có thì chọn: cho hàng nút xuống dòng, hay nâng cỡ cửa sổ nhỏ nhất?
4. "+ Bin mới" có nên chặn các ký tự `: & / \ * ? " < > |` giống đổi tên không?
5. Mở FramePilot lần hai cho cùng project nay bị chặn kèm thông báo. Bạn muốn thế, hay muốn tự đưa cửa sổ cũ lên trước?
