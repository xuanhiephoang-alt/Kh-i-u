import tempfile
import unittest
from collections import Counter
from pathlib import Path

import ezdxf

from dienkit.iodraw import IOPoint, build_dxf, check_polarity, paginate, read_io

EX = Path(__file__).parent.parent / "examples"


def texts(doc):
    return [e.dxf.text for e in doc.modelspace().query("TEXT")]


class IODrawTests(unittest.TestCase):
    def test_symbol_from_device(self):
        cases = {"nút nhấn NO": "NO", "nút dừng NC": "NC", "E-stop NC": "NC", "cảm biến PNP": "SENSOR",
                 "đèn": "LAMP", "contactor": "COIL", "rơ le": "COIL", "van điện từ": "VALVE", "4-20mA": "TX"}
        for dev, sym in cases.items():
            self.assertEqual(IOPoint("X0", "DI", device=dev).symbol, sym, dev)
        self.assertEqual(IOPoint("X0", "DI").symbol, "NO")
        self.assertEqual(IOPoint("Y0", "DO").symbol, "COIL")

    def test_paginate_by_type_module_and_16_rows(self):
        pts = [IOPoint(f"X{i}", "DI", module="A") for i in range(20)] + [IOPoint("Y0", "DO", module="A")]
        pages = paginate(pts)
        self.assertEqual([(k, len(p)) for k, _, p in pages], [("DI", 16), ("DI", 4), ("DO", 1)])
        self.assertEqual(pts[16].terminal, "XT1:17")  # domino danh so lien tuc qua cac trang
        self.assertEqual(pts[-1].terminal, "XT3:1")

    def test_read_io_rejects_bad_rows(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "io.csv")
            f.write_text("dia_chi,loai\nX0,DI\nX0,DI\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Trung dia chi"):
                read_io(f)
            f.write_text("dia_chi,loai\nX0,XX\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "khong hop le"):
                read_io(f)

    def test_example_drawing(self):
        pts = read_io(EX / "io_list.csv")
        doc, n = build_dxf(pts, "Test", "QA")
        self.assertEqual(n, 5)  # DI 16 + DI 2 (module khac) + AI + DO + AO
        with tempfile.TemporaryDirectory() as d:
            out = Path(d, "io.dxf")
            doc.saveas(out)
            doc = ezdxf.readfile(out)
        self.assertEqual(len(doc.audit().errors), 0)
        t = texts(doc)
        for p in pts:
            self.assertIn(p.address, t)
            self.assertIn(p.terminal, t)
            if p.desc:
                self.assertIn(p.desc, t)
        syms = Counter(e.dxf.name for e in doc.modelspace().query("INSERT") if e.dxf.name != "TERM")
        self.assertEqual(sum(syms.values()), len(pts))
        self.assertEqual(syms["NC"], 4)  # PB_STOP, ESTOP, OL_M1, DOOR

    def test_polarity_labels_and_warning(self):
        pts = [IOPoint("X0", "DI", device="cảm biến NPN"), IOPoint("Y0", "DO")]
        self.assertEqual(len(check_polarity(pts, "pnp")), 1)
        self.assertEqual(check_polarity(pts, "npn"), [])
        doc, _ = build_dxf(pts, di_mode="npn", do_mode="sink")
        t = texts(doc)
        # npn: bus thiet bi 0V, COM +24V; sink: tai lay +24V, COM 0V
        self.assertEqual(t.count("+24VDC"), 2)
        self.assertEqual(t.count("0VDC"), 2)


if __name__ == "__main__":
    unittest.main()
