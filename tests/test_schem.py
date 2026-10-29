import unittest

from dienkit.iodraw import IOPoint, TitleInfo, positions_2col, zone
from dienkit.schem import DrawingSet

EN = TitleInfo(project="P", code="AB01", lang="en", style="laymac", company="LAYMAC", designer="X")


def texts(doc):
    return [e.dxf.text for e in doc.modelspace().query("TEXT")]


def io_pts():
    pts = [IOPoint(f"R{i:03d}", "DI", desc=f"in {i}", module="KV-N60AT") for i in range(16)]
    pts += [IOPoint("R500", "DO", desc="sig", device="tín hiệu", designation="AMC1", xref="E031-B3",
                    module="KV-N60AT"),
            IOPoint("R501", "DO", desc="van", device="van", module="KV-N60AT")]
    return pts


class SchemTests(unittest.TestCase):
    def test_zone(self):
        self.assertEqual(zone(16, 281), "A0")
        self.assertEqual(zone(300, 190), "C7")
        self.assertEqual(zone(404, 46), "F9")

    def test_positions_2col(self):
        pos = positions_2col(io_pts(), EN)
        self.assertEqual(pos["R000"], "E300-A1")
        self.assertTrue(pos["R500"].startswith("E400-"))

    def test_drawing_set_order_and_numbering(self):
        def draw(sh):
            sh.text("HELLO", 50, 200)
            pins = sh.pin_column(100, 200, [(1, "A"), (("k", "?"), "B")])
            self.assertEqual(set(pins), {1, "k"})
            sh.cp2(150, 200, 191, "CP1", "5A")
            sh.ref_out(300, 200, "R1", "E035")

        ds = DrawingSet(EN, sheets=[("S000", "S000_TITLE", lambda sh: None), ("E000", "E000_MAIN", draw),
                                    ("E500", "E500_AFTER", lambda sh: None)],
                        io_points=io_pts(), io_after="E000")
        self.assertEqual([n for n, _ in ds.order()], ["S000", "E000", "E300", "E400", "E500"])
        doc, total = ds.build()
        self.assertEqual(total, 5)
        t = texts(doc)
        for s in ("HELLO", "AB01-E000", "AB01-E300", "AB01-E400", "A3   5/5", "(E035)", "LAYMAC", "(E031-B3)"):
            self.assertIn(s, t)
        self.assertIn("DASHED", doc.linetypes)

    def test_sig_row_not_on_bus(self):
        # tin hieu sang thiet bi khac: bus +24V chi xuong toi dong tai cuoi cung
        ds = DrawingSet(EN, io_points=[IOPoint("R500", "DO", device="van", module="M"),
                                       IOPoint("R501", "DO", device="tín hiệu", xref="E010-A4", module="M")])
        doc, _ = ds.build()
        bus = [e for e in doc.modelspace().query("LINE")
               if e.dxf.start.x == e.dxf.end.x and abs(e.dxf.start.x - (18 + 178)) < 1e-6]
        self.assertEqual(len(bus), 1)
        self.assertAlmostEqual(min(bus[0].dxf.start.y, bus[0].dxf.end.y), 255)


if __name__ == "__main__":
    unittest.main()
