# Performans iyileştirmeleri — 12 Kasım 2026

Yerel son dağıtım doğrulaması: API, frontend, PostgreSQL, Redis ve worker sağlıklı. Beş kullanıcının profil/portföy/rapor/takip uçlarında toplam 20 yetkili okuma başarılı; 5 kullanıcı, 6 portföy kaydı ve 3 takip kaydı korunuyor. Dört yeni indeks geçerli; gerçek veride cursor sayfalaması başarılı. Üretim frontend dosyaları, Nginx güvenlik/önbellek başlıkları ve API proxy smoke kontrolü geçti. Veritabanının güncelleme öncesi yedeği geçici veritabanına geri yüklenerek doğrulandı.

Haber kaynakları ayrıca gerçek HTTP çağrılarıyla kontrol edildi: Finnhub 15, Yahoo Finance 15, CoinDesk 10 haber döndürdü. Yahoo'nun 404 veren eski RSS adresi endeks haberleri akışıyla değiştirildi; Yahoo/CoinDesk için yönlendirme takibi eklendi. Bu sayılar anlık entegrasyon kontrolüdür. Yük testlerinde dış servisler taklit edildi; gerçek sağlayıcı kota ve gecikmeleri kapasite ölçümüne dahil değildir. Son RSS düzenlemesi ve log seviyesi düzeltmesinden sonra 26 test yeniden geçti; performans ölçümleri çekirdek API/worker iyileştirmelerini kapsar.

## Uygulanan değişiklikler

- Haber toplama ve FinBERT ayrı worker süreci/konteynerine taşındı; API model yüklemiyor.
- Tarih+kimlik, kategori+tarih+kimlik, duygu+tarih+kimlik ve kategori+duygu+tarih+kimlik indeksleri eklendi. Mevcut tablolar silinmez; indeksler concurrent ve tekrar çalıştırılabilir biçimde oluşturulur.
- Haberlerde eşit tarihli kayıtlar için kimlikli cursor sayfalaması eklendi; eski offset API korunuyor. Frontend daha fazla yüklerken cursor kullanıyor. Offset yolunda önce yalnızca sayfa kimlikleri seçiliyor.
- Fiyatlar ticker, portföy ve grafikte ortak Redis önbelleği kullanıyor (60 sn). Yerel ve dağıtık doldurma kilidi aynı verinin eşzamanlı tekrar çekilmesini azaltıyor.
- Duygu özetleri 30 sn önbellekleniyor; worker yeni haberleri commit ettikten sonra generation değerini artırarak haber/duygu önbelleğini geçersiz kılıyor.
- Redis bağlantı/okuma, SQL bağlantı/komut ve HTTP yanıt bütçeleri sınırlandı. Health kontrolü, sürücü iptalinin takılmasını beklemeden 503 dönebiliyor.
- Parola hash/doğrulama iki iş parçacığıyla sınırlı ayrı havuza taşındı.

## Kapsam ve karşılaştırma sınırları

Aynı yerel Docker host, sentetik PostgreSQL ve Yahoo/Gemini taklitleri kullanıldı. Önceki SQL tablosu API 4 CPU kotasıyla; yeni tablo API 1 CPU ve ayrı NLP worker 1 CPU kotasıyla ölçüldü. PostgreSQL 1 CPU, Nginx/Redis toplam 1 CPU olarak aynı kaldı. NLP karşılaştırmasında eski API 2 CPU bütçesi, yeni API 1 + worker 1 şeklinde bölündü; toplam CPU tavanı aynı. Bellek limitleri yeni API 1 GiB + worker 2 GiB; bunlar fiziksel VPS minimum gereksinim kanıtı değildir. Ham örnekler aynı gün/host olsa da süre, önbellek sıcaklığı ve işletim sistemi zamanlaması değişebilir.

## 100 bin haber, 30 eşzamanlı istek

| Senaryo | Önce p95 ms | Sonra p95 ms | Sonra hata % |
|---|---:|---:|---:|
| portfolio | 704.49 | 233.22 | 0.0 |
| correlation | 1304.76 | 412.32 | 0.0 |
| db_news | 3995.93 | 304.01 | 0.0 |

`db_news` derin OFFSET yoludur; normal frontend artık cursor kullanır. Önbellekli örneklerde çok daha az SQL çalışması beklenen davranıştır; sıcak cache sonucu ham DB kapasitesi değildir.

