# ADR-0024: Bước 3 In/Out làm lại – cây clip sao, gợi ý hai mức, nhận gợi ý bằng A, khung chữ Whisper

Ngày 18/11/2026. Trạng thái: CHỜ NGƯỜI DỰNG THỬ. Giao diện chuẩn: Design canvas "Trợ lý File Quay – Bước 3 In/Out (bản phác mới)" (2 bảng); bản sao 2 file ở `design/3_inout_moi/` (+ `demo_main.png` dựng lại bằng Edge để so sánh).

## Quy trình anh chốt
Bước 2 xếp bin + gắn sao (J) → Bước 3 bấm MỘT nút "Gợi ý In/Out cho clip sao" → lướt từng clip: đúng thì A (nhận, tự sang clip kế), sai thì kéo chỉnh → "Ghi In/Out clip sao" vào DaVinci (hộp xác nhận, sao lưu, Hoàn tác như cũ, ADR-0016).

## Quyết định
- **Cột trái** (thay danh sách phẳng + ô chọn bin): cây giai đoạn > bin con vẽ giống Bước 2 (`pool-row` / `sub`), mỗi dòng "số clip sao / tổng". Công tắc "Chỉ hiện clip có sao" mặc định BẬT (dùng chung bộ lọc lưới của Bước 2 nhưng nhớ riêng từng bước, ra khỏi Bước 3 thì trả lại giá trị của Bước 2); tắt thì clip chưa sao hiện mờ, J gắn sao ngay tại đó. Dưới bin đang chọn là danh sách clip: ★, chấm trạng thái (cam = đặt tay, viền cam = có trong DaVinci, xanh = gợi ý), tên, giờ quay, thời lượng giữ lại.
- **Nút "Gợi ý In/Out cho clip sao"** (đầu cột trái): chạy NỀN một lượt cho mọi clip sao, tiến độ trên nút, "đã chạy N/M". Lưu theo project: `plan["inout_sug"][clip] = {in, out, src, rule, sig, pad, at}` (chỉ xuất hiện khi anh bấm). Không mức nào tự ghi DaVinci; In/Out đặt tay LUÔN thắng.
  - **Mức 1** (quy tắc bin): `suggest_inout` theo bảng "Quy tắc gợi ý từng bin" và kiểu PSC/Truyền thống; KHÔNG sửa quy tắc.
  - **Mức 2** (lời nói): clip đã có chữ Whisper trong kho Bước 4: In = đầu câu đầu tiên − đệm, Out = cuối câu cuối cùng + đệm, kẹp trong [0, độ dài]; đệm mặc định 0,3 s (ô chỉnh 0–3 s, lưu `plan["inout_sug_cfg"]` chỉ khi anh chỉnh). Chưa chép lời, không có tiếng nói, hoặc đoạn ngắn hơn 0,5 s → rơi về mức 1.
  - Chưa chạy nút thì vẫn hiện gợi ý tức thời mức 1 như trước. Đổi quy tắc/kiểu quay/số giây Truyền thống/đệm sau khi chạy: gợi ý đã lưu được báo "cũ", chưa tự đổi (cột phải nhắc chạy lại). Cột phải ghi rõ nguồn: "theo lời nói" / "theo quy tắc bin" / "tức thời theo quy tắc bin".
