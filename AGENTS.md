# AGENTS.md — đọc file này đầu tiên (FramePilot, panel DaVinci Resolve)

Dự án này vốn do Claude Code làm. Nếu bạn là một agent khác (ví dụ Antigravity), làm tiếp theo đúng các quy tắc dưới đây.
File này chỉ là CHỈ ĐƯỜNG. Nguồn thật nằm ở các file được trỏ tới, không chép lại ở đây.

## 1. Đọc theo thứ tự (đủ để làm tiếp, không cần gì khác)
1. `CLAUDE.md` — mục tiêu, quy tắc, an toàn với DaVinci, cấu trúc mã, lệnh chạy. NGUỒN QUY TẮC CHÍNH.
2. `docs/VIEC_TIEP_THEO.md` — đang làm gì, việc tiếp theo, quyết định đã chốt, việc chưa được làm khi chưa có lệnh của người dùng.
3. `docs/BAN_GIAO.md` — sơ đồ code, lệnh test/mở panel, bảng tài nguyên, danh sách quyết định (ADR).
4. `TRANG_THAI.md` — lịch sử chi tiết (dài, mới nhất ở trên). Chỉ tra khi cần. `docs/adr/` — lý do từng quyết định.
Không cần đọc repo VideoAI cũ, Notion hay chat cũ.

## 2. Người dùng
- Người dựng phim cưới, KHÔNG chuyên IT. Trả lời tiếng Việt, giải thích thuật ngữ ngắn như thầy dạy IT (ví dụ đời thường).
- Windows, DaVinci Resolve Studio 21. Python: `C:\VideoAI_venv\Scripts\python.exe`.
- "Brainstorm", "cung cấp thông tin" KHÔNG phải lệnh làm. Chỉ trao đổi và hỏi lại. Chỉ làm khi người dùng nói rõ "làm đi".

## 3. Lệnh hay dùng (PowerShell, `$py = "C:\VideoAI_venv\Scripts\python.exe"`)
- Test (phải đạt trước khi báo xong): `$env:PYTHONUTF8="1"; & $py -m unittest discover -s tests -q`
- Mở panel: `& $py app\panel_troly_web.py --project "<tên project đang mở trong DaVinci>"` (thêm `--debug` để mở F12)
- Chạy lại chỉ test lỗi khi đang sửa, đừng chạy cả bộ nhiều lần.

## 4. Tám điều không được quên (chi tiết trong CLAUDE.md)
1. DaVinci mặc định chỉ ĐỌC. Chỉ được GHI những việc CLAUDE.md liệt kê (bin con, MoveClips, timeline MỚI, In/Out có sao lưu + Hoàn tác, SaveProject theo ADR-0017).
2. Không bao giờ xóa clip, đổi tên file, đụng file trên ổ đĩa, sửa/xóa timeline đang có, render.
3. Ghi In/Out hàng loạt hoặc tải model/thư viện: phải hỏi và được người dùng đồng ý trước.
4. Hỏi trước khi XÓA hay ghi đè dữ liệu của người dùng. Không đụng file gốc của khách.
5. Riêng tư: KHÔNG đưa lên git: video, `config.json`, `hoc_tu_cu.local.json`, thư mục data, chữ chép lời, TÊN KHÁCH THẬT (dùng tên ví dụ như LV_Ten). Chỉ đưa số liệu.
6. Giao diện đã có demo trong `design/`: bản mã phải giống demo 80–90% ngay lần đầu, chụp panel thật so với demo trước khi báo xong.
7. Phím tắt đọc bằng `event.code`, không dùng `event.key`.
8. Báo trung thực: phần nào chưa chạy thử thật trên DaVinci thì nói rõ. Việc cần người dùng thử thì đặt "Chờ anh thử", KHÔNG tự đặt "Xong".

## 5. Kết thúc mỗi lượt làm (kết sổ) khi KHÔNG có Notion
Claude Code ghi vào Notion bảng "Frame Pilot 2 – Tiến độ". Bạn không có Notion, nên làm thế này:
1. Thêm mỗi việc vừa làm một dòng vào khối **"Ghi tạm khi không có Notion"** ở ĐẦU `TRANG_THAI.md`, theo mẫu trong khối đó (ngày, việc, trạng thái, mã commit). Một việc một dòng, không sửa hay xóa dòng của người khác.
2. Cập nhật `docs/VIEC_TIEP_THEO.md` nếu việc tiếp theo hoặc các điểm "chờ anh" thay đổi. Thêm dòng vào `CHANGELOG.md` nếu có thay đổi hành vi.
3. Commit (không push nếu người dùng chưa bảo).
4. Cuối câu trả lời ghi một dòng: `Kết sổ: ghi tạm N dòng; VIEC_TIEP_THEO.md đã sửa; commit <mã>` (lấy mã từ `git log`).
Khi người dùng quay lại làm việc với Claude, họ nói "đồng bộ": Claude chép các dòng ghi tạm sang Notion rồi dọn khối đó. Đừng tự dọn.
