import csv
import tempfile
import unittest
from pathlib import Path

from dienkit.tags import Tag, column_field, main, parse_address, read_template, validate, write_table

EX = Path(__file__).parent.parent / "examples"


def check(rows, fam="fx5"):
    tags = [Tag(t, a, d, row=i + 2, plc="P") for i, (t, a, d) in enumerate(rows)]
    validate(tags, {"P": fam})
    return tags


class AddressTests(unittest.TestCase):
    def test_fx5_xy_octal(self):
        self.assertEqual(parse_address("X17", "fx5")[:2], ("X", "17"))
        with self.assertRaisesRegex(ValueError, "bat phan"):
            parse_address("X8", "fx5")
        self.assertEqual(parse_address("X1F", "iqr")[:2], ("X", "1F"))  # iQ-R: he 16

    def test_longest_prefix_first(self):
        self.assertEqual(parse_address("SM400", "fx5")[0], "SM")
        self.assertEqual(parse_address("MR500", "kv")[0], "MR")
        self.assertEqual(parse_address("DM100", "kv")[0], "DM")

    def test_keyence_channel_bits(self):
        self.assertEqual(parse_address("R1015", "kv")[1], "1015")
        with self.assertRaisesRegex(ValueError, "00-15"):
            parse_address("R016", "kv")

    def test_bit_of_word(self):
        self.assertEqual(parse_address("D30.F", "fx5")[2], 15)
        with self.assertRaises(ValueError):
            parse_address("M10.1", "fx5")

    def test_unknown_prefix(self):
        with self.assertRaisesRegex(ValueError, "tien to"):
            parse_address("DM100", "fx5")


class ValidateTests(unittest.TestCase):
    def test_overlap_32bit(self):
        t = check([("A", "D100", "REAL"), ("B", "D101", "INT"), ("C", "D102", "INT")])
        self.assertIn("chong lan", t[1].errors[0])
        self.assertEqual(t[2].errors, [])

    def test_type_mismatch(self):
        t = check([("A", "D200", "BOOL"), ("B", "M10", "INT"), ("C", "D0", "")])
        self.assertTrue(t[0].errors and t[1].errors)
        self.assertEqual(t[2].dtype, "INT")  # mac dinh cho thanh ghi

    def test_duplicate_name_and_bad_name(self):
        t = check([("A", "M0", ""), ("a", "M1", ""), ("1X", "M2", "")])
        self.assertIn("trung ten", t[1].errors[0])
        self.assertTrue(t[2].errors)

    def test_warnings(self):
        t = check([("W", "D30", "WORD"), ("B0", "D30.0", ""), ("ODD", "D41", "DINT"), ("HEX", "W1B", "DINT")])
        self.assertIn("bit cua W", t[1].warnings[0])
        self.assertTrue(t[2].warnings)
        self.assertTrue(t[3].warnings)  # W1B = 27 (he 16) -> le


class ExportTests(unittest.TestCase):
    def test_column_mapping(self):
        cases = {"Assign (Device/Label)": "address", "Label Name": "tag", "Device name": "plc",
                 "Address type": "prefix", "Address": "address", "データ型": "type", "ラベル名": "tag",
                 "割付(デバイス/ラベル)": "address", "コメント": "comment", "Reserved": None}
        for h, f in cases.items():
            self.assertEqual(column_field(h), f, h)

    def test_template_utf16_tab_with_preamble(self):
        with tempfile.TemporaryDirectory() as d:
            tpl_path = Path(d, "tpl.csv")
            text = "Project1\r\nラベル名\tデータ型\tクラス\t割付(デバイス/ラベル)\t初期値\tコメント\r\n"
            tpl_path.write_bytes(b"\xff\xfe" + text.encode("utf-16-le"))
            tpl = read_template(tpl_path)
            self.assertEqual((tpl.delimiter, tpl.preamble, len(tpl.header)), ("\t", ["Project1"], 6))
            tags = check([("SP", "D10", "REAL")])
            tags[0].comment = "Cài đặt"
            out = Path(d, "out.csv")
            write_table(out, tags, "gx3", tpl)
            raw = out.read_bytes()
            self.assertEqual(raw[:2], b"\xff\xfe")
            lines = raw.decode("utf-16").splitlines()
            self.assertEqual(lines[0], "Project1")
            self.assertEqual(lines[2].split("\t"),
                             ['"SP"', '"FLOAT [Single Precision]"', '"VAR_GLOBAL"', '"D10"', '""', '"Cài đặt"'])

    def test_cli_example(self):
        with tempfile.TemporaryDirectory() as d:
            rc = main([str(EX / "tags.csv"), "--plc", "PLC_MITSU=fx5", "--plc", "PLC_KV=kv", "-o", d])
            self.assertEqual(rc, 0)
            with open(Path(d, "weintek_address_tags.csv"), encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            kv = next(r for r in rows if r["Tag name"] == "KV_LENGTH")
            self.assertEqual((kv["Device name"], kv["Address type"], kv["Address"], kv["Data format"]),
                             ("PLC_KV", "DM", "200", "32-bit Float"))
            self.assertNotIn("LS_UP", [r["Tag name"] for r in rows])  # hmi trong
            self.assertTrue(Path(d, "PLC_KV_kv_device_comment.csv").exists())
            self.assertFalse(Path(d, "PLC_KV_gx3_global_label.csv").exists())

    def test_cli_blocks_on_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "t.csv")
            p.write_text("tag,dia_chi\nA,X8\n", encoding="utf-8")
            self.assertEqual(main([str(p), "--plc", "P=fx5", "-o", d]), 1)
            self.assertFalse(Path(d, "weintek_address_tags.csv").exists())


if __name__ == "__main__":
    unittest.main()
