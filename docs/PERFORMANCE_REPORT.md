# Performans incelemesi — 11–12 Kasım 2026

## Kapsam ve ortam

AMD Ryzen 7 8840HX, 12 çekirdek/24 mantıksal işlemci; Docker Desktop Linux VM: 24 CPU, 15.21 GiB RAM. Gerçek uygulama değiştirilmeden ayrı ağ ve geçici PostgreSQL/Redis üzerinde ölçüldü. Tek Uvicorn worker; API kotaları 2 vCPU/2 GiB ve 4 vCPU/4 GiB. Her iki profilde ayrıca PostgreSQL 1 CPU/768 MiB, Nginx 0.5 CPU/128 MiB, Redis 0.5 CPU/128 MiB. Dolayısıyla bunlar tüm makinenin 2 veya 4 vCPU ile sınırlandığı testler değildir.

10.000 sentetik haber, 100 sentetik kullanıcı ve kullanıcı başına iki portföy kaydı. Büyüme testi 100.040 haberle yapıldı. Yahoo fiyatları ve Gemini beklemesi taklit edildi; FinBERT, veritabanı, önbellek, parola hash işlemi ve JWT gerçek. Sohbet sağlayıcısı sabit 200 ms asenkron bekleme kullanır. Gerçek Gemini/Yahoo kapasitesi veya kota/maliyeti ölçülmedi.

Kapasite testinde limiter yalnızca izole API sürecinde kapatıldı. Gerçek uygulamanın korumaları değiştirilmedi. İstekler Nginx üzerinden gönderildi. Kapalı döngüde 1/10/30 ve ayrıca 100 eşzamanlı istek denendi; bu sayılar insan kullanıcı sayısı değildir. WAN/TLS/tarayıcı render ve yük üreticisi/ana makine etkisi dahil değildir.

Hedefler: okumalarda p95 ≤500 ms, girişte p95 ≤1000 ms, hata oranı <%1. Bunlar bu proje için değerlendirme eşikleridir. p99 ve maksimum süre ayrıca değerlendirilmelidir.

## Ölçümler

