"""Sinh ban ve dau noi I/O PLC (DXF, kem PDF xem truoc) tu bang I/O.

Bang I/O (CSV/Excel), cot:
    dia_chi  - dia chi PLC (X0, Y10, R000, %IX0.0...) - bat buoc
    loai     - DI / DO / AI / AO                        - bat buoc
    tag      - ten tag (PB_START, KM1...)
    mo_ta    - mo ta (co the co dau)
    thiet_bi - loai thiet bi: nut nhan, NC, cam bien, den, role/contactor, van, 4-20mA (bo trong = mac dinh)
    dau_day  - so domino (XT1:1). Bo trong = tu danh so.
    module   - ten module (vd: FX5-16EX). Doi module => sang trang moi.

Moi trang A3 ngang (420x297, ty le 1:1, don vi mm), toi da 16 diem/trang.
Cac trang dat canh nhau trong model space, cach nhau 450 mm.
"""
from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

from .pricelist import norm

PAGE_W, PAGE_H, PAGE_GAP = 420, 297, 450
ROWS_PER_PAGE = 16
ROW_PITCH = 12
Y_TOP = 255  # dong dau tien
TXT = 2.5    # chieu cao chu thuong

TYPE_ORDER = ["DI", "AI", "DO", "AO"]
TYPE_TITLE = {"DI": "ĐẦU VÀO SỐ (DI)", "AI": "ĐẦU VÀO TƯƠNG TỰ (AI)",
              "DO": "ĐẦU RA SỐ (DO)", "AO": "ĐẦU RA TƯƠNG TỰ (AO)"}
TYPE_TITLE_EN = {"DI": "PLC INPUT CIRCUIT", "AI": "PLC ANALOG INPUT CIRCUIT",
                 "DO": "PLC OUTPUT CIRCUIT", "AO": "PLC ANALOG OUTPUT CIRCUIT"}
TERMINAL_STRIP = {"DI": "XT1", "AI": "XT2", "DO": "XT3", "AO": "XT4"}
DEFAULT_SYMBOL = {"DI": "NO", "AI": "TX", "DO": "COIL", "AO": "TX"}

# tu khoa (khong dau) -> ky hieu
SYMBOL_KEYWORDS = [
    # noi sang dau vao/ra cua thiet bi khac (driver, camera...): chi ghi o cot thiet_bi
    ("SIG", ["tin hieu", "signal", "sig"]),
    ("NC", ["nc", "thuong dong", "dung", "stop", "estop", "e-stop", "khan"]),
    ("SENSOR", ["cam bien", "sensor", "pnp", "npn", "prox", "quang", "tiem can"]),
    ("LAMP", ["den", "lamp", "hl", "bao"]),
    ("VALVE", ["van", "valve", "yv", "sol", "cyl", "cylinder", "vacuum", "xy lanh", "xilanh"]),
    ("COIL", ["role", "ro le", "relay", "contactor", "khoi dong tu", "km", "ka", "cuon"]),
    ("TX", ["4-20", "4 20", "ma", "transmitter", "bien doi", "pt", "tt", "ft", "lt", "0-10"]),
    ("NO", ["no", "nut", "pb", "thuong mo", "cong tac", "sw", "limit", "hanh trinh"]),
]
# Khi doan ky hieu tu MO TA (cot thiet_bi trong), chi cho phep ky hieu hop voi loai diem:
# "U1 CYL UP" o dau vao la cong tac tu, o dau ra moi la van.
ALLOWED_FROM_DESC = {"DI": {"NC", "SENSOR"}, "AI": {"TX"}, "DO": {"LAMP", "VALVE", "COIL"}, "AO": {"TX"}}


def _match_symbol(text: str, allowed=None) -> str | None:
    d = norm(text)
    words = set(re.split(r"[\s/,_.()]+", d))
    for sym, keys in SYMBOL_KEYWORDS:
        if allowed is not None and sym not in allowed:
            continue
        for k in keys:
            if (" " in k or "-" in k) and k in d or k in words:
                return sym
    return None


@dataclass
class IOPoint:
    address: str
    kind: str
    tag: str = ""
    desc: str = ""
    device: str = ""
    terminal: str = ""
    module: str = ""
    designation: str = ""  # ky hieu thiet bi tren ban ve: SS2, LS1, SV0...

    @property
    def symbol(self) -> str:
        return (_match_symbol(self.device) if self.device else None) \
            or _match_symbol(self.desc, ALLOWED_FROM_DESC[self.kind]) or DEFAULT_SYMBOL[self.kind]

    @property
    def label(self) -> str:
        """Chu tren ky hieu: ky hieu thiet bi neu co, khong thi ten tag."""
        return self.designation or self.tag


