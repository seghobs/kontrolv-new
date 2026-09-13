# Instagram Yorum ve Beğeni Denetimi

Instagram gruplarında paylaşılan post ve Reels bağlantıları için yorum ve beğeni kontrolü yapan Flask uygulaması.

## Güncel özellikler

- Tekli ve toplu kontrol; tam yeniden tarama ve hızlı eksik güncellemesi.
- Üyeye özel günlük yorum + beğeni analizi; iki eksik listesi ayrı kopyalanır.
- Denetim geçmişi, karşılaştırma, şablonlar, muafiyetler ve geri alma.
- Mobil uyumlu kahve/karamel arayüz; arama, yorum önizlemesi ve gönderi detayları.
- SQLite üzerinde kalıcı sonuçlar; kod güncellemeleri veritabanının üzerine yazmaz.
- Boş veya bozuk yorum kayıtlarına karşı koruma. Eksik veri kesin yokluk olarak değerlendirilmez; bilinen kullanıcıya ait metinsiz yorumun varlığı korunur.
- Beğeni listesinin eksik döndüğü durumlarda yokluk kararı için bütünlük kontrolü.

## Kurulum

Python 3.10 veya üzeri kullanın.

```sh
pip install -r requirements.txt
python start_local.py
```

Windows'ta `baslat.bat` da kullanılabilir. Kontrol ekranı şifre istemez; yönetim paneli `/admin` adresindedir.

Yönetici şifresini `ADMIN_PASSWORD` ortam değişkeniyle belirleyin. Değişken yoksa Git dışında tutulan `admin_password.txt` dosyası kullanılır; dosya da yoksa rastgele oluşturulur. Şifreleri, tokenları, `secret.key`, `.env` dosyalarını ve veritabanlarını Git'e eklemeyin.

## PythonAnywhere ücretsiz hesap

Kontroller web isteği içinde çalışır; ayrı worker veya Always-on Task gerekmez. Gözetimsiz saatli otomasyon kapalıdır. Yönetim panelindeki mesaj gönderen işlemler yalnız kullanıcı tarafından başlatılır.

- `APP_DB_FILE` ortam değişkenini mevcut SQLite dosyanızın tam yoluna ayarlayın. Varsayılan dosya proje içindeki `app.db` dosyasıdır.
- WSGI için `pythonanywhere_wsgi.py` örneğini kendi hesabınıza göre düzenleyin.
- `/static/` adresini projenin `static` klasörüne eşleyin.
- Güncellemeden önce veritabanınızı yedekleyin; mevcut dosyanın üzerine başka veritabanı yüklemeyin. Kod güncellemesinden sonra web uygulamasını yeniden başlatın.
- Denetim bitene kadar sayfayı açık tutun. Büyük kontroller ücretsiz hesabın istek süresini aşabilir; bu durumda daha az paylaşım seçin.
- Tamamlanmış raporlar korunur. Yeniden tarama yeni denetim kaydı oluşturur.

## Günlük analiz ve belirsiz veriler

Seçilen tarih, paylaşımın gruba gönderildiği gündür. Analiz güncel yorum ve beğenileri kontrol eder; kişisel analizde muafiyet uygulanmaz. Günlük beğeni analizinde 90 beğeni sınırı yoktur; normal beğeni kontrolü mevcut 90 sınırını korur.

Boş kullanıcı veya eksik yorum listesi, kesin eksik üretmez. Toplu kontrolde ilgili paylaşım doğrulanamadı olarak gösterilir; diğer paylaşımlar devam eder. Günlük analizde bulunan kullanıcı olumlu, verisi doğrulanamayan kullanıcı belirsiz kalır. Instagram'ın hiç göstermediği verilerden engelleme veya hesap gizliliği kesin olarak anlaşılamaz.

## Testler

```sh
python -B -m unittest discover -s tests
node tests/test_comment_modal.cjs
node tests/test_interactions.cjs
node tests/test_low_likes_filter.cjs
node tests/test_member_copy.mjs
node tests/test_result_polling.cjs
```

Testleri yalnız `tests` dizininden çalıştırın. Yerel deneme dosyaları dağıtıma dahil değildir.