| Profil | Senaryo | Eşzamanlı istek | İstek/sn | p95 ms | p99 ms | En uzun ms | Hata % |
|---|---|---:|---:|---:|---:|---:|---:|
| api2cpu-2gb | static | 1 | 1072.5 | 1.24 | 1.55 | 13.95 | 0.0 |
| api2cpu-2gb | static | 10 | 750.03 | 39.85 | 73.78 | 1898.27 | 0.0 |
| api2cpu-2gb | static | 30 | 593.88 | 136.21 | 212.23 | 428.81 | 0.0 |
| api2cpu-2gb | warm_news | 1 | 425.2 | 2.66 | 2.94 | 12.64 | 0.0 |
| api2cpu-2gb | warm_news | 10 | 949.06 | 11.53 | 19.16 | 108.13 | 0.0 |
| api2cpu-2gb | warm_news | 30 | 638.27 | 142.29 | 212.0 | 361.72 | 0.0 |
| api2cpu-2gb | db_news | 1 | 135.25 | 8.06 | 9.6 | 41.58 | 0.0 |
| api2cpu-2gb | db_news | 10 | 134.56 | 180.78 | 217.56 | 361.17 | 0.0 |
| api2cpu-2gb | db_news | 30 | 162.28 | 293.78 | 359.34 | 458.36 | 0.0 |
| api2cpu-2gb | portfolio | 1 | 109.2 | 10.66 | 12.87 | 42.27 | 0.0 |
| api2cpu-2gb | portfolio | 10 | 176.88 | 135.64 | 171.41 | 221.14 | 0.0 |
| api2cpu-2gb | portfolio | 30 | 170.05 | 396.71 | 490.51 | 526.77 | 0.0 |
| api2cpu-2gb | login | 1 | 36.88 | 29.45 | 36.85 | 39.66 | 0.0 |
| api2cpu-2gb | login | 10 | 46.61 | 247.62 | 277.43 | 500.78 | 0.0 |
| api2cpu-2gb | login | 30 | 47.17 | 676.12 | 698.76 | 1009.96 | 0.0 |
| api2cpu-2gb | correlation | 1 | 139.29 | 8.61 | 9.57 | 13.07 | 0.0 |
| api2cpu-2gb | correlation | 10 | 214.89 | 132.02 | 190.97 | 310.16 | 0.0 |
| api2cpu-2gb | correlation | 30 | 220.35 | 247.02 | 291.91 | 383.26 | 0.0 |
| api2cpu-2gb | news_during_40_article_collection | 10 | 541.39 | 12.53 | 131.47 | 2767.47 | 0.0 |
| api2cpu-2gb | news_soak | 10 | 286.56 | 96.24 | 102.51 | 316.52 | 0.0 |
| api2cpu-2gb | dashboard | 1 | 250.32 | 6.61 | 7.36 | 36.56 | 0.0 |
| api2cpu-2gb | dashboard | 10 | 518.06 | 24.8 | 36.08 | 99.94 | 0.0 |
| api2cpu-2gb | dashboard | 30 | 349.76 | 248.47 | 405.06 | 978.64 | 0.0 |
| api2cpu-2gb | chat_stub | 1 | 4.86 | 207.94 | 207.99 | 207.99 | 0.0 |
| api2cpu-2gb | chat_stub | 10 | 47.9 | 210.55 | 341.61 | 343.5 | 0.0 |
| api2cpu-2gb | chat_stub | 30 | 71.59 | 419.6 | 675.42 | 687.53 | 0.0 |
| api2cpu-2gb | warm_news | 100 | 372.35 | 774.76 | 1286.8 | 2102.39 | 0.0 |
| api4cpu-4gb | static | 1 | 1090.26 | 1.19 | 1.47 | 8.9 | 0.0 |
| api4cpu-4gb | static | 10 | 1023.81 | 8.97 | 12.15 | 3501.45 | 0.0 |
| api4cpu-4gb | static | 30 | 498.46 | 165.99 | 264.93 | 473.48 | 0.0 |
| api4cpu-4gb | warm_news | 1 | 411.89 | 2.81 | 3.22 | 15.13 | 0.0 |
| api4cpu-4gb | warm_news | 10 | 962.66 | 11.32 | 15.38 | 116.12 | 0.0 |
| api4cpu-4gb | warm_news | 30 | 636.93 | 137.06 | 217.95 | 419.24 | 0.0 |
| api4cpu-4gb | db_news | 1 | 133.64 | 8.52 | 9.34 | 27.04 | 0.0 |
| api4cpu-4gb | db_news | 10 | 125.76 | 183.0 | 220.79 | 261.59 | 0.0 |
| api4cpu-4gb | db_news | 30 | 155.45 | 298.26 | 366.23 | 424.79 | 0.0 |
| api4cpu-4gb | portfolio | 1 | 101.47 | 11.79 | 12.96 | 25.26 | 0.0 |
| api4cpu-4gb | portfolio | 10 | 171.44 | 165.13 | 190.98 | 210.35 | 0.0 |
| api4cpu-4gb | portfolio | 30 | 160.68 | 438.47 | 497.42 | 520.42 | 0.0 |
| api4cpu-4gb | login | 1 | 35.45 | 29.59 | 35.74 | 224.74 | 0.0 |
| api4cpu-4gb | login | 10 | 45.25 | 260.2 | 420.56 | 513.4 | 0.0 |
| api4cpu-4gb | login | 30 | 46.17 | 674.15 | 705.31 | 746.91 | 0.0 |
| api4cpu-4gb | correlation | 1 | 132.13 | 8.64 | 9.76 | 14.71 | 0.0 |
| api4cpu-4gb | correlation | 10 | 199.57 | 140.57 | 174.69 | 207.02 | 0.0 |
| api4cpu-4gb | correlation | 30 | 208.56 | 261.18 | 350.05 | 414.61 | 0.0 |
| api4cpu-4gb | news_during_40_article_collection | 10 | 642.17 | 13.82 | 106.82 | 1854.72 | 0.0 |
| api4cpu-4gb | news_soak | 10 | 267.54 | 98.97 | 109.54 | 189.94 | 0.0 |
| api4cpu-4gb | dashboard | 1 | 248.45 | 6.69 | 7.52 | 38.56 | 0.0 |
| api4cpu-4gb | dashboard | 10 | 475.44 | 34.86 | 52.66 | 112.21 | 0.0 |
| api4cpu-4gb | dashboard | 30 | 468.98 | 102.54 | 161.27 | 309.35 | 0.0 |
| api4cpu-4gb | chat_stub | 1 | 4.86 | 207.46 | 207.79 | 207.79 | 0.0 |
| api4cpu-4gb | chat_stub | 10 | 47.94 | 209.72 | 335.94 | 338.31 | 0.0 |
| api4cpu-4gb | chat_stub | 30 | 72.09 | 420.04 | 658.61 | 679.64 | 0.0 |
| api4cpu-4gb | warm_news | 100 | 364.48 | 797.67 | 1314.34 | 2355.33 | 0.0 |
| api4cpu-100k | portfolio | 1 | 50.1 | 22.52 | 26.96 | 60.62 | 0.0 |
| api4cpu-100k | portfolio | 10 | 60.14 | 365.51 | 426.82 | 524.57 | 0.0 |
| api4cpu-100k | portfolio | 30 | 54.6 | 704.49 | 874.89 | 1179.76 | 0.0 |
| api4cpu-100k | correlation | 1 | 30.18 | 35.3 | 65.73 | 83.29 | 0.0 |
| api4cpu-100k | correlation | 10 | 32.51 | 406.66 | 501.09 | 501.94 | 0.0 |
| api4cpu-100k | correlation | 30 | 27.6 | 1304.76 | 1485.0 | 1789.55 | 0.0 |
| api4cpu-100k | db_news | 1 | 9.85 | 146.58 | 167.68 | 167.68 | 0.0 |
| api4cpu-100k | db_news | 10 | 12.75 | 1491.09 | 1832.12 | 1833.72 | 0.0 |
| api4cpu-100k | db_news | 30 | 11.95 | 3995.93 | 4299.27 | 4753.68 | 0.0 |
| api4cpu-100k | 100k_news_mixed_300s_with_collection | 10 | 118.87 | 294.88 | 478.96 | 4243.93 | 0.0 |

