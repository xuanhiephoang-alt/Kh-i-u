import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from dienkit.gx3 import compare, compare_text, io_ranges, module_of, read_project, write_tags_csv
from dienkit.pdfio import extract_io, extract_models


def make_gx3(folder: Path) -> Path:
    """Project GX Works3 gia lap: chi gom cac bang ma dienkit.gx3 doc."""
    dc = folder / "aa_DC.db"
    with sqlite3.connect(dc) as c:
        c.execute("CREATE TABLE DEVICE_DATA(SEQ INTEGER PRIMARY KEY, DevCode INTEGER, ExtCode INTEGER, ExtNo INTEGER,"
                  " IsLocal INTEGER, DevNoHigh INTEGER, DevNoLow INTEGER, BitNo INTEGER)")
        c.execute("CREATE TABLE COMMENT_DATA(SEQ INTEGER PRIMARY KEY, DeviceSEQ INTEGER, CmtNo INTEGER, CmtData TEXT, DelFlag INTEGER)")
        rows = [(16, 0, "READY PB"), (16, 2, "CHECK NG BOX"), (16, 8, "WORK INPUT"), (16, 40, "U1 INPUT1 CYL UP"),
                (17, 6, "END OF LINEAR CLOSE"), (17, 7, "END OF LINEAR OPEN"), (1, 100, "AUTO MODE"),
                (2, 400, "Always ON"), (32, 10, "COUNTER"), (99, 1, "???")]
        for i, (code, n, t) in enumerate(rows, 1):
            c.execute("INSERT INTO DEVICE_DATA VALUES (?,?,0,0,0,0,?,0)", (i, code, n))
            c.execute("INSERT INTO COMMENT_DATA VALUES (?,?,6,?,NULL)", (i, i, t))
    ld = folder / "bb_LDDB.db"
    with sqlite3.connect(ld) as c:
        c.execute("CREATE TABLE LadderBlocks (id text primary key, pos REAL, blocktype INTEGER, data TEXT,"
                  " rowsize INTEGER, translated INTEGER, ConvTarget INTEGER)")
        e = "e{s=ce{op=ct{op=#:ct=a:as=[as{vt=Abl}]}:args=[d{s=#:a=%d:vt=nn}]}:pos=0,0}"
        blocks = [
            # X0, X10 (luu 0x10 = 16), M100 -> Y6
            "V1:4:1:1:1:1:a:X:a:X:a:M:c:Y:cb{fg=fg{es=[" + ":".join(e % n for n in (0, 16, 100, 6)) + "]}}",
            # MOV K1 D10: hang so K_1 + gia tri phai bo qua
            "V1:3:1:3:1:a:M:MOV:K_1:1:D:cb{fg=fg{es=[" + ":".join(e % n for n in (100, 10)) + "]}}",
            "V1:0:end{type=end:dim=1x1}",
        ]
        for i, b in enumerate(blocks):
            c.execute("INSERT INTO LadderBlocks VALUES (?,?,0,?,1,1,0)", (f"g{i}", i, b))
    cfg = folder / "UnitConfig.dat"
    cfg.write_bytes(b"\x00\x01FX5-32ER/ES\x00\x00FX5U-80MT/ES\x00")
    gx3 = folder / "p.gx3"
    with zipfile.ZipFile(gx3, "w") as z:
        z.write(dc, "aa_DC.db")
        z.write(ld, "bb_LDDB.db")
        z.write(cfg, "UnitConfig.dat")
    return gx3


def make_pdf(path: Path) -> None:
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=landscape(A3))
    c.setFont("Helvetica", 8)
    for y, a, d in [(700, "X0", "READY ON"), (670, "X2", "SPARE"), (640, "X10", "WORK INPUT"),
                    (610, "Y6", "END OF LINEAR OPEN"), (580, "Y7", "END OF LINEAR CLOSE")]:
        c.drawString(400, y, a)
        c.drawString(440, y, d)
        c.drawString(250, y + 6, a)                 # nhan so day: khong co mo ta canh -> bo qua
        c.drawString(150, y + 6, "(E031-E2)")
    c.drawString(440, 552, "PRESSURE SENSOR")       # mo ta 2 dong
    c.drawString(400, 543, "X44")
    c.drawString(440, 543, "INPUT 1")
    c.drawString(900, 40, "TPV25A01-E300")
    c.drawString(100, 400, "(S8VK-C48024)  (EX-L221) (EX-L221) (LIG1) (E000-D4)")
    c.save()


class Gx3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.p = read_project(make_gx3(Path(cls.tmp.name)))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_comments_octal_and_unknown(self):
        c = self.p.comments
        self.assertEqual(c["X10"], "WORK INPUT")   # DevNoLow 8 -> X10 bat phan
        self.assertEqual(c["X50"], "U1 INPUT1 CYL UP")
        self.assertEqual(c["SM400"], "Always ON")
        self.assertEqual(self.p.unknown_codes, {99: 1})

    def test_ladder_usage(self):
        self.assertTrue({"X0", "X10", "M100", "Y6", "D10"} <= self.p.used)
        self.assertNotIn("X2", self.p.used)
        self.assertEqual((self.p.rungs, self.p.rungs_skipped), (3, 0))

    def test_models_cpu_first_and_ranges(self):
        self.assertEqual(self.p.models, ["FX5U-80MT/ES", "FX5-32ER/ES"])
        r = io_ranges(self.p.models)
        self.assertEqual(module_of("X47", r), "FX5U-80MT/ES")
        self.assertEqual(module_of("X50", r), "FX5-32ER/ES")
        self.assertEqual(module_of("Y67", r), "FX5-32ER/ES")
        self.assertEqual(module_of("X70", r), "")

    def test_tags_skip_system(self):
        with tempfile.TemporaryDirectory() as d:
            n = write_tags_csv(Path(d, "t.csv"), self.p, "PLC1")
            text = Path(d, "t.csv").read_text(encoding="utf-8-sig")
        self.assertEqual(n, 8)
        self.assertNotIn("SM400", text)
        self.assertIn("PLC1,COUNTER,D10,INT", text)

    def test_compare_with_drawing(self):
        with tempfile.TemporaryDirectory() as d:
            pdf = Path(d, "dwg.pdf")
            make_pdf(pdf)
            dwg = extract_io(pdf)
            models = [m.model for m in extract_models(pdf)]
        self.assertEqual(dwg["X44"].desc, "PRESSURE SENSOR INPUT 1")
        self.assertEqual(dwg["X0"].sheet, "E300")
        self.assertEqual(models, ["EX-L221", "S8VK-C48024"])
        res = {r.address: r for r in compare(self.p, dwg)}
        self.assertEqual(res["X10"].level, "KHOP")
        self.assertEqual(res["X0"].level, "GAN_GIONG")
        self.assertEqual(res["X2"].level, "KHAC")
        self.assertEqual((res["Y6"].level, res["Y7"].level), ("DAO_CHO", "DAO_CHO"))
        self.assertEqual(res["X50"].level, "THIEU_BAN_VE")
        self.assertEqual(res["X44"].level, "THIEU_CHU_THICH")

    def test_antonyms(self):
        self.assertEqual(compare_text("CYL UP", "CYL DOWN")[0], "NGUOC_NGHIA")
        self.assertEqual(compare_text("U1 ROTATE CYL ORG", "U1 ROTATE CYL ORG")[0], "KHOP")


if __name__ == "__main__":
    unittest.main()
