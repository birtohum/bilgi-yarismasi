"""Haftanın Yarışması: her cuma 21:00'de (TR) açılan, herkesin aynı 10 soruyu çözdüğü yarışma.
Puan tablosunda on yapay zekâ modeli de yer alır; bilgileri karnedeki gerçek ölçümlerden gelir.

Sorular haftanın anahtarından deterministik seçilir (sunucu yeniden başlasa da aynı kalır).
Süre sunucuda ölçülür: /basla jeton ve başlangıç zamanı verir, /bitir puanı sunucuda hesaplar.
Kayıt: kayitlar/hafta-<anahtar>.jsonl (yalnız ad, doğru sayısı, süre). IP saklanmaz; özet bellekte sınır için tutulur.
"""
import hashlib
import json
import os
import random
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import oyun

TR = timezone(timedelta(hours=3))
KAYIT = Path(os.environ.get("YARISMA_KAYIT", Path(__file__).parent / "kayitlar"))
SORU_SURE = 20
EN_COK_IP = 8          # bir IP'den haftada en fazla kayıt
_kilit = threading.Lock()
_basla = {}            # jeton -> {"hafta", "t"}
_ip = {}               # (hafta, ip özeti) -> sayı
_tablo = {}            # hafta -> [{"ad","d","sn"}]

# Tabloya kötü söz ve bağlantı yazılmasın. Eşleşirse ad reddedilir.
YASAK = re.compile(r"(https?:|www\.|\.com|\.net|\.org|@|amk|aq\b|orospu|sik[it]|s[i1]kt[i1]r|yarra|göt|got\b|piç|pic\b|ibne|kahpe|pezevenk|gavat|"
                   r"fuck|shit|bitch|nigg|hitler|nazi|pkk|isis)", re.I)


def hafta_anahtari(simdi=None):
    """Hafta cuma 21:00'de başlar. Anahtar: o cumanın tarihi."""
    t = (simdi or datetime.now(TR)).astimezone(TR)
    geri = (t.weekday() - 4) % 7
    cuma = (t - timedelta(days=geri)).replace(hour=21, minute=0, second=0, microsecond=0)
    if cuma > t:
        cuma -= timedelta(days=7)
    return cuma.date().isoformat(), cuma + timedelta(days=7)


def sorular(anahtar):
    return oyun.soru_sec(random.Random("hafta:" + anahtar))


def yz_tablosu(s):
    out = []
    for i, md in enumerate(oyun.VERI["modeller"]):
        out.append({"ad": md["ad"], "d": sum(q["m"][i] for q in s), "yz": True})
    return sorted(out, key=lambda x: -x["d"])


def _dosya(anahtar):
    return KAYIT / f"hafta-{anahtar}.jsonl"


def _yukle(anahtar):
    if anahtar not in _tablo:
        p = _dosya(anahtar)
        _tablo[anahtar] = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []
    return _tablo[anahtar]


def _sirali(k):
    return sorted(k, key=lambda x: (-x["d"], x["sn"]))


def durum(simdi=None):
    anahtar, bitis = hafta_anahtari(simdi)
    s = sorular(anahtar)
    with _kilit:
        k = _yukle(anahtar)
        tablo = [{"ad": x["ad"], "d": x["d"], "sn": x["sn"]} for x in _sirali(k)[:15]]
    return {"hafta": anahtar, "bitis": bitis.isoformat(), "katilan": len(k), "soru_sayisi": len(s), "soru_sure": SORU_SURE,
            "tablo": tablo, "yz": yz_tablosu(s)}


def basla(simdi=None):
    anahtar, _ = hafta_anahtari(simdi)
    s = sorular(anahtar)
    j = secrets.token_urlsafe(12)
    with _kilit:
        # eski başlangıçları temizle
        sinir = time.time() - 3600
        for x in [x for x, v in _basla.items() if v["t"] < sinir]:
            del _basla[x]
        _basla[j] = {"hafta": anahtar, "t": time.time()}
    return {"jeton": j, "hafta": anahtar, "soru_sure": SORU_SURE,
            "sorular": [{"kategori": oyun.KATEGORI[q["k"]], "metin": q["s"], "secenekler": q["o"]} for q in s]}


def bitir(jeton, ad, cevaplar, ip):
    ad = " ".join(str(ad or "").split())[:16]
    if ad and YASAK.search(ad):  # jeton harcanmadan: oyun boşa gitmesin
        raise ValueError("Bu adı tabloya yazamıyorum, başka bir ad dene.")
    with _kilit:
        b = _basla.pop(jeton, None)
    if not b:
        raise ValueError("Bu oyun zaten bitmiş ya da süresi dolmuş. Yeniden başla.")
    anahtar = b["hafta"]
    s = sorular(anahtar)
    if not isinstance(cevaplar, list) or len(cevaplar) != len(s):
        raise ValueError("Cevaplar eksik.")
    sn = round(min(time.time() - b["t"], len(s) * SORU_SURE + 30), 1)
    d = sum(1 for q, c in zip(s, cevaplar) if c == q["a"])
    gosterildi = False
    ozet = hashlib.sha256((anahtar + ip).encode()).hexdigest()[:16]
    with _kilit:
        k = _yukle(anahtar)
        n = _ip.get((anahtar, ozet), 0)
        if ad and n < EN_COK_IP:
            kayit = {"ad": ad, "d": d, "sn": sn}
            k.append(kayit)
            KAYIT.mkdir(parents=True, exist_ok=True)
            with open(_dosya(anahtar), "a", encoding="utf-8") as f:
                f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
            _ip[(anahtar, ozet)] = n + 1
            gosterildi = True
        # sıra: bu puandan yüksek olanlar + aynı puanda daha hızlı olanlar + 1
        sira = 1 + sum(1 for x in k if (x["d"], -x["sn"]) > (d, -sn))
        toplam = len(k)
        gecti = sum(1 for x in k if x["d"] < d)
    yz = yz_tablosu(s)
    return {"dogru": d, "toplam": len(s), "sn": sn, "sira": sira, "katilan": toplam, "gecti": gecti, "tabloda": gosterildi,
            "yz": yz, "yz_gecti": sum(1 for m in yz if m["d"] < d),
            "inceleme": [{"metin": q["s"], "secenekler": q["o"], "dogru": q["a"], "senin": c, "yz": oyun.yz_ozet(q["m"])} for q, c in zip(s, cevaplar)]}
