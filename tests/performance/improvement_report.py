import json
from pathlib import Path

root=Path('/results')
def read(name):
    return json.loads((root/name).read_text())
old=read('api4cpu-100k-extra.json')
new=read('optimized-final-100k-extra.json')
base_nlp=read('api2cpu-2gb.json')
new_nlp=read('optimized-api1-worker1.json')
base_fault=read('resilience.json')
new_fault=read('optimized-resilience.json')
soak=read('optimized-100k-soak.json')
arrival=read('optimized-fixed-arrival-100k.json')

lines=['# Performans iyileştirmeleri — 12 Kasım 2026','',
'## Uygulanan değişiklikler','',
'- Haber toplama ve FinBERT ayrı worker süreci/konteynerine taşındı; API model yüklemiyor.',
'- Tarih+kimlik, kategori+tarih+kimlik, duygu+tarih+kimlik ve kategori+duygu+tarih+kimlik indeksleri eklendi. '
'Mevcut tablolar silinmez; indeksler concurrent ve tekrar çalıştırılabilir biçimde oluşturulur.',
'- Haberlerde eşit tarihli kayıtlar için kimlikli cursor sayfalaması eklendi; eski offset API korunuyor. '
'Frontend daha fazla yüklerken cursor kullanıyor. Offset yolunda önce yalnızca sayfa kimlikleri seçiliyor.',
'- Fiyatlar ticker, portföy ve grafikte ortak Redis önbelleği kullanıyor (60 sn). '
'Yerel ve dağıtık doldurma kilidi aynı verinin eşzamanlı tekrar çekilmesini azaltıyor.',
'- Duygu özetleri 30 sn önbellekleniyor; worker yeni haberleri commit ettikten sonra '
'generation değerini artırarak haber/duygu önbelleğini geçersiz kılıyor.',
'- Redis bağlantı/okuma, SQL bağlantı/komut ve HTTP yanıt bütçeleri sınırlandı. '
'Health kontrolü, sürücü iptalinin takılmasını beklemeden 503 dönebiliyor.',
'- Parola hash/doğrulama iki iş parçacığıyla sınırlı ayrı havuza taşındı.', '',
'## Kapsam ve karşılaştırma sınırları','',
'Aynı yerel Docker host, sentetik PostgreSQL ve Yahoo/Gemini taklitleri kullanıldı. '
'Önceki SQL tablosu API 4 CPU kotasıyla; yeni tablo API 1 CPU ve ayrı NLP worker 1 CPU kotasıyla ölçüldü. '
'PostgreSQL 1 CPU, Nginx/Redis toplam 1 CPU olarak aynı kaldı. '
'NLP karşılaştırmasında eski API 2 CPU bütçesi, yeni API 1 + worker 1 şeklinde bölündü; toplam CPU tavanı aynı. '
'Bellek limitleri yeni API 1 GiB + worker 2 GiB; bunlar fiziksel VPS minimum gereksinim kanıtı değildir. '
'Ham örnekler aynı gün/host olsa da süre, önbellek sıcaklığı ve işletim sistemi zamanlaması değişebilir.', '',
'## 100 bin haber, 30 eşzamanlı istek','',
'| Senaryo | Önce p95 ms | Sonra p95 ms | Sonra hata % |',
'|---|---:|---:|---:|']
for kind in ('portfolio','correlation','db_news'):
    before=next(row for row in old if row['case']==kind and row['concurrency']==30)
    after=next(row for row in new if row['case']==kind and row['concurrency']==30)
    lines.append(f"| {kind} | {before['p95_ms']} | {after['p95_ms']} | {after['error_pct']} |")
lines+=['','`db_news` derin OFFSET yoludur; normal frontend artık cursor kullanır. '
'Önbellekli örneklerde çok daha az SQL çalışması beklenen davranıştır; sıcak cache sonucu ham DB kapasitesi değildir.', '',
'## Toplu NLP sırasında API','',
'| Ölçüm | Önce (API içinde) | Sonra (ayrı worker) |','|---|---:|---:|']
before=next(row for row in base_nlp['results'] if row['case']=='news_during_40_article_collection')
after=next(row for row in new_nlp['results'] if row['case']=='news_during_40_article_collection')
for field in ('p95_ms','p99_ms','max_ms'):
    lines.append(f"| {field} | {before[field]} | {after[field]} |")
