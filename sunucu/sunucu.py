"""Bilgi yarışması sunucusu. Yalnız Python standart kütüphanesi; canlı güncelleme Server-Sent Events ile.
Caddy önde HTTPS'i yapar, /yarisma/* isteklerini 127.0.0.1:8792'ye iletir.

  POST /oda                        -> {kod, jeton}            (sunucu ekranı odayı kurar)
  POST /oda/KOD/katil  {ad}        -> {jeton}
  POST /oda/KOD/ilerle {jeton}     (yalnız sunucu: başla / cevapları kapat / sonraki)
  POST /oda/KOD/cevap  {jeton, secim}
  GET  /oda/KOD/akis?j=JETON       text/event-stream, her değişiklikte durum
  GET  /hafta, POST /hafta/basla, POST /hafta/bitir {jeton, ad, cevaplar}   Haftanın Yarışması
Adlar ve puanlar yalnız bellekte durur; oda 3 saat hareketsiz kalınca silinir.
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import haftalik
import oyun

PORT = int(os.environ.get("YARISMA_PORT", "8792"))
IZINLI = {"https://birtohum.github.io", "http://127.0.0.1:8881"}
EN_COK_AKIS = 400
SALON = oyun.Salon()
_akis = {"n": 0}
_akis_kilit = threading.Lock()
_oda_kuran = {}  # IP -> son oda kurma zamanları (kötüye kullanım sınırı)


class Isleyici(BaseHTTPRequestHandler):
    server_version = "yarisma"
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _cors(self):
        koken = self.headers.get("Origin", "")
        if koken in IZINLI:
            self.send_header("Access-Control-Allow-Origin", koken)
            self.send_header("Vary", "Origin")

    def _gonder(self, kod, veri):
        govde = json.dumps(veri, ensure_ascii=False).encode()
        self.send_response(kod)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(govde)

    def _govde(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n > 2000:
            raise ValueError("İstek çok büyük.")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        parca = urlsplit(self.path).path.strip("/").split("/")
        try:
            g = self._govde()
            if parca == ["hafta", "basla"]:
                return self._gonder(200, haftalik.basla())
            if parca == ["hafta", "bitir"]:
                ip = (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()
                return self._gonder(200, haftalik.bitir(g.get("jeton"), g.get("ad"), g.get("cevaplar"), ip))
            if parca == ["oda"]:
                ip = (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()
                simdi = time.time()
                son = [t for t in _oda_kuran.get(ip, []) if simdi - t < 3600]
                if len(son) >= 10:
                    return self._gonder(429, {"hata": "Bir saatte en fazla 10 oda kurulabilir."})
                _oda_kuran[ip] = son + [simdi]
                oda = SALON.oda_kur()
                return self._gonder(200, {"kod": oda.kod, "jeton": oda.sunucu_jetonu})
            if len(parca) == 3 and parca[0] == "oda":
                oda = SALON.bul(parca[1])
                if not oda:
                    return self._gonder(404, {"hata": "Bu kodla bir oda yok. Kodu kontrol et."})
                if parca[2] == "katil":
                    return self._gonder(200, {"jeton": oda.katil(g.get("ad", ""))})
                if parca[2] == "ilerle":
                    if g.get("jeton") != oda.sunucu_jetonu:
                        return self._gonder(403, {"hata": "Yalnız odayı kuran ekran ilerletebilir."})
                    oda.ilerle()
                    return self._gonder(200, {"tamam": True})
                if parca[2] == "cevap":
                    return self._gonder(200, {"alindi": oda.cevapla(g.get("jeton"), g.get("secim"))})
            return self._gonder(404, {"hata": "bulunamadı"})
        except ValueError as e:
            return self._gonder(400, {"hata": str(e)})

    def do_GET(self):
        u = urlsplit(self.path)
        parca = u.path.strip("/").split("/")
        if parca == ["durum"] or parca == [""]:
            return self._gonder(200, {"oda": len(SALON.odalar), "akis": _akis["n"]})
        if parca == ["hafta"]:
            return self._gonder(200, haftalik.durum())
        if len(parca) == 2 and parca[0] == "oda":
            return self._gonder(200, {"var": True}) if SALON.bul(parca[1]) else self._gonder(404, {"hata": "Bu kodla bir oda yok."})
        if len(parca) == 3 and parca[0] == "oda" and parca[2] == "akis":
            oda = SALON.bul(parca[1])
            if not oda:
                return self._gonder(404, {"hata": "Bu kodla bir oda yok."})
            with _akis_kilit:
                if _akis["n"] >= EN_COK_AKIS:
                    return self._gonder(503, {"hata": "Sunucu şu an dolu."})
                _akis["n"] += 1
            jeton = (parse_qs(u.query).get("j") or [None])[0]
            try:
                self._akis(oda, jeton)
            finally:
                with _akis_kilit:
                    _akis["n"] -= 1
            return
        return self._gonder(404, {"hata": "bulunamadı"})

    def _akis(self, oda, jeton):
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True
        gorulen = -1
        try:
            while oda.kod in SALON.odalar:
                with oda.kosul:
                    if oda.surum == gorulen:
                        oda.kosul.wait(timeout=15)
                if oda.surum != gorulen:
                    v = oda.gorunum(jeton)
                    gorulen = v["surum"]
                    self.wfile.write(f"data: {json.dumps(v, ensure_ascii=False)}\n\n".encode())
                else:
                    self.wfile.write(b": nabiz\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass


def saat():
    """Süresi dolan soruları kapatır, eski odaları siler."""
    while True:
        time.sleep(0.5)
        for oda in list(SALON.odalar.values()):
            oda.zaman_kontrol()
        with SALON.kilit:
            SALON.temizle()


if __name__ == "__main__":
    threading.Thread(target=saat, daemon=True).start()
    ThreadingHTTPServer.daemon_threads = True
    print(f"yarışma: 127.0.0.1:{PORT}, {len(oyun.VERI['sorular'])} soru")
    ThreadingHTTPServer(("127.0.0.1", PORT), Isleyici).serve_forever()