# ---------------------------------------------------------------- doc bang I/O

def read_io(path: str | Path) -> list[IOPoint]:
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        ws = openpyxl.load_workbook(path, data_only=True).active
        rows = [["" if c is None else str(c) for c in r] for r in ws.iter_rows(values_only=True)]
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    head = [norm(h).replace(" ", "_") for h in rows[0]]
    for need in ("dia_chi", "loai"):
        if need not in head:
            raise ValueError(f"Bang I/O thieu cot '{need}' (co: {head})")
    pts = []
    for n, r in enumerate(rows[1:], 2):
        d = {k: (r[i].strip() if i < len(r) else "") for i, k in enumerate(head)}
        if not d["dia_chi"]:
            continue
        kind = d["loai"].upper()
        if kind not in TYPE_ORDER:
            raise ValueError(f"Dong {n}: loai '{d['loai']}' khong hop le (DI/DO/AI/AO)")
        pts.append(IOPoint(d["dia_chi"], kind, d.get("tag", ""), d.get("mo_ta", ""),
                           d.get("thiet_bi", ""), d.get("dau_day", ""), d.get("module", ""),
                           d.get("ky_hieu", "")))
    seen = set()
    for p in pts:
        if p.address in seen:
            raise ValueError(f"Trung dia chi: {p.address}")
        seen.add(p.address)
    return pts


def _number_terminals(group: list[IOPoint], kind: str) -> None:
    n = 0
    for p in group:
        if not p.terminal:
            n += 1
            p.terminal = f"{TERMINAL_STRIP[kind]}:{n}"


def _columns(points: list[IOPoint], kind: str, per_col: int, terminals: bool):
    group = [p for p in points if p.kind == kind]
    if terminals:
        _number_terminals(group, kind)
    modules: dict[str, list[IOPoint]] = {}
    for p in group:
        modules.setdefault(p.module, []).append(p)
    return [(mod, pts[i:i + per_col]) for mod, pts in modules.items() for i in range(0, len(pts), per_col)]


def paginate_columns(points: list[IOPoint], cols: int = 2, per_col: int = ROWS_PER_PAGE,
                     terminals: bool = True) -> list[tuple[str, list[tuple[str, list[IOPoint]]]]]:
    """Bo cuc nhieu cot: [(loai, [(module, diem), ...toi da `cols` cot])]. Moi cot chi 1 module."""
    pages = []
    for kind in TYPE_ORDER:
        columns = _columns(points, kind, per_col, terminals)
        pages += [(kind, columns[i:i + cols]) for i in range(0, len(columns), cols)]
    return pages


def paginate(points: list[IOPoint]) -> list[tuple[str, str, list[IOPoint]]]:
    """Nhom theo loai -> module -> toi da 16 diem. Tu danh so domino neu bo trong."""
    pages = []
    for kind in TYPE_ORDER:
        group = [p for p in points if p.kind == kind]
        _number_terminals(group, kind)
        modules: dict[str, list[IOPoint]] = {}
        for p in group:
            modules.setdefault(p.module, []).append(p)
        for mod, pts in modules.items():
            for i in range(0, len(pts), ROWS_PER_PAGE):
                pages.append((kind, mod, pts[i:i + ROWS_PER_PAGE]))
    return pages


# ---------------------------------------------------------------- ky hieu (block)

