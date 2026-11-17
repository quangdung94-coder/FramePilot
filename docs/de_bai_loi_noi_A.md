# Đề bài cho Claude Code: Lời nói, giai đoạn A (bước 4 của Trợ lý File Quay)

Ngày soạn: 17/11/2026. Người dựng đã duyệt bản phác giao diện. Làm trong thư mục `D:\VideoAI\TroLyFileQuay`. Đọc trước `CLAUDE.md`, `TRANG_THAI.md` và `docs/`. Đề bài dài thì đọc hết file này, đừng làm theo trí nhớ phần đầu.

## 1. Mục tiêu giai đoạn A
Người dựng bấm một nút trong tab mới "4 · Lời nói": panel chép lời tất cả file source có tiếng trong bin đã chọn, lưu vào MỘT kho dữ liệu cho cả project, hiện "bản đồ lời nói" để lướt, và xuất SRT theo giai đoạn.

**Không làm trong A:** tầng 2 (đọc kỹ clip dài), nhập bản dịch về, ghi In/Out vào Media Pool, từ điển sửa lỗi, mô hình lớn hơn medium, chép từ Tascam. Nút hoặc liên kết thuộc phần sau thì hiện mờ, ghi "sắp có".

## 2. Đánh số bước (đã đổi 17/11)
1 Giai đoạn, 2 Phân loại bin, 3 In/Out, **4 Lời nói (mới)**, 5 Thời lượng (đổi từ số 4 cũ), 6 AI. Sửa nhãn tab và mọi chỗ ghi số bước trong giao diện, tài liệu, kiểm thử. Số ADR: bước này lấy ADR-0014.

## 3. Giao diện chuẩn (phải giống demo 80–90%, chụp màn hình so sánh)
- Demo đã duyệt: canvas `https://claude.ai/artifact/TYazsAmJ8rVAnRR5LSZWwX`, màn "4a Lời nói, tầng 1: bản đồ". Nguồn và ảnh nằm trong `design/loi_noi_demo/` (người dựng sẽ chép vào; nếu thiếu ảnh thì dừng và nhắc người dựng, đừng tự đoán giao diện). Dữ liệu trong demo là dữ liệu giả.
- Kiểm 1440x900 và 4K 150%, không lẹm mép, theo quy tắc trong CLAUDE.md.
- Thanh màu mỗi clip: xanh lá = đoạn có cụm key lễ cưới, xanh dương = có người nói, vàng = tiếng méo hoặc "kết quả có thể sai", trống = im lặng. Khung trắng = đoạn gợi ý In/Out.
- Mỗi clip một câu tiêu biểu: câu có nhiều cụm key nhất, không có thì câu dài nhất. Cột Key = số cụm key. Cột Ngữ = vi / en.
- Bộ lọc: "Chỉ clip có cụm key", "Tiếng nói từ 20 giây", ô "Tìm chữ" trong cả project. Dòng đếm "Hiện X / Y clip".
- Cột phải khi bấm clip: thanh màu lớn, In/Out gợi ý (cộng timecode bắt đầu của file vào giờ trong kho), chữ của clip với câu có cụm key tô đậm.
- Khung gợi ý In/Out ở bước này chỉ dựa vào chữ: từ câu có cụm key đầu tiên tới câu có cụm key cuối cùng, đệm khoảng 1 giây hai đầu. Không dùng quy tắc tự tính cũ (đang hoãn). In/Out người dựng đặt tay luôn thắng.
- Nút "Gắn sao (J)": dùng lại cơ chế sao có sẵn. Nút "Đặt In/Out": chỉ lưu vào kế hoạch của panel như In/Out đặt tay, KHÔNG ghi vào DaVinci.
- Liên kết "Đọc kỹ từng câu": hiện mờ, ghi "sắp có".

