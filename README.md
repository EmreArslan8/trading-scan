# TradingView Tarayıcı

TradingView'in screener servisini kullanan yerel tarama uygulaması.
Kriterler ekrandan seçilir, sonuçlar tabloya düşer, CSV olarak indirilir.
Range modu, güncel fiyatı önceki tamamlanmış ayın veya çeyreğin düşük/orta/yüksek
seviyesiyle karşılaştırarak seçilen piyasa evrenini otomatik tarar.

## Çalıştırma

    python3 server.py          # http://127.0.0.1:8777
    python3 server.py 9000     # başka port

Python 3.8+ yeterli. **Kurulacak paket yok** — yalnızca standart kütüphane.

## Masaüstü program

Aynı uygulama kendi penceresinde, sunucusuz çalışır; istekler kullanıcının
kendi bağlantısından gider, demo sınırı yoktur.

    python3 -m venv .venv
    .venv/bin/pip install pywebview pyinstaller
    .venv/bin/python desktop.py     # paketlemeden dene
    .venv/bin/python build.py       # → dist/TVTarayici.app (Windows'ta .exe)

Her işletim sistemi kendi programını derler; bunu GitHub Actions yapar.
Yeni sürüm yayınlamak için etiket push'lanır:

    git tag v1.1 && git push origin v1.1

Windows `.exe` ve macOS `.zip` derlenip GitHub Releases'a konur. Sitedeki
"Bilgisayar programı" butonu `releases/latest/download/...` adresini kullandığı
için her zaman en son sürümü indirir.

İmzasız olduğu için ilk açılışta uyarı çıkar: Windows'ta *Daha fazla bilgi →
Yine de çalıştır*, macOS'ta uygulamaya sağ tık → *Aç*.

## Dosyalar

| dosya | işi |
|---|---|
| `api/_core.py` | tarama mantığı; ekrandan gelen kriterleri TradingView sorgusuna çevirir |
| `api/scan.py` | `POST /api/scan` uç noktası |
| `api/pinescan.py` | `POST /api/pinescan` — özel indikatör kodunu çalıştırır |
| `api/rangescan.py` | `POST /api/rangescan` — önceki ay/çeyrek range seviyelerini tarar |
| `api/reset.py` | `POST /api/reset` — demo çerezini temizler |
| `api/_series.py` | seri aritmetiği ve indikatörler (saf Python) |
| `api/_pine.py` | ifade değerlendirici (AST beyaz liste) |
| `api/_feeds.py` | mum verisi kaynakları (Yahoo, Binance) |
| `api/catalog.py` | `GET /api/catalog` uç noktası |
| `api/fields.json` | piyasalar, periyotlar, operatörler, alanlar, hazır taramalar |
| `public/index.html` | arayüz (tek dosya, çerçeve yok) |
| `server.py` | yerel geliştirme sunucusu; aynı çekirdeği kullanır |
| `desktop.py` | masaüstü sürüm: sunucuyu arka planda açıp kendi penceresinde gösterir |
| `build.py` | masaüstü programı PyInstaller ile paketler |
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

## Kendi indikatör kodunuz ("Kendi kodum" modu)

Pine Script TradingView dışında çalışmaz; bu mod, Pine'ın karşılığı olan
fonksiyonları Python'da sunar ve ifadeyi her sembolün mumları üzerinde çalıştırır.

    crossover(ema(close, 9), ema(close, 21)) and rsi(close, 14) > 45
    close > bb_upper(20, 2) and volume > sma(volume, 20) * 2
    barssince(crossover(macd(), macd_signal())) < 5 and adx(14) > 25

- **Kaynaklar:** `open high low close volume hl2 hlc3 ohlc4`
- **Fonksiyonlar:** `sma ema rma wma vwap rsi macd macd_signal macd_hist
  stoch_k stoch_d atr tr adx di_plus di_minus bb_upper bb_lower bb_basis stdev
  highest lowest change crossover crossunder cross rising falling barssince nz
  abs sum max min`
- **Gecikme:** `close[1]` bir önceki mum
- Sonuç, **son mumda** doğru olan sembollerdir.

Akış iki aşamalıdır: önce ekrandaki kriterlerle evren daraltılır (TradingView,
saniyenin altında), sonra kalan sembollerin mumları indirilip kod çalıştırılır.
100 sembol yaklaşık 13 saniye sürer.

### Doğruluk

İndikatörler TradingView'in kendi değerleriyle karşılaştırıldı; RSI, EMA, SMA,
MACD, sinyal, ATR, ADX, Stokastik ve Bollinger değerleri dört ondalık basamağa
kadar örtüşüyor.

### Güvenlik

İfade `eval` ile çalıştırılmaz. Metin AST'ye çevrilir, yalnızca izin verilen
düğüm türleri ve isimler kabul edilir; öznitelik erişimi, içe aktarma, döngü ve
atama reddedilir.

### Veri kaynakları

| piyasa | kaynak |
|---|---|
| BIST, ABD, Almanya, İngiltere | Yahoo Finance |
| Kripto | Binance |
| Forex | Yahoo Finance |

Dört saatlik periyot yalnızca kriptoda vardır. Bazı BIST sembollerinde Yahoo
verisi bulunmaz; bu semboller "veri yok" olarak raporlanır.

## Range taraması

"Range taraması" modunda piyasa, önceki ay/çeyrek, düşük/orta/yüksek seviye ve
"altında/üstünde" koşulu seçilir. Uygulama önce TradingView'den piyasa evrenini
alır, sonra günlük mumları takvim dönemlerine ayırır. İçinde bulunulan tamamlanmamış
dönem referansa katılmaz. Sonuç tablosu güncel fiyatı, referans seviyeyi, range'in
iki sınırını ve yüzde uzaklığı gösterir.

## Demo kullanım sınırı

Yayındaki demo herkese açık olduğundan kullanım sınırlıdır.

| ortam değişkeni | işi |
|---|---|
| `FREE_SCANS` | anahtarsız kullanıcının tarama hakkı (varsayılan 3) |
| `ACCESS_KEYS` | virgülle ayrılmış geçerli erişim anahtarları; anahtarla sınır yok |
| `DEMO_SECRET` | sayaç çerezini imzalayan gizli anahtar |
| `ACCESS_ONLY` | `1` yapılırsa anahtarsız erişim tamamen kapanır |

Sayaç, HMAC ile imzalanmış bir çerezde taşınır; kurcalanmış çerez reddedilir.
Hak `/api/scan` çağrısında harcanır, `/api/pinescan` parçaları ek hak yemez.

**Bunun bir kimlik doğrulama olmadığını bilerek kurgulandı:** çerezi silen ya da
gizli pencere açan kullanıcı hakkını tazeler. Amaç, demoyu sınırsız kullanmayı
zahmetli kılmaktır. Erişimi gerçekten kapatmak için `ACCESS_ONLY=1` kullanın.

## Sınırlar

- Pine Script sunucu tarafında çalıştırılamaz; "Kendi kodum" modu Pine'ın
  karşılığı olan fonksiyonları Python'da sunar. Çok karmaşık bir strateji
  (birden fazla zaman dilimi, pozisyon yönetimi) bire bir taşınmayabilir.
- Servis TradingView'in resmî olarak belgelenmemiş uç noktasıdır; kolon adları
  zamanla değişebilir. Değişirse düzeltme `api/fields.json` içindedir.