def _define_blocks(doc) -> None:
    """Ky hieu dat theo chieu ngang, chan trai (0,0), chan phai (20,0)."""
    # NO: luoi ho, khong cham tiep diem tinh
    b = doc.blocks.new("NO")
    b.add_line((0, 0), (6, 0)); b.add_line((6, 0), (14, 4)); b.add_line((14, 0), (20, 0))

    # NC: tiep diem tinh co vach dung, luoi cat qua vach
    b = doc.blocks.new("NC")
    b.add_line((0, 0), (6, 0)); b.add_line((6, 0), (17, 4)); b.add_line((14, 0), (20, 0))
    b.add_line((14, 0), (14, 4.5))

    b = doc.blocks.new("SENSOR")
    b.add_line((0, 0), (4, 0)); b.add_lwpolyline([(4, -3), (16, -3), (16, 3), (4, 3)], close=True)
    b.add_line((16, 0), (20, 0)); b.add_line((10, -3), (13, 0)); b.add_line((13, 0), (10, 3))

    b = doc.blocks.new("LAMP")
    b.add_line((0, 0), (6, 0)); b.add_circle((10, 0), 4); b.add_line((14, 0), (20, 0))
    b.add_line((7.17, 2.83), (12.83, -2.83)); b.add_line((7.17, -2.83), (12.83, 2.83))

    b = doc.blocks.new("COIL")
    b.add_line((0, 0), (5, 0)); b.add_lwpolyline([(5, -3), (15, -3), (15, 3), (5, 3)], close=True)
    b.add_line((15, 0), (20, 0))

    b = doc.blocks.new("VALVE")
    b.add_line((0, 0), (5, 0)); b.add_lwpolyline([(5, -3), (15, -3), (15, 3), (5, 3)], close=True)
    b.add_line((5, -3), (15, 3)); b.add_line((15, 0), (20, 0))

    b = doc.blocks.new("TX")
    b.add_line((0, 0), (5, 0)); b.add_circle((10, 0), 5); b.add_line((15, 0), (20, 0))
    b.add_text("mA", height=2.2).set_placement((10, 0), align=TextEntityAlignment.MIDDLE_CENTER)

    # SIG: noi sang thiet bi khac (mui ten), nhan = ky hieu thiet bi do (AMC1, CAM...)
    b = doc.blocks.new("SIG")
    b.add_line((0, 0), (20, 0))
    b.add_lwpolyline([(7, -2), (12, 0), (7, 2)], close=True)

    b = doc.blocks.new("TERM")
    b.add_circle((0, 0), 1.2)


# ---------------------------------------------------------------- ve trang

class Page:
    def __init__(self, msp, index: int):
        self.msp, self.ox = msp, index * PAGE_GAP

    def p(self, x, y):
        return (self.ox + x, y)

    def line(self, a, b, layer="WIRE"):
        self.msp.add_line(self.p(*a), self.p(*b), dxfattribs={"layer": layer})

    def text(self, s, x, y, h=TXT, align=TextEntityAlignment.LEFT, layer="TEXT"):
        if s:
            self.msp.add_text(str(s), height=h, dxfattribs={"layer": layer, "style": "VN"}
                              ).set_placement(self.p(x, y), align=align)

    def rect(self, x1, y1, x2, y2, layer):
        self.msp.add_lwpolyline([self.p(x1, y1), self.p(x2, y1), self.p(x2, y2), self.p(x1, y2)],
                                close=True, dxfattribs={"layer": layer})

    def insert(self, name, x, y, layer="SYMBOL"):
        self.msp.add_blockref(name, self.p(x, y), dxfattribs={"layer": layer})


@dataclass
class TitleInfo:
    project: str = ""        # ten du an (PROJECT NAME)
    code: str = ""           # ma du an (PROJECT CODE), vd TPV25A01
    designer: str = ""
    sheet_base: dict = None  # so to bat dau theo loai, vd {"DI": 300, "DO": 400}
    lang: str = "vi"         # "en": ten to kieu "E300_PLC INPUT CIRCUIT"

    def __post_init__(self):
        self.sheet_base = {"DI": 300, "AI": 500, "DO": 400, "AO": 600, **(self.sheet_base or {})}


def _frame(pg: Page, name: str, drawing_code: str, sheet: int, total: int, info: TitleInfo) -> None:
    pg.rect(10, 10, 410, 287, "FRAME")
    pg.rect(15, 15, 405, 282, "FRAME")
    # luoi vung 0-9 / A-F tren vien (de ghi tham chieu cheo kieu E300-B4)
    for i in range(10):
        x = 15 + i * 39
        if i:
            pg.line((x, 10), (x, 15), "FRAME"); pg.line((x, 282), (x, 287), "FRAME")
        for y in (12.5, 284.5):
            pg.text(str(i), x + 19.5, y, 2.5, TextEntityAlignment.MIDDLE_CENTER, "FRAME")
    for j, ch in enumerate("ABCDEF"):
        y = 282 - j * 44.5
        if j:
            pg.line((10, y), (15, y), "FRAME"); pg.line((405, y), (410, y), "FRAME")
        for x in (12.5, 407.5):
            pg.text(ch, x, y - 22.25, 2.5, TextEntityAlignment.MIDDLE_CENTER, "FRAME")
    # khung ten: goc phai duoi
    x0, y0, x1 = 215, 15, 405
    pg.rect(x0, y0, x1, 45, "FRAME")
    for y in (25, 35):
        pg.line((x0, y), (x1, y), "FRAME")
    pg.line((300, 35), (300, 45), "FRAME")
    pg.line((350, y0), (350, 35), "FRAME")
    pg.text(f"PROJECT CODE: {info.code}", x0 + 2, 40, 2.2)
    pg.text(f"PROJECT NAME: {info.project}", 302, 40, 2.2)
    pg.text(f"DRAWING NAME: {name}", x0 + 2, 30, 2.2)
    pg.text(f"DRAWING CODE: {drawing_code}", x0 + 2, 20, 2.2)
    pg.text(f"DESIGNER: {info.designer}", 352, 30, 2.0)
    pg.text(f"{date.today():%Y%m%d}   A3   {sheet}/{total}", 352, 20, 2.0)


