# Oracle pilotu ve Coolify dagitimi

Bu belge dagitim hazirligidir; uygulamanin yayina alindigi anlamina gelmez.
Yerel `docker-compose.yml` korunur. Canlida **yalnizca** kokteki
`docker-compose.coolify.yml` kullanilir; iki dosya birlestirilmez.

## Dogrulanmis sunucu

- Frankfurt, AD 3; A1.Flex, 2 OCPU, 12 GB RAM, 100 GB / 10 VPU disk.
- Ubuntu 24.04 Minimal aarch64; guncelleme ve yeniden baslatma kontrol edildi.
- Docker 29.9.3 ve Compose 5.7.1; ARM hello-world testi gecti.
- Coolify 4.7.5, `ubuntu` SSH kullanicisi, ayri Coolify anahtari; panel SSH tuneliyle aciliyor.
- Root ve parola ile SSH kapali. Oracle SSH girisi yoneticinin mevcut IP/32 adresiyle sinirli.
- Traefik panelde Running, sunucu Ready. Bu durum uygulama HTTPS testinin yerine gecmez.
- Docker adres havuzu `172.20.0.0/16`; Coolify otomatik guncellemesi kapali.

Gercek ARM FinBERT kontrolu (kullanici terminal ciktisi, 12 Kasim 2026):
1 CPU / 4 GiB konteyner sinirinda 30 kisa metin analizi PASS;
ortalama 0.126 sn, en yavas 0.134 sn, tepe **surec RSS** 1132.3 MiB.
Model yukleme/indirme 14.82 sn. PyTorch 2.15.0+cpu132, Transformers 5.22.2.
Olumlu/olumsuz etiket assertleri gecti, ucuncu ornek notr cikti.
Bu kisa sentetik ornek tam uygulama kapasitesi, konteyner toplam bellegi veya uzun haber gecikmesi degildir.
`requirements.txt` bazi bagimliliklarda aralik kullandigindan sonraki build ayni surumleri garanti etmez;
yeni build surumleri kaydedilmeli ve kontrol edilmeli.

## Canli Compose davranisi

- API, worker, frontend, PostgreSQL ve Redis ayri servislerdir; sabit `container_name` yoktur.
- Host `ports` eslemesi yoktur. Coolify'da yalnizca **frontend:80** servisine domain verilir.
  API, PostgreSQL ve Redis'e domain verilmez; public database/port secenekleri acilmaz.
- API ve worker ayni uygulama kaynak kodundan build edilir; model sadece worker'da yuklenir.
- PostgreSQL verileri `postgres_data`, Redis AOF `redis_data`, model onbellegi `hf_cache` named volume'undedir.
  Coolify bu adlara kaynak kimligi ekleyebilir; tasimadan once gercek volume adini kontrol et.
- API 1 GiB, worker 3 GiB, PostgreSQL 1 GiB, Redis 512 MiB ve frontend 128 MiB bellek tavanina sahiptir.
  CPU tavanlari toplam fiziksel CPU taahhudu degildir; 2 CPU sunucuda servisler zamani paylasir.
- Redis 256 MiB veri sinirinda `noeviction` kullanir: istek siniri kayitlari bellek baskisinda sessizce atilmaz.
  Dolarsa kontrollu servis hatasi olusabilir; bellek ve AOF disk buyumesi izlenmelidir.
- JSON loglari servis basina 3 x 10 MB ile doner. PostgreSQL/WAL, Redis AOF, model ve Docker imajlari bu sinira dahil degildir.
- `.env` baglantisi yoktur. Gercek degerler Coolify Environment Variables ekraninda tutulur.

## Git kaynagi ve ayarlar

1. Repo: `https://github.com/Eastblood23/Finansal_Duygu_Analizi_Motoru.git`.
2. Hedef proje/production ortaminda Git kaynagindan Application olustur; Compose Empty secme.
3. Build strategy: Docker Compose. Base Directory: `/`. Compose Location: `/docker-compose.coolify.yml`.
4. Normal Coolify Compose yonetimini kullan; Raw mode ve previews kapali kalsin.
5. Baslangicta otomatik deployment/webhook kapali olsun. Testten sonra secilen commit elle yayinlanir.
6. Yerel `.env` dosyasini yukleme veya Git'e ekleme. Zorunlu degiskenler:
   - `JWT_SECRET_KEY`: yerelden bagimsiz rastgele en az 32 karakter. Degismesi oturumlari gecersiz kilar.
   - `POSTGRES_PASSWORD`: yeni, guclu parola. Mevcut volume'de bu alani degistirmek PostgreSQL parolasini degistirmez.
7. Varsayilan `POSTGRES_USER=finans_user`, `POSTGRES_DB=finans_db`, `UPDATE_INTERVAL_MINUTES=15` korunabilir.
8. `GEMINI_API_KEY` ve `FINNHUB_API_KEY` istege baglidir. Bosken Gemini sohbeti kullanilamaz,
   Finnhub atlanir; Yahoo/CoinDesk worker tarafinda denenir. Ucretsiz kota/ticari kullanim haklari ayri kontrol edilir.
9. Sirlar frontend build degiskenlerine eklenmez. Dummy degerlerle canli yayin yapilmaz.

## Proxy guven siniri

