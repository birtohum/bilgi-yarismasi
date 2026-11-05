"""Oyun mantığı: odalar, oyuncular, sorular, puanlar. Ağdan bağımsız; testler doğrudan bunu çağırır."""
import json
import random
import secrets
import threading
import time
from pathlib import Path

VERI = json.loads((Path(__file__).parent / "sorular.json").read_text(encoding="utf-8"))
SORU_SAYISI = 10
SURE = 20.0           # saniye
EN_COK_ODA = 40
EN_COK_OYUNCU = 60
ODA_OMRU = 3 * 3600   # saniye
HARFLER = "ABCDEFGHJKLMNPRSTUVYZ"  # karışabilecek harfler (I, O, Q, W, X) yok
KATEGORI = {"nufus": "İl nüfusu", "ilce": "İlçe", "plaka": "Plaka", "rakim": "Rakım", "gol": "Göl", "dogum": "Doğum yılı"}
# 10 soruluk dengeli karışım
KARISIM = ["nufus", "ilce", "ilce", "plaka", "rakim", "gol", "dogum", "dogum", "nufus", "rakim"]


def soru_sec(rnd):
    secilen = []
    for k in KARISIM[:SORU_SAYISI]:
        aday = [s for s in VERI["sorular"] if s["k"] == k and s not in secilen]
        secilen.append(rnd.choice(aday))
    rnd.shuffle(secilen)
    cikti = []
    for s in secilen:
        sira = list(range(len(s["o"])))
        rnd.shuffle(sira)
        cikti.append({"k": s["k"], "s": s["s"], "o": [s["o"][i] for i in sira], "a": sira.index(s["a"]), "m": s["m"]})
    return cikti


def yz_ozet(m):
    """Bu soruyu hangi modellerin bildiği: Meta modelleri toplu, yereller tek tek."""
    meta = [v for v, md in zip(m, VERI["modeller"]) if md["meta"]]
    yerel = [{"ad": md["ad"], "bildi": bool(v)} for v, md in zip(m, VERI["modeller"]) if not md["meta"]]
    return {"meta_bildi": sum(meta), "meta_toplam": len(meta), "yerel": yerel}


