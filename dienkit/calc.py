"""Tinh toan dien: dong dien, chon aptomat, tiet dien cap, sut ap.

Bang dong cho phep la gia tri THAM KHAO (IEC 60364-5-52, cap dong Cu cach dien PVC 70C,
3 day mang tai, nhiet do moi truong 30C). Hay doi chieu voi TCVN 9207 / catalogue nha san xuat
(vi du Cadivi) truoc khi dung cho ho so thiet ke. Co the ghi de bang tham so `ampacity`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Tiet dien chuan (mm2)
SECTIONS = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240]

# Dong cho phep (A), Cu/PVC, 3 day mang tai.
AMPACITY_TABLES = {
    # Phuong phap C: cap di ho/ kep truc tiep tren tuong, mang cap
    "C": dict(zip(SECTIONS, [17.5, 24, 32, 41, 57, 76, 96, 119, 144, 184, 223, 259, 294, 341, 403])),
    # Phuong phap B1: cap di trong ong tren tuong (chi den 120 mm2 trong bang nay)
    "B1": dict(zip(SECTIONS[:12], [13.5, 18, 24, 31, 42, 56, 73, 89, 108, 136, 164, 188])),
}

# He so hieu chinh nhiet do moi truong (cach dien PVC)
TEMP_FACTOR_PVC = {25: 1.03, 30: 1.0, 35: 0.94, 40: 0.87, 45: 0.79, 50: 0.71, 55: 0.61, 60: 0.5}

# Day dong dien dinh muc aptomat tieu chuan (A)
BREAKER_SIZES = [6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 320, 400, 500, 630, 800, 1000, 1250, 1600]

RHO_CU = 0.0225  # ohm.mm2/m o 70C
X_PER_M = 0.00008  # ohm/m (dien khang tham khao)


@dataclass
class Load:
    name: str
    kw: float
    phases: int = 3          # 1 hoac 3
    voltage: float = 380.0   # V (day-day neu 3 pha, day-trung tinh neu 1 pha: 220)
    pf: float = 0.85
    eff: float = 1.0         # hieu suat (dong co ~0.9)
    length_m: float = 20.0
    kd: float = 1.0          # he so nhu cau
    motor: bool = False
    cores: int = 0           # so loi cap (0 = tu dong: 3P->4, 1P->3)


@dataclass
class Result:
    load: Load
    kva: float
    ib: float                # dong thiet ke (A)
    breaker_in: int | None
    breaker_poles: int
    section: float | None
    vdrop_pct: float | None
    iz: float | None
    note: str = ""


def design_current(load: Load) -> float:
    """Dong thiet ke Ib (A) co tinh he so nhu cau."""
    if load.kw < 0 or not (0 < load.pf <= 1) or not (0 < load.eff <= 1) or load.voltage <= 0:
        raise ValueError(f"Thong so khong hop le: {load.name}")
    p_w = load.kw * 1000 * load.kd
    k = math.sqrt(3) if load.phases == 3 else 1.0
    return p_w / (k * load.voltage * load.pf * load.eff)


def apparent_kva(load: Load) -> float:
    return load.kw * load.kd / (load.pf * load.eff)


def pick_breaker(ib: float, motor: bool = False) -> int | None:
    """Aptomat nho nhat co In >= Ib (x1.25 voi dong co: quy tac kinh nghiem)."""
    need = ib * (1.25 if motor else 1.0)
    for size in BREAKER_SIZES:
        if size >= need:
            return size
    return None


def temp_factor(ambient: float) -> float:
    temps = sorted(TEMP_FACTOR_PVC)
    if ambient <= temps[0]:
        return TEMP_FACTOR_PVC[temps[0]]
    for t in temps:
        if ambient <= t:
            return TEMP_FACTOR_PVC[t]
    raise ValueError("Nhiet do moi truong vuot bang he so (>60C)")


def voltage_drop_pct(ib: float, section: float, length_m: float, load: Load) -> float:
    sin = math.sqrt(1 - load.pf ** 2)
    z = (RHO_CU / section) * load.pf + X_PER_M * sin
    k = math.sqrt(3) if load.phases == 3 else 2.0
    return 100 * k * ib * length_m * z / load.voltage


def pick_cable(ib: float, in_a: int, load: Load, *, method: str = "C", ambient: float = 30,
               grouping: float = 1.0, max_vdrop_pct: float = 5.0,
               ampacity: dict[float, float] | None = None):
    """Chon tiet dien nho nhat thoa Iz >= In (bao ve qua tai) va sut ap <= gioi han.
    Tra ve (section, iz, vdrop_pct) hoac (None, None, None) neu khong co tiet dien phu hop."""
    table = ampacity or AMPACITY_TABLES[method]
    k = temp_factor(ambient) * grouping
    for s in sorted(table):
        iz = table[s] * k
        if iz >= in_a and voltage_drop_pct(ib, s, load.length_m, load) <= max_vdrop_pct:
            return s, iz, voltage_drop_pct(ib, s, load.length_m, load)
    return None, None, None


def size_load(load: Load, **cable_opts) -> Result:
    ib = design_current(load)
    in_a = pick_breaker(ib, load.motor)
    poles = 3 if load.phases == 3 else 2
    kva = apparent_kva(load)
    if in_a is None:
        return Result(load, kva, ib, None, poles, None, None, None, "Dong qua lon: can tach nhieu mach")
    s, iz, vd = pick_cable(ib, in_a, load, **cable_opts)
    note = "" if s else "Khong co tiet dien <=240mm2 dat yeu cau: can cap song song/giam chieu dai"
    return Result(load, kva, ib, in_a, poles, s, vd, iz, note)


def size_main(results: list[Result], ks: float = 0.8, voltage: float = 380.0) -> dict:
    """Tai tong: tong kVA x he so dong thoi Ks -> dong tong va aptomat tong."""
    kva = sum(r.kva for r in results) * ks
    kw = sum(r.load.kw * r.load.kd for r in results) * ks
    i = kva * 1000 / (math.sqrt(3) * voltage)
    return {"kw": kw, "kva": kva, "i": i, "breaker": pick_breaker(i), "ks": ks}
