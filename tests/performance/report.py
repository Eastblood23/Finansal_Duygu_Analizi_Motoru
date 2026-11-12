import json
from pathlib import Path

root=Path('/results')
profiles={name:json.loads((root/(name+'.json')).read_text()) for name in ('api2cpu-2gb','api4cpu-4gb')}
extras={name:json.loads((root/(name+'-extra.json')).read_text()) for name in ('api2cpu-2gb','api4cpu-4gb','api4cpu-100k')}
soak=json.loads((root/'100k-soak.json').read_text())
lines=['# Performans incelemesi — 11–12 Kasım 2026', '',
'## Kapsam ve ortam', '',
'AMD Ryzen 7 8840HX, 12 çekirdek/24 mantıksal işlemci; Docker Desktop Linux VM: 24 CPU, 15.21 GiB RAM. '
'Gerçek uygulama değiştirilmeden ayrı ağ ve geçici PostgreSQL/Redis üzerinde ölçüldü. '
'Tek Uvicorn worker; API kotaları 2 vCPU/2 GiB ve 4 vCPU/4 GiB. '
'Her iki profilde ayrıca PostgreSQL 1 CPU/768 MiB, Nginx 0.5 CPU/128 MiB, Redis 0.5 CPU/128 MiB. '
'Dolayısıyla bunlar tüm makinenin 2 veya 4 vCPU ile sınırlandığı testler değildir.', '',
'10.000 sentetik haber, 100 sentetik kullanıcı ve kullanıcı başına iki portföy kaydı. '
'Büyüme testi 100.040 haberle yapıldı. Yahoo fiyatları ve Gemini beklemesi taklit edildi; '
'FinBERT, veritabanı, önbellek, parola hash işlemi ve JWT gerçek. '
'Sohbet sağlayıcısı sabit 200 ms asenkron bekleme kullanır. Gerçek Gemini/Yahoo kapasitesi veya kota/maliyeti ölçülmedi.', '',
'Kapasite testinde limiter yalnızca izole API sürecinde kapatıldı. Gerçek uygulamanın korumaları değiştirilmedi. '
'İstekler Nginx üzerinden gönderildi. Kapalı döngüde 1/10/30 ve ayrıca 100 eşzamanlı istek denendi; '
'bu sayılar insan kullanıcı sayısı değildir. WAN/TLS/tarayıcı render ve yük üreticisi/ana makine etkisi dahil değildir.', '',
'Hedefler: okumalarda p95 ≤500 ms, girişte p95 ≤1000 ms, hata oranı <%1. '
'Bunlar bu proje için değerlendirme eşikleridir. p99 ve maksimum süre ayrıca değerlendirilmelidir.', '',
'## Ölçümler', '',
'| Profil | Senaryo | Eşzamanlı istek | İstek/sn | p95 ms | p99 ms | En uzun ms | Hata % |',
'|---|---|---:|---:|---:|---:|---:|---:|']
all_rows=[]
for name,profile in profiles.items():
    for row in profile['results']+extras[name]:
        all_rows.append((name,row))
for row in extras['api4cpu-100k']:
    all_rows.append(('api4cpu-100k',row))
all_rows.append(('api4cpu-100k',soak['result']))
for name,row in all_rows:
    lines.append(f"| {name} | {row['case']} | {row['concurrency']} | {row['rps']} | {row['p95_ms']} | {row['p99_ms']} | {row['max_ms']} | {row['error_pct']} |")
lines+=['', f"Toplam ölçülen istek: {sum(row['requests'] for _,row in all_rows):,}.", '',
'`db_news`: derin OFFSET taramasıdır; çoğu sonuç boştur ve önbelleğe yazılmaz. 100 bin kayıt sınırında '
'ilk birkaç cevap son sayfa verisi içerip önbelleklenebilir. Normal ilk sayfa ile eşdeğer değildir. '
'`dashboard`: altı API okuması dönüşümlü gönderilir, tam bir tarayıcı oturumu değildir. '
'45 saniyelik haber ve 300 saniyelik karma yük, kısa kararlılık örnekleridir; bellek sızıntısı olmadığını kanıtlamaz. '
'İlk 180 saniyelik örnekte %26.6 HTTP 401 görüldü; başarılı sayılmadı ve ham dosya korundu. '
'Kök neden kesinleşmedi; tekrar testinde elle imzalanan kısa token yerine uygulamanın giriş endpointinin verdiği token kullanıldı. '
'Aşağıdaki kararlılık sonucu yeniden ölçülen örnektir.', '',
'## FinBERT ve bellek', '']
for name,profile in profiles.items():
    resources=json.loads((root/(name+'-final-resources.json')).read_text())
    lines.append(f"- {name}: 40 haber toplama/analiz/kayıt döngüsü {profile['collection']['seconds']:.2f} sn. Süreç belleği: {resources['process_memory']}. Cgroup tepe değeri: {int(resources['cgroup_memory_peak'])/1024**2:.1f} MiB.")
