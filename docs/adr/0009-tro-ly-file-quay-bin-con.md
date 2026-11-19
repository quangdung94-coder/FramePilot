# ADR-0009: Trợ lý File Quay: chia giai đoạn theo giờ quay, phân loại vào bin con (quyền GHI mới: tạo bin + chuyển clip)

> Ghi chú 17/11/2026: đánh số bước đã đổi thành 1 Giai đoạn, 2 Phân loại bin, 3 In/Out, 4 Lời nói (mới), 5 Thời lượng. Chữ "bước 4 Thời lượng" trong ADR này là bước 5 hiện nay.

- Ngày: 2026-11-15
- Trạng thái: Đã chốt (hướng mới "huong-di-moi-tro-ly-file-quay", phiên chat 15/11/2026; làm Phần 1 + 2 trước)

## Bối cảnh
Giai đoạn phân tích hình để đặt in/out đã đóng (ADR-0005). Việc tốn thời gian nhất còn lại của người dựng là XEM và
XẾP hàng trăm file quay (533 clip ở project 17/10) theo từng đoạn của ngày cưới. DaVinci đã có sẵn giờ bấm quay thật
của từng file ("Date Created", đo 15/11/2026), proxy 1080p và LUT gắn trong Media Pool, đủ để chia ngày quay thành giai
đoạn và xem nhanh bằng thumbnail mà không phải mở từng clip. Nhãn người dựng xếp tay cũng là dữ liệu để AI học sau.

Đến nay DaVinci chỉ được ghi in/out + màu clip (ADR-0003/0004) và Rough Cut trên timeline chính (ADR-0006/0007).
Xếp clip vào bin con là quyền GHI mới, nên cần ADR riêng.

## Các lựa chọn đã cân nhắc
1. Chỉ hiện giai đoạn/nhãn trong panel, không đụng Media Pool: an toàn nhưng người dựng vẫn phải tự kéo clip trong DaVinci.
2. Gắn nhãn bằng màu clip hoặc keyword: đụng màu clip (đang dùng cho "clip bỏ qua", ADR-0004) và khó nhìn khi có 9 nhóm.
3. Tạo bin con trong bin nguồn và CHUYỂN clip vào (MoveClips), có nhật ký và hoàn tác (chọn).
4. Tạo bin mới ngoài bin nguồn / nhân bản clip: làm rối cấu trúc Media Pool người dựng quen, nhân bản dễ nhầm clip.

## Quyết định
- Panel riêng `src/panel_troly.py` (menu "VideoAI Trợ lý File Quay", cài bằng `scripts/install_troly.py`), lõi
  `troly_core.py` (không gọi DaVinci), thumbnail `troly_thumbs.py`, cầu nối `troly_resolve.py` (một luồng nền).
- Giờ quay: "Date Created" nếu khớp "Date Modified - độ dài" (lệch <= 15 giây); không khớp (file đã chép lại) thì dùng
  "Date Modified - độ dài". Không dùng Start TC (lệch nhiều giờ). Lệch giờ chỉnh được theo từng máy (giây).
- Giai đoạn: gợi ý ban đầu bằng các khoảng nghỉ quay dài nhất theo mẫu sự kiện; người dựng kéo lại trên thanh thời gian.
  Clip thuộc giai đoạn theo giờ BẮT ĐẦU; hai giai đoạn chồng nhau thì giai đoạn sau thắng.
- Phân loại: phím 1-9 xếp clip của một giai đoạn vào bin con của giai đoạn đó, 0 bỏ nhãn. Nhãn lưu ở
  `<data_root>\troly\projects\<project>.json`, khóa là đường dẫn TƯƠNG ĐỐI của file (bền khi chuyển ổ).
  Nhãn chỉ có hiệu lực khi đúng tên giai đoạn hiện tại của clip (kéo giờ làm clip đổi giai đoạn thì nhãn cũ không kéo
  clip vào sai bin). Đổi tên giai đoạn thì nhãn đi theo tên mới.
- Quyền GHI mới vào DaVinci, CHỈ khi người dựng bấm "Áp dụng vào Media Pool" và đồng ý ở hộp xác nhận (liệt kê số clip
  mỗi bin):
  - tạo bin con BÊN TRONG bin nguồn: `01_<giai đoạn>` và `01_<giai đoạn>/<bin con>` (AddSubFolder; bin đã có thì dùng lại);
  - chuyển clip vào bin đó bằng `MediaPool.MoveClips`. Clip ngoài mọi giai đoạn giữ nguyên chỗ cũ.
  - KHÔNG xóa clip, không xóa bin, không đổi tên clip, không đổi in/out, màu, metadata, không đụng file trên ổ.