lines += [f"| 40 haberin tamamlanması (sn) | {base_nlp['collection']['seconds']:.2f} | {new_nlp['collection']['seconds']:.2f} |", '',
'Worker CPU bütçesi düşük tutulduğundan batch süresi uzayabilir; amaç HTTP API olay döngüsünü model işinden ayırmaktır. '
'Maksimum yanıtlar ayrıca izlenir; ayrı worker tek başına bütün kuyruk gecikmelerini sıfırlamaz.', '',
'## Beş dakikalık karma yük ve üç turlu sabit hız','']
lines.append('```json\n'+json.dumps(soak['result'],ensure_ascii=False,indent=2)+'\n```')
lines+=['','| Tur | Hedef istek/sn | p95 ms | Bırakılan | Hata % (bırakılan dahil) |',
        '|---|---:|---:|---:|---:|']
for row in arrival:
    lines.append(f"| {row['round']} | {row['offered_rps']} | {row['p95_ms']} | {row['dropped']} | {row['error_pct']} |")
lines+=['','## Kesinti ve yeniden başlatma','',
'| Servis | Önce | Sonra |','|---|---|---|']
for before,after in zip(base_fault,new_fault):
    if 'unavailable_health' in before:
        b=before['unavailable_health']; a=after['unavailable_health']
        lines.append(f"| {after['service']} health | {b['status']} / {b['elapsed_s']} sn | {a['status']} / {a['elapsed_s']} sn |")
        b=before['unavailable_read']; a=after['unavailable_read']
        lines.append(f"| {after['service']} haber okuma | {b['status']} / {b['elapsed_s']} sn | {a['status']} / {a['elapsed_s']} sn |")
    else:
        lines.append(f"| API yeniden hazır | {before['restart_ready_seconds']} sn | {after['restart_ready_seconds']} sn |")
lines+=['',
'Önbellek süresine göre DB kesintisinde haber okuma 200 veya kontrollü 503 dönebilir. '
'Redis kesintisinde istek sınırlarını sessizce devre dışı bırakmak yerine 503 dönülür. '
'Kesintiler yalnızca geçici test konteynerlerinde uygulandı.', '',
'## Doğrulama ve işletim','',
'26 regresyon testi; timestamp eşitliğinde cursor/offset eşitliği; doğrudan SQL ile cache raporunun sayısal eşitliği; '
'indeks geçerliliği ve API importunda torch/collector bulunmaması kontrol edildi. '
'NLP test workerının ilk kuyruk bekleme denemesinde socket bütçesi uyumsuzluğu tespit edilip düzeltildi; '
'o eksik batch örneği başarılı karşılaştırma olarak kullanılmadı.', '',
'Docker Compose artık `worker` servisini de başlatır. Docker dışı geliştirmede API yanında '
'`python -m app.worker` ayrıca çalıştırılmalıdır. Aynı veritabanındaki workerlar advisory lock ile korunur. '
'Şema hazırlığı API başlangıcında additive indeks oluşturur; büyük veritabanında süre ve yetkiler izlenmelidir. '
'Worker sağlık kontrolü Redis heartbeat liveness kontrolüdür, her kaynağın veri getirdiğinin garantisi değildir.', '',
'Başlangıç sunucu önerisi 4 vCPU / 8 GB RAM / tercihen 160 GB SSD olarak korunur. '
'Seçilecek gerçek VPS üzerinde HTTPS/WAN ve kontrollü gerçek sağlayıcı entegrasyonu yeniden ölçülmelidir. '
'Beş dakikalık örnek uzun süreli bellek sızıntısı veya binlerce gerçek kullanıcı garantisi sağlamaz.', '']
(root/'PERFORMANCE_IMPROVEMENTS.md').write_text('\n'.join(lines),encoding='utf-8')
print('Before/after report written')