mem=[int(sample['resources']['memory.current'])/1024**2 for sample in soak['samples']]
lines += [f"- 300 sn karma yükte API cgroup bellek aralığı: {min(mem):.1f}–{max(mem):.1f} MiB.", '',
'Paylaşılan model dosyaları/sayfa önbelleği nedeniyle cgroup belleği ile süreç RSS aynı değildir. '
'Tek başına düşük Docker bellek sayısı minimum RAM kanıtı sayılmadı. Model diskte önceden mevcut; '
'başlangıç ölçümü ağdan model indirmeyi içermez. OOM gözlenmemesi daha düşük bellek sınırlarının da güvenli olduğu anlamına gelmez.', '',
'## Bulgular ve öncelikler', '',
'1. FinBERT API olay döngüsünde senkron çalışıyor. Toplu analiz sırasında maksimum yanıt süreleri yükseliyor; '
'arka plan işini ayrı worker sürecine taşımak öncelikli.',
'2. Parola hash doğrulaması da asenkron endpoint içinde senkron. API CPU kotasını artırmak tek worker içindeki bu işi otomatik paralelleştirmiyor.',
'3. Büyüyen veri kümesinde tarih sıralama ve duygu gruplama maliyeti belirginleşiyor. '
'Sorgu planlarına göre indeks, sayfalama ve özet/önbellek düzeni değerlendirilmeli; bu incelemede şema değiştirilmedi.',
'4. Gerçek kodda portföy ve grafik istekleri fiyat servisine tekrar gidebiliyor. '
'Testte sağlayıcı anlık döndüğü için bu uçların gerçek dış servis gecikmesi ve kota sınırları sonuçlara dahil değil. '
'Paylaşılan fiyat önbelleği ve eşzamanlı aynı veriyi çekmeyi birleştirme gerekli.', '',
'## Boyutlandırma kararı', '',
'İlk sınırlı yayın için öneri: **4 vCPU, 8 GB RAM, x86 Linux, 80 GB minimum / 160 GB tercih edilen SSD; GPU gerekmez**. '
'Bu bir satın alınacak VPS üzerinde garanti edilmiş kullanıcı kapasitesi değildir. API için 2 vCPU civarı bütçe, '
'diğer servisler ve işletim sistemi için kalan kaynaklarla başlanabilir. 4 GB toplam RAM ancak daha düşük '
'güvenlik payıyla adaydır; tam makine 4 GB sınırında bu çalışmada doğrulanmadı.', '',
'Yerel API imajı yaklaşık 10.15 GB; GPU kullanılmadığı halde kurulu ML bağımlılıkları disk alanını büyütüyor. '
'Kurulum/derleme tepe diski, yedek birikimi ve uzun süreli veri büyümesi ayrıca izlenmeli. '
'Canlı sunucuda HTTPS üzerinden, gerçekçi geliş hızı ve kontrollü sağlayıcı çağrılarıyla tekrar test şarttır. '
'Bu ölçümler “kesin olarak X kullanıcı taşır” sonucunu desteklemez.', '',
'## Yeniden çalıştırma', '',
'Test komutları ve izolasyon sınırları: `tests/performance/README.md`. '
'Ham JSON ve SQL sorgu planları yerel `performance-results/` altında. '
'Yedekleme dosyaları ve gerçek kullanıcı verileri bu sonuçlara dahil değildir.', '']
arrivals=json.loads((root/'fixed-arrival-100k.json').read_text())
faults=json.loads((root/'resilience.json').read_text())
lines += ['## Sabit geliş hızlı tekrarlar', '',
    'Her hız 15 saniye boyunca üç tur denendi. Gecikme planlanan gönderim anından ölçülür; '
    'yük üreticisi gecikmesi ve 200 bekleyen istek sınırında bırakılan işler ayrıca raporlanır.', '',
    '| Tur | Hedef istek/sn | Tamamlanan | p95 ms | p99 ms | Üretici gecikmesi p95 ms | Bırakılan | Hata % |',
    '|---|---:|---:|---:|---:|---:|---:|---:|']