Canli frontend build'i `NGINX_CONFIG=nginx.coolify.conf` kullanir. Yerel build'in
varsayilani eski `nginx.conf` olarak kalir. Canli Nginx sadece `172.20.0.0/16`
adres havuzundan gelen peer'lerin X-Forwarded-For ve HTTP/HTTPS bilgisini guvenir kabul eder.
Traefik'te `forwardedHeaders.insecure` acilmaz; arayuze host portu eklenmez.
Bu adres havuzu degisirse Nginx guven araligi da yeniden ayarlanip test edilir.
Bu ayni sunucudaki Docker aglarini guvenilir kabul eder; ilgisiz/guvenilmeyen kiracilar eklenirse
guven siniri daraltilmalidir. Cloudflare veya baska bir on proxy eklenmesi ayrica tasarlanir.
Yalnizca SQL/Redis onbelleklerini dogrulamak IP bazli istek sinirlarinin dogrulandigi anlamina gelmez.

## Veri tasima ve yayin oncesi kalanlar

- Ilk kurulumda yeni volume bos veritabani olusturur; yerel kullanicilar otomatik tasinmaz.
- Restore sirasinda worker ve uygulama yazmalari durdurulmali, hedef DB ve volume kimligi dogrulanmali.
  Yereldeki yedekleme araci Windows icindir; sunucu cron'una dogrudan baglanamaz.
  Linux yedekleme/zamanlama, sifreli sunucu disi kopya ve gercek geri yukleme testi henuz kurulacak.
- `docker compose down -v`, Coolify volume silme ve kaynak yeniden yaratma veri kaybina neden olabilir.
- Once hedefte geri yukleme ve 5 kullanici/portfoy/takip sayilari kontrol edilir; sonra worker baslatilir.
- Alan adi/ucretsiz DNS secimi ve HTTPS henuz tamamlanmadi. Traefik'in Oracle'dan 80/443 erisimi,
  isletim sistemi kurallari ve sertifika dogrulamasi ayrica yapilacak. DB/Redis/API portlari acilmaz.
- Tam uygulama ve frontend ARM testi, kimlik dogrulama/portfoy smoke testi, iki istemci IP testi,
  HTTPS testi, bildirim kanali, dis yedek, Coolify `.env` guvenli yedegi ve rollback plani tamamlanmadan
  genel kullanima acilmaz. Coolify panelinin hazir olmasi bu adimlarin tamamlandigi anlamina gelmez.
- Tek ucretsiz sunucu yuksek erisilebilirlik saglamaz; geri alinma/kesinti icin dis yedek gereklidir.

## Izole proxy testi

`tests/smoke_coolify_network.py` yalnizca gecici test projesinde calistirilir;
bilerek basarisiz login/429 uretir. Gercek kullanici veya canli ortamda calistirilmaz.
Trusted modda iki farkli ziyaretcinin 10'ar login hakki bagimsiz kalmali; sonraki istek 429 olmalidir.
Untrusted modda sahte forwarded header degistirilerek ayni limit asilamamali.
Bu test Nginx/API sinirini olcer; Oracle + Traefik + HTTPS zinciri gercek sunucuda ayrica test edilir.

## Hazirlik dogrulamasi (12 Kasim 2026)

- Canli Compose parse kontrolu gecti; zorunlu sirlar bosken baslatma tanimi reddediliyor.
- Yerel build varsayilan `nginx.conf` dosyasini byte olarak aynen koruyor.
  Canli frontend build ve `nginx -t` gecti; mobil arayuz kaynaklari degistirilmedi.
- Gecici `finans-coolify-check` projesinde gercek PostgreSQL/Redis/API/Nginx kullanildi.
  API/worker kaynaklari degismedigi icin onceki uygulama imaji yeniden kullanildi
  (x86_64, PyTorch 2.14.1, Transformers 5.19.0); yeni frontend imaji build edildi.
  Bu, tum yiginin ARM'de test edildigi anlamina gelmez. ARM model testi yukarida ayridir.
- 26 regresyon testi, production assets/header/SPA/API smoke testi ve guvenilir/guvenilmeyen
  peer'den login limiti testi gecti. Testlerde gercek kullanici, gercek API anahtari veya canli DB kullanilmadi.
- Test hostunda `172.20.0.0/16` baska projede oldugu icin ona dokunulmadi;
  gecici stack `172.27.240.0/24` ve guvenilmeyen peer agi `172.28.240.0/24` kullandi.
  Test Nginx ayarinda sadece guven araligi `172.27.0.0/16` olarak degistirildi;
  diger proxy davranisi canli dosyayla ayniydi. Asil `172.20.0.0/16` ayarinin syntax kontrolu ayrica gecti.
- PostgreSQL'e deneme kaydi ve Redis'e deneme anahtari yazilip iki konteyner yeniden olusturuldu;
  PostgreSQL named volume ve Redis AOF verileri korundu. Bu islem dis yedekleme testi degildir.
- Docker inspect ile test servislerinde host portu yayinlanmadigi dogrulandi.
- Worker dahil bes servis healthy oldu. Worker'in health kontrolu heartbeat liveness kontroludur;
  her haber kaynaginin daima veri sagladigini kanitlamaz. Gecici test projesi ve sadece ona ait volume'ler temizlendi.