Toplam ölçülen istek: 180,838.

`db_news`: derin OFFSET taramasıdır; çoğu sonuç boştur ve önbelleğe yazılmaz. 100 bin kayıt sınırında ilk birkaç cevap son sayfa verisi içerip önbelleklenebilir. Normal ilk sayfa ile eşdeğer değildir. `dashboard`: altı API okuması dönüşümlü gönderilir, tam bir tarayıcı oturumu değildir. 45 saniyelik haber ve 300 saniyelik karma yük, kısa kararlılık örnekleridir; bellek sızıntısı olmadığını kanıtlamaz. İlk 180 saniyelik örnekte %26.6 HTTP 401 görüldü; başarılı sayılmadı ve ham dosya korundu. Kök neden kesinleşmedi; tekrar testinde elle imzalanan kısa token yerine uygulamanın giriş endpointinin verdiği token kullanıldı. Aşağıdaki kararlılık sonucu yeniden ölçülen örnektir.

## FinBERT ve bellek

- api2cpu-2gb: 40 haber toplama/analiz/kayıt döngüsü 6.27 sn. Süreç belleği: ['VmHWM:\t 1159308 kB', 'VmRSS:\t 1157212 kB', 'RssAnon:\t  488804 kB']. Cgroup tepe değeri: 510.6 MiB.
- api4cpu-4gb: 40 haber toplama/analiz/kayıt döngüsü 4.16 sn. Süreç belleği: ['VmHWM:\t 1159920 kB', 'VmRSS:\t 1159920 kB', 'RssAnon:\t  490820 kB']. Cgroup tepe değeri: 506.3 MiB.
- 300 sn karma yükte API cgroup bellek aralığı: 499.8–510.1 MiB.

