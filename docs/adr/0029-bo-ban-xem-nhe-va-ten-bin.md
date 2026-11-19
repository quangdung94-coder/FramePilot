# ADR-0029: Bỏ "bản xem nhẹ", một hàm kiểm tra tên bin, đưa cửa sổ cũ lên trước

Ngày: 19/11/2026. Nhánh ra-soat-19-11. Quyết định của người dùng lúc 09:03 và 09:05 sau báo cáo rà soát (docs/RA_SOAT_19_11.md).

## 1. Bỏ hẳn "bản xem nhẹ" (thay phần phương án dự phòng của ADR-0016)
- Đã xóa: `troly_play.transcode_cmd`, `troly_play.ensure_play_mp4`, tham số `transcode` của `TrolyApi.play_info`, thư mục phục vụ `cache\troly_play`,
  nhánh "Đang tạo bản xem nhẹ..." trong player.js, và 2 test cũ của nó (`TranscodeCmd`, `PlayerFallback`; thay bằng `KhongTaoBanXemNhe`).
- Proxy không phát được (WebView2 không giải mã: HEVC, ProRes...): panel hiện thông báo nói rõ clip nào, vì sao, nên tạo lại proxy H.264 trong DaVinci,
  và giữ thumbnail. Không tạo bất kỳ file nào.
- Quyết định 18/11 "không tạo proxy hay bản nhẹ mới trên đĩa" được GIỮ NGUYÊN; phương án dự phòng trái quy tắc đó đã bị bỏ. Lý do người dùng: proxy gần như toàn H.264.
- Thư mục cache cũ `<data_root>\cache\troly_play` (nếu có từ các bản trước) KHÔNG bị xóa tự động; người dùng tự xóa nếu muốn.

## 2. Kiểm tra tên bin: một hàm chung
- Một hàm duy nhất kiểm tra tên bin cho cả "+ Bin mới" và "Đổi tên bin" (cùng bộ ký tự, cùng thông báo).
- Chặn: ký tự Windows cấm trong tên file/thư mục `: / \ * ? " < > |`, ký tự điều khiển, tên kết thúc bằng dấu chấm hoặc dấu cách.
- KHÔNG chặn `&` (người dùng có dùng & trong tên bin, Windows không cấm).

## 3. Mở FramePilot lần hai cho cùng project
- Đưa cửa sổ cũ lên trước (khôi phục nếu đang thu nhỏ). Không đưa lên được thì giữ thông báo chặn hiện tại.
