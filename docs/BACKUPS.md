# PostgreSQL yedekleme

Proje klasorunde PowerShell ile:

```powershell
./scripts/Backup-Database.ps1
```

Bu bilgisayarda `.ps1` calistirma kapaliysa sistem politikasini degistirmeden,
proje klasorunde ayni kodu mevcut PowerShell oturumunda calistirmak icin:

```powershell
$backupCode = [System.IO.File]::ReadAllText((Join-Path $PWD 'scripts/Backup-Database.ps1'))
& ([scriptblock]::Create($backupCode)) -OutputDirectory (Join-Path $PWD 'backups')
```

Script calisan PostgreSQL konteynerinin kullanici/veritabani adini okur; parola yazdirmaz.
PostgreSQL custom-format yedegi `backups/` altina ikili dosya olarak kopyalar.
Bilgisayardaki kopyayi konteynere geri aktarir. Her calistirmada benzersiz bir test veritabani olusturur, tum arsivi tek islemde geri
yukler ve dort uygulama tablosunun kayit sayilarini kaynakla karsilastirir.
Kaynak kayit sayilari islem sirasinda degisirse dogrulama basarisiz sayilir; yedek
korunur, sessiz bir zamanda tekrar denenmelidir.
Basarili dogrulama SHA-256 ve kayit sayilarini iceren manifest ile belgelenir.
Test veritabani ve konteynerdeki gecici arsiv temizlenir; kaynak veritabani degistirilmez.
Script hata durumunda durur; yedekleri otomatik silmez.

Yedekler kullanici verilerini icerir. Git ve Docker build disinda tutulurlar.
Bu klasor henuz sifreli veya bilgisayar disina kopyalanan bir yedekleme sistemi degildir.
Veritabani rolleri, `.env`, JWT anahtari ve API anahtarlari bu arsive dahil degildir;
yeniden kurulum icin bunlar ayri, guvenli bir yerde saklanmalidir.

Canli veritabanina geri yukleme bu scriptin parcasi degildir. Dogrulama yalnizca yeni
test veritabaninda yapilir. PostgreSQL ana surumu degisirken uyumluluk ayrica test edilmelidir.

Sonraki kurulum: gunluk zamanlama, 14 gun saklama, sifreli bilgisayar disi kopya ve
basarisizlik bildirimi. Bunlar henuz etkin degildir.
