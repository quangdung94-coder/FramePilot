# FramePilot

**Trợ lý AI sắp xếp source, chọn In/Out, chép lời & dựng nháp tự động cho DaVinci Resolve** (chạy **100% offline**, tối ưu cho phim **Cưới, Mừng thọ, Sự kiện / Hội nghị / Gala**, hỗ trợ **Windows** & **macOS Apple Silicon**).

> 📄 **Hướng dẫn sử dụng chi tiết (PDF 7 trang, có ảnh minh họa):** [`docs/FramePilot_Huong_Dan_Su_Dung.pdf`](docs/FramePilot_Huong_Dan_Su_Dung.pdf)
> ## ⬇️ Tải bản cài đặt trọn bộ (Google Drive)

- 💻 **Windows (10/11 · GPU NVIDIA hoặc CPU):** [Tải FramePilot cho Windows (Google Drive)](https://drive.google.com/drive/folders/10EAf58ajXnPvmtjd9aVrZyOAaU7-eFOv)
- 🍎 **macOS Apple Silicon (M1 / M2 / M3 / M4):** [Tải FramePilot cho macOS (Google Drive)](https://drive.google.com/drive/folders/1AZtAxwH6wzPxfQTymWYuaMj9odrsdzz-)

> Sau khi tải về và giải nén, chạy `CaiDat_MayMoi.bat` (Windows) hoặc `CaiDat_MayMoi.command` (macOS) để tự cài đặt.
---

## Tính năng nổi bật

- **An toàn dữ liệu tuyệt đối (Chỉ đọc source):** Không sửa, không đổi tên, không xóa file quay gốc hay proxy. Mọi thay đổi lên DaVinci Resolve (tạo bin, ghi In/Out, tạo timeline) chỉ chạy khi bấm nút xác nhận và đều có **Hoàn tác (Undo)** kèm sao lưu.
- **Quy trình 5 bước khép kín, giao diện Dark Mode chuẩn DaVinci:**
  1. **Bước 1 · Giai đoạn:** Đọc Media Pool hoặc timeline multicam đã sync trong DaVinci, chia mốc giai đoạn bằng phím `F1–F12` / `Shift+F1–F12`, hỗ trợ nhiều mẫu sự kiện (Cưới đầy đủ/chỉ tiệc, Lễ mừng thọ, Event Hội nghị/Khai trương, Gala Dinner/YEP).
  2. **Bước 2 · Phân loại bin:** Lưới thumbnail nhiều camera, **Hover Scrub** lướt hình mượt không đổi mốc chọn `Shift+Click`, xem trước đúng màu **LUT `.cube` bằng WebGL2**, gắn sao (`P`), loại (`X`), tìm góc/cảnh tương tự (**DINOv2**), và **AI tự phân loại cảnh offline (SigLIP 2 / OpenCLIP)**.
  3. **Bước 3 · In / Out:** Gợi ý đoạn đẹp nhất theo **độ nét (Laplacian) + độ êm (Optical Flow) + biểu cảm khuôn mặt cười/tránh nhắm mắt (MediaPipe) + tiếng nói (Silero VAD) + tiếng động tiệc (CLAP)**; hỗ trợ cắt nhiều khúc `Shift+I / Shift+O`, sóng âm zoom + hút lặng, ghi & hoàn tác In/Out DaVinci.
  4. **Bước 4 · Lời nói & Recorder rời:** Tự động **Sync tiếng Recorder rời (Tascam/Zoom/Mixer)** từ Media Pool bằng đối khớp sóng âm 2 tầng đa luồng; chép lời tiếng Việt offline (**Whisper large-v3-turbo / PhoWhisper / MLX-Whisper / Const-me**), tách người nói (**WavLM-SV**), lọc câu đắt giá, bật/tắt tiếng `A1` bằng phím `M`.
  5. **Bước 5 · Thời lượng & Xuất Timeline:** Căn thời lượng theo 5 kiểu dựng (`Teaser 1:00`, `Highlight 4:00`, `Event 5:00`, `Phóng sự 10:00`, `Truyền thống 18:00`), kéo thả sắp xếp bin con/giai đoạn, tự xuất lên Timeline DaVinci kèm nhiều track `V1–V4` và track `A2` tiếng Recorder sạch (mặc định `A1` tắt, `A2` bật để dễ đối chiếu).
- **Hoàn tác linh hoạt:** `Ctrl+Z` / `Ctrl+Y` (macOS: `Cmd+Z` / `Cmd+Shift+Z`) 50 bước cho mọi thao tác nhỏ trên cả 5 trang.

---

## Cài đặt & Sử dụng nhanh

### 1. Bản đóng gói sẵn (khuyên dùng cho máy dựng)
- **Windows (`.exe`):** Xem [`HUONG_DAN_CAI_DAT.txt`](HUONG_DAN_CAI_DAT.txt) — chạy `CaiDat_MayMoi.bat` (tự quét & bỏ qua plugin/model đã có) rồi mở `FramePilot.exe`.
- **macOS Apple Silicon (M1/M2/M3/M4, `.app`):** Tải gói `FramePilot_Mac_ARM64_Core.zip` (và `FramePilot_Mac_ARM64_OfflineEnv.zip` nếu cài 100% offline) từ tab **Actions** trên GitHub, xem [`HUONG_DAN_CAI_DAT_MAC.txt`](HUONG_DAN_CAI_DAT_MAC.txt) và chạy `CaiDat_MayMoi.command`.

### 2. Chạy từ mã nguồn (dành cho phát triển)
- **Yêu cầu:** Python 3.10+, DaVinci Resolve (bật *External scripting using: Local*), `ffmpeg` & `ffprobe`.
- Sao chép cấu hình mẫu:
  ```bash
  cp config.example.json config.json
  ```
- Cài thư viện nền & chạy panel:
  ```bash
  pip install -r requirements.txt
  python app/panel_troly_web.py
  ```
- Cài thư viện AI (tùy chọn, chạy GPU CUDA trên Windows hoặc Apple MPS / MLX trên macOS):
  - Windows: `pip install -r requirements_ai.txt`
  - macOS Apple Silicon: `pip install -r requirements_mac.txt -r requirements_ai_mac.txt`

---

## Đóng gói & Kiểm thử

```bash
# Chạy toàn bộ unit test (667+ tests)
python -m unittest discover -s tests -p "test_*.py"

# Đóng gói bản sạch Windows (dist/FramePilot/)
python build_exe.py

# Đóng gói bản sạch macOS Apple Silicon (dist/FramePilot_Mac_ARM64_Core/)
bash build_mac.sh
```

GitHub Actions tự động chạy kiểm thử và đóng gói **macOS Apple Silicon (`arm64`)** mỗi khi push lên nhánh `main` ([`.github/workflows/build-mac-arm64.yml`](.github/workflows/build-mac-arm64.yml)).

---

## Phím tắt nhanh

| Phím | Chức năng |
| --- | --- |
| `Space` / `J` `K` `L` | Phát / Dừng / Tua lùi–tới chuẩn DaVinci |
| `F1–F12` / `Shift+F1–F12` | Đặt mốc đầu / cuối giai đoạn (Bước 1) · Chuyển giai đoạn (Bước 2) |
| `1–9` / `0` | Xếp clip vào bin con / Bỏ nhãn (Bước 2) |
| `P` / `X` | Gắn sao ★ / Đánh dấu loại |
| `I` `O` / `Shift+I` `Shift+O` | Đặt In/Out / Thêm nhiều khúc In/Out trong 1 clip |
| `A` / `M` | Nhận gợi ý In/Out (Bước 3) / Bật–tắt tiếng `A1` (Bước 4) |
| `Ctrl+Z` / `Ctrl+Y` (`Cmd`) | Hoàn tác / Làm lại 50 bước |

---

## Tài liệu tham khảo trong kho

- [`CHANGELOG.md`](CHANGELOG.md) — Nhật ký thay đổi chi tiết từng bản cập nhật.
- [`TRANG_THAI.md`](TRANG_THAI.md) — Trạng thái tiến độ & danh sách hạng mục.
- [`docs/FramePilot_Huong_Dan_Su_Dung.pdf`](docs/FramePilot_Huong_Dan_Su_Dung.pdf) — Tài liệu hướng dẫn sử dụng 7 trang.
- [`CHECKLIST_TEST_MAC.txt`](CHECKLIST_TEST_MAC.txt) — Danh sách kiểm thử bản macOS Apple Silicon.