- **Phím A / nút "Nhận gợi ý (A)"** (chỉ Bước 3; Bước 2 vẫn là nhận gợi ý AI xếp bin): biến gợi ý (xanh) của clip đang chọn thành In/Out đặt tay (cam) trong kế hoạch panel rồi sang clip kế (hết bin thì sang bin/giai đoạn kế có clip). Không nhận hàng loạt. Đọc bằng `event.code`, bỏ qua khi đang gõ chữ.
- **Khung chữ Whisper** dưới sóng âm: các câu theo mốc thời gian; câu nằm trong In/Out tô cam (nằm trong gợi ý chưa nhận: tô xanh); câu đang phát có viền và hai nút "Đặt In ở đây / Đặt Out ở đây"; bấm câu = đặt In/Out theo câu; Shift + bấm câu khác = nối dài từ câu đã bấm trước. Chưa chép lời: khung nét đứt "Chưa chép lời" + nút "Mở Bước 4 · Lời nói". Không có tiếng nói: ẩn khung chữ, sóng âm cao hơn.
- **Chân trang**: "N clip có sao trong K giai đoạn · gợi ý đã chạy a/N · đã nhận hoặc chỉnh b/N". Khung xem 444×250 như demo (bản trước tràn hết chiều ngang, làm khung chữ không còn chỗ).
- **Ghi nhận để có số đo thật** (`plan["inout_stats"]["clips"][clip] = {src, state: accepted|adjusted, bin, sug, final}`, mỗi clip một trạng thái, chỉ có khi anh nhận hoặc chỉnh một clip đã có gợi ý): A = "nhận nguyên"; kéo/I/O/mũi tên/bấm câu cho khác gợi ý = "đã chỉnh" (kéo về đúng gợi ý lại tính nhận nguyên); xóa In/Out tay thì bỏ ghi nhận. Số đếm hiện ở chân trang; tách theo nguồn lời nói / quy tắc.

## Đo độ đúng của gợi ý (chỉ đọc; `tools/sug_accuracy.py`)
"Thật" = đoạn nguồn anh đã dùng trên timeline thành phẩm của 2 project đã dựng (cách lấy mẫu của ADR-0021: bỏ slow-motion và trùng). "Lệch dưới T giây" = CẢ điểm vào và điểm ra cùng lệch dưới T.
- **Mức 1 (bảng quy tắc hiện có, chưa chọn kiểu quay)**: P1 (245 đoạn, không có bin con) dưới 1 giây 9%, dưới 2 giây 26%. P2 (150 đoạn): dưới 1 giây 25%, dưới 2 giây 56%. P2 theo bin (n, <1 s, <2 s): Decor (4) 75%, 100%; Gia đình (10) 60%, 100%; Nhà trai đến (9) 44%, 67%; Cô dâu chú rể (8) 38%, 75%; Chào bàn (22) 23%, 86%; Khách (16) 25%, 75%; Nghi lễ (61) 20%, 43%; Phỏng vấn (15) 0%, 0% (anh trích ~7 s từ clip dài ~200 s, điểm vào cách xa đầu clip); Khác (4) 0%, 0%. Mẫu theo bin nhỏ (4–22), đoạn trên timeline có thể đã trượt/cắt lại sau khi đặt In/Out nên là con số tham khảo.
- **Mức 2 (lời nói): CHƯA ĐO ĐƯỢC.** Chỉ project đang mở có chữ Whisper (kho Bước 4); 2 project có timeline thành phẩm chưa chép lời, và project đang mở mới có 1 In/Out đặt tay. Không bịa số: panel đã ghi nhận số clip anh nhận nguyên / chỉnh (theo nguồn) để có số đo thật sau vài lần dùng.
- Độ đúng của "nhận nguyên" thật sẽ đọc từ `plan["inout_stats"]` của project anh dùng.

## Đã thử thật / chưa
- Đã: cửa sổ pywebview thật (4K 150% và giả lập 1440×900, 1100×700), DaVinci chỉ đọc, dữ liệu là BẢN SAO tạm (kế hoạch + gợi ý, kho lời nói thật chỉ đọc): chạy nút gợi ý (10 clip sao, 8 theo lời nói, còn lại theo quy tắc), bấm câu đặt In/Out, Shift nối dài, hai nút nhỏ, A nhận và sang clip kế, đếm 1 nhận nguyên + 1 chỉnh, clip không có tiếng nói ẩn khung chữ; console không lỗi JS; không lẹm mép.
- Chưa: trạng thái "Chưa chép lời" mới thấy bằng dữ liệu ép (project mẫu đã chép hết), ghi In/Out thật vào DaVinci từ trang mới (nút Ghi giữ nguyên mã cũ, đã test ở ADR-0016), project có nhiều giai đoạn dài (nhiều trăm clip sao), kiểu PSC trên gợi ý mức 2 (mức 2 không phụ thuộc kiểu quay).
