"""Generate assets/icon.ico for the app."""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui     import QPixmap, QPainter, QColor, QPen, QPainterPath, QFont, QImage
from PySide6.QtCore    import Qt

app = QApplication(sys.argv)

ASSETS = Path("assets")
ASSETS.mkdir(exist_ok=True)


def draw_shield(size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    w = h = size
    pad = size * 0.06

    path = QPainterPath()
    path.moveTo(w * 0.50, pad)
    path.lineTo(w - pad,  h * 0.22)
    path.lineTo(w - pad,  h * 0.55)
    path.cubicTo(w - pad,  h * 0.80, w * 0.72, h * 0.93, w * 0.50, h * 0.99)
    path.cubicTo(w * 0.28, h * 0.93, pad,       h * 0.80, pad,       h * 0.55)
    path.lineTo(pad, h * 0.22)
    path.closeSubpath()

    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#16161e"))
    p.drawPath(path)

    pen = QPen(QColor("#ff7220"), size * 0.055)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)

    p.setPen(QColor("#ff7220"))
    font = QFont("Segoe UI", int(size * 0.40), QFont.Bold)
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignCenter, "S")
    p.end()
    return pix


# Save PNG versions
sizes = [16, 24, 32, 48, 64, 128, 256]
images = []
for s in sizes:
    pix = draw_shield(s)
    img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    images.append((s, img))
    pix.save(str(ASSETS / f"icon_{s}.png"))
    print(f"Saved icon_{s}.png")

# Build ICO manually (Windows ICO format)
import struct, io

def to_ico(images: list):
    """Pack multiple ARGB32 QImages into a .ico file."""
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)   # reserved, type=1 (ICO), count

    # Collect PNG-encoded images (modern ICO supports PNG for sizes >= 256)
    # For smaller sizes use BMP DIB
    entries = []
    data_chunks = []
    offset = 6 + count * 16   # header + directory entries

    for size, img in images:
        buf = io.BytesIO()
        pix = QPixmap.fromImage(img)
        ba_arr = pix.toImage()

        # Save as PNG via Qt into bytes
        from PySide6.QtCore import QByteArray, QBuffer
        ba = QByteArray()
        qbuf = QBuffer(ba)
        qbuf.open(QBuffer.OpenModeFlag.WriteOnly)
        pix.save(qbuf, "PNG")
        qbuf.close()
        png_bytes = bytes(ba)

        entries.append((size, len(png_bytes), offset))
        data_chunks.append(png_bytes)
        offset += len(png_bytes)

    with open(ASSETS / "icon.ico", "wb") as f:
        f.write(header)
        for (size, data_len, data_offset) in entries:
            w = 0 if size >= 256 else size
            h = 0 if size >= 256 else size
            f.write(struct.pack("<BBBBHHII",
                w, h,       # width, height (0 = 256)
                0,          # color count
                0,          # reserved
                1,          # planes
                32,         # bit count
                data_len,   # size of image data
                data_offset # offset
            ))
        for chunk in data_chunks:
            f.write(chunk)

    print(f"Saved icon.ico ({len(images)} sizes)")

to_ico(images)
print("Done.")