def _draw_input_page(pg: Page, kind: str, module: str, pts: list[IOPoint], bus: str, com: str) -> None:
    """Bus nguon ben trai -> thiet bi -> domino -> chan module PLC (ben phai)."""
    rows = [Y_TOP - i * ROW_PITCH for i in range(len(pts))]
    y_com = rows[-1] - ROW_PITCH
    bus_x, sym_x, term_x, mod_x1, mod_x2 = 30, 60, 150, 220, 255
    pg.line((bus_x, rows[0] + 8), (bus_x, rows[-1]))
    pg.text(bus, bus_x, rows[0] + 10, align=TextEntityAlignment.BOTTOM_CENTER)
    pg.rect(mod_x1, y_com - 6, mod_x2, rows[0] + 7, "PLC")
    pg.text(module or "PLC", (mod_x1 + mod_x2) / 2, rows[0] + 9, align=TextEntityAlignment.BOTTOM_CENTER)
    for y, pt in zip(rows, pts):
        pg.line((bus_x, y), (sym_x, y))
        pg.insert(pt.symbol, sym_x, y)
        pg.text(pt.label, sym_x + 10, y + 5, 2.2, TextEntityAlignment.BOTTOM_CENTER)
        pg.line((sym_x + 20, y), (term_x - 1.2, y))
        pg.text(pt.address, (sym_x + 20 + term_x) / 2, y + 0.8, 2.0, TextEntityAlignment.BOTTOM_CENTER)
        pg.insert("TERM", term_x, y, "TERMINAL")
        pg.text(pt.terminal, term_x, y + 2, 2.0, TextEntityAlignment.BOTTOM_CENTER)
        pg.line((term_x + 1.2, y), (mod_x1, y))
        pg.text(pt.address, mod_x1 + 2, y, 2.5, TextEntityAlignment.MIDDLE_LEFT, "PLC")
    _text_cols(pg, pts, 265, {p.address: y for y, p in zip(rows, pts)})
    pg.text(_com_pin(kind, module), mod_x1 + 2, y_com, 2.5, TextEntityAlignment.MIDDLE_LEFT, "PLC")
    pg.line((mod_x1, y_com), (mod_x1 - 25, y_com))
    pg.text(com, mod_x1 - 27, y_com, 2.5, TextEntityAlignment.MIDDLE_RIGHT)
    _legend(pg)