Paylaşılan model dosyaları/sayfa önbelleği nedeniyle cgroup belleği ile süreç RSS aynı değildir. Tek başına düşük Docker bellek sayısı minimum RAM kanıtı sayılmadı. Model diskte önceden mevcut; başlangıç ölçümü ağdan model indirmeyi içermez. OOM gözlenmemesi daha düşük bellek sınırlarının da güvenli olduğu anlamına gelmez.

## Bulgular ve öncelikler

1. FinBERT API olay döngüsünde senkron çalışıyor. Toplu analiz sırasında maksimum yanıt süreleri yükseliyor; arka plan işini ayrı worker sürecine taşımak öncelikli.
2. Parola hash doğrulaması da asenkron endpoint içinde senkron. API CPU kotasını artırmak tek worker içindeki bu işi otomatik paralelleştirmiyor.
3. Büyüyen veri kümesinde tarih sıralama ve duygu gruplama maliyeti belirginleşiyor. Sorgu planlarına göre indeks, sayfalama ve özet/önbellek düzeni değerlendirilmeli; bu incelemede şema değiştirilmedi.
4. Gerçek kodda portföy ve grafik istekleri fiyat servisine tekrar gidebiliyor. Testte sağlayıcı anlık döndüğü için bu uçların gerçek dış servis gecikmesi ve kota sınırları sonuçlara dahil değil. Paylaşılan fiyat önbelleği ve eşzamanlı aynı veriyi çekmeyi birleştirme gerekli.

## Boyutlandırma kararı

İlk sınırlı yayın için öneri: **4 vCPU, 8 GB RAM, x86 Linux, 80 GB minimum / 160 GB tercih edilen SSD; GPU gerekmez**. Bu bir satın alınacak VPS üzerinde garanti edilmiş kullanıcı kapasitesi değildir. API için 2 vCPU civarı bütçe, diğer servisler ve işletim sistemi için kalan kaynaklarla başlanabilir. 4 GB toplam RAM ancak daha düşük güvenlik payıyla adaydır; tam makine 4 GB sınırında bu çalışmada doğrulanmadı.

Yerel API imajı yaklaşık 10.15 GB; GPU kullanılmadığı halde kurulu ML bağımlılıkları disk alanını büyütüyor. Kurulum/derleme tepe diski, yedek birikimi ve uzun süreli veri büyümesi ayrıca izlenmeli. Canlı sunucuda HTTPS üzerinden, gerçekçi geliş hızı ve kontrollü sağlayıcı çağrılarıyla tekrar test şarttır. Bu ölçümler “kesin olarak X kullanıcı taşır” sonucunu desteklemez.

## Yeniden çalıştırma

Test komutları ve izolasyon sınırları: `tests/performance/README.md`. Ham JSON ve SQL sorgu planları yerel `performance-results/` altında. Yedekleme dosyaları ve gerçek kullanıcı verileri bu sonuçlara dahil değildir.

## Sabit geliş hızlı tekrarlar

Her hız 15 saniye boyunca üç tur denendi. Gecikme planlanan gönderim anından ölçülür; yük üreticisi gecikmesi ve 200 bekleyen istek sınırında bırakılan işler ayrıca raporlanır.

