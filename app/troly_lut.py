"""
troly_lut.py - Đọc file LUT .cube 3D để giao diện áp bằng WebGL lên khung xem trước (Việc 1, ADR-0023). CHỈ ĐỌC file LUT, không tạo file mới.
Trả dữ liệu thô (float32 RGB, R chạy nhanh nhất rồi G rồi B, đúng thứ tự file .cube) dạng base64 để JS dựng texture 3D.
"""
import array
import base64
import os
import sys

MAX_SIZE = 65                    # LUT 3D lớn nhất chấp nhận (65^3 × 12 byte ≈ 3,3 MB)


class LutError(ValueError):
    pass


def parse_cube(path):
    """-> dict(size, dmin[3], dmax[3], data=array('f') độ dài size^3*3, title). Ném LutError nếu không đọc được / LUT 1D / sai số dòng."""
    size, dmin, dmax, title = None, [0.0, 0.0, 0.0], [1.0, 1.0, 1.0], ""
    vals = array.array("f")
    try:
        f = open(path, "r", encoding="utf-8", errors="replace")
    except OSError as e:
        raise LutError("Không mở được file LUT: %s" % e)
    with f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            head = line.split(None, 1)[0].upper()
            if head == "TITLE":
                title = line[5:].strip().strip('"')
            elif head == "LUT_3D_SIZE":
                try:
                    size = int(line.split()[1])
                except (IndexError, ValueError):
                    raise LutError("LUT_3D_SIZE hỏng.")
                if not 2 <= size <= MAX_SIZE:
                    raise LutError("Cỡ LUT %s không hỗ trợ (2–%d)." % (size, MAX_SIZE))
            elif head == "LUT_1D_SIZE":
                raise LutError("LUT 1D chưa hỗ trợ.")
            elif head in ("DOMAIN_MIN", "DOMAIN_MAX"):
                try:
                    v = [float(x) for x in line.split()[1:4]]
                except ValueError:
                    raise LutError("%s hỏng." % head)
                if len(v) != 3:
                    raise LutError("%s thiếu số." % head)
                if head == "DOMAIN_MIN":
                    dmin = v
                else:
                    dmax = v
            elif head[0] in "0123456789-+.":
                p = line.split()
                if len(p) < 3:
                    raise LutError("Dòng dữ liệu thiếu số.")
                try:
                    vals.extend((float(p[0]), float(p[1]), float(p[2])))
                except ValueError:
                    raise LutError("Dòng dữ liệu không phải số.")
            # các từ khóa khác (LUT_IN_VIDEO_RANGE, ...) bỏ qua
    if size is None:
        raise LutError("Không thấy LUT_3D_SIZE (không phải LUT 3D).")
    if len(vals) != size ** 3 * 3:
        raise LutError("Số dòng dữ liệu (%d) không khớp cỡ LUT %d." % (len(vals) // 3, size))
    if any(dmax[i] <= dmin[i] for i in range(3)):
        raise LutError("DOMAIN_MAX phải lớn hơn DOMAIN_MIN.")
    return {"size": size, "dmin": dmin, "dmax": dmax, "data": vals, "title": title}


def payload(path):
    """Dữ liệu gửi cho giao diện: {size, dmin, dmax, b64, title}. b64 = float32 little-endian."""
    d = parse_cube(path)
    data = d["data"]
    if sys.byteorder != "little":
        data = array.array("f", data)
        data.byteswap()
    return {"size": d["size"], "dmin": d["dmin"], "dmax": d["dmax"], "title": d["title"] or os.path.splitext(os.path.basename(path))[0],
            "b64": base64.b64encode(data.tobytes()).decode("ascii")}