class Oda:
    def __init__(self, kod, rnd=None):
        self.kod = kod
        self.sunucu_jetonu = secrets.token_urlsafe(16)
        self.oyuncular = {}  # jeton -> {"ad", "puan", "cevap", "son_puan"}
        self.durum = "lobi"  # lobi | soru | sonuc | bitti
        self.sorular = soru_sec(rnd or random.Random())
        self.sira = -1
        self.bitis = 0.0
        self.surum = 0
        self.olusma = self.son_hareket = time.time()
        self.kosul = threading.Condition()

    # --- değişiklikler (kosul kilidi altında çağrılır)
    def _degisti(self):
        self.surum += 1
        self.son_hareket = time.time()
        self.kosul.notify_all()

    def katil(self, ad):
        ad = " ".join(str(ad).split())[:16]
        if not ad:
            raise ValueError("Bir ad yaz.")
        with self.kosul:
            if self.durum != "lobi":
                raise ValueError("Yarışma başladı; yeni oyuncu alınmıyor.")
            if len(self.oyuncular) >= EN_COK_OYUNCU:
                raise ValueError("Oda dolu.")
            if any(o["ad"].casefold() == ad.casefold() for o in self.oyuncular.values()):
                raise ValueError("Bu ad alınmış, başka bir ad dene.")
            jeton = secrets.token_urlsafe(12)
            self.oyuncular[jeton] = {"ad": ad, "puan": 0, "cevap": None, "son_puan": 0}
            self._degisti()
            return jeton

    def ilerle(self, simdi=None):
        """Sunucunun 'Başla / Sonraki' düğmesi."""
        simdi = simdi or time.time()
        with self.kosul:
            if self.durum in ("lobi", "sonuc"):
                if self.durum == "lobi" and not self.oyuncular:
                    raise ValueError("Önce en az bir oyuncu katılmalı.")
                if self.sira + 1 >= len(self.sorular):
                    self.durum = "bitti"
                else:
                    self.sira += 1
                    self.durum = "soru"
                    self.bitis = simdi + SURE
                    for o in self.oyuncular.values():
                        o["cevap"], o["son_puan"] = None, 0
                self._degisti()
            elif self.durum == "soru":
                self._kapat()

    def cevapla(self, jeton, secim, simdi=None):
        simdi = simdi or time.time()
        with self.kosul:
            o = self.oyuncular.get(jeton)
            if not o:
                raise ValueError("Oyuncu bulunamadı.")
            if self.durum != "soru" or simdi > self.bitis or o["cevap"] is not None:
                return False
            s = self.sorular[self.sira]
            if not (isinstance(secim, int) and 0 <= secim < len(s["o"])):
                raise ValueError("Geçersiz seçenek.")
            o["cevap"] = secim
            if secim == s["a"]:
                o["son_puan"] = 500 + round(500 * max(0.0, self.bitis - simdi) / SURE)
                o["puan"] += o["son_puan"]
            if all(x["cevap"] is not None for x in self.oyuncular.values()):
                self._kapat()
            else:
                self._degisti()
            return True

    def _kapat(self):
        self.durum = "sonuc"
        self._degisti()

    def zaman_kontrol(self, simdi=None):
        simdi = simdi or time.time()
        with self.kosul:
            if self.durum == "soru" and simdi > self.bitis:
                self._kapat()

    # --- görünüm: cevap yalnız sonuçta açılır
    def gorunum(self, jeton=None, simdi=None):
        simdi = simdi or time.time()
        with self.kosul:
            v = {"kod": self.kod, "durum": self.durum, "surum": self.surum, "sira": self.sira + 1, "toplam": len(self.sorular),
                 "oyuncu_sayisi": len(self.oyuncular)}
            if self.durum == "lobi":
                v["oyuncular"] = [o["ad"] for o in self.oyuncular.values()]
            if self.durum in ("soru", "sonuc"):
                s = self.sorular[self.sira]
                v["soru"] = {"kategori": KATEGORI[s["k"]], "metin": s["s"], "secenekler": s["o"]}
                v["kalan"] = max(0.0, round(self.bitis - simdi, 1)) if self.durum == "soru" else 0
                v["cevaplayan"] = sum(o["cevap"] is not None for o in self.oyuncular.values())
            if self.durum == "sonuc":
                s = self.sorular[self.sira]
                v["dogru"] = s["a"]
                v["dagilim"] = [sum(o["cevap"] == i for o in self.oyuncular.values()) for i in range(len(s["o"]))]
                v["yz"] = yz_ozet(s["m"])
            if self.durum in ("sonuc", "bitti"):
                sirali = sorted(self.oyuncular.values(), key=lambda o: -o["puan"])
                v["tablo"] = [{"ad": o["ad"], "puan": o["puan"], "son": o["son_puan"]} for o in sirali[:10]]
            if jeton in self.oyuncular:
                o = self.oyuncular[jeton]
                ben = {"ad": o["ad"], "puan": o["puan"], "cevap": o["cevap"], "son_puan": o["son_puan"]}
                if self.durum in ("sonuc", "bitti"):
                    sirali = sorted(self.oyuncular.values(), key=lambda x: -x["puan"])
                    ben["siralama"] = next(i for i, x in enumerate(sirali, 1) if x is o)
                v["ben"] = ben
            return v


class Salon:
    def __init__(self):
        self.odalar = {}
        self.kilit = threading.Lock()

    def oda_kur(self):
        with self.kilit:
            self.temizle()
            if len(self.odalar) >= EN_COK_ODA:
                raise ValueError("Şu an çok fazla açık oda var; birazdan yeniden dene.")
            while True:
                kod = "".join(secrets.choice(HARFLER) for _ in range(4))
                if kod not in self.odalar:
                    break
            oda = self.odalar[kod] = Oda(kod)
            return oda

    def bul(self, kod):
        return self.odalar.get(str(kod).upper())

    def temizle(self, simdi=None):
        simdi = simdi or time.time()
        for k in [k for k, o in self.odalar.items() if simdi - o.son_hareket > ODA_OMRU or simdi - o.olusma > 2 * ODA_OMRU]:
            del self.odalar[k]
