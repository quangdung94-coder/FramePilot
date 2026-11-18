# ADR-0013: Bước 5 Thời lượng – chia thời lượng, cắt gọt, tạo timeline MỚI

Ngày 18/11/2026. Trạng thái: CHỜ NGƯỜI DỰNG THỬ. Demo `design/4_thoi_luong.dc.html` (bản tĩnh dựng lại để so sánh: `design/4_thoi_luong_tinh/`). Các con số mặc định bên dưới là ĐỀ XUẤT, CHƯA được người dựng xác nhận; giao diện ghi rõ "đề xuất, anh sửa được".

## Quyết định
- Ô "Video mục tiêu" (phút, mặc định 12, nhập 1–120, nhắc khi ngoài 10–15). Biểu đồ chia tỉ lệ theo giai đoạn: kéo vạch giữa hai giai đoạn, các giai đoạn khác co giãn nên TỔNG luôn bằng 1 (mỗi giai đoạn tối thiểu 2%). Chưa kéo thì tỉ lệ theo nội dung (tổng độ dài tự nhiên của clip sao trong giai đoạn, đã chặn bởi Max từng bin).
- Bảng Min–Max là TỔNG của cả bin (khác độ dài từng clip ở Bước 3), sửa được từng ô. Mặc định (đề xuất): Decor 10–20 giây, Beauty cô dâu 20–30 giây. Các bin còn lại tự suy ra: **tự nhiên = Σ độ dài gợi ý của các clip có sao trong bin** (độ dài từng clip DÙNG LẠI bảng `bin_rules` / kiểu quay / số giây Truyền thống của Bước 3, hoặc In/Out đặt tay; không có bảng thứ hai); **Max = min(90, tự nhiên)**, **Min = min(Max, 0,6 × tự nhiên)**; bin không có clip sao: 0–0. 90 là thang của thanh trong demo.
- Lưu trong kế hoạch: `plan["durations"] = {"target_min", "stage_share": {tên giai đoạn: tỉ lệ}, "bins": {tên giai đoạn: {tên bin: [min, max]}}}`. Khóa chỉ xuất hiện khi anh sửa; ghi qua file tạm, có `.bak`; đổi tên giai đoạn/bin (ADR-0015) đổi theo.

## Cắt gọt (`app/troly_dur.py`, logic thuần, chỉ ra KẾ HOẠCH trong panel)
1. Thứ tự giữ nguyên: giai đoạn rồi giờ quay thật. Clip sao nằm ngoài mọi giai đoạn không đưa lên (có cảnh báo). Clip chưa xếp bin vào nhóm "(chưa xếp bin)".
2. Ngân sách giai đoạn = tỉ lệ × mục tiêu. Mỗi bin có trần = min(tự nhiên, Max). Nếu tổng trần vượt ngân sách: co dần các bin về Min theo tỉ lệ (không thấp hơn Min); nếu tổng Min vẫn vượt thì cảnh báo.
3. Trong một bin vượt ngân sách: trước hết BỎ clip ít ưu tiên nhất (mức sao thấp nhất; bằng nhau thì clip quay muộn hơn) chừng nào tổng độ dài TỐI THIỂU còn vượt; rồi rút In/Out các clip (giữ điểm vào, rút điểm ra) cho vừa. Độ dài tối thiểu của clip = Min của quy tắc bin ở Bước 3; In/Out đặt tay cố định (không rút); kiểu Truyền thống không rút (vẫn bớt 1,5 giây đầu và cuối như Bước 3), chỉ bỏ clip.
4. Mức sao: hiện chỉ có sao/không sao (xem đều nhau); giá trị số trong `plan["stars"]` sẽ được dùng làm độ ưu tiên khi có sao nhiều mức.
5. Bin thiếu Min: CHỈ cảnh báo, không tự thêm clip chưa sao. Tổng ngắn hơn mục tiêu: chỉ cảnh báo. Giao diện hiện tổng dự kiến và phần chênh với mục tiêu trước khi tạo.

## Tạo timeline (`TrolyWorker.do_create_cut_timeline`, theo ADR-0011)
- Nút "Cắt gọt cho vừa" ghi nhớ đúng bản đã xem; nút "Đưa lên Timeline mới" chỉ bật khi bản đó còn khớp số liệu hiện tại, hỏi xác nhận (nói rõ số đoạn, tổng, chênh, cảnh báo, không sửa timeline cũ), ghi nhật ký `<data_root>\troly\timeline_log\<project>_<giờ>.json` (số clip, tổng giây, từng đoạn) TRƯỚC khi gọi DaVinci.
- Chỉ tạo timeline MỚI: `CreateTimelineFromClips(tên, [{mediaPoolItem, startFrame, endFrame}])` (clip con theo In/Out, KHÔNG SetMarkInOut lên clip gốc); trả rỗng thì `CreateEmptyTimeline` + `AppendToTimeline`. Tên "Rough Cut thoi luong <project> <ngày giờ giây>", bỏ ký tự `: & / \ * ? " < > |`. Chỉ chạy khi DaVinci đang mở đúng project của panel. Không xóa, không sửa timeline có sẵn, không render. Sau khi tạo: kiểm số timeline tăng đúng 1 và timeline cũ còn nguyên tên.

## Đã đo thật trên DaVinci Resolve Studio 21.1.1 (18/11/2026, project đang mở, 1 timeline thử)
- Trước khi thử: ExportProject (.drp 1,2 MB) vào `D:\VideoAI\backup\drp_<ngày giờ>_truoc_thu_timeline\`; project có 0 timeline.
- `CreateTimelineFromClips` với clipInfo `{mediaPoolItem, startFrame, endFrame}` tạo 1 timeline (project: 0 → 1), 6 đoạn clip con, có cả 3 track âm thanh. **Độ dài trên timeline = endFrame − startFrame** (đoạn yêu cầu 45→194 ra 149 frame), nên endFrame = round(ra × fps) (không trừ 1; bản đầu trừ 1 làm mỗi đoạn ngắn hơn 1 frame, đã sửa sau khi đo). Đọc lại `GetMarkInOut` của 6 clip gốc: vẫn trống (không bị ghi In/Out).
- Bản sửa công thức frame chưa được kiểm lại bằng timeline thứ hai (giới hạn 1 timeline thử); đã có test cho công thức.
- Timeline thử còn nằm trong project (Trợ lý không xóa timeline), tên bắt đầu "Rough Cut thoi luong"; anh xóa tay được.

## Giới hạn
- Số đề xuất chưa kiểm với dữ liệu thật của anh; bin tự suy ra phụ thuộc bảng quy tắc Bước 3 (giữ nguyên nội dung bảng đó, không đổi ở bước này).
- Chia tỉ lệ giai đoạn theo nội dung chỉ là điểm khởi đầu; không tự thêm clip để đủ mục tiêu.
- Chưa có sao nhiều mức; chưa tách theo máy quay.
