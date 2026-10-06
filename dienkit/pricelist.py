"""Doc bang gia vat tu tu Excel/CSV/PDF va tim kiem mat hang theo tu khoa."""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Item:
    code: str
    name: str
    unit: str
    price: float | None
    source: str = ""

    @property
    def text(self) -> str:
        return f"{self.code} {self.name}"


def strip_accents(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s: str) -> str:
    return strip_accents(str(s or "")).lower().strip()


# Tu khoa nhan dien tieu de cot (khong dau, viet thuong)
HEADER_ALIASES = {
    "code": ["ma", "ma hang", "ma vt", "ma sp", "code", "model", "part no", "item"],
    "name": ["ten", "ten hang", "ten vat tu", "ten thiet bi", "mo ta", "quy cach", "description", "name"],
    "unit": ["dvt", "don vi", "don vi tinh", "unit", "uom"],
    "price": ["don gia", "gia", "gia ban", "gia niem yet", "price", "unit price", "thanh tien/dvt"],
}


def _field_of(header: str) -> str | None:
    h = norm(header)
    h = re.sub(r"\(.*?\)", "", h).strip()
    for field, aliases in HEADER_ALIASES.items():
        if h in aliases:
            return field
    # khop mot phan: uu tien don gia/ten truoc ma
    for field in ("price", "unit", "name", "code"):
        for a in HEADER_ALIASES[field]:
            if len(a) > 3 and a in h:
                return field
    return None


def parse_price(value) -> float | None:
    """'1.250.000', '1,250,000d', '1.250,5', 1250000 -> float. Tra None neu khong doc duoc."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"[^\d.,]", "", str(value))
    if not re.search(r"\d", s):
        return None
    s = s.strip(".,")
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        s = s.replace(thou, "").replace(dec, ".")
    elif "." in s or "," in s:
        sep = "." if "." in s else ","
        parts = s.split(sep)
        if len(parts) > 2 or len(parts[-1]) == 3:  # nhom 3 chu so => ngan cach hang nghin
            s = "".join(parts)
        else:
            s = ".".join(parts)
    try:
        return float(s)
    except ValueError:
        return None


def _map_header(row) -> dict[int, str] | None:
    mapping: dict[int, str] = {}
    for i, cell in enumerate(row):
        if cell is None:
            continue
        f = _field_of(str(cell))
        if f and f not in mapping.values():
            mapping[i] = f
    # can it nhat ten + gia
    if "name" in mapping.values() and "price" in mapping.values():
        return mapping
    return None


def _rows_to_items(rows, source: str) -> list[Item]:
    items: list[Item] = []
    mapping = None
    for row in rows:
        row = list(row)
        m = _map_header(row)
        if m:
            mapping = m
            continue
        if not mapping:
            continue
        rec = {f: (row[i] if i < len(row) else None) for i, f in mapping.items()}
        name = str(rec.get("name") or "").replace("\n", " ").strip()
        price = parse_price(rec.get("price"))
        if not name or price is None:
            continue
        items.append(Item(str(rec.get("code") or "").strip(), name,
                          str(rec.get("unit") or "").strip(), price, source))
    return items


def load_excel(path: str | Path) -> list[Item]:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    items: list[Item] = []
    for ws in wb.worksheets:
        items += _rows_to_items(ws.iter_rows(values_only=True), f"{Path(path).name}:{ws.title}")
    return items


def load_csv(path: str | Path) -> list[Item]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return _rows_to_items(csv.reader(f), Path(path).name)


# dong van ban PDF: "... ten hang ...  DVT  1.250.000"
_LINE_RE = re.compile(r"^(?P<name>.+?)\s+(?P<unit>[^\W\d_]{1,6}\.?)\s+(?P<price>\d[\d.,]{2,})\s*(?:đ|d|vnd|vnđ)?$", re.I)


def load_pdf(path: str | Path) -> list[Item]:
    import pdfplumber
    items: list[Item] = []
    src = Path(path).name
    with pdfplumber.open(path) as pdf:
        for n, page in enumerate(pdf.pages, 1):
            got = []
            for table in page.extract_tables():
                got += _rows_to_items(table, f"{src}:p{n}")
            if not got:  # PDF khong co duong ke bang: thu doc theo dong
                for line in (page.extract_text() or "").splitlines():
                    m = _LINE_RE.match(line.strip())
                    p = parse_price(m["price"]) if m else None
                    if m and p is not None:
                        got.append(Item("", m["name"].strip(), m["unit"], p, f"{src}:p{n}"))
            items += got
    return items


def load_any(path: str | Path) -> list[Item]:
    ext = Path(path).suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        return load_excel(path)
    if ext == ".csv":
        return load_csv(path)
    if ext == ".pdf":
        return load_pdf(path)
    raise ValueError(f"Dinh dang khong ho tro: {ext} (dung .xlsx/.csv/.pdf)")


def load_many(paths) -> list[Item]:
    items: list[Item] = []
    for p in paths:
        items += load_any(p)
    return items


# Token giu nguyen don vi/kich thuoc: "63A" -> "63a", "10kA" -> "10ka", "4x2.5" -> "4x2.5"
_TOK = re.compile(r"\d+(?:[.,]\d+)?(?:x\d+(?:[.,]\d+)?)*[a-z]*|[a-z]+")


def tokens(s: str) -> list[str]:
    return [t.replace(",", ".") for t in _TOK.findall(norm(s))]


def search(items: list[Item], query: str, min_score: float = 0.75) -> tuple[Item | None, float]:
    """Tim mat hang khop nhat. Diem = ti le token cua `query` xuat hien trong mat hang.
    Token so kem don vi phai trung nguyen (10a khac 10ka, 4x2.5 khac 3x2.5). Hoa diem: lay gia thap hon."""
    q = tokens(query)
    if not q:
        return None, 0.0
    best, best_score = None, 0.0
    for it in items:
        toks = set(tokens(it.text))
        score = sum(t in toks for t in q) / len(q)
        if score > best_score or (score == best_score and best and it.price is not None
                                  and (best.price is None or it.price < best.price)):
            best, best_score = it, score
    return (best, best_score) if best_score >= min_score else (None, best_score)


def find_by_code(items: list[Item], code: str) -> Item | None:
    """Tim theo MA HANG chinh xac (vd S8VK-C48024): bo qua dau cach/gach nhung khong chap nhan ma gan giong
    (S8VK-C24024 khac S8VK-C48024) hay co hau to (EX-L221 khac EX-L221-P). Nhieu mat hang trung ma: lay gia thap nhat."""
    parts = re.findall(r"[A-Z0-9]+", strip_accents(code).upper())
    if not parts:
        return None
    pat = re.compile(r"(?<![A-Z0-9])" + r"[^A-Z0-9]*".join(map(re.escape, parts)) + r"(?![A-Z0-9]|[-/][A-Z0-9])")  # EX-L221 khong khop EX-L221-P
    hits = [it for it in items if pat.search(strip_accents(it.text).upper())]
    return min(hits, key=lambda it: it.price if it.price is not None else float("inf"), default=None)
