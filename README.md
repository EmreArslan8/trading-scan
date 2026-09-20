# TradingView Tarayıcı

TradingView'in screener servisini kullanan yerel tarama uygulaması.
Kriterler ekrandan seçilir, sonuçlar tabloya düşer, CSV olarak indirilir.

## Çalıştırma

    python3 server.py          # http://127.0.0.1:8777
    python3 server.py 9000     # başka port

Python 3.8+ yeterli. **Kurulacak paket yok** — yalnızca standart kütüphane.

## Dosyalar

| dosya | işi |
|---|---|
| `api/_core.py` | tarama mantığı; ekrandan gelen kriterleri TradingView sorgusuna çevirir |
| `api/scan.py` | `POST /api/scan` uç noktası |
| `api/catalog.py` | `GET /api/catalog` uç noktası |
| `api/fields.json` | piyasalar, periyotlar, operatörler, alanlar, hazır taramalar |
| `public/index.html` | arayüz (tek dosya, çerçeve yok) |
| `server.py` | yerel geliştirme sunucusu; aynı çekirdeği kullanır |
| `vercel.json` | Vercel yapılandırması |

## Yayına alma (Vercel)

Depo Vercel'e bağlandığında ek ayar gerekmez: `public/` statik olarak,
`api/*.py` serverless fonksiyon olarak yayınlanır. Bağımlılık olmadığı için
`requirements.txt` yoktur.

## Yeni alan / kriter eklemek

Koda dokunulmaz, `api/fields.json` içine bir satır eklenir:

    { "id": "Perf.3M", "label": "3 aylık perf. %", "group": "Fiyat", "tf": false, "fmt": "percent" }

- `id` — TradingView kolon adı
- `tf` — periyot (1s, 4s…) bu alana uygulanabiliyor mu
- `fmt` — `price` · `percent` · `int` · `num`
- `markets` — (isteğe bağlı) alan yalnızca bu piyasalarda görünsün, ör. F/K kriptoda yok

Sunucu yalnızca katalogdaki alan ve operatörleri kabul eder; ekrandan gelen
serbest metin sorguya girmez.

## Kullanım notları

- **Değer alanı** `1.5M`, `250k`, `2,5` gibi girdileri anlar.
- **"Başka bir alanla karşılaştır"** işaretlenirse sağ taraf sayı değil kolon olur:
  `Fiyat > EMA50`, `MACD > MACD sinyal` gibi.
- **Kesişim** operatörleri (`yukarı keser` vb.) yalnızca kolon karşılaştırmasında anlamlıdır.
- `⌘↵` / `Ctrl+Enter` taramayı çalıştırır.
- Periyot seçimi yalnızca `tf: true` alanlara uygulanır; temel analiz alanları hep günlüktür.
- Tek istekte en fazla 500 satır döner (`MAX_ROWS`).

## Sınırlar

- Pine Script sunucu tarafında çalıştırılamaz. Özel bir Pine indikatörü gerekiyorsa
  mantığın Python'da yeniden yazılması gerekir; bu uygulama TradingView'in kendi
  hesapladığı kolonları kullanır.
- Servis TradingView'in resmî olarak belgelenmemiş uç noktasıdır; kolon adları
  zamanla değişebilir. Değişirse düzeltme `api/fields.json` içindedir.
