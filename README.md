<div align="center">

# ☕ Kontrol

### Instagram yorum ve beğeni denetimi

**Paylaşımları kontrol et · Eksikleri gör · Üyeye özel günlük analiz yap**

![Python](https://img.shields.io/badge/Python-3.10%2B-C4956A?style=flat-square&labelColor=211A14)
![Flask](https://img.shields.io/badge/Web-Flask-C4956A?style=flat-square&labelColor=211A14)
![SQLite](https://img.shields.io/badge/Veritabanı-SQLite-C4956A?style=flat-square&labelColor=211A14)
![PythonAnywhere](https://img.shields.io/badge/PythonAnywhere-Ücretsiz_hesap-C4956A?style=flat-square&labelColor=211A14)

Kahve ve karamel tonlarında, mobil uyumlu bir arayüzle Instagram gruplarındaki post ve Reels paylaşımlarının etkileşimlerini takip edin.

[Hızlı kurulum](#kurulum) · [Özellikler](#ozellikler) · [Kullanım](#kullanim) · [Sorun giderme](#sorun-giderme)

</div>

---

> **Yeni başlıyorsanız:** [PythonAnywhere kurulumu](#kurulum) bölümünü izleyin. Betik proje dosyalarını indirir, gerekli ortamı hazırlar ve web uygulamasını yapılandırır. Önceden kurulmuş bir uygulamanız varsa [mevcut kurulum](#mevcut-kurulum) bölümünden başlayın.

<a id="icerik"></a>
## İçindekiler

- [Neler yapabilirsiniz?](#ozellikler)
- [PythonAnywhere ücretsiz hesap kurulumu](#kurulum)
- [Mevcut kurulum ve özel seçenekler](#mevcut-kurulum)
- [İlk giriş ve kullanım](#kullanim)
- [Sonuçlar nasıl değerlendirilir?](#sonuclar)
- [Bilgisayarınızda çalıştırma](#yerel-kurulum)
- [Yapılandırma](#yapilandirma)
- [Güncelleme ve yedekleme](#guncelleme)
- [Sorun giderme](#sorun-giderme)
- [Testler ve proje yapısı](#gelistirme)
- [Sık sorulan sorular](#sss)

<a id="ozellikler"></a>
## Neler yapabilirsiniz?

| Özellik | Ne işe yarar? |
| :--- | :--- |
| **Tekli kontrol** | Bir post veya Reels bağlantısını seçilen üyeler için kontrol eder. |
| **Toplu kontrol** | Birden fazla paylaşımın eksiklerini aynı raporda toplar. |
| **Hızlı güncelleme** | Önceki rapordaki eksikleri yeniden kontrol eder; sorunsuz tamamlanmış paylaşımları tekrar sorgulamadan kullanabilir. |
| **Tam yeniden tarama** | Seçilen paylaşımları yeniden sorgular ve yeni bir denetim kaydı oluşturur. |
| **Üyeye özel günlük analiz** | Bir üyenin, seçilen gün gruba gönderilen paylaşımlardaki yorumlarını ve beğenilerini birlikte kontrol eder. |
| **Ayrı kopyalama** | Günlük analizde yorum eksiklerini ve beğeni eksiklerini birbirine karıştırmadan kopyalar. |
| **Yorum ve medya önizlemesi** | Yorum metinlerini, gönderi detaylarını ve uygun medya verisi geldiğinde Reels önizlemesini gösterir. |
| **Arama ve filtreleme** | Üye, grup, paylaşım ve etkileşim listelerinde arama yapar. |
| **Geçmiş ve karşılaştırma** | Önceki denetimleri saklar; uygun iki rapor arasındaki eksik değişimlerini gösterir. |
| **Şablonlar ve muafiyetler** | Tekrarlanan kontrolleri kolaylaştırır; süreli veya gönderiye özel muafiyetleri yönetir. |
| **Hesap yönetimi** | Yönetici panelinden Instagram oturumlarını ve tokenları yönetir. |

### Ücretsiz hesapta çalışma şekli

Kontroller, tarayıcının başlattığı web istekleri içinde çalışır. **Ayrı worker, MySQL veya Always-on Task kurulmaz.** SQLite sonuçları kalıcı olarak saklar.

Gözetimsiz saatli otomasyon bu sürümde kapalıdır. Yönetim panelindeki mesaj gönderme işlemleri kullanıcı tarafından başlatılır. Büyük denetimler ücretsiz hesabın istek süresini aşabilir; böyle durumlarda paylaşımları daha küçük gruplara ayırın.

<a id="kurulum"></a>
## PythonAnywhere ücretsiz hesap kurulumu

### 1. Hesabınızı hazırlayın

1. PythonAnywhere hesabınıza giriş yapın.
2. **Account → API token** bölümünden bir API tokenı oluşturun.
3. Tokenı oluşturduktan sonra **Consoles → Bash** üzerinden **yeni bir konsol** açın.

Yeni konsolda token genellikle `API_TOKEN` ortam değişkeniyle erişilebilir. Değişken yoksa kurulum tokenı gizli olarak girmenizi ister; yazarken ekranda görünmemesi normaldir.

> PythonAnywhere API tokenı, sunucunun kurulumunu yönetmek içindir. Instagram oturum tokenı farklıdır; uygulama açıldıktan sonra eklenir. API tokenını kaynak koda veya README'ye yazmayın.

### 2. Kurulumu başlatın

Yeni Bash konsoluna aşağıdaki iki satırı sırayla yapıştırın:

```bash
curl -fsSL https://raw.githubusercontent.com/seghobs/kontrolv-new/main/setup.sh -o /tmp/kontrol-setup.sh
bash /tmp/kontrol-setup.sh --path "$HOME/mysite"
```

Kurulumun hedefi hesabınızın ana dizinindeki `mysite` klasörüdür. Bu klasör yoksa proje indirilir. Klasörde mevcut uygulama varsa o kod kullanılır; klasör silinmez veya zorla yenilenmez.

**Konsolu kapatmadan işlemin tamamlanmasını bekleyin.** Son satırda `Kurulum tamamlandı:` ve sitenizin adresi görünmelidir. Betik canlı sayfayı doğrulayamazsa başarı mesajı vermez.

### 3. Sitenizi açın

Kurulum sonunda gösterilen adresi ziyaret edin:

```text
https://KULLANICI_ADINIZ.pythonanywhere.com
```

Avrupa sistemindeki hesaplarda adres şu biçimdedir:

```text
https://KULLANICI_ADINIZ.eu.pythonanywhere.com
```

`KULLANICI_ADINIZ` yerine kendi PythonAnywhere kullanıcı adınız gelir; kurulum bunu otomatik belirler.

### 4. Yönetici paneline giriş yapın

Sitedeki **Admin Panel** bağlantısını açın. İlk kurulumda üretilen şifreyi PythonAnywhere **Files** bölümünden şu dosyada bulabilirsiniz:

```text
/home/KULLANICI_ADINIZ/mysite/admin_password.txt
```

Mevcut şifre dosyası korunur. Önceden WSGI dosyasında veya ortam değişkeninde tanımlanmış yönetici şifresi varsa o ayar öncelikli olabilir. Kontrol ekranına girerken yönetici şifresi istenmez.

### Kurulum sizin yerinize neleri yapar?

| Adım | Yapılan işlem |
| :--- | :--- |
| Ön kontrol | API erişimi, proje yolu ve web uygulamasının Python sürümü kontrol edilir. |
| Veri seçimi | Mevcut SQLite dosyası belirlenir; birden çok aday varsa belirsiz seçim yapılmaz. |
| Yedekleme | Var olan veritabanının tutarlı bir SQLite yedeği alınır; anahtar ve kurulum ayarları korunur. |
| Python ortamı | Projeye ait `.venv` hazırlanır ve `requirements.txt` bağımlılıkları kurulur. |
| Uygulama kontrolü | Eksik tablolar oluşturulur ve ana sayfanın yerel açılışı doğrulanır. |
| Yayın ayarları | Web uygulaması, WSGI dosyası, sanal ortam, HTTPS yönlendirmesi ve `/static/` eşlemesi yapılandırılır. |
| Son kontrol | Web uygulaması yeniden yüklenir ve canlı ana sayfa kontrol edilir. |

Kurulum hatalarını gizlemez. API erişimi, disk alanı, paket indirme veya hizmet bağlantısı sorunlarında verilen hata mesajını [sorun giderme](#sorun-giderme) bölümünden inceleyin.

<a id="mevcut-kurulum"></a>
## Mevcut kurulum ve özel seçenekler

### Uygulama zaten indirilmişse

PythonAnywhere Bash konsolunda:

```bash
cd "$HOME/mysite"
bash setup.sh
```

Tekrar çalıştırma, mevcut web uygulamasını ve statik dosya eşlemesini kullanır. Mevcut veritabanı veya şifre dosyası yeni bir dosyayla değiştirilmez.

### Önce yalnız ön kontrol yapmak için

```bash
bash setup.sh --check
```

Bu seçenek temel hesap, yol ve Python sürümü kontrollerini yapar; paket kurmaz, yedek almaz veya web ayarlarını değiştirmez. Tam kurulumun başarılı olacağını tek başına garanti etmez.

### Avrupa hesabı için

Otomatik bölge seçimi doğru değilse:

```bash
bash setup.sh --api-host eu.pythonanywhere.com
```

### Farklı proje klasörü için

```bash
bash setup.sh --path "$HOME/kontrol"
```

Hesapta zaten bu uygulama için tanımlanmış bir kaynak klasörü varsa aynı yolu kullanın. Betik başka bir web uygulamasının klasörüne kendiliğinden geçmez.

### Birden fazla veritabanı varsa

Örneğin hem `app.db` hem `app-sqlite.db` mevcutsa, aktif dosyayı belirtin:

```bash
bash setup.sh --database "$HOME/mysite/app-sqlite.db"
```

Bu yalnızca bir örnektir; gerçekten kullandığınız dosyayı seçin. Öncelik sırası: **`--database` → mevcut WSGI ayarı → kayıtlı kurulum ayarı → tek mevcut veritabanı**. İlk kurulumda veritabanı yoksa `app.db` oluşturulur.

Tüm seçenekleri görmek için:

```bash
bash setup.sh --help
```

<a id="kullanim"></a>
## İlk giriş ve kullanım

### İlk kontrolünüz

1. **Token Al** veya yönetici paneli üzerinden geçerli bir Instagram oturumu ekleyin.
2. Ana sayfadan **Tekli Kontrol** ya da **Toplu Kontrol** seçin.
3. Instagram grubunu ve kontrol edilecek üyeleri belirleyin; gerekiyorsa üye listesini düzenleyin.
4. Paylaşım bağlantısını girin veya gruptan tarih ve paylaşım seçin.
5. İlgili kontrol seçeneğiyle denetimi başlatın. **Sonuç gelene kadar sayfayı açık tutun.**
6. Raporda eksikleri inceleyin; kullanıcı araması, yorum önizlemesi ve kopyalama düğmelerini kullanın.

### Aynı paylaşımı tekrar kontrol etmek

| Seçenek | Ne zaman kullanılır? |
| :--- | :--- |
| **Hızlı Güncelle** | Önceden eksik çıkan üyelerin sonradan etkileşim yapıp yapmadığını kontrol etmek istediğinizde. |
| **Tam Yeniden Tara** | Önceki olumlu sonuçlar dahil tüm paylaşımları yeniden sorgulamak istediğinizde. |

Hızlı güncelleme tamamlanmış paylaşım sonuçlarını yeniden kullanabilir. Silinen yorumlar gibi önceki olumlu sonuçların da değişmiş olabileceği durumlarda tam yeniden taramayı seçin. Yeniden taramalar yeni kayıt oluşturur; kaynak rapor korunur.

### Üyeye özel günlük analiz

Eksik üyenin yanındaki **Günlük Analiz** düğmesine basın ve tarih seçin. Sistem, kaynak raporun grubunda o gün gönderilen paylaşımlar için hem yorum hem beğeni kontrolü yapar.

Sonuç ekranındaki **yorum eksikleri** ve **beğeni eksikleri** ayrı ayrı kopyalanabilir. Doğrulanamayan paylaşımlar kesin eksik listelerine eklenmez.

> Seçilen tarih, paylaşımın **gruba gönderildiği gündür**. Analiz, etkileşimlerin o tarihteki geçmiş görüntüsünü değil, kontrol anında erişilebilen yorum ve beğenileri gösterir.

<a id="sonuclar"></a>
## Sonuçlar nasıl değerlendirilir?

| Durum | Anlamı |
| :--- | :--- |
| **Yorum yapmış / Beğenmiş** | İlgili kullanıcıya ait etkileşim alınan veride bulundu. |
| **Eksik** | Kontrolün bütünlük koşullarını karşılayan veride ilgili etkileşim bulunamadı. |
| **Doğrulanamadı** | Eksik, bozuk veya erişilemeyen veri nedeniyle kesin karar verilemedi. |
| **Yorum mevcut; metni alınamadı** | Yorumun yazarı belli, ancak yorum metni boş veya erişilemiyor. |

### Boş veya bozuk veri koruması

`user=None`, `username=None`, `comments=None` gibi veriler güvenle ayrıştırılır. Bilinen kullanıcıya ait metinsiz yorumun varlığı korunur; metin alınamadığı için format ihlali yazılmaz. Kimliği belirsiz kayıtlar içeren paylaşım için kesin eksik listesi üretilmez; toplu kontrolde diğer paylaşımlar devam eder.

Instagram bazı verileri hiçbir hata veya eksiklik işareti vermeden gizleyebilir. Uygulama, bu tür yanıtlardan kişinin bir hesabı engellediğini veya gizli hesabın gerçek etkileşim durumunu kesin olarak belirleyemez.

### Beğeni kontrolünün sınırları

- Normal beğeni kontrolünde **90 üzerindeki** paylaşımlar mevcut kurala göre atlanır.
- Üyeye özel günlük beğeni analizinde **90 beğeni sınırı uygulanmaz**.
- Instagram beğenenlerin yalnız bir kısmını döndürürse, listede bulunmamak tek başına kesin yokluk sayılmaz.
- Günlük kişisel analizde muafiyet uygulanmaz; alınabilen gerçek etkileşim verisi değerlendirilir.

<a id="yerel-kurulum"></a>
## Bilgisayarınızda çalıştırma

**Gereksinimler:** Python 3.10 veya üzeri, Git ve internet bağlantısı. `setup.sh` PythonAnywhere içindir; bilgisayarınızda aşağıdaki adımları kullanın.

<details>
<summary><strong>Windows — PowerShell</strong></summary>

```powershell
git clone https://github.com/seghobs/kontrolv-new.git
cd kontrolv-new
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe start_local.py
```

Sanal ortamı etkinleştirmek zorunlu değildir; komutlar doğrudan ortamın Python dosyasını kullanır.

</details>

<details>
<summary><strong>Linux / macOS — Terminal</strong></summary>

```bash
git clone https://github.com/seghobs/kontrolv-new.git
cd kontrolv-new
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python start_local.py
```

</details>

Tarayıcıdan [http://127.0.0.1:3434](http://127.0.0.1:3434) adresini açın. İlk açılışta gerekli yerel veritabanı ve anahtar dosyaları oluşturulur.

<a id="yapilandirma"></a>
## Yapılandırma

| Ayar | Açıklama | Varsayılan davranış |
| :--- | :--- | :--- |
| `APP_DB_FILE` | Kullanılacak SQLite dosyasının yolu. | Proje içindeki `app.db`. Otomatik kurulum mevcut dosyayı seçer. |
| `ADMIN_PASSWORD` | Yönetici giriş şifresi. | Yoksa `admin_password.txt`; dosya da yoksa rastgele şifre. |
| `SECRET_KEY` | Flask oturum imzalama anahtarı. | Yoksa kalıcı `secret.key` dosyası. |
| `APP_ENV` | Uygulama ortamı: `dev`, `stage`, `prod`. | Yerelde `dev`; otomatik kurulumda `prod`. |
| `SQLITE_JOURNAL_MODE` | SQLite günlükleme modu: `DELETE` veya `WAL`. | `DELETE`; PythonAnywhere kurulumu bunu kullanır. |
| `API_TOKEN` | PythonAnywhere kurulum API tokenı. | Hesabın ortamından okunur. |
| `PYTHONANYWHERE_API_TOKEN` | Kurulum tokenı için alternatif değişken. | `API_TOKEN` yoksa kullanılır. |

`.env` dosyası oluşturmak tek başına bu ayarları yüklemez. Ortam değişkenlerini çalıştırma ortamında veya WSGI yapılandırmasında tanımlayın. Otomatik kurulum gerekli web ayarlarını kendisi yazar.

### Uygulama adresleri

| Sayfa | Yol |
| :--- | :--- |
| Ana kontrol | `/` |
| Yönetici paneli | `/admin` |
| Instagram oturumu ekleme | `/token_al` |
| Denetim geçmişi | `/history` |
| Şablonlar ve yönetim araçları | `/tools` |

<a id="guncelleme"></a>
## Güncelleme ve yedekleme

### Git ile güncelleme

Aşağıdaki adımlar, **bu depodan Git ile klonlanmış** kurulumlar içindir. Önce çalışan denetimlerin bitmesini bekleyin.

```bash
cd "$HOME/mysite"
git remote get-url origin
git status --short
```

Uzak depo `seghobs/kontrolv-new` olmalıdır. Yerel değişiklik varsa önce onları koruyun; `reset --hard` kullanmayın. Depo doğru ve çalışma alanı temizse:

```bash
git pull --ff-only
bash setup.sh
```

Betik bağımlılıkları kontrol eder, veritabanını yedekler ve web uygulamasını yeniden yükler. Git geçmişi olmayan, dosyaları elle yüklenmiş kurulumlarda yalnız güncel kaynak dosyalarını aktarın; veritabanı ve anahtarların üzerine yazmayın.

### Yedekler nerede?

```text
/home/KULLANICI_ADINIZ/.kontrol-backups/
└── TARIH-SAAT-KIMLIK/
    ├── database.sqlite         # Önceden veritabanı varsa
    ├── admin_password.txt      # Önceden mevcutsa
    ├── secret.key              # Önceden mevcutsa
    ├── previous_wsgi.py        # Önceden mevcutsa
    ├── web-config.json
    └── static-mappings.json
```

Bu klasör tam bir kaynak kod arşivi değildir; veritabanı ve kurulum yapılandırması yedeğidir. Yeni kurulumda henüz olmayan dosyaların yedeği bulunmaz.

Şifre, token, `.env`, `secret.key`, SQLite dosyaları ve yedekleri GitHub'a yüklemeyin. `.gitignore` bu dosyaların yaygın adlarını dışarıda tutar. Veritabanı dosyaları kendiliğinden şifrelenmez; dosya erişimini koruyun.

### Geri dönüş gerektiğinde

Kurulum, mevcut web uygulamasının yapılandırılması sırasında hata alırsa eski WSGI ve ilgili web ayarlarını geri yüklemeyi dener. **Veritabanını otomatik geri sarmaz:** Bu sırada oluşmuş yeni kayıtların kaybolması önlenir. Otomatik geri dönüş de başarısızsa yedek klasörünün yolunu bildirir.

<a id="sorun-giderme"></a>
## Sorun giderme

| Mesaj / belirti | Yapılacak işlem |
| :--- | :--- |
| **API_TOKEN bulunamadı** | Account → API token bölümünden token oluşturun, yeni Bash konsolu açın ve tekrar çalıştırın. |
| **API HTTP 401 / 403** | Tokenın bu hesaba ait ve geçerli olduğunu; doğru ABD/Avrupa sunucusunu kullandığınızı kontrol edin. |
| **Birden çok veritabanı var** | Aktif SQLite dosyasını `--database` ile belirtin. Dosyaları silmeyin. |
| **Kayıtlı veritabanı bulunamadı** | WSGI veya kurulum ayarındaki dosya yolunu kontrol edin; eski veritabanını bulun. |
| **Web uygulamasının klasörü farklı** | Web sekmesindeki kaynak diziniyle aynı yolu `--path` seçeneğine verin. |
| **Hedef klasör boş değil** | İçinde başka dosyalar olan bir klasör seçilmiş olabilir. Mevcut uygulama klasörünü veya yeni, boş bir hedefi kullanın. |
| **Aktif denetim var** | Kontrolün tamamlanmasını bekleyin; sonra kurulumu yeniden başlatın. |
| **Python / .venv sürümü farklı** | Web uygulamasıyla sanal ortamın Python sürümünü eşleştirin. Betik mevcut ortamı silmez. |
| **Paket kurulumu başarısız / No space left on device** | Konsoldaki ilk hatayı inceleyin. Disk kotasını ve bağlantıyı kontrol edin; veritabanını silerek yer açmayın. |
| **Canlı sayfa doğrulanamadı / 502** | PythonAnywhere Web sekmesindeki hata günlüğünü açın; Python sürümü, sanal ortam ve kaynak yolunu kontrol edin. |
| **Kontrol uzun sürüyor** | Daha az paylaşım seçin. Sayfayı açık tutun; denetim geçmişindeki durumu inceleyin. |
| **Yorum veya beğeni doğrulanamadı** | Instagram oturumunu ve veri erişimini kontrol edin. Belirsiz sonucu kesin eksik olarak yorumlamayın. |
| **Eski görünüm geliyor** | Web uygulamasını Reload edin ve sayfayı yenileyin. Statik dosya sürümleri yeniden hesaplanır. |

Hata bildirirken kullanılan adımları ve gizli bilgiler temizlenmiş hata mesajını paylaşın. Token, şifre, oturum başlıkları veya veritabanı dosyası eklemeyin.

<a id="gelistirme"></a>
## Testler ve proje yapısı

### Testleri çalıştırma

Uygulama bağımlılıklarına ek olarak Python testleri için Beautiful Soup gerekir:

```bash
python -m pip install beautifulsoup4
python -B -m unittest discover -s tests
```

Komutları uygulamanın sanal ortamındaki Python ile çalıştırın. JavaScript testleri için Node.js 20 veya üzeri kullanın; Node.js uygulamanın sunucuda çalışması için gerekli değildir.

```bash
node tests/test_comment_modal.cjs
node tests/test_interactions.cjs
node tests/test_low_likes_filter.cjs
node tests/test_member_copy.mjs
node tests/test_result_polling.cjs
```

**Son doğrulama — 14 Eylül 2026:** 119 Python testi ve beş JavaScript test grubu başarılı. Kurulum testleri yedekleme, veri seçimi, şifre koruma, tekrar çalıştırma ve yapılandırma geri dönüşü senaryolarını kapsar. Bunlar canlı PythonAnywhere hesabında sıfırdan kurulmuş uçtan uca bir ortam testinin yerine geçmez.

Test keşfini `tests` diziniyle sınırlandırın. Yerel deneme dosyaları üretim test paketine dahil değildir.

### Dizin yapısı

```text
kontrolv-new/
├── app_core/
│   ├── routes/                 # Ana sayfa, yönetim ve geçmiş
│   ├── instagram_api.py        # Instagram veri sorguları
│   ├── member_analysis.py      # Üyeye özel günlük analiz
│   ├── jobs.py                 # Kalıcı denetim kayıtları
│   ├── web_jobs.py             # Web isteği içinde denetim yürütme
│   └── storage.py              # SQLite işlemleri
├── scripts/
│   └── pythonanywhere_setup.py # Otomatik kurulum ve veri koruma
├── static/                     # CSS ve JavaScript
├── templates/                  # Sayfa şablonları
├── tests/                      # Otomatik testler
├── setup.sh                    # PythonAnywhere kurulum girişi
├── start_local.py              # Yerel çalıştırma
├── pythonanywhere_wsgi.py      # Elle kurulum için WSGI örneği
└── requirements.txt            # Uygulama bağımlılıkları
```

Depodaki MySQL geçiş araçları eski kurulumlarla veri aktarımı içindir. Güncel uygulamanın çalışma veritabanı **SQLite**'tır; otomatik kurulum MySQL hizmeti oluşturmaz.

<a id="sss"></a>
## Sık sorulan sorular

<details>
<summary><strong>Kurulumu tekrar çalıştırırsam verilerim silinir mi?</strong></summary>

Betik mevcut uygulama klasörünü veya veritabanını silmez. Aktif SQLite dosyasını kullanır ve işlem öncesi yedek alır. Birden çok dosya veya hatalı yol varsa tahmin etmek yerine durur. Yine de doğru hesabı ve proje yolunu seçtiğinizden emin olun.

</details>

<details>
<summary><strong>Tarayıcı kapalıyken kontroller otomatik çalışır mı?</strong></summary>

Bu sürüm ücretsiz hesaba uygun olarak web isteği içinde çalışır. Yeni kontrollerin başlaması ve sonuç takibinin sürmesi için sayfayı açık tutun. Gözetimsiz saatli otomasyon kurulmaz.

</details>

<details>
<summary><strong>Gizli hesap veya engelleme kesin tespit edilir mi?</strong></summary>

Hayır. Uygulama Instagram'ın döndürdüğü veriyi değerlendirir. Eksik veya bozuk veri tespit edildiğinde belirsiz sonuç gösterir; hiçbir işaret vermeden gizlenen verilerden kesin engelleme tespiti yapamaz.

</details>

<details>
<summary><strong>Yönetici şifresi ile Instagram tokenı aynı şey mi?</strong></summary>

Hayır. Yönetici şifresi panel girişini, Instagram tokenı etkileşim verilerine erişimi, PythonAnywhere API tokenı ise sunucu kurulumunu yönetir. Üçünü birbirinin yerine kullanmayın.

</details>

<details>
<summary><strong>Kurulum her ortamda hatasız tamamlanır mı?</strong></summary>

Hesap kotaları, ağ bağlantısı, Python sürümü ve API erişimi kurulumu etkileyebilir. Betik bu sorunları gizlemez; tamamlanmayan işlemi başarılı göstermez. Hata mesajını düzelttikten sonra yeniden çalıştırabilirsiniz.

</details>

---

<div align="center">

**Kontrol · SQLite · PythonAnywhere**

[Kaynak kod](https://github.com/seghobs/kontrolv-new) · [Hata bildir](https://github.com/seghobs/kontrolv-new/issues) · [PythonAnywhere API belgeleri](https://help.pythonanywhere.com/pages/API/)

</div>
