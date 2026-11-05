# Türkiye'yi kim daha iyi tanıyor?

**Oyna:** https://birtohum.github.io/bilgi-yarismasi/

Arkadaşlarla, sınıfta ya da ailecek oynanan canlı bilgi yarışması. Bir ekran (projeksiyon, televizyon) odayı kurar, herkes telefonundan dört harfli kodla katılır. On soru, her biri 20 saniye; doğru cevap 500 puan, hıza göre 500'e kadar fazlası. Her sorudan sonra on yapay zekâ modelinin o soruyu bilip bilmediği gösterilir.

## Sorular

[Türkçe yapay zekâ karnesi](https://birtohum.github.io/turkce-yz-karnesi/)'nin Wikidata'dan otomatik üretilmiş açık sorularından (`araclar/sorular.py`): il nüfusu, ilçenin ili, plaka kodu, şehir rakımı, gölün ili, ünlülerin doğum yılı. Karnede “tartışmalı” işaretlenen, yani Wikidata cevabının şüpheli olduğu 11 soru havuzdan çıkarıldı; kalan 1.136 soru. Her oyunda kategorileri dengeli 10 soru seçilir, seçeneklerin sırası karıştırılır. Modellerin bilip bilmediği karnenin ölçümlerinden gelir (aynı soru, iki farklı ifade).

## Sunucu

`sunucu/` yalnız Python standart kütüphanesiyle yazıldı. Canlı güncelleme Server-Sent Events ile; oyuncular cevaplarını küçük POST istekleriyle gönderir. Doğru cevap, soru kapanana kadar istemciye gönderilmez. Sınırlar: IP başına saatte 10 oda, en fazla 40 açık oda, oda başına 60 oyuncu; oda 3 saat hareketsiz kalınca silinir. Adlar ve puanlar yalnız bellekte durur.

AWS'de Caddy arkasında `systemd` servisi (`sunucu/bilgi-yarismasi.service`).

```bash
python -m unittest discover -s testler
cd sunucu && python sunucu.py          # 127.0.0.1:8792
cd site && python -m http.server 8881  # arayüz yerelde sunucuya bağlanır
```

Lisans: MIT. Sorular Wikidata (CC0) verisinden.