def _draw_output_page(pg: Page, kind: str, module: str, pts: list[IOPoint], bus: str, com: str) -> None:
    """Chan module PLC (ben trai) -> domino -> tai -> bus nguon ben phai."""
    rows = [Y_TOP - i * ROW_PITCH for i in range(len(pts))]
    y_com = rows[-1] - ROW_PITCH
    mod_x1, mod_x2, term_x, sym_x, bus_x = 30, 65, 130, 180, 245
    pg.rect(mod_x1, y_com - 6, mod_x2, rows[0] + 7, "PLC")
    pg.text(module or "PLC", (mod_x1 + mod_x2) / 2, rows[0] + 9, align=TextEntityAlignment.BOTTOM_CENTER)
    pg.line((bus_x, rows[0] + 8), (bus_x, rows[-1]))
    pg.text(bus, bus_x, rows[0] + 10, align=TextEntityAlignment.BOTTOM_CENTER)
    for y, pt in zip(rows, pts):
        pg.text(pt.address, mod_x2 - 2, y, 2.5, TextEntityAlignment.MIDDLE_RIGHT, "PLC")
        pg.line((mod_x2, y), (term_x - 1.2, y))
        pg.text(pt.address, (mod_x2 + term_x) / 2, y + 0.8, 2.0, TextEntityAlignment.BOTTOM_CENTER)
        pg.insert("TERM", term_x, y, "TERMINAL")
        pg.text(pt.terminal, term_x, y + 2, 2.0, TextEntityAlignment.BOTTOM_CENTER)
        pg.line((term_x + 1.2, y), (sym_x, y))
        pg.insert(pt.symbol, sym_x, y)
        pg.text(pt.label, sym_x + 10, y + 5, 2.2, TextEntityAlignment.BOTTOM_CENTER)
        pg.line((sym_x + 20, y), (bus_x, y))
    _text_cols(pg, pts, 255, {p.address: y for y, p in zip(rows, pts)})
    pg.text(_com_pin(kind, module), mod_x2 - 2, y_com, 2.5, TextEntityAlignment.MIDDLE_RIGHT, "PLC")
    pg.line((mod_x2, y_com), (mod_x2 + 25, y_com))
    pg.text(com, mod_x2 + 27, y_com, 2.5, TextEntityAlignment.MIDDLE_LEFT)
    _legend(pg)


def _text_cols(pg: Page, pts: list[IOPoint], x: float, y_of) -> None:
    """3 cot chu: dia chi | tag | mo ta. Cot mo ta lui theo tag dai nhat de khong de chu."""
    tag_w = max((len(p.tag) for p in pts), default=0) * 2.1  # do rong chu hoa cao 2.5 (do tren ban in)
    x_desc = x + 20 + max(30.0, tag_w + 4)
    for pt in pts:
        y = y_of[pt.address]
        pg.text(pt.address, x, y, 2.5, TextEntityAlignment.MIDDLE_LEFT)
        pg.text(pt.tag, x + 20, y, 2.5, TextEntityAlignment.MIDDLE_LEFT)
        pg.text(pt.desc, x_desc, y, 2.5, TextEntityAlignment.MIDDLE_LEFT)


COL_W = 195  # bo cuc 2 cot: moi cot rong 195 mm, cot 1 bat dau x=18, cot 2 x=213


def _col_input(pg: Page, cx: float, kind: str, module: str, pts: list[IOPoint], bus: str, com: str,
               terminals: bool) -> None:
    """Cot dau vao gon: bus | thiet bi | (domino) | module | mo ta."""
    rows = [Y_TOP - i * ROW_PITCH for i in range(len(pts))]
    y_com = rows[-1] - ROW_PITCH
    bus_x, sym_x, term_x, m1, m2 = cx + 6, cx + 30, cx + 92, cx + 112, cx + 131
    pg.line((bus_x, rows[0] + 8), (bus_x, rows[-1]))
    pg.text(bus, bus_x, rows[0] + 10, 2.2, TextEntityAlignment.BOTTOM_CENTER)
    pg.rect(m1, y_com - 6, m2, rows[0] + 7, "PLC")
    pg.text(module or "PLC", (m1 + m2) / 2, rows[0] + 9, 2.2, TextEntityAlignment.BOTTOM_CENTER)
    for y, pt in zip(rows, pts):
        pg.line((bus_x, y), (sym_x, y))
        pg.insert(pt.symbol, sym_x, y)
        pg.text(pt.label, sym_x + 10, y + 5, 2.0, TextEntityAlignment.BOTTOM_CENTER)
        if terminals:
            pg.line((sym_x + 20, y), (term_x - 1.2, y))
            pg.insert("TERM", term_x, y, "TERMINAL")
            pg.text(pt.terminal, term_x, y + 2, 1.8, TextEntityAlignment.BOTTOM_CENTER)
            pg.line((term_x + 1.2, y), (m1, y))
        else:
            pg.line((sym_x + 20, y), (m1, y))
        pg.text(pt.address, (sym_x + 20 + (term_x if terminals else m1)) / 2, y + 0.8, 1.8,
                TextEntityAlignment.BOTTOM_CENTER)
        pg.text(pt.address, m1 + 1.5, y, 2.2, TextEntityAlignment.MIDDLE_LEFT, "PLC")
        pg.text(pt.desc, m2 + 3, y, 2.2, TextEntityAlignment.MIDDLE_LEFT)
    pg.text(_com_pin(kind, module), m1 + 1.5, y_com, 2.2, TextEntityAlignment.MIDDLE_LEFT, "PLC")
    pg.line((m1, y_com), (m1 - 20, y_com))
    pg.text(com, m1 - 22, y_com, 2.2, TextEntityAlignment.MIDDLE_RIGHT)