| Tur | Hedef istek/sn | Tamamlanan | p95 ms | p99 ms | Üretici gecikmesi p95 ms | Bırakılan | Hata % |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 25 | 375 | 35.21 | 45.12 | 1.95 | 0 | 0.0 |
| 1 | 50 | 750 | 32.52 | 33.56 | 1.83 | 0 | 0.0 |
| 1 | 100 | 1500 | 33.92 | 36.51 | 1.64 | 0 | 0.0 |
| 1 | 200 | 2155 | 2642.53 | 2790.69 | 1.38 | 845 | 28.17 |
| 2 | 25 | 375 | 38.74 | 59.67 | 2.03 | 0 | 0.0 |
| 2 | 50 | 750 | 32.87 | 33.76 | 1.76 | 0 | 0.0 |
| 2 | 100 | 1500 | 34.12 | 35.97 | 1.57 | 0 | 0.0 |
| 2 | 200 | 2143 | 2649.93 | 2859.29 | 1.24 | 857 | 28.57 |
| 3 | 25 | 375 | 40.05 | 60.22 | 1.95 | 0 | 0.0 |
| 3 | 50 | 750 | 35.98 | 41.5 | 1.41 | 0 | 0.0 |
| 3 | 100 | 1500 | 35.88 | 39.21 | 1.66 | 0 | 0.0 |
| 3 | 200 | 2116 | 2706.28 | 2892.61 | 1.32 | 884 | 29.47 |

## Arıza ve toparlanma

Yalnızca `finans-performance` proje etiketi doğrulanan konteynerler kısa süreli duraklatıldı; her duraklatma `finally` ile geri alındı. Üretim konteynerleri açılmadı/durdurulmadı.
- finans-performance-redis-1: kesintide health=503 (3.004 sn), haber okuma=TimeoutError (6.009 sn); toparlanmada health=200.
- finans-performance-postgres-1: kesintide health=TimeoutError (6.009 sn), haber okuma=200 (0.005 sn); toparlanmada health=200.
- API yeniden başlatma: hazır olma 14.18 sn, health=200.

Duraklatılmış Redis bağlantısında haber isteğinin istemci zaman aşımına uğraması, sunucu endpointinin kontrollü ve hızlı hata verdiği anlamına gelmez. Bağlantı/okuma zaman aşımı ve uygun hata/fallback davranışı ayrı bir iyileştirmedir. PostgreSQL duraklatıldığında health istemcisinin 6 saniyede zaman aşımına uğraması da hedeflenen 3 saniyelik kontrolün sürücü iptali tamamlanmasını beklerken aşılabildiğini gösterir. PostgreSQL yokken önbellekli haberin sunulabilmesi de yeni sorguların çalıştığını kanıtlamaz.

Sonrasında 19 regresyon testi ve Nginx üzerinden statik dosya/API smoke kontrolleri yeniden çalıştırıldı. Bunlar tarayıcı performans testi, güvenlik denetimi veya dış sağlayıcı yük testi yerine geçmez.

Tekrarlı sabit geliş testleri dahil ölçülen istek: 195,127.

## Son karar

**Yerel test kapsamı tamamlandı; performans onayı koşulludur.** 100 istek/sn düzeyindeki üç kısa sabit-hız örneği başarılıdır; 200 istek/sn sürdürülememiştir. Bu sayılar gerçek Gemini/Yahoo çağrıları veya tarayıcı kullanıcıları için kapasite garantisi değildir. Beş dakikalık 10 eşzamanlı karma yükte 35.680 istek HTTP 200 dönmüş, p95 294.88 ms, en uzun süre 4243.93 ms ölçülmüştür. 100 bin haberde 30 eşzamanlı portföy/grafik okuması ve 100 eşzamanlı haber örnekleri hız hedefini aşmıştır.

Canlı öncesi öncelikler: (1) FinBERT işini API sürecinden ayırma; (2) tarih indeksleri, sayfalama ve duygu özeti/önbelleği; (3) ortak fiyat önbelleği; (4) Redis/SQL bağlantı ve okuma zaman aşımı ile kontrollü hata davranışı. Bu çalışmada sorunları ölçmek için üretim iş mantığı değiştirilmedi. Güvenlik sızma testi, gerçek disk/crash dayanıklılığı, Lighthouse/Web Vitals, uzun saatler süren soak ve seçilecek VPS üzerinde HTTPS/WAN testleri kapsam dışıdır.
