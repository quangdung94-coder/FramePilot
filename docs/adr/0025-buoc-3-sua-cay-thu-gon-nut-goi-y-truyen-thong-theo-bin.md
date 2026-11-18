# ADR-0025: Bước 3 – cây thu gọn/mở, nút "Chạy gợi ý" rõ ràng, Truyền thống cắt đầu/đuôi theo bin

Ngày 18/11/2026. Trạng thái: CHỜ NGƯỜI DỰNG THỬ. Sửa ba điểm sau ADR-0024.

## 1. Cây cột trái thu gọn/mở
- Mũi tên ▸/▾ đầu dòng giai đoạn, "Chưa xếp" và bin con. Bấm mũi tên hoặc bấm lại dòng đang chọn thì thu gọn/mở danh sách clip của dòng đó; trạng thái nhớ trong `P3.fold` (giữ khi đổi clip, đổi bước).
- Chọn cả giai đoạn: mặc định chỉ hiện các bin con, danh sách clip cả giai đoạn thu gọn sẵn (mở bằng mũi tên); bin: mặc định mở. Bấm mũi tên của dòng khác thì chọn và mở luôn.
- Bấm bin vẫn chỉ là XEM (không đổi nhãn). Phím ↑/↓ đổi clip vẫn chạy (đã thử trong cửa sổ thật).

## 2. Nút "Chạy gợi ý cho N clip sao"
- Là nút chính: nền cam nổi, chữ "Chạy gợi ý cho N clip sao"; đang chạy thì tiến độ chạy ngay trên nút ("Đang gợi ý… n/N"); xong đổi thành "Chạy lại gợi ý (N clip sao)" kèm "đã chạy N/N"; dòng trạng thái dưới nút báo kết quả (X theo lời nói, Y theo quy tắc bin).
- Không im lặng khi lỗi: chưa có clip sao, API lỗi hoặc ngoại lệ đều hiện chữ đỏ dưới nút và trên thanh trạng thái; nút chỉ bị khoá khi đang chạy. Nếu sự kiện nền không tới, hỏi tiến độ định kỳ để vẫn kết thúc đúng.

## 3. Quay Truyền thống: cắt ĐẦU và ĐUÔI riêng, THEO TỪNG BIN
- `plan["trad_trim"] = {tên bin: [đầu, đuôi]}` (chỉ có khi anh sửa). Mặc định chung cho bin chưa sửa vẫn ở `plan["trad_trim_s"]`, nay là số (đầu = đuôi, y như khóa cũ nên kế hoạch cũ đọc được) hoặc cặp `[đầu, đuôi]` khi khác nhau; chưa sửa gì thì không có khóa và gợi ý y hệt cũ (1,5 / 1,5; test so từng độ dài kể cả clip ngắn).
- `suggest_inout(..., trad_trim, trad_bin)`: cặp riêng của bin thắng cặp chung; clip ngắn vẫn chừa ít nhất 1 giây (co đều hai đầu theo tỉ lệ). `suggest_plan(plan, dur, label)` là cửa duy nhất dùng đủ thông số kế hoạch (gợi ý tức thời, chạy nền, Bước 5 đều gọi). PSC và chưa chọn kiểu giữ nguyên bảng min/max.
- Kiểm hợp lệ (`check_trad`): số, không âm, tối đa 600 giây; sai thì báo lỗi rõ và KHÔNG ghi gì. Có "Về mặc định" (cả bảng, gồm cắt đầu/đuôi) và nút "chung" từng bin.
- Giao diện: khi kiểu = Truyền thống, bảng "Quy tắc gợi ý từng bin" đổi thành hai cột "Cắt đầu (s)" / "Cắt đuôi (s)" (min/max ẩn); khung "Kiểu quay" có hai ô chung "cắt đầu" / "cắt đuôi".
- Chữ ký gợi ý đã lưu (`sug_signature`) gộp kiểu quay, min, max, whole, cắt đầu/đuôi chung, cắt đầu/đuôi riêng của bin, đệm: đổi số thì gợi ý đã lưu báo "cũ" (cột phải nhắc "Chạy lại"), chạy lại thì tính theo số mới (đã thử: Decor 1,5/1,5 → 1,0/0,5 cho clip 4,8 s ra vào 1,0, ra 4,3).

## Chưa chạy thử thật
- Gợi ý theo bin cho Bước 5 (cắt gọt) khi dùng Truyền thống theo bin: có test chung nhưng chưa thử bằng tay trong trang Bước 5.
- Ví dụ "Đón khách / Tiễn khách giữ gần trọn clip": đã thử bằng bin mẫu Decor (project mẫu không có hai bin đó), công thức giống nhau cho mọi bin.
- Ghi In/Out vào DaVinci không đụng đến ở lượt này.