def _col_output(pg: Page, cx: float, kind: str, module: str, pts: list[IOPoint], bus: str, com: str,
                terminals: bool) -> None:
    """Cot dau ra gon: mo ta | module | (domino) | tai | bus."""
    rows = [Y_TOP - i * ROW_PITCH for i in range(len(pts))]
    y_com = rows[-1] - ROW_PITCH
    m1, m2, term_x, sym_x, bus_x = cx + 50, cx + 69, cx + 98, cx + 128, cx + 178
    pg.rect(m1, y_com - 6, m2, rows[0] + 7, "PLC")
    pg.text(module or "PLC", (m1 + m2) / 2, rows[0] + 9, 2.2, TextEntityAlignment.BOTTOM_CENTER)
    pg.line((bus_x, rows[0] + 8), (bus_x, rows[-1]))
    pg.text(bus, bus_x, rows[0] + 10, 2.2, TextEntityAlignment.BOTTOM_CENTER)
    for y, pt in zip(rows, pts):
        pg.text(pt.desc, m1 - 2, y, 2.2, TextEntityAlignment.MIDDLE_RIGHT)
        pg.text(pt.address, m2 - 1.5, y, 2.2, TextEntityAlignment.MIDDLE_RIGHT, "PLC")
        if terminals:
            pg.line((m2, y), (term_x - 1.2, y))
            pg.insert("TERM", term_x, y, "TERMINAL")
            pg.text(pt.terminal, term_x, y + 2, 1.8, TextEntityAlignment.BOTTOM_CENTER)
            pg.line((term_x + 1.2, y), (sym_x, y))
        else:
            pg.line((m2, y), (sym_x, y))
        pg.text(pt.address, (m2 + (term_x if terminals else sym_x)) / 2, y + 0.8, 1.8,
                TextEntityAlignment.BOTTOM_CENTER)
        pg.insert(pt.symbol, sym_x, y)
        pg.text(pt.label, sym_x + 10, y + 5, 2.0, TextEntityAlignment.BOTTOM_CENTER)
        pg.line((sym_x + 20, y), (bus_x, y))
    pg.text(_com_pin(kind, module), m2 - 1.5, y_com, 2.2, TextEntityAlignment.MIDDLE_RIGHT, "PLC")
    pg.line((m2, y_com), (m2 + 20, y_com))
    pg.text(com, m2 + 22, y_com, 2.2, TextEntityAlignment.MIDDLE_LEFT)


def _com_pin(kind: str, module: str) -> str:
    # Mitsubishi FX5: chan chung dau vao ghi la S/S
    return "S/S" if kind == "DI" and module.upper().startswith("FX5") else "COM"


def _legend(pg: Page) -> None:
    pg.text("Ghi chú: số trên dây = số dây (theo địa chỉ PLC); XTn:m = số domino; chân COM nối theo nhãn nguồn.",
            20, 50, 2.2)


# ---------------------------------------------------------------- xuat file

# Chieu nguon: (nhan bus phia thiet bi, nhan chan COM)
# DI pnp (source input, Mitsubishi: S/S noi 0V): thiet bi lay +24V, COM ve 0V. npn: nguoc lai.
# DO source (vd FX5U-..MT/ESS): COM +24V, tai ve 0V. sink (vd FX5U-..MT/ES): COM 0V, tai lay +24V.
INPUT_MODES = {"pnp": ("+24VDC", "0VDC"), "npn": ("0VDC", "+24VDC")}
OUTPUT_MODES = {"source": ("0VDC", "+24VDC"), "sink": ("+24VDC", "0VDC")}


def check_polarity(points: list[IOPoint], di_mode: str = "npn") -> list[str]:
    """Canh bao thiet bi ghi PNP/NPN trai voi kieu dau vao da chon."""
    other = "npn" if di_mode == "pnp" else "pnp"
    return [f"{p.address} ({p.tag}): thiet bi ghi '{p.device}' nhung dau vao dang ve kieu {di_mode.upper()}"
            for p in points if p.kind == "DI" and other in norm(p.device).split()]