## 4. Chép lời
- Quét bin nguồn trong Media Pool (DaVinci chỉ đọc). Mỗi clip dùng khóa là UniqueId và đường dẫn tương đối, KHÔNG dùng tên file chép lời (lần trước tên lệch tên file âm thanh làm sót 6/17 đoạn).
- Trích âm thanh ra bản tạm, xóa sau khi xong. File gốc không bị đụng.
- **Âm lượng:** file gốc thường -10 đến -15 dB nhưng kéo lên là dùng được, nên KHÔNG loại file vì tiếng nhỏ. Kéo lên mức chuẩn trên bản tạm rồi mới lọc khoảng lặng. "Có tiếng" xác định bằng VAD sau khi kéo, không theo mức dB cố định. Lưu mức kéo của từng clip. Clip phải kéo nhiều (ngưỡng do em đo) hoặc kết quả đáng ngờ thì đánh dấu "kết quả có thể sai". **Việc đầu tiên:** đo trên 3–5 clip thật người dựng chỉ, báo mức kéo tối đa đề xuất và tỉ lệ câu nghi bịa trước khi chạy hàng loạt.
- Cách chép (đã chọn tạm 04/11): Const-me + ggml medium + silero-vad + gợi ý từ ngữ lễ cưới. Gợi ý từ ngữ CHỈ dùng cho file tiếng Việt. Chỉ tiếng Việt và tiếng Anh. Mỗi project có ô "ngôn ngữ mặc định" (tiếng Việt), tự nhận ngôn ngữ từng file, sửa tay được từng clip. Không tải gì về, cần tải thì hỏi trước.
- Chép phần cần dùng từ kho cũ `D:\VideoAI\repo` sang `app/` (kho cụm key `wedding_phrases.json`, phần lọc khoảng lặng trong `analyze_audio.py`, cấu hình whisper trong `config.json`). Không import ngược sang kho cũ.
- Cuối lượt phải có bước đối chiếu: số file có tiếng = số đã chép + số lỗi. Lệch thì báo đỏ, không im lặng.

## 5. Kho dữ liệu (không tạo một SRT cho mỗi clip)
- Một kho cho cả project, nằm trong thư mục người dựng chọn (panel nhớ theo project). Thư mục này KHÔNG nằm trong kho mã. Chữ chép lời không vào git, không vào Notion, chỉ có số liệu.
- Mỗi dòng lưu: clip, giờ bắt đầu và kết thúc tính từ đầu file, chữ, ngôn ngữ. Mỗi clip lưu: ngôn ngữ, độ dài, số dòng, các đoạn nói (để vẽ thanh màu), số cụm key, câu tiêu biểu, mức kéo âm lượng, cờ "có thể sai", kích thước và ngày sửa file, timecode bắt đầu. Định dạng cụ thể do em chọn, ghi lý do trong ADR-0014.
- Chạy tiếp được nếu bị ngắt: clip đã chép và file không đổi thì bỏ qua; file đổi thì chép lại.
- Chạy ban đêm: thanh tiến độ, nhật ký, chạy xong tự báo và không tắt máy. Cuối lượt báo: tổng file, có tiếng, đã chép, lỗi, có thể sai.

## 6. Xuất SRT theo giai đoạn
- Nút "Xuất SRT theo giai đoạn": mỗi giai đoạn một file (khoảng 6–8 file một đám). Giờ nối tiếp liên tục qua các clip; mỗi dòng có mã (clip và số dòng) nằm ngay trong dòng chữ để khi ChatGPT dịch xong vẫn ghép về đúng clip. Xuất vào thư mục người dựng chọn.
- Cũng cho xuất phần đã chọn, và SRT riêng một clip khi người dựng bấm yêu cầu.
- Kiểm thử vòng đủ: xuất, đọc lại, ghép đúng clip và đúng giờ gốc (có cộng timecode khi hiển thị trong panel).

## 7. Quy tắc cứng
- Không đụng file gốc. DaVinci chỉ đọc. Không ghi In/Out vào Media Pool.
- Tên khách thật không nằm trong mã, kiểm thử, ADR hay commit (dùng LV_Ten).
- Thử bằng chuột/phím thật trên BẢN SAO dữ liệu, chỉ một cửa sổ Trợ lý.
- Chưa chụp màn hình so với demo thì chưa báo xong phần giao diện.
- Kiểm thử mới cho: khóa clip, đối chiếu có tiếng/đã chép/lỗi, chạy tiếp, lọc, câu tiêu biểu, xuất SRT vòng đủ, tab đổi số.

## 8. Thứ tự làm và báo cáo
1. Chép code cần dùng, đo trên 3–5 clip thật, báo số đo (mức kéo, tốc độ, câu nghi bịa). **Dừng, chờ người dựng đọc** trước bước 2.
2. Kho dữ liệu và chạy cả bin.
3. Giao diện bản đồ lời nói, chụp màn hình so demo.
4. Xuất SRT theo giai đoạn.
5. Kiểm thử, ADR-0014, CHANGELOG, TRANG_THAI, commit và push, cập nhật dòng "Lời nói A" trong bảng Notion "Trợ lý File Quay – Tiến độ" (chỉ số liệu và ghi chú, không có chữ chép lời).

Báo cáo cuối: số liệu, ảnh so sánh demo kèm phần trăm, chỗ nào chưa chắc, việc người dựng cần làm.
