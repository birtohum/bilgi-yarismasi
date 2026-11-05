import random, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sunucu"))
import oyun


class Oyun(unittest.TestCase):
    def setUp(self):
        self.oda = oyun.Oda("TEST", random.Random(1))
        self.a = self.oda.katil("Ayşe"); self.b = self.oda.katil("Mehmet")

    def test_soru_karisimi_ve_secenek_karistirma(self):
        s = self.oda.sorular
        self.assertEqual(len(s), 10)
        self.assertEqual(sorted(x["k"] for x in s), sorted(oyun.KARISIM))
        self.assertTrue(any(x["a"] != 0 for x in s))  # doğru cevap hep ilk sırada değil

    def test_ayni_ad_alinmaz(self):
        with self.assertRaises(ValueError):
            self.oda.katil("  ayşe ")

    def test_cevap_soru_sirasinda_gizli(self):
        self.oda.ilerle(simdi=100)
        v = self.oda.gorunum(self.a, simdi=101)
        self.assertNotIn("dogru", v)
        self.assertNotIn("a", v["soru"])

    def test_puan_hiza_gore_ve_herkes_cevaplayinca_kapanir(self):
        self.oda.ilerle(simdi=100)
        d = self.oda.sorular[0]["a"]
        yanlis = (d + 1) % len(self.oda.sorular[0]["o"])
        self.assertTrue(self.oda.cevapla(self.a, d, simdi=100))      # anında: 1000
        self.assertFalse(self.oda.cevapla(self.a, d, simdi=101))     # ikinci cevap sayılmaz
        self.assertEqual(self.oda.durum, "soru")
        self.oda.cevapla(self.b, yanlis, simdi=110)
        self.assertEqual(self.oda.durum, "sonuc")
        v = self.oda.gorunum(self.a)
        self.assertEqual(v["tablo"][0], {"ad": "Ayşe", "puan": 1000, "son": 1000})
        self.assertEqual(v["ben"]["siralama"], 1)
        self.assertEqual(sum(v["dagilim"]), 2)
        self.assertEqual(v["yz"]["meta_toplam"], 6)

    def test_sure_dolunca_kapanir_ve_gec_cevap_sayilmaz(self):
        self.oda.ilerle(simdi=100)
        self.assertFalse(self.oda.cevapla(self.a, 0, simdi=100 + oyun.SURE + 1))
        self.oda.zaman_kontrol(simdi=100 + oyun.SURE + 1)
        self.assertEqual(self.oda.durum, "sonuc")

    def test_on_sorudan_sonra_biter_ve_yeni_oyuncu_alinmaz(self):
        for i in range(10):
            self.oda.ilerle(); self.oda.ilerle()
        self.oda.ilerle()
        self.assertEqual(self.oda.durum, "bitti")
        with self.assertRaises(ValueError):
            self.oda.katil("Geç")

    def test_tartismali_soru_havuzda_yok(self):
        self.assertFalse(any(s["s"].startswith("Hangi şehir merkezi") and set(s["o"]) == {"Batman", "Kahramanmaraş"} for s in oyun.VERI["sorular"]))


if __name__ == "__main__":
    unittest.main()