def _modes(kind: str, di_mode: str, do_mode: str) -> tuple[str, str]:
    if kind in ("DI", "AI"):
        return INPUT_MODES[di_mode] if kind == "DI" else INPUT_MODES["pnp"]  # AI 2 day luon lay +24V
    return OUTPUT_MODES[do_mode] if kind == "DO" else OUTPUT_MODES["source"]


def _sheet_name(info: "TitleInfo", kind: str, num: str, first: str, last: str) -> str:
    return f"{num}_{TYPE_TITLE_EN[kind]}" if info.lang == "en" else f"{num}_{TYPE_TITLE[kind]} {first}-{last}"


def build_dxf(points: list[IOPoint], info: TitleInfo | None = None,
              di_mode: str = "npn", do_mode: str = "sink", columns: int = 1, terminals: bool = True):
    """Mac dinh sink/sink nhu FX5U-..MT/ES: dau vao S/S noi +24V (thiet bi dong 0V), tai lay +24V, COM ve 0V.
    columns=2: 2 cot x 16 diem moi to (nhu ban ve TPV25A01). terminals=False: thiet bi noi thang vao PLC."""
    info = info or TitleInfo()
    if columns == 2:
        return _build_2col(points, info, di_mode, do_mode, terminals)
    doc = ezdxf.new("R2010", setup=True, units=4)  # 4 = mm
    doc.styles.add("VN", font="arial.ttf")
    for name, color in [("FRAME", 7), ("WIRE", 1), ("SYMBOL", 3), ("TEXT", 7), ("TERMINAL", 5), ("PLC", 4)]:
        doc.layers.add(name, color=color)
    _define_blocks(doc)
    msp = doc.modelspace()
    pages = paginate(points)
    seq = {k: 0 for k in TYPE_ORDER}
    for i, (kind, module, pts) in enumerate(pages):
        pg = Page(msp, i)
        first, last = pts[0].address, pts[-1].address
        num = f"E{info.sheet_base[kind] + seq[kind]}"
        seq[kind] += 1
        code = f"{info.code}-{num}" if info.code else num
        _frame(pg, _sheet_name(info, kind, num, first, last), code, i + 1, len(pages), info)
        if kind in ("DI", "AI"):
            # AI 2 day 4-20mA luon lay nguon +24V
            bus, com = INPUT_MODES[di_mode] if kind == "DI" else INPUT_MODES["pnp"]
            _draw_input_page(pg, kind, module, pts, bus, com)
        else:
            bus, com = OUTPUT_MODES[do_mode] if kind == "DO" else OUTPUT_MODES["source"]
            _draw_output_page(pg, kind, module, pts, bus, com)
    return doc, len(pages)


def _new_doc():
    doc = ezdxf.new("R2010", setup=True, units=4)  # 4 = mm
    doc.styles.add("VN", font="arial.ttf")
    for name, color in [("FRAME", 7), ("WIRE", 1), ("SYMBOL", 3), ("TEXT", 7), ("TERMINAL", 5), ("PLC", 4)]:
        doc.layers.add(name, color=color)
    _define_blocks(doc)
    return doc


def _build_2col(points, info, di_mode, do_mode, terminals):
    doc = _new_doc()
    msp = doc.modelspace()
    pages = paginate_columns(points, 2, ROWS_PER_PAGE, terminals)
    seq = {k: 0 for k in TYPE_ORDER}
    for i, (kind, cols) in enumerate(pages):
        pg = Page(msp, i)
        num = f"E{info.sheet_base[kind] + seq[kind]}"
        seq[kind] += 1
        first, last = cols[0][1][0].address, cols[-1][1][-1].address
        _frame(pg, _sheet_name(info, kind, num, first, last), f"{info.code}-{num}" if info.code else num,
               i + 1, len(pages), info)
        bus, com = _modes(kind, di_mode, do_mode)
        draw = _col_input if kind in ("DI", "AI") else _col_output
        for c, (module, pts) in enumerate(cols):
            draw(pg, 18 + c * COL_W, kind, module, pts, bus, com, terminals)
        if terminals:
            _legend(pg)
    return doc, len(pages)


_MPL_ALIGN = {
    TextEntityAlignment.LEFT: ("left", "baseline"),
    TextEntityAlignment.BOTTOM_CENTER: ("center", "bottom"),
    TextEntityAlignment.MIDDLE_LEFT: ("left", "center"),
    TextEntityAlignment.MIDDLE_RIGHT: ("right", "center"),
    TextEntityAlignment.MIDDLE_CENTER: ("center", "center"),
}


