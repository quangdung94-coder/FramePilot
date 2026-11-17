# Nhật ký thay đổi

## 2026-11-17 (tối) – Kho Git riêng
- Tạo kho riêng tư TroLyFileQuay; gỡ tên khách thật khỏi CLAUDE.md và lịch sử (amend + force-push); .gitignore thêm cache/, projects/*.json, *.bak, *.corrupt-*, *.log.
- Chép tests/ (47 bài), docs/adr (0009-0011), docs/troly-ban-giao.md từ kho cũ; đánh số ADR tiếp: 0012 = Bước 3, 0013 = Bước 4.

## 2026-11-17 (v0.2.5, đồng bộ với kho cũ commit b13c7fb)
- Sao ★ (phím J), lọc chỉ clip có sao, `suggest_inout`, nút "★ Đưa clip sao lên Timeline" chỉ tạo timeline MỚI (không sửa timeline có sẵn, không ghi In/Out). Quyết định ghi ở ADR-0011 (kho VideoAI cũ).
- Bản CustomTkinter `panel_troly.py` đã bỏ ở kho cũ; thư mục này chỉ có bản HTML.

## 2026-11-17
- Tách Trợ lý File Quay khỏi repo VideoAI sang thư mục độc lập TroLyFileQuay: app/troly_env.py thay các module dùng chung cũ (panel_common, analyze_project, extract_timelines); install.py riêng; CLAUDE.md và TRANG_THAI.md tự đủ.
