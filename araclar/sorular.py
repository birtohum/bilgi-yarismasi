"""Türkçe yapay zekâ karnesinin açık sorularından yarışma havuzu üretir: sunucu/sorular.json

Karne'nin 'tartışmalı' listesindeki (Wikidata cevabı şüpheli) sorular çıkarılır.
Her soruda 10 modelin bilip bilmediği de taşınır; yarışmada her sorudan sonra gösterilir.
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
KARNE = Path.home() / "Desktop" / "karne" / "site" / "data"
HEDEF = Path(__file__).resolve().parent.parent / "sunucu" / "sorular.json"

q = json.loads((KARNE / "quiz.json").read_text(encoding="utf-8"))
r = json.loads((KARNE / "results.json").read_text(encoding="utf-8"))
ad = {m["id"]: m["name"] for m in r["models"]}

tartismali = set()
for d in r["disputed"]:
    m = re.search(r"\(([^()]*)\)\s*$", d["q"])
    secenek = frozenset(s.strip() for s in m.group(1).split("/")) if m else frozenset()
    tartismali.add((secenek, d["gold"]))

havuz, cikan = [], 0
for it in q["items"]:
    if (frozenset(it["o"]), it["o"][it["a"]]) in tartismali:
        cikan += 1
        continue
    havuz.append({"k": it["c"], "s": it["q"], "o": it["o"], "a": it["a"], "m": it["m"]})

veri = {"modeller": [{"id": i, "ad": ad[i], "meta": i.startswith("meta_")} for i in q["models"]], "sorular": havuz,
        "kaynak": "https://birtohum.github.io/turkce-yz-karnesi/"}
HEDEF.write_text(json.dumps(veri, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"{len(havuz)} soru, {cikan} tartışmalı soru çıkarıldı")
