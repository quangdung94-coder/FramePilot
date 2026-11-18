# ADR-0020: Bước 6 AI – OpenCLIP nhúng thumbnail, gợi ý bin theo mô tả (chỉ gợi ý)

Ngày 18/11/2026. Trạng thái: đã làm phần chạy dòng lệnh + trang báo cáo; CHƯA có giao diện trong panel, CHƯA được người dựng duyệt kết quả.

## Quyết định
- Model: OpenCLIP ViT-B/32 `laion2B-s34B-b79K` (MIT), chỉ file `open_clip_model.safetensors` (605.143.316 byte, SHA-256
  `ac4f8c4b…6e6`, trùng SHA do Hugging Face công bố). Lưu `D:\VideoAI\data\models\openclip_vitb32_laion2b\`. Không tải file .bin (pickle), SigLIP hay model khác.
  Từ vựng chữ (BPE) có sẵn trong thư viện nên không cần tải thêm file nào.
- Thư viện nằm trong venv RIÊNG `C:\VideoAI_ai_venv` (Python 3.10, torch 2.14.1+cu130, open_clip_torch 4.2.2, ~3,1 GB trên đĩa; `requirements_ai.txt`).
  `C:\VideoAI_venv` (panel, Whisper) không bị đụng: torch 2.14.1+cu130 và numpy 2.2.6 vẫn như cũ.
- Chạy cục bộ trên RTX 3060 (CUDA); ảnh không gửi đi đâu.
- CHỈ GỢI Ý: không ghi DaVinci, không đổi kế hoạch panel, không chuyển clip (có test chặn). Kết quả ở file riêng
  `<data_root>\troly\ai_suggest\<project>.json`; vector ở `<data_root>\cache\troly_embed\<project>\vectors.npz` (xóa được, tạo lại được);
  trang xem `<data_root>\troly\ai_review\<project>\index.html`.

## Cách làm
1. Ghép thumbnail với clip KHÔNG cần DaVinci: dựng lại mã băm tên cache từ file proxy (đường dẫn + cỡ + giờ sửa + LUT + vị trí + chiều rộng 320),
   chỉ đọc danh sách file proxy. Còn proxy thì thumbnail thừa (cache cũ) bị bỏ qua; project không còn proxy nào thì nhúng thumbnail "mồ côi" (không có tên clip, không đo được nhãn).
2. Nhúng: lô 32 ảnh, lưu mỗi 5 lô, dừng bằng cờ `STOP` (`--stop`), chạy lại thì làm tiếp (đã thử: cắt còn 100 vector, chạy lại bù đủ 254). Clip chưa có thumbnail bị bỏ qua và đếm trong log (`<data_root>\logs\ai_embed_*.log`).
3. Gợi ý: mỗi bin hiện có trong kế hoạch có 2–4 câu mô tả tiếng Anh (luật theo từ khóa tên bin, bin lạ dùng câu chung); lấy trung bình vector chữ, so cosine
   với vector ảnh, softmax nhiệt độ 100 → hạng 1-2-3 + điểm. Có nhãn tay ≥ 20 clip thì đo độ khớp từng bin, ít hơn thì báo "chưa đủ nhãn để đo".

## Số đo (máy này)
- Nhúng ~350–530 clip mất 4–9 giây mỗi project (nạp model ~3 giây). Dung lượng vector: ~3,5 MB cho 4 project.
- Project có nhãn tay (324 clip có nhãn, 13 bin con theo từng giai đoạn): gợi ý theo mô tả, lần đầu hạng 1 trùng 10,8% / nằm trong 3 đầu 29,9%;
  sau khi viết lại mô tả cho các bin chưa khớp từ khóa (Khách, Sân khấu, Trao lễ vật, Cô dâu chú rể…) lên 17% / 58%.
  Lưu ý: lần viết lại này nhìn kết quả có nhãn nên 58% KHÔNG phải số đo độc lập. Bin Decor khá chắc (độ chính xác 89%); các bin theo giai đoạn
  (Nghi lễ, Khách, Nhà trai đến…) gần như đoán mò vì ảnh giống nhau, chỉ phân biệt được bằng giờ quay/giai đoạn.
- Tham khảo (không phải sản phẩm): kNN trên chính vector này, học từ nhãn tay, leave-one-out cho 81% hạng 1 (đa số = 30%). Số này lạc quan vì các clip liền kề cùng cảnh.
  → Hướng đúng cho bước sau: học từ nhãn người dựng (few-shot) mạnh hơn nhiều so với mô tả; mô tả chỉ dùng khi project mới chưa có nhãn.
- Project còn lại không có nhãn nên chưa đo được.

## Giới hạn
- Gợi ý theo mô tả có thể sai nhiều, chỉ để tham khảo; không tự áp dụng.
- Chỉ nhìn 1 khung (40% độ dài clip) nên clip dài đổi cảnh vẫn chỉ có 1 gợi ý.
- Gợi ý chưa dùng giai đoạn/giờ quay; bin giống nhau về hình (Nghi lễ/Khách/Sân khấu) dễ lẫn.
- Chưa có giao diện trong panel; chưa thử khi có thumbnail mới sinh ra sau lúc nhúng (chạy lại `embed` sẽ bù).