- Nhật ký: mỗi lần áp dụng ghi `moves` (uid, bin cũ, bin mới, giờ) vào kế hoạch của project TRƯỚC khi báo xong.
  "Hoàn tác lần chuyển gần nhất" chuyển clip về bin cũ theo nhật ký; bin con đã tạo để lại (không xóa), nhật ký chỉ
  bỏ khi mọi clip về được.
- Thumbnail: ffmpeg cắt 1 khung ở 40% độ dài, ưu tiên proxy, áp "Input LUT" của clip (proxy không nướng LUT), cache ở
  `<data_root>\cache\troly_thumbs\<project>\`. Video không rời máy.

## Hệ quả
- Người dựng xem cả ngày quay trên một thanh thời gian và xếp clip bằng bàn phím; Media Pool có cấu trúc bin theo giai
  đoạn, tool chỉ đọc cho tới khi bấm áp dụng.
- Có dữ liệu nhãn (giờ, giai đoạn, bin) theo từng project để sau này huấn luyện gợi ý phân loại (Phần sau của hướng mới).
- MoveClips với clip đang nằm trên timeline: ĐÃ ĐO 15/11/2026 trên project thật (533 clip, 2 timeline, 338 clip trên
  timeline): mọi clip trên timeline giữ nguyên vị trí, độ dài và media pool item. Hoàn tác cần "Đọc clip" lại trong cùng phiên panel (worker cần MediaPoolItem).
- Chưa làm: thẻ 3 In/Out, thẻ 4 Thời lượng; gợi ý nhãn tự động.

> Từ 19/11/2026 phím chọn giai đoạn là F1–F12 thay cho Shift+số: xem ADR-0030. Các đoạn Shift+số dưới đây là lịch sử.

## Bổ sung 15/11/2026 (chiều): chọn tay giai đoạn, phím Shift+số, kéo thả (người dựng duyệt)
- Người dựng thử trên project 25/10: thiếu cách đưa một clip sang giai đoạn khác khi giờ quay không khớp. Thêm "CHỌN TAY":
  `plan["manual"][đường dẫn tương đối] = {stage: tên giai đoạn, ...}`. Giai đoạn chọn tay THẮNG giai đoạn tính theo giờ
  (`troly_core.assign(..., manual=)`, `target_folder(..., clip_manual)`), kéo lại mốc giờ ở thẻ 1 không làm mất; đổi tên
  giai đoạn thì chọn tay đi theo; giai đoạn bị xóa thì clip quay về tính theo giờ. Thẻ 1 hiện số clip chọn tay và nút
  "Bỏ chọn tay" (hỏi trước; nhãn bin con vẫn giữ).
- Phím ở bước 2 (đọc `event.code` Digit/Numpad, không dùng `event.key` vì Shift+3 ra "#" và Unikey kiểu VNI dùng phím số;
  bỏ qua khi đang gõ trong ô nhập chữ): 1-9 xếp vào bin con của giai đoạn đang xem, 0 bỏ nhãn; Shift+số chuyển clip đang
  chọn sang giai đoạn số đó; Shift+số rồi số trong 2 giây: sang giai đoạn đó và vào bin con (bảng nhỏ liệt kê bin con,
  hết 2 giây chỉ đổi giai đoạn, Esc hủy).
- Kéo một hoặc nhiều thumbnail đang chọn thả vào cây MEDIA POOL: bin giai đoạn = đổi giai đoạn, bin con = đổi giai đoạn +
  nhãn. Bin đang kéo tới sáng lên; giữ chuột 0,6 giây trên bin giai đoạn thì bin con của nó mở thêm (không gập bin đang
  mở, để cây không dịch dưới con trỏ). Chuột phải trên thumbnail: "Chuyển sang giai đoạn", "Xếp vào bin con".
- Vẫn chỉ ghi vào kế hoạch của Trợ lý; Media Pool chỉ đổi khi bấm "Áp dụng" (hộp xác nhận như trên).
- Đã thử bằng chuột/bàn phím thật trên project 25/10 (405 clip): phím 1, Shift+3 rồi 1, Shift+2 chờ 2 giây, kéo 2 clip vào
  bin giai đoạn, kéo vào bin con, chuột phải đều đúng; kế hoạch của project được trả lại như trước khi thử.
- Bản dự phòng CustomTkinter (panel_troly.py) chưa có chọn tay.

## Bổ sung 15/11/2026 (tối): BẤM bin trong cây Media Pool chỉ để XEM (lỗi 3, người dựng đã chốt)
- Lỗi: bấm bin con trong cây (ví dụ 01_Chuẩn bị nhà gái > Beauty cô dâu) (a) chuyển luôn clip đang chọn sang bin đó,
  (b) lưới vẫn hiện cả giai đoạn. Nguyên nhân: v0.2.1 gắn "bấm bin con = xếp nhãn" và lưới chỉ lọc theo giai đoạn.
- Quy tắc đúng (giống mở thư mục con trong Windows): BẤM bin = chỉ XEM, không bao giờ đổi nhãn hay giai đoạn của clip nào.
  Việc chuyển clip CHỈ qua phím 1-9 / Shift+số / 0, kéo thả vào bin, chuột phải.
  - Bấm bin con: lưới chỉ hiện clip có nhãn bin đó (trong giai đoạn đó). Bấm bin giai đoạn: toàn bộ clip của giai đoạn.
    Mục mới "Chưa xếp" trong mỗi giai đoạn: chỉ clip chưa có nhãn.
  - Đổi bin đang xem: bỏ chọn các clip không còn trong lưới. Xếp/chuyển clip khi đang xem một bin con: clip rời lưới,
    con trỏ giữ nguyên vị trí (không nhảy cách một clip).
  - Bin đang xem sáng nhẹ + vạch trắng bên trái; bin đích kéo thả nền cam + viền cam (khác nhau). Tiêu đề lưới:
    "Giai đoạn > Bin (n clip)".
  - Số cạnh mỗi bin con và lưới lấy từ CÙNG danh sách clip (`Api.state()`: stage.uids / none / bins[].uids), nên số
    đếm luôn bằng số clip lưới hiện.
- Kiểm thử: tests/test_troly_api.py (danh sách theo bin con khớp số đếm, xem không đổi nhãn/chọn tay/nhật ký). Thử thật
  bằng chuột và bàn phím thật trên project 25/10 (405 clip), 23/23 điểm đạt: bấm bin con/"Chưa xếp"/bin giai đoạn không
  đổi nhãn nào, lưới đúng clip, bỏ chọn clip ngoài lưới, tiêu đề, bin sáng khác bin đích kéo thả, số đếm đúng sau khi thả.

## Bổ sung 15/11/2026 (tối, 2): sửa ô co khi Shift chọn nhiều; BỎ giới hạn 2 giây của Shift+số (người dựng quyết định)
- Lỗi ô co: giữ Shift chọn nhiều thumbnail thì ô được chọn co còn ~40 px, mất ảnh, tên file và nhãn. Tái hiện bằng Shift thật
  trên project 25/10: ô được chọn cao 40 px trong khi ảnh bên trong cao 155 px. NGUYÊN NHÂN: class JS gắn cho ô được chọn là
  `sel`, trùng với luật CSS `.sel { height: 40px }` của ô chọn thả xuống (bin nguồn, mẫu sự kiện). Chữa: đổi class thành
  `picked`; thumbnail luôn giữ chiều cao (aspect-ratio + min-height, không co); chặn bôi chọn chữ/ảnh (user-select: none,
  mousedown có Shift/Ctrl thì preventDefault, ảnh draggable=false); đổi trạng thái chọn chỉ đổi class (nhãn chỉ dựng lại khi
  nhãn đổi). Bài học: tên class trạng thái của thành phần không được trùng class dùng chung; có bài kiểm tra tĩnh
  (tests/test_troly_web.py) bắt trường hợp này.
- Shift+số KHÔNG còn giới hạn thời gian. Lý do: phân loại source không gấp, đếm ngược 2 giây làm người dùng bấm không kịp và
  tự "hết hạn" khi đang suy nghĩ. Quy tắc mới: Shift+số chuyển ngay clip đang chọn sang giai đoạn đó rồi vào chế độ chờ bin con;
  dải báo luôn hiện ("Đang chờ bin con của 03_Gia tiên", kèm bảng bin con và phím) tới khi: bấm số bin con (xếp xong), 0 (bỏ nhãn),
  Esc (thôi, clip giữ giai đoạn mới), bấm chuột ở bất kỳ đâu ngoài dải, phím mũi tên, hoặc đổi bước. Số không có bin thì giữ
  chờ. Không còn timer nào, không còn chữ "2 giây". Vẫn đọc phím bằng event.code, bỏ qua khi đang gõ trong ô nhập chữ.
- Thử thật bằng chuột/bàn phím thật trên project 25/10 (bản sao dữ liệu): 17/17 điểm đạt (trước khi sửa: lỗi 1 tái hiện được,
  Shift+3 hết hạn sau 2 giây nên bấm số sau 5,5 giây không vào bin con).

## Bổ sung 15/11/2026 (tối, 3): panel NHỚ project khi tắt rồi mở lại (người dựng duyệt)
- Đo thực tế (tái hiện trên kế hoạch thật của project 25/10): file `data\troly\projects\<tên project>.json` ĐÃ ghi đủ nhãn, chọn
  tay, mốc giờ, lệch giờ theo máy, bin nguồn, nhật ký áp dụng, và tên project có `&` hay dấu tiếng Việt không làm hỏng đường dẫn.
  Cái MẤT khi mở lại: (1) panel không hiện gì (0 clip) cho tới khi bấm "Đọc clip"; (2) trạng thái làm việc (bước đang ở,
  giai đoạn/bin con đang xem, thu phóng thanh giờ, ô lọc) chưa từng được lưu. Hai điểm nguy hiểm: (3) file kế hoạch bị hỏng thì
  lần lưu sau GHI ĐÈ bằng kế hoạch rỗng (mất sạch nhãn); (4) lưu trễ 0,5 giây bằng timer nền; (5) project đổi tên trong
  DaVinci thì mất kế hoạch vì file đặt theo tên.
- Quyết định:
  - **Khóa project:** vẫn đặt file theo TÊN project (người dựng đọc/tìm dễ), thêm `project_uid` = `Project.GetUniqueId()` vào file.
    Mở một project có kế hoạch còn trống mà có file khác cùng `project_uid` (project đã đổi tên): chép kế hoạch cũ sang tên mới,
    file cũ giữ nguyên (không xóa), báo cho người dựng.
  - **Tên file:** chỉ đổi ký tự cấm của Windows (`<>:"/\|?*`, ký tự điều khiển) và dấu chấm/khoảng trắng cuối tên; `&`, dấu tiếng
    Việt, khoảng trắng giữa tên giữ nguyên. Hai project trùng tên file sau khi đổi (a:b và a|b) thì project đến sau thêm đuôi băm,
    không ghi đè nhau.
  - **Lưu NGAY** mỗi khi đổi nhãn/giai đoạn/chọn tay/mốc giờ/lệch giờ/bin nguồn/thêm bin (không timer). Ghi nguyên tử: file tạm +
    `fsync` + giữ bản trước làm `.bak` + `os.replace`.
  - **File hỏng:** đổi tên giữ lại thành `.corrupt-<giờ>` (không bao giờ ghi đè), nạp `.bak`, báo người dựng; cả hai hỏng mới ra
    kế hoạch rỗng.
  - **Trạng thái làm việc** lưu trong `plan["ui"]`: `page`, `view` (thu phóng thanh giờ), `gStage`, `gSub`, `onlyNew`. JS gom
    thay đổi 400 ms rồi gọi `api.save_ui`.
  - **Mở lại panel:** lấy tên project đang mở trong DaVinci (menu truyền `--project`), nạp file, TỰ nạp clip của bin nguồn đã dùng
    (chỉ một lần; không nạp lại sau Áp dụng/Hoàn tác), dựng lại giao diện đúng bước/bin/thu phóng đã lưu.
  - **Clip đổi giữa hai lần mở:** `plan["seen"]` ghi khóa (đường dẫn tương đối) các clip lần đọc trước. Clip mới = chưa có trong
    `seen`: hiện "N file MỚI chưa phân loại" (thẻ 1 và thanh trạng thái). Nhãn/chọn tay của clip không còn trong Media Pool: bỏ qua
    khi hiển thị nhưng GIỮ trong file (clip có thể quay lại).
- Kiểm thử: tests/test_troly_persist.py (13 bài: tên có `&` và tiếng Việt, ký tự cấm, trùng tên file, ghi nguyên tử + .bak, file
  hỏng, ghi-thoát-nạp-so khớp, tự nạp một lần, clip mới/mất, đổi tên project theo uid, project khác uid không nhận nhầm).
  Thử thật bằng hai tiến trình panel liên tiếp (phiên 2 KHÔNG bấm "Đọc clip") trên bản sao dữ liệu project 25/10: 10/10 điểm đạt.
  Chưa thử bằng cách tắt hẳn DaVinci (sẽ đóng project đang mở của người dựng); phần panel không phụ thuộc DaVinci đang chạy,
  còn việc nạp clip sau khi mở lại DaVinci dùng đúng đường đọc bin đã thử nhiều lần.
