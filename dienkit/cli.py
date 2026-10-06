import argparse
import sys

from .bom import build_bom, read_loads, write_excel
from .calc import size_load, size_main
from .pricelist import load_many


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="dienkit", description="Tinh tai, chon cap/aptomat, lap BOM + chi phi")
    p.add_argument("loads", help="File danh sach tai (.csv/.xlsx)")
    p.add_argument("-p", "--prices", nargs="*", default=[], help="Bang gia (.xlsx/.csv/.pdf), co the nhieu file")
    p.add_argument("-o", "--out", default="bom.xlsx")
    p.add_argument("--method", default="C", choices=["B1", "C"], help="Cach lap dat cap (B1: trong ong, C: mang cap)")
    p.add_argument("--ambient", type=float, default=30, help="Nhiet do moi truong (C)")
    p.add_argument("--grouping", type=float, default=1.0, help="He so nhom cap")
    p.add_argument("--max-vdrop", type=float, default=5.0, help="Sut ap toi da (%%)")
    p.add_argument("--ks", type=float, default=0.8, help="He so dong thoi tong")
    p.add_argument("--vat", type=float, default=0.10)
    p.add_argument("--cable-prefix", default="CVV", help="Ma loai cap trong bang gia (CVV, CXV...)")
    a = p.parse_args(argv)

    loads = read_loads(a.loads)
    if not loads:
        print("Khong co tai nao trong file", file=sys.stderr)
        return 1
    results = [size_load(l, method=a.method, ambient=a.ambient, grouping=a.grouping,
                         max_vdrop_pct=a.max_vdrop) for l in loads]
    main_r = size_main(results, a.ks)
    items = load_many(a.prices) if a.prices else []
    print(f"Doc duoc {len(items)} mat hang tu {len(a.prices)} bang gia")
    lines = build_bom(results, items, a.cable_prefix)
    write_excel(a.out, results, main_r, lines, a.vat)

    for r in results:
        print(f"{r.load.name:<22} Ib={r.ib:7.1f}A  CB={r.breaker_in}A  cap={r.section}mm2  {r.note}")
    print(f"TONG: {main_r['kw']:.1f}kW {main_r['kva']:.1f}kVA {main_r['i']:.0f}A  CB tong={main_r['breaker']}A")
    miss = sum(1 for l in lines if not l.item)
    print(f"Da ghi {a.out}  ({len(lines)} dong vat tu, {miss} dong khong co gia)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
