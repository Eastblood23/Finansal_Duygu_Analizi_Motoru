# Kayıtta e-posta doğrulama

Yeni kullanıcı, e-postasına gelen 6 haneli kodu doğrulamadan hesap açamaz.
Mevcut kullanıcıların girişi korunur; veritabanı şema değişikliği gerekmez.
Bu özellik her girişte ikinci faktör isteyen bir 2FA sistemi değildir.

## Coolify ayarları

1. Değişiklikleri GitHub'a gönderin. Uygulamanın General ekranında
   `/docker-compose.coolify.yml` seçili kalsın; **Reload Compose** ile yenileyin.
2. **Environment Variables** bölümünde aşağıdaki değerleri kaydedin.

| Değişken | Değer |
| --- | --- |
| SMTP_HOST | smtp.gmail.com |
| SMTP_PORT | 465 |
| SMTP_SECURITY | ssl |
| SMTP_USERNAME | finansalduygumotoru@gmail.com |
| SMTP_FROM_EMAIL | finansalduygumotoru@gmail.com |
| SMTP_PASSWORD | Google'ın oluşturduğu uygulama şifresi; boşluksuz |

Normal Gmail şifresini kullanmayın. Uygulama şifresini sohbete, kaynak koda
veya GitHub'a yazmayın. Bu değişkenlerin **Runtime** seçeneği açık,
**Build time** seçeneği kapalı olsun. Ortam değerlerini loglarda gizleyin.

3. **Redeploy** ile API ve arayüzü birlikte güncelleyin. PostgreSQL/Redis
   volume'lerini silmeyin. SMTP eksikse yeni kayıtlar kapalı kalır; mevcut
   kullanıcılar giriş yapabilir.
4. Kontrolünüzdeki farklı bir e-posta ile kayıt başlatın. Gelen kodla hesabı
   açın. E-posta gelmezse spam klasörüne bakın ve SMTP ayarlarını kontrol edin.
   Gerçek Gmail gönderimi bu kurulumdan sonra ayrıca doğrulanmalıdır.

## Davranış ve sınırlar

- Kod 10 dakika geçerlidir, 5 yanlış denemeden sonra iptal olur; yalnızca bir
  kez kullanılabilir. Eşzamanlı doğrulama istekleri ikinci hesap açamaz.
- Aynı adrese yeni kod için 60 saniye beklenir. IP başına kayıt başlatma
  sınırı dakikada 2, saatte 5; doğrulama sınırı dakikada 10, saatte 50'dir.
- Bekleyen kayıtta parola açık metin olarak tutulmaz; parola hash'i ve kodun
  HMAC özeti Redis'te süreli saklanır. SMTP şifreli bağlantı kullanır.
- Redis verisi kaybolursa bekleyen kullanıcı kayıt işlemini yeniden başlatır.
  Kod tüketildikten sonra veritabanı yazımı başarısız olursa da yeniden kayıt
  başlatmak gerekir.
- Doğrulama e-posta adresine erişimi kanıtlar; bir kişinin birden fazla
  kendisine ait e-postayla hesap açmasını veya tüm kötüye kullanımları engellemez.
- Gmail, düşük hacimli pilot içindir; gönderim kotaları ve teslimat garantisi
  nedeniyle yoğun kullanımda özel bir posta servisine geçilebilir.

## Yerel kontroller

Test dosyası gerçek PostgreSQL ve Redis ile izole bir Compose projesi kullanır;
SMTP gönderimleri taklit edilir, gerçek alıcıya e-posta gönderilmez.
Test Dockerfile'ı mevcut `finansal_duygu_analizi_motoru-api:latest` yerel
imajını temel alır; önce bu imajı oluşturmuş olmalısınız.

```powershell
docker compose -p finans-email-check -f tests/email-verification.compose.yml run --build --rm tests python -m unittest discover -s tests -v
docker compose -p finans-email-check -f tests/email-verification.compose.yml down -v
```

`down -v` yalnızca belirtilen geçici test projesine uygulanmalıdır.
