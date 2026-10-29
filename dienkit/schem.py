"""Ve so do mach dien nhieu to (DXF + PDF) theo kieu bo ban ve may: nguon chinh, mach thiet bi, I/O.

Dung chung khung ten, luoi o, Page va xuat PDF voi dienkit.iodraw. Toa do tinh bang mm tren to A3
(420x297), vung ve 15..405 x 45..282. Cac ham chi la ky hieu/thao tac co ban; noi dung tung to do
script du an tu ghep.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ezdxf.enums import TextEntityAlignment as TA

from .iodraw import (PAGE_GAP, IOPoint, Page, TitleInfo, _frame, _new_doc, build_dxf, export_pdf,  # noqa: F401
                     zone)


class Sheet:
    """Mot to ban ve + cac ky hieu mach dien."""

    def __init__(self, msp, index: int):
        self.pg = Page(msp, index)
        self.msp = msp

    # ---------------------------------------------------------------- co ban
    def text(self, s, x, y, h=2.2, align=TA.MIDDLE_LEFT, layer="TEXT", rot=0):
        self.pg.text(s, x, y, h, align, layer, rot)

    def wire(self, *pts, layer="WIRE"):
        """Duong day noi cac diem (x, y)."""
        for a, b in zip(pts, pts[1:]):
            self.pg.line(a, b, layer)

    def cable(self, *pts, width=1.2):
        """Cap nhieu loi (net dam), vd cap motor/encoder."""
        self.msp.add_lwpolyline([self.pg.p(*p) for p in pts], dxfattribs={"layer": "WIRE", "const_width": width})

    def rect(self, x1, y1, x2, y2, layer="SYMBOL"):
        self.pg.rect(x1, y1, x2, y2, layer)

    def circle(self, x, y, r, layer="SYMBOL"):
        self.msp.add_circle(self.pg.p(x, y), r, dxfattribs={"layer": layer})

    def dot(self, x, y):
        """Diem noi day (tron dac)."""
        h = self.msp.add_hatch(color=7, dxfattribs={"layer": "WIRE"})
        h.paths.add_edge_path().add_arc(self.pg.p(x, y), 0.55, 0, 360)
        self.circle(x, y, 0.55, "WIRE")

    def terminal(self, x, y, label="", side="left"):
        """Dau cuc (tron rong), vd TB0."""
        self.circle(x, y, 1.2, "TERMINAL")
        if label:
            if side == "up":
                self.text(label, x, y + 2.2, 1.8, TA.BOTTOM_CENTER)
            else:
                self.text(label, x - 2, y, 1.8, TA.MIDDLE_RIGHT)

    def wno(self, x, y, label, vertical=False):
        """So day: gach cheo nho tren day + chu."""
        self.pg.line((x - 0.9, y - 1.2), (x + 0.9, y + 1.2), "WIRE")
        if vertical:
            self.text(label, x - 1.5, y, 1.7, TA.MIDDLE_RIGHT)
        else:
            self.text(label, x, y + 1.6, 1.7, TA.BOTTOM_CENTER)

    def ref_out(self, x, y, label, ref):
        """Day di sang to khac:  label ▷ (ref)  - mui ten tai x (dau day den x)."""
        self.msp.add_lwpolyline([self.pg.p(x, y + 1.3), self.pg.p(x + 3, y), self.pg.p(x, y - 1.3)],
                                close=True, dxfattribs={"layer": "WIRE"})
        if label:
            self.text(label, x - 1, y + 0.6, 2.0, TA.BOTTOM_RIGHT)
        if ref:
            self.text(f"({ref})", x + 4, y, 2.0, TA.MIDDLE_LEFT)

    def ref_in(self, x, y, label, ref):
        """Day den tu to khac:  (ref) ▷ label  - mui ten ket thuc tai x (day bat dau tu x)."""
        self.msp.add_lwpolyline([self.pg.p(x - 3, y + 1.3), self.pg.p(x, y), self.pg.p(x - 3, y - 1.3)],
                                close=True, dxfattribs={"layer": "WIRE"})
        if label:
            self.text(label, x + 1, y + 0.6, 2.0, TA.BOTTOM_LEFT)
        if ref:
            self.text(f"({ref})", x - 4, y, 2.0, TA.MIDDLE_RIGHT)

    # ---------------------------------------------------------------- thiet bi
    def cp2(self, x, y_a, y_b, name, rating):
        """Aptomat/CP 2 cuc nam ngang tren 2 day y_a (tren) va y_b (duoi): day toi x, noi tiep tu x+8."""
        for y in (y_a, y_b):
            self.pg.line((x - 0.8, y - 0.8), (x + 0.8, y + 0.8), "SYMBOL")
            self.pg.line((x - 0.8, y + 0.8), (x + 0.8, y - 0.8), "SYMBOL")
            self.pg.line((x, y), (x + 7, y + 3.2), "SYMBOL")
        self.msp.add_line(self.pg.p(x + 3.5, y_b + 1.6), self.pg.p(x + 3.5, y_a + 1.6),
                          dxfattribs={"layer": "SYMBOL", "linetype": "DASHED"})
        self.text(name, x + 3.5, y_a + 4.5, 2.2, TA.BOTTOM_CENTER)
        self.text(rating, x + 3.5, y_b - 2, 2.0, TA.TOP_CENTER)

    def elcb2(self, x_a, x_b, y, name, spec, model=""):
        """ELCB 2 cuc tren 2 day dung x_a, x_b: day tren den y, day duoi tiep tu y-20."""
        for x in (x_a, x_b):
            self.pg.line((x - 0.8, y - 0.8), (x + 0.8, y + 0.8), "SYMBOL")
            self.pg.line((x - 0.8, y + 0.8), (x + 0.8, y - 0.8), "SYMBOL")
            self.pg.line((x, y), (x - 3, y - 7), "SYMBOL")
            self.wire((x, y - 8), (x, y - 10))
            self.rect(x - 2.5, y - 17, x + 2.5, y - 10)
            self.text("Id", x, y - 13.5, 2.0, TA.MIDDLE_CENTER)
            self.wire((x, y - 17), (x, y - 20))
        self.msp.add_line(self.pg.p(x_a - 1.5, y - 3.5), self.pg.p(x_b - 1.5, y - 3.5),
                          dxfattribs={"layer": "SYMBOL", "linetype": "DASHED"})
        self.text(name, x_b + 5, y - 2, 2.2, TA.MIDDLE_LEFT)
        self.text(spec, x_b + 5, y - 6.5, 2.0, TA.MIDDLE_LEFT)
        if model:
            self.text(f"({model})", x_b + 5, y - 10.5, 1.6, TA.MIDDLE_LEFT)

    def fuse(self, x, y, name, rating):
        """Cau chi nam ngang tu x den x+8."""
        self.rect(x, y - 1.2, x + 8, y + 1.2)
        self.wire((x - 0.01, y), (x, y))
        self.text(name, x + 4, y + 3, 2.2, TA.BOTTOM_CENTER)
        self.text(f"({rating})", x + 4, y - 2.5, 2.0, TA.TOP_CENTER)

    def lamp(self, x, y, name, model="", r=2.2):
        """Den bao: tam (x+r, y), day vao x, ra x+2r."""
        cx = x + r
        self.circle(cx, y, r)
        d = r * 0.7
        self.pg.line((cx - d, y - d), (cx + d, y + d), "SYMBOL")
        self.pg.line((cx - d, y + d), (cx + d, y - d), "SYMBOL")
        self.text(name, cx, y + r + 2, 2.2, TA.BOTTOM_CENTER)
        if model:
            self.text(model, cx, y - r - 1.5, 1.4, TA.TOP_CENTER)

    def ground(self, x, y):
        """Ky hieu noi dat, chan tai (x, y) di xuong."""
        self.wire((x, y), (x, y - 3))
        for i, w in enumerate((3, 2, 1)):
            self.pg.line((x - w, y - 3 - i * 0.9), (x + w, y - 3 - i * 0.9), "SYMBOL")

    def psu(self, x, y, name, model, power):
        """Bo nguon AC/DC: hop 22x22 goc trai duoi (x, y). Chan L,N,E ben trai; +,- ben phai.
        Tra ve toa do cac chan."""
        self.rect(x, y, x + 22, y + 22)
        self.pg.line((x, y), (x + 22, y + 22), "SYMBOL")
        self.text("1~", x + 4, y + 17, 2.6, TA.MIDDLE_LEFT)
        self.text("=", x + 17, y + 5, 3, TA.MIDDLE_CENTER)
        self.text(name, x + 11, y + 26, 2.2, TA.BOTTOM_CENTER)
        self.text(power, x + 11, y + 23.2, 2.0, TA.BOTTOM_CENTER)
        self.text(f"({model})", x + 11, y - 2, 2.0, TA.TOP_CENTER)
        pins = {"L": (x, y + 17), "N": (x, y + 11), "E": (x, y + 4), "+": (x + 22, y + 17), "-": (x + 22, y + 11)}
        for k, (px, py) in pins.items():
            self.text(k, px + (1 if px == x else -1), py, 1.7, TA.MIDDLE_LEFT if px == x else TA.MIDDLE_RIGHT)
        return pins

    def coil(self, x, y, name="", pins=("", "")):
        """Cuon day relay nam ngang 8x4, tu x den x+8; so chan 2 ben."""
        self.rect(x, y - 2, x + 8, y + 2)
        if name:
            self.text(name, x + 4, y + 3.5, 2.0, TA.BOTTOM_CENTER)
        if pins[0]:
            self.text(pins[0], x - 0.8, y + 0.6, 1.6, TA.BOTTOM_RIGHT)
        if pins[1]:
            self.text(pins[1], x + 8.8, y + 0.6, 1.6, TA.BOTTOM_LEFT)

    def contact(self, x, y, kind="NO", name="", pins=("", ""), vertical=False):
        """Tiep diem NO/NC (block cua iodraw, dai 20). Ngang: tu x den x+20. Dung: tu y xuong y-20."""
        if vertical:
            self.pg.insert(kind, x, y, rot=-90)
            if name:
                self.text(name, x - 4, y - 10, 2.0, TA.MIDDLE_RIGHT)
            if pins[0]:
                self.text(pins[0], x + 1.2, y - 4, 1.6, TA.MIDDLE_LEFT)
            if pins[1]:
                self.text(pins[1], x + 1.2, y - 16, 1.6, TA.MIDDLE_LEFT)
        else:
            self.pg.insert(kind, x, y)
            if name:
                self.text(name, x + 10, y + 5, 2.0, TA.BOTTOM_CENTER)
            if pins[0]:
                self.text(pins[0], x + 3, y - 1, 1.6, TA.TOP_CENTER)
            if pins[1]:
                self.text(pins[1], x + 17, y - 1, 1.6, TA.TOP_CENTER)

    def device(self, x1, y1, x2, y2, title_lines, h=2.2):
        """Hop thiet bi + cac dong tieu de phia tren (vd '-AMC1', 'ABSODEX DRIVER', '(AX9000TS)')."""
        self.rect(x1, y1, x2, y2)
        for i, t in enumerate(reversed(title_lines)):
            self.text(t, (x1 + x2) / 2, y2 + 2 + i * (h + 1.2), h, TA.BOTTOM_CENTER)

    def pin_column(self, x, y_top, pins, side="left", pitch=7, w=26):
        """Cot chan dau noi trong hop: pins = [(so chan, ten)]. side='left': diem noi o x, o chu ben phai.
        So chan chua biet: ghi (khoa, chu hien thi), vd (("IN1", "?"), "START").
        Tra ve {so chan hoac khoa: (x, y)} diem noi day."""
        out = {}
        for i, (key, name) in enumerate(pins):
            key, no = key if isinstance(key, tuple) else (key, key)
            y = y_top - i * pitch
            if side == "left":
                self.rect(x, y - pitch / 2 + 0.6, x + w, y + pitch / 2 - 0.6)
                self.pg.line((x + 7, y - pitch / 2 + 0.6), (x + 7, y + pitch / 2 - 0.6), "SYMBOL")
                self.text(str(no), x + 1, y, 1.9, TA.MIDDLE_LEFT)
                self.text(name, x + 8, y, 1.9, TA.MIDDLE_LEFT)
            else:
                self.rect(x - w, y - pitch / 2 + 0.6, x, y + pitch / 2 - 0.6)
                self.pg.line((x - 7, y - pitch / 2 + 0.6), (x - 7, y + pitch / 2 - 0.6), "SYMBOL")
                self.text(str(no), x - 1, y, 1.9, TA.MIDDLE_RIGHT)
                self.text(name, x - 8, y, 1.9, TA.MIDDLE_RIGHT)
            out[key] = (x, y)
        return out

    def table(self, x, y_top, widths, rows, h=2.0, row_h=6.5, header=True):
        """Bang: rows = [[o1, o2, ...]]; dong dau la tieu de neu header."""
        xs = [x]
        for w in widths:
            xs.append(xs[-1] + w)
        n = len(rows)
        for i in range(n + 1):
            self.pg.line((xs[0], y_top - i * row_h), (xs[-1], y_top - i * row_h), "FRAME")
        for xx in xs:
            self.pg.line((xx, y_top), (xx, y_top - n * row_h), "FRAME")
        for i, row in enumerate(rows):
            y = y_top - (i + 0.5) * row_h
            for j, cell in enumerate(row):
                if cell in (None, ""):
                    continue
                if header and i == 0:
                    self.text(cell, (xs[j] + xs[j + 1]) / 2, y, h, TA.MIDDLE_CENTER)
                else:
                    self.text(cell, xs[j] + 1.2, y, h, TA.MIDDLE_LEFT)


@dataclass
class DrawingSet:
    """Bo ban ve: danh sach to (ma, ten, ham ve) + to I/O tu iodraw; danh so to tu dong."""
    info: TitleInfo
    sheets: list = field(default_factory=list)   # (ma to, ten to, ham ve(Sheet))
    io_points: list[IOPoint] = field(default_factory=list)
    io_after: str = ""                            # chen cac to I/O sau to co ma nay

    def code(self, num: str) -> str:
        return f"{self.info.code}-{num}" if self.info.code else num

    def io_sheet_list(self):
        from .iodraw import ROWS_PER_PAGE, _sheet_name, paginate_columns, sheet_numbers
        pages = paginate_columns(self.io_points, 2, ROWS_PER_PAGE, False)
        out = []
        for num, (kind, cols) in zip(sheet_numbers(pages, self.info), pages):
            out.append((num, _sheet_name(self.info, kind, num, cols[0][1][0].address, cols[-1][1][-1].address)))
        return out

    def order(self):
        """Danh muc to theo thu tu in: [(ma, ten)]."""
        lst = [(n, t) for n, t, _ in self.sheets]
        if self.io_points:
            i = next((k + 1 for k, (n, _) in enumerate(lst) if n == self.io_after), len(lst))
            lst[i:i] = self.io_sheet_list()
        return lst

    def build(self):
        doc = _new_doc()
        if "DASHED" not in doc.linetypes:
            doc.linetypes.add("DASHED", pattern=[3.0, 2.0, -1.0])
        msp = doc.modelspace()
        order = self.order()
        total = len(order)
        draw = {n: (t, f) for n, t, f in self.sheets}
        io_done = False
        for idx, (num, name) in enumerate(order):
            if num in draw:
                sh = Sheet(msp, idx)
                _frame(sh.pg, name, self.code(num), idx + 1, total, self.info)
                draw[num][1](sh)
            elif not io_done:
                build_dxf(self.io_points, self.info, columns=2, terminals=False, doc=doc, start=idx, total=total)
                io_done = True
        return doc, total
