import sys, tempfile, unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sunucu"))
import haftalik as h
TR = timezone(timedelta(hours=3))


class Hafta(unittest.TestCase):
    def setUp(self):
        h.KAYIT = Path(tempfile.mkdtemp()); h._tablo.clear(); h._ip.clear(); h._basla.clear()

    def test_hafta_cuma_21de_degisir(self):
        a, _ = h.hafta_anahtari(datetime(2026, 11, 6, 20, 59, tzinfo=TR))
        b, _ = h.hafta_anahtari(datetime(2026, 11, 6, 21, 0, tzinfo=TR))
        c, _ = h.hafta_anahtari(datetime(2026, 11, 12, 12, 0, tzinfo=TR))
        self.assertEqual(a, "2026-10-30"); self.assertEqual(b, "2026-11-06"); self.assertEqual(c, "2026-11-06")

    def test_sorular_deterministik(self):
        self.assertEqual(h.sorular("2026-11-06"), h.sorular("2026-11-06"))
        self.assertNotEqual(h.sorular("2026-11-06"), h.sorular("2026-11-13"))

    def test_basla_cevabi_gizli(self):
        self.assertNotIn('"a"', str(h.basla()["sorular"][0].keys()))

    def test_puan_sunucuda_hesaplanir_ve_jeton_tek_kullanimlik(self):
        b = h.basla(); s = h.sorular(b["hafta"])
        r = h.bitir(b["jeton"], "Ayşe", [q["a"] for q in s], "1.1.1.1")
        self.assertEqual(r["dogru"], 10); self.assertTrue(r["tabloda"]); self.assertEqual(r["sira"], 1)
        with self.assertRaises(ValueError):
            h.bitir(b["jeton"], "Ayşe", [q["a"] for q in s], "1.1.1.1")

    def test_kotu_ad_ve_baglanti_reddedilir(self):
        for ad in ("siktir", "www.spam", "a.com"):
            b = h.basla(); s = h.sorular(b["hafta"])
            with self.assertRaises(ValueError):
                h.bitir(b["jeton"], ad, [0] * len(s), "2.2.2.2")

    def test_adsiz_oyun_tabloya_girmez_ip_siniri(self):
        b = h.basla(); s = h.sorular(b["hafta"])
        self.assertFalse(h.bitir(b["jeton"], "", [0] * 10, "3.3.3.3")["tabloda"])
        for i in range(h.EN_COK_IP + 2):
            b = h.basla(); r = h.bitir(b["jeton"], f"O{i}", [0] * 10, "3.3.3.3")
        self.assertFalse(r["tabloda"])
        self.assertEqual(h.durum()["katilan"], h.EN_COK_IP)

    def test_yz_tablosu_on_model(self):
        self.assertEqual(len(h.durum()["yz"]), 10)


if __name__ == "__main__":
    unittest.main()
