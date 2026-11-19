"""S4a (19/11/2026): hai lần kế hoạch hỏng cùng một giây không ghi đè bản .corrupt."""
import datetime
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import troly_core as tc  # noqa: E402


class CorruptKhongGhiDe(unittest.TestCase):
    """(a) Hai lần kế hoạch hỏng trong CÙNG MỘT GIÂY: bản .corrupt của lần đầu bị lần sau ghi đè (os.replace ghi đè trên Windows)."""

    def test_hai_lan_hong_cung_mot_giay_giu_ca_hai_ban(self):
        tmp = tempfile.mkdtemp()
        try:
            name = "2026.11.19.Thu_S4"
            p = tc.plan_path(tmp, name)
            os.makedirs(os.path.dirname(p))

            class Fixed(datetime.datetime):
                @classmethod
                def now(cls, tz=None):
                    return cls(2026, 11, 19, 9, 30, 0)
            noidung = []
            with mock.patch.object(tc.datetime, "datetime", Fixed):
                for i in range(3):
                    rac = "{rác lần %d" % i
                    noidung.append(rac)
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(rac)
                    back = tc.load_plan(tmp, name)
                    self.assertIn("_note", back)
            kept = sorted(f for f in os.listdir(os.path.dirname(p)) if ".corrupt-" in f)
            self.assertEqual(len(kept), 3, kept)                                     # không bản nào bị ghi đè
            got = sorted(open(os.path.join(os.path.dirname(p), f), encoding="utf-8").read() for f in kept)
            self.assertEqual(got, sorted(noidung))
            self.assertTrue(all(f.startswith(os.path.basename(p) + ".corrupt-20261119-093000") for f in kept))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
