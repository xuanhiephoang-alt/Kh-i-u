import tempfile
import unittest
from collections import Counter
from pathlib import Path

import ezdxf

from dienkit.iodraw import IOPoint, TitleInfo, build_dxf, check_polarity, paginate, paginate_columns, read_io

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
        doc, n = build_dxf(pts, TitleInfo("Test", "TPV00", "QA"), di_mode="pnp", do_mode="source")
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


    def test_symbol_from_description_respects_kind(self):
        self.assertEqual(IOPoint("Y34", "DO", desc="U1 VACUUM INPUT 1").symbol, "VALVE")
        self.assertEqual(IOPoint("Y40", "DO", desc="U1 INPUT 1 CYL UP").symbol, "VALVE")
        self.assertEqual(IOPoint("X50", "DI", desc="U1 INPUT1 CYL UP").symbol, "NO")  # cong tac tu, khong phai van
        self.assertEqual(IOPoint("X1", "DI", desc="EMG STOP PB").symbol, "NC")
        self.assertEqual(IOPoint("Y64", "DO", desc="TOWER LAMP RED").symbol, "LAMP")
        self.assertEqual(IOPoint("X44", "DI", desc="PRESSURE SENSOR INPUT 1").symbol, "SENSOR")
        # cot thiet_bi luon uu tien hon mo ta
        self.assertEqual(IOPoint("Y0", "DO", desc="READY LAMP", device="role").symbol, "COIL")

    def test_designation_sheet_codes_and_default_sink(self):
        pts = [IOPoint("X0", "DI", tag="PB", designation="PBRD"), IOPoint("Y0", "DO", tag="L")]
        doc, n = build_dxf(pts, TitleInfo("May", "TPV25A01", "HX"))
        t = texts(doc)
        self.assertIn("PBRD", t)
        self.assertIn("DRAWING CODE: TPV25A01-E300", t)
        self.assertIn("DRAWING CODE: TPV25A01-E400", t)
        # sink: dau vao S/S (COM) noi +24V, thiet bi dong 0V; dau ra COM 0V, tai lay +24V
        self.assertEqual(t.count("+24VDC"), 2)
        self.assertEqual(t.count("0VDC"), 2)

    def test_two_columns_like_tpv25a01(self):
        # CPU 40 vao (X0-X47) + mo rong 16 (X50-X67): E300 = X0-X37, E301 = X40-X47 | X50-X67
        pts = [IOPoint(f"X{n:o}", "DI", module="FX5U-80MT/ES") for n in range(40)] + \
              [IOPoint(f"X{n:o}", "DI", module="FX5-32ER/ES") for n in range(0o50, 0o70)] + \
              [IOPoint("Y0", "DO", desc="START SIGNAL", device="tín hiệu", designation="AMC1", module="FX5U-80MT/ES")]
        pages = paginate_columns(pts, terminals=False)
        self.assertEqual([[(m, p[0].address, p[-1].address) for m, p in cols] for _, cols in pages], [
            [("FX5U-80MT/ES", "X0", "X17"), ("FX5U-80MT/ES", "X20", "X37")],
            [("FX5U-80MT/ES", "X40", "X47"), ("FX5-32ER/ES", "X50", "X67")],
            [("FX5U-80MT/ES", "Y0", "Y0")]])
        self.assertEqual(pts[0].terminal, "")  # khong domino
        doc, n = build_dxf(pts, TitleInfo("M", "TPV25A01", lang="en"), columns=2, terminals=False)
        self.assertEqual(n, 3)
        t = texts(doc)
        self.assertIn("DRAWING NAME: E301_PLC INPUT CIRCUIT", t)
        self.assertIn("DRAWING CODE: TPV25A01-E400", t)
        self.assertEqual(t.count("S/S"), 4)  # moi cot dau vao FX5 co chan S/S
        self.assertNotIn("TERM", [e.dxf.name for e in doc.modelspace().query("INSERT")])
        self.assertIn("SIG", [e.dxf.name for e in doc.modelspace().query("INSERT")])

    def test_pdf_has_real_text_readable_by_pdfio(self):
        from dienkit.iodraw import export_pdf
        from dienkit.pdfio import extract_io
        pts = [IOPoint("X0", "DI", desc="READY ON", module="FX5U-80MT/ES"),
               IOPoint("Y6", "DO", desc="END OF LINEAR CLOSE", designation="SV1", device="van", module="FX5U-80MT/ES")]
        doc, n = build_dxf(pts, TitleInfo("M", "TPV25A01", lang="en"), columns=2, terminals=False)
        with tempfile.TemporaryDirectory() as d:
            pdf = Path(d, "io.pdf")
            export_pdf(doc, n, pdf)
            io = extract_io(pdf)
        self.assertEqual(io["X0"].desc, "READY ON")
        self.assertEqual(io["Y6"].desc, "END OF LINEAR CLOSE")
        self.assertEqual(io["Y6"].sheet, "E400")


if __name__ == "__main__":
    unittest.main()
