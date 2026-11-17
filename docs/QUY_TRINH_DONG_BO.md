# Quy trình đồng bộ Code ↔ Chat ↔ Notion (chốt 17/11/2026)

Mục tiêu: người dựng KHÔNG phải cập nhật Notion hay tài liệu bằng tay. Anh chỉ nói kết quả thử ("ok", "lỗi chỗ X") trong chat hoặc với Claude Code.

## Vì sao đang lệch (rà soát 17/11 tối)
1. **Một thông tin nằm ở nhiều nơi.** Bảng tiến độ vừa có trong Notion, vừa chép trong tài liệu Project; mỗi nơi sửa một lúc nên lệch.
2. **Hai bên cùng tạo dòng cho một việc.** Chat tạo "Lời nói A", Code tạo thêm 3 dòng "Lời nói A, bước 1-2/3/4" cho cùng việc.
3. **Hai kiểu "bước" trùng số.** "Bước 4" của đề bài (xuất SRT) khác "Bước 4" của panel (tab Lời nói).
4. **Code đọc cấu trúc bảng cũ**, báo cột Bước thiếu lựa chọn "4 Lời nói", nên ghi "Chung".
5. **Trạng thái không cùng nghĩa.** Có dòng đã thử xong vẫn ghi "Chờ anh thử"; có việc tạm hoãn vẫn ghi "Chưa làm".
6. **Chat không nhìn thấy kho mã** (chưa nối GitHub), nên chỉ biết Code làm gì qua báo cáo và Notion.
7. **Điểm dừng không có chỗ ghi.** Đề bài bảo "đo 3–5 clip rồi dừng chờ anh", nhưng không có dòng nào trong bảng giữ điểm dừng đó.

## Mỗi loại thông tin chỉ có MỘT nơi
| Loại thông tin | Nơi duy nhất | Ai ghi |
|---|---|---|
| Việc gì, xong chưa, commit, phiên bản | Bảng Notion "Trợ lý File Quay – Tiến độ" | Code ghi trạng thái, commit, phiên bản; Chat ghi dòng mới khi soạn đề bài; anh không ghi |
| Quyết định, thiết kế, hướng đi | Tài liệu trong Project "Panel VideoAI" | Chat |
| Mã, ADR, CHANGELOG, TRANG_THAI.md | Kho `TroLyFileQuay` | Code |
| Quy tắc làm việc | `CLAUDE.md` trong kho | Code (skill `dong-bo-quy-tac` đồng bộ với Notion) |

Tài liệu Project KHÔNG chép bảng tiến độ, chỉ trỏ tới Notion.

## Quy tắc cho Claude Code
1. **Một việc một dòng.** Đề bài có "Mã dòng Notion" ở đầu. Làm tới đâu thì cập nhật đúng dòng đó. Việc nhiều phần thì thêm dòng con, đặt tên bắt đầu bằng tên dòng cha, cùng cột Bước. Không tạo dòng trùng nghĩa.
2. **Gọi tên mục là "Mục A1, A2…"**, không dùng "bước 1–4". "Bước 1–6" chỉ dùng cho các tab của panel.
3. **Trước khi tạo hoặc sửa dòng Notion:** lấy lại cấu trúc bảng (fetch), đừng dùng bản nhớ cũ. Cột Bước chỉ nhận: 1 Đọc giờ, 2 Phân loại, 3 In/Out, 4 Lời nói, 5 Timeline, 6 AI, Chung. "Chung" chỉ cho việc hạ tầng (kho mã, kiểm thử, quy tắc). Lỗi thì thử lại một lần; vẫn lỗi thì ghi vào báo cáo cuối: dòng nào, cột nào, lỗi gì.
4. **Nghĩa của trạng thái:**
   - Chưa làm: chưa bắt đầu hoặc đang tạm hoãn (ghi "TẠM HOÃN" trong Ghi chú).
   - Đang làm: Code đang làm.
   - Chờ anh thử: Code xong, cần anh thử bằng tay. Code không tự đặt "Xong" cho việc cần anh thử.
   - Xong: anh đã thử và đạt, hoặc việc không cần anh thử.
5. **Điểm dừng là một dòng.** Đề bài ghi "DỪNG chờ anh" thì Code đặt dòng đó "Chờ anh thử", ghi số đo vào Ghi chú, rồi dừng thật. Chỉ làm tiếp khi anh nói tiếp trong chat. Không tự làm sang mục sau.
6. **Kết sổ cuối mỗi lượt làm** (làm đủ cả ba rồi mới báo xong):
   - a) Cập nhật các dòng Notion: Trạng thái, Commit, Phiên bản, Ghi chú ngắn, Cập nhật = hôm nay.
   - b) Sửa `TRANG_THAI.md`.
   - c) Cuối báo cáo thêm một dòng: `Kết sổ: Notion N dòng đã cập nhật, M lỗi (liệt kê); TRANG_THAI.md đã sửa; commit ...`.
7. Không đưa chữ chép lời, tên khách thật lên Notion hay git (quy tắc cũ).

## Quy tắc cho Claude trong chat
1. **Đầu phiên làm việc về Trợ lý File Quay: rà soát.** Đọc bảng Notion, so với tài liệu Project, báo anh một dòng nếu có lệch, tự sửa phần sửa được (cột Bước sai, trạng thái cũ, dòng trùng).
2. Khi anh nói "thử xong, ok" hay "lỗi chỗ X", Claude cập nhật dòng tương ứng, anh không mở Notion.
3. Tài liệu Project viết về quyết định và hướng đi, không chép bảng tiến độ.
4. Soạn đề bài: ghi "Mã dòng Notion" (tạo dòng trước, dán mã vào đề bài), ghi điểm dừng rõ ràng, gọi mục là A1, A2…

## Việc của anh
- Chỉ nói kết quả thử trong chat hoặc với Claude Code. Không cập nhật Notion tay.
- Dòng loại "Việc của anh" (Ctrl+S, thử tắt DaVinci…) anh nói "xong" là Claude đóng dòng.
- Nếu muốn Claude thấy cả kho mã trong chat: nối tài khoản GitHub (hiện chat báo chưa nối). Chưa nối thì Code phải kết sổ đủ, vì chat chỉ đọc được qua Notion và báo cáo.

## Giới hạn nói thẳng
Quy trình dựa vào việc Code làm đủ bước "kết sổ". Em đã thêm dòng kiểm tra vào báo cáo để lần sau nhìn là biết có làm hay không. Nếu Code bỏ sót, lần rà soát đầu phiên của Claude sẽ bắt được trong Notion, nhưng phần chỉ có trong kho mã (TRANG_THAI.md) thì chat không tự xác minh được.