def export_pdf(doc, n_pages: int, path: str | Path) -> None:
    """Moi trang DXF -> 1 trang PDF A3 (can matplotlib)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration, TextPolicy
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    # Duong net ve bang ezdxf; chu ve lai bang chu that cua matplotlib de PDF tim kiem/doc lai duoc
    # (ezdxf bien chu thanh duong cong, PDF se khong co lop chu).
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK,
                        text_policy=TextPolicy.IGNORE)
    msp = doc.modelspace()
    texts = list(msp.query("TEXT"))
    for ins in msp.query("INSERT"):
        texts += [e for e in ins.virtual_entities() if e.dxftype() == "TEXT"]
    with PdfPages(path) as pdf:
        for i in range(n_pages):
            fig = plt.figure(figsize=(16.54, 11.69))  # A3 inch
            ax = fig.add_axes([0, 0, 1, 1])
            Frontend(RenderContext(doc), MatplotlibBackend(ax, adjust_figure=False), config=cfg).draw_layout(msp)
            x0 = i * PAGE_GAP
            for t in texts:
                align, p1, _ = t.get_placement()
                if not x0 - 5 <= p1.x <= x0 + PAGE_W + 5:
                    continue
                ha, va = _MPL_ALIGN.get(align, ("left", "baseline"))
                # 1 mm = 72/25.4 pt; chieu cao chu hoa ~0.72 co chu
                ax.text(p1.x, p1.y, t.dxf.text, fontsize=t.dxf.height * 72 / 25.4 / 0.72, ha=ha, va=va,
                        family="DejaVu Sans", color="black")
            ax.set_xlim(i * PAGE_GAP, i * PAGE_GAP + PAGE_W)
            ax.set_ylim(0, PAGE_H)
            ax.set_aspect("equal", adjustable="box")
            ax.axis("off")
            pdf.savefig(fig)
            plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m dienkit.iodraw", description="Sinh ban ve dau noi I/O PLC (DXF/PDF)")
    ap.add_argument("io", help="Bang I/O (.csv/.xlsx)")
    ap.add_argument("-o", "--out", default="io.dxf")
    ap.add_argument("--pdf", help="Xuat them PDF (vd: io.pdf)")
    ap.add_argument("--project", default="", help="Ten du an (PROJECT NAME)")
    ap.add_argument("--code", default="", help="Ma du an (PROJECT CODE), vd TPV25A01 -> to TPV25A01-E300")
    ap.add_argument("--designer", "--drawer", default="", help="Nguoi thiet ke")
    ap.add_argument("--so-to-di", type=int, default=300, help="So to dau tien cua DI (mac dinh E300)")
    ap.add_argument("--so-to-do", type=int, default=400, help="So to dau tien cua DO (mac dinh E400)")
    ap.add_argument("--hai-cot", action="store_true", help="2 cot x 16 diem moi to (32 diem/to)")
    ap.add_argument("--khong-domino", action="store_true", help="Thiet bi noi thang vao PLC, khong ve domino")
    ap.add_argument("--en", action="store_true", help="Ten to tieng Anh: E300_PLC INPUT CIRCUIT")
    ap.add_argument("--di", default="npn", choices=list(INPUT_MODES),
                    help="Dau vao: npn = sink, S/S noi +24V (mac dinh) | pnp = source, S/S noi 0V")
    ap.add_argument("--do", default="sink", choices=list(OUTPUT_MODES),
                    help="Dau ra transistor: sink = COM noi 0V, vd FX5U-..MT/ES (mac dinh) | source = ../ESS")
    a = ap.parse_args(argv)
    info = TitleInfo(a.project, a.code, a.designer, {"DI": a.so_to_di, "DO": a.so_to_do}, "en" if a.en else "vi")

    pts = read_io(a.io)
    for w in check_polarity(pts, a.di):
        print("CANH BAO:", w)
    doc, n = build_dxf(pts, info, a.di, a.do, 2 if a.hai_cot else 1, not a.khong_domino)
    doc.saveas(a.out)
    counts = {k: sum(p.kind == k for p in pts) for k in TYPE_ORDER}
    print(f"Da ghi {a.out}: {n} to, " + ", ".join(f"{k}={v}" for k, v in counts.items() if v))
    if a.pdf:
        export_pdf(doc, n, a.pdf)
        print(f"Da ghi {a.pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