for row in arrivals:
    lines.append(f"| {row['round']} | {row['offered_rps']} | {row['completed']} | {row['p95_ms']} | {row['p99_ms']} | {row['generator_lag_p95_ms']} | {row['dropped']} | {row['error_pct']} |")
lines += ['', '## Arıza ve toparlanma', '',
    'Yalnızca `finans-performance` proje etiketi doğrulanan konteynerler kısa süreli duraklatıldı; '
    'her duraklatma `finally` ile geri alındı. Üretim konteynerleri açılmadı/durdurulmadı.']
for fault in faults:
    if 'unavailable_health' in fault:
        lines.append(f"- {fault['service']}: kesintide health={fault['unavailable_health']['status']} "
            f"({fault['unavailable_health']['elapsed_s']} sn), haber okuma={fault['unavailable_read']['status']} "
            f"({fault['unavailable_read']['elapsed_s']} sn); toparlanmada health={fault['recovered_health']['status']}.")
    else:
        lines.append(f"- API yeniden başlatma: hazır olma {fault['restart_ready_seconds']} sn, health={fault['recovered_health']['status']}.")
lines += ['',
    'Duraklatılmış Redis bağlantısında haber isteğinin istemci zaman aşımına uğraması, '
    'sunucu endpointinin kontrollü ve hızlı hata verdiği anlamına gelmez. Bağlantı/okuma zaman aşımı '
    've uygun hata/fallback davranışı ayrı bir iyileştirmedir. PostgreSQL duraklatıldığında health '
    'istemcisinin 6 saniyede zaman aşımına uğraması da hedeflenen 3 saniyelik kontrolün sürücü iptali '
    'tamamlanmasını beklerken aşılabildiğini gösterir. PostgreSQL yokken önbellekli haberin '
    'sunulabilmesi de yeni sorguların çalıştığını kanıtlamaz.', '',
    'Sonrasında 19 regresyon testi ve Nginx üzerinden statik dosya/API smoke kontrolleri yeniden çalıştırıldı. '
    'Bunlar tarayıcı performans testi, güvenlik denetimi veya dış sağlayıcı yük testi yerine geçmez.', '',
    f"Tekrarlı sabit geliş testleri dahil ölçülen istek: {sum(row['requests'] for _,row in all_rows)+sum(row['completed'] for row in arrivals):,}.", '',
    '## Son karar', '',
    '**Yerel test kapsamı tamamlandı; performans onayı koşulludur.** '
    '100 istek/sn düzeyindeki üç kısa sabit-hız örneği başarılıdır; 200 istek/sn sürdürülememiştir. '
    'Bu sayılar gerçek Gemini/Yahoo çağrıları veya tarayıcı kullanıcıları için kapasite garantisi değildir. '
    'Beş dakikalık 10 eşzamanlı karma yükte 35.680 istek HTTP 200 dönmüş, p95 294.88 ms, '
    'en uzun süre 4243.93 ms ölçülmüştür. '
    '100 bin haberde 30 eşzamanlı portföy/grafik okuması ve 100 eşzamanlı haber örnekleri hız hedefini aşmıştır.', '',
    'Canlı öncesi öncelikler: (1) FinBERT işini API sürecinden ayırma; (2) tarih indeksleri, '
    'sayfalama ve duygu özeti/önbelleği; (3) ortak fiyat önbelleği; '
    '(4) Redis/SQL bağlantı ve okuma zaman aşımı ile kontrollü hata davranışı. '
    'Bu çalışmada sorunları ölçmek için üretim iş mantığı değiştirilmedi. '
    'Güvenlik sızma testi, gerçek disk/crash dayanıklılığı, Lighthouse/Web Vitals, '
    'uzun saatler süren soak ve seçilecek VPS üzerinde HTTPS/WAN testleri kapsam dışıdır.', '']
(root/'PERFORMANCE_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print('Report written; total requests:',sum(row['requests'] for _,row in all_rows))