## Toplu NLP sırasında API

| Ölçüm | Önce (API içinde) | Sonra (ayrı worker) |
|---|---:|---:|
| p95_ms | 12.53 | 34.7 |
| p99_ms | 131.47 | 99.78 |
| max_ms | 2767.47 | 1368.82 |
| 40 haberin tamamlanması (sn) | 6.27 | 12.77 |

Worker CPU bütçesi düşük tutulduğundan batch süresi uzayabilir; amaç HTTP API olay döngüsünü model işinden ayırmaktır. Maksimum yanıtlar ayrıca izlenir; ayrı worker tek başına bütün kuyruk gecikmelerini sıfırlamaz.

## Beş dakikalık karma yük ve üç turlu sabit hız

```json
{
  "case": "100k_news_mixed_300s_with_collection",
  "concurrency": 10,
  "elapsed_s": 300.02,
  "requests": 101954,
  "rps": 339.82,
  "p50_ms": 18.77,
  "p95_ms": 88.81,
  "p99_ms": 100.28,
  "max_ms": 255.19,
  "error_pct": 0.0,
  "statuses": {
    "200": 101954
  }
}
```

| Tur | Hedef istek/sn | p95 ms | Bırakılan | Hata % (bırakılan dahil) |
|---|---:|---:|---:|---:|
| 1 | 25 | 9.0 | 0 | 0.0 |
| 1 | 50 | 6.04 | 0 | 0.0 |
| 1 | 100 | 5.7 | 0 | 0.0 |
| 1 | 200 | 5.69 | 0 | 0.0 |
| 2 | 25 | 7.14 | 0 | 0.0 |
| 2 | 50 | 6.1 | 0 | 0.0 |
| 2 | 100 | 5.71 | 0 | 0.0 |
| 2 | 200 | 5.6 | 0 | 0.0 |
| 3 | 25 | 7.17 | 0 | 0.0 |
| 3 | 50 | 5.96 | 0 | 0.0 |
| 3 | 100 | 5.78 | 0 | 0.0 |
| 3 | 200 | 5.61 | 0 | 0.0 |

## Kesinti ve yeniden başlatma

| Servis | Önce | Sonra |
|---|---|---|
| finans-performance-redis-1 health | 503 / 3.004 sn | 503 / 1.006 sn |
| finans-performance-redis-1 haber okuma | TimeoutError / 6.009 sn | 503 / 1.006 sn |
| finans-performance-postgres-1 health | TimeoutError / 6.009 sn | 503 / 1.504 sn |
| finans-performance-postgres-1 haber okuma | 200 / 0.005 sn | 503 / 3.007 sn |
| API yeniden hazır | 14.18 sn | 2.74 sn |

Önbellek süresine göre DB kesintisinde haber okuma 200 veya kontrollü 503 dönebilir. Redis kesintisinde istek sınırlarını sessizce devre dışı bırakmak yerine 503 dönülür. Kesintiler yalnızca geçici test konteynerlerinde uygulandı.

## Doğrulama ve işletim

26 regresyon testi; timestamp eşitliğinde cursor/offset eşitliği; doğrudan SQL ile cache raporunun sayısal eşitliği; indeks geçerliliği ve API importunda torch/collector bulunmaması kontrol edildi. NLP test workerının ilk kuyruk bekleme denemesinde socket bütçesi uyumsuzluğu tespit edilip düzeltildi; o eksik batch örneği başarılı karşılaştırma olarak kullanılmadı.

Docker Compose artık `worker` servisini de başlatır. Docker dışı geliştirmede API yanında `python -m app.worker` ayrıca çalıştırılmalıdır. Aynı veritabanındaki workerlar advisory lock ile korunur. Şema hazırlığı API başlangıcında additive indeks oluşturur; büyük veritabanında süre ve yetkiler izlenmelidir. Worker sağlık kontrolü Redis heartbeat liveness kontrolüdür, her kaynağın veri getirdiğinin garantisi değildir.

Başlangıç sunucu önerisi 4 vCPU / 8 GB RAM / tercihen 160 GB SSD olarak korunur. Seçilecek gerçek VPS üzerinde HTTPS/WAN ve kontrollü gerçek sağlayıcı entegrasyonu yeniden ölçülmelidir. Beş dakikalık örnek uzun süreli bellek sızıntısı veya binlerce gerçek kullanıcı garantisi sağlamaz.
