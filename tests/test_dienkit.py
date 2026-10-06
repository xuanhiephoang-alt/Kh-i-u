import unittest
from pathlib import Path

from dienkit.calc import Load, design_current, pick_breaker, size_load, size_main, voltage_drop_pct
from dienkit.pricelist import Item, load_any, parse_price, search

EX = Path(__file__).parent.parent / "examples"


class CalcTests(unittest.TestCase):
    def test_current_3phase(self):
        l = Load("bom", 7.5, 3, 380, 0.85, 0.9)
        self.assertAlmostEqual(design_current(l), 14.9, 1)

    def test_current_1phase(self):
        self.assertAlmostEqual(design_current(Load("den", 2, 1, 220, 0.95)), 9.57, 2)

    def test_breaker_motor_margin(self):
        self.assertEqual(pick_breaker(14.9), 16)
        self.assertEqual(pick_breaker(14.9, motor=True), 20)  # 18.6A -> 20A
        self.assertIsNone(pick_breaker(5000))

    def test_cable_protected_by_breaker(self):
        r = size_load(Load("bom", 7.5, 3, 380, 0.85, 0.9, 25, motor=True))
        self.assertEqual((r.breaker_in, r.section), (20, 2.5))  # 1.5mm2 chi 17.5A < 20A
        self.assertGreaterEqual(r.iz, r.breaker_in)

    def test_voltage_drop_drives_section(self):
        near = size_load(Load("a", 22, 3, 380, 0.88, 0.92, 30))
        far = size_load(Load("a", 22, 3, 380, 0.88, 0.92, 300))
        self.assertGreater(far.section, near.section)
        self.assertLessEqual(far.vdrop_pct, 5.0)

    def test_voltage_drop_value(self):
        l = Load("x", 10, 3, 380, 0.8)
        # tinh tay: z=0.0225/16*0.8+0.00008*0.6=0.001173; dU=1.732*20*50*z=2.03V -> 0.535%
        self.assertAlmostEqual(voltage_drop_pct(20, 16, 50, l), 0.535, 3)

    def test_temperature_derating(self):
        l = Load("x", 7.5, 3, 380, 0.85, 0.9, 25, motor=True)
        hot = size_load(l, ambient=45)
        self.assertGreater(hot.section, size_load(l).section - 0.01)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            design_current(Load("x", 5, pf=0))

    def test_main(self):
        rs = [size_load(Load("a", 10, 3, 380, 0.85)), size_load(Load("b", 10, 3, 380, 0.85))]
        m = size_main(rs, ks=0.8)
        self.assertAlmostEqual(m["kw"], 16.0)
        self.assertIsNotNone(m["breaker"])


class PriceTests(unittest.TestCase):
    def test_parse_price(self):
        for raw, want in [("1.250.000", 1250000), ("1,250,000đ", 1250000), ("1.250,5", 1250.5),
                          ("12.5", 12.5), ("2.300.000 VNĐ", 2300000), (1250000, 1250000)]:
            self.assertEqual(parse_price(raw), want)
        self.assertIsNone(parse_price("lien he"))

    def test_search_exact_units(self):
        items = [Item("", "MCB 3P 63A 10kA", "cai", 980000), Item("", "MCB 3P 16A 6kA", "cai", 285000)]
        self.assertIsNone(search(items, "MCB 3P 10A")[0])  # 10A khong duoc khop 10kA
        self.assertEqual(search(items, "MCB 3P 16A")[0].price, 285000)

    def test_search_cable_cores(self):
        items = [Item("", "CVV 3x2.5", "m", 22000)]
        self.assertIsNone(search(items, "CVV 4x2.5")[0])

    def test_load_excel_and_pdf(self):
        x = load_any(EX / "bang_gia_mau.xlsx")
        p = load_any(EX / "bang_gia_cap_mau.pdf")
        self.assertEqual(len(x), 12)
        self.assertEqual(len(p), 9)
        self.assertEqual(search(p, "CVV 4x10")[0].price, 108000)


if __name__ == "__main__":
    unittest.main()


class FindByCodeTests(unittest.TestCase):
    def test_exact_code_only(self):
        from dienkit.pricelist import find_by_code
        items = [Item("", "Nguon Omron S8VK-C24024 240W", "cai", 2100000),
                 Item("", "Nguon Omron S8VK-C48024 480W", "cai", 3900000),
                 Item("", "Cam bien EX-L221-P (PNP)", "cai", 900000),
                 Item("", "Cam bien Panasonic EX L221", "cai", 850000)]
        self.assertEqual(find_by_code(items, "S8VK-C48024").price, 3900000)
        self.assertEqual(find_by_code(items, "EX-L221").price, 850000)  # khong lay ban -P
        self.assertIsNone(find_by_code(items, "S8VK-C96024"))
