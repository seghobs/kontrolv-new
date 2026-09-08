# Kontrol Aiohttp Speed Edition (Ultra-Fast Instagram Automation & Audit)

**Kontrol Aiohttp Speed Edition**, Instagram etkileşim ve yardımlaşma grupları için geliştirilmiş; **`aiohttp` tabanlı asenkron paralel sorgulama motoru**, sinematik **Coffee / Caramel / Espresso** tasarım dili, dahili **Reels video oynatıcısı**, **interaktif beğeni & yorum denetim modalları** ve **tam otomatik arka plan otomasyonu** sunan yeni nesil bir analiz platformudur.

Orijinal Instagram Android mobil uygulamasının API başlıklarını, oturum protokollerini ve cihaz kimliklerini birebir taklit ederek yüksek kararlılık ve maksimum hızla çalışır.

---

## ⚡ Öne Çıkan Yeni Nesil Özellikler

### 🚀 1. Ultra Hızlı `aiohttp` Asenkron Paralel Motor
* **Eşzamanlı Çoklu Gönderi Taraması:** 10+ gönderiyi aynı anda asenkron (paralel) olarak tarar; denetim süresini saniyelere indirir.
* **Akıllı Proxy ve Sıkıştırma (PythonAnywhere & Cloud Ready):** `gzip / deflate` optimizasyonu ve otomatik `http://proxy.server:3128` tüneliyle hiçbir harici C bağımlılığına (`brotli` vb.) gerek kalmadan tak-çalıştır çalışır.
* **Kusursuz Otomatik Failover (Yedek Motor):** Asenkron isteklerde ağ dalgalanması yaşanırsa sistem anında `requests` failover motoruna devrederek taramayı asla yarıda bırakmaz.

### 🎬 2. Gelişmiş Medya & Reels Video Oynatıcısı
* **Dahili Reels Oynatıcı:** Sonuç ekranındaki modalda Reels ve video paylaşımlarını sayfa değiştirmeden doğrudan dinleyip izleyebilirsiniz.
* **Orijinal Boyutlu Kapak ve Profil Avatarları:** 9:16 dikey Reels veya kare gönderiler bozulmadan, kırpılmadan en yüksek çözünürlükte gösterilir.

### 💬 3. İnteraktif Beğeni & Yorum Listeleme Modalı
* **Tıklanabilir İstatistik Kutuları:** Post detay modalındaki `[❤️ Beğeni]` veya `[💬 Yorum]` kutularına tıklandığında açılan özel etkileşim modalı.
* **Canlı Arama & Filtreleme:** Yüzlerce yorum/beğeni arasından kullanıcı adı veya yorum metnine göre anında arama yapma.
* **Yorum Balonları & Tek Tıkla Kopyalama:** Yapılan yorumları konuşma balonu formatında inceleme ve tüm etkileşim listesini panoya kopyalama.

### 🧈 4. İpeksi Arayüz (Soft Easing & Luxury Caramel Scrollbar)
* **Titremesiz Akordeon Kartlar:** Kartlar açılıp kapanırken sıfır titreme (jitter-free) ve Apple tarzı `cubic-bezier(0.25, 1, 0.5, 1)` yumuşak akış.
* **Lüks Karamel Scrollbar:** Koyu espresso arka planla bütünleşen, karamel ve altın tonlarında özel yuvarlak hatlı kaydırma çubuğu.
* **Önce Eksikler Hiyerarşisi:** Sonuç sayfasında kullanıcıların en çok ihtiyaç duyduğu "Eksikler" kartı varsayılan olarak en üstte gelir.

### 🤖 5. Arka Plan Otomasyonu (Auto-Pilot)
* **Zamanlanmış Otomatik Kontroller:** Günün belirlenen saatlerinde (örn. 23:59) otomatik olarak dünün paylaşımlarını denetler.
* **Otomatik Grup Bildirimi:** Eksik listesini ve etiket şablonunu otomatik olarak DM grubuna yollar.
* **Kişiye Özel Uyarı DM'si:** Görevini yapmayan kullanıcılara tek tek otomatik uyarı DM'si gönderir.
* **Yönetici Raporlama:** İşlem bittiğinde yönetici hesabına detaylı durum raporu iletir.
* **Geri Alma (Unsend) Desteği:** Botun DM grubuna attığı mesajları tek tıkla Instagram sunucularından geri alabilirsiniz.

### 🔑 6. Token, Havuz ve Güvenlik Yönetimi
* **Çoklu Hesap Desteği (Token Pool):** Birden fazla hesabı havuza ekleyip rotasyonlu kullanma.
* **Akıllı Relogin:** Oturumu düşen hesapları tek tıkla admin panelinden şifreyle yeniden bağlama.
* **Cihaz Simülasyonu:** Her hesap için özel Android ID, Device ID ve User Agent taklidi.

---

## 🛠️ Kurulum

### 1. Projeyi Klonlayın
```bash
git clone https://github.com/seghobs/kontrolaiohttp.git kontrol
cd kontrol
```

### 2. Gerekli Paketleri Yükleyin
```bash
pip install -r requirements.txt
```

### 3. Yönetici Şifresi

Uygulama ekranları ve API uçları yönetici oturumu gerektirir. Varsayılan yönetici şifresi `seho` olarak ayarlanmıştır. İsterseniz `ADMIN_PASSWORD` ortam değişkeniyle değiştirebilirsiniz; değişken boş olarak tanımlanırsa giriş kapalıdır.

Şifreyi değiştirmek için PowerShell'de komut geçmişine yazmadan ayarlayın:

```powershell
$adminCredential = Get-Credential -UserName admin -Message "Uygulama yönetici şifresi"
$env:ADMIN_PASSWORD = $adminCredential.GetNetworkCredential().Password
```

Linux / macOS:

```bash
read -s -p "Yönetici şifresi: " ADMIN_PASSWORD
export ADMIN_PASSWORD
```

### 4. Uygulamayı Başlatın
```bash
# Windows:
python start_local.py
# veya baslat.bat

# Linux / macOS:
python3 start_local.py
```

---

## 💻 Kullanım Adresleri

* **Ana Denetim Ekranı:** `http://localhost:5000` (veya `http://127.0.0.1:3434`)
* **Admin & Otomasyon Paneli:** `http://127.0.0.1:3434/admin`
* **Token & Hesap Yönetimi:** `http://127.0.0.1:3434/token_al`

---

## 📁 Dizin Yapısı

```text
├── app_core/
│   ├── routes/              # Flask Blueprint yönlendirmeleri (main, admin)
│   ├── instagram_api.py     # aiohttp & requests Instagram API motoru
│   ├── token_service.py     # Token havuzu ve oturum yönetimi
│   ├── automation.py        # Arka plan zamanlayıcı ve otomatik DM botu
│   ├── storage.py           # SQLite veritabanı CRUD işlemleri
│   └── config.py            # Uygulama ve güvenlik ayarları
├── static/
│   ├── css/                 # Caramel & Espresso UI stilleri, animasyonlar
│   └── js/                  # aiohttp veri işleme, modal, Reels player & arama
├── templates/               # Modern Jinja2 HTML şablonları
├── flask_app.py             # Ana Flask çalıştırma dosyası
└── requirements.txt         # Gerekli kütüphaneler
```

---

## 🔒 Güvenlik & Yasal Bilgilendirme
Bu proje yalnızca eğitim, test ve analiz amaçlıdır. Instagram kullanım koşullarına uygun kullanım kullanıcının sorumluluğundadır. Veriler yerel SQLite veritabanında şifreli/güvenli olarak barındırılır.


## PythonAnywhere: sonuç ekranı ve statik dosyalar

- Web sekmesinde `/static/` URL'sini projenin gerçek `static` klasörüne eşleyin (örnek: `/home/KULLANICI/mysite/static`). Böylece CSS ve JavaScript dosyaları web uygulamasının işçilerini meşgul etmez.
- Kod veya CSS/JavaScript güncellemesinden sonra **Reload web app** uygulayın. Dosya içerik sürümleri başlangıçta hesaplanır; yeni sürüm eski tarayıcı önbelleğini geçersiz kılar.
- Sonuç ve görev durum yanıtları özel veri içerdiği için önbelleğe alınmaz. Statik dosyalar tekrar kullanılabilir.
- Sonuç ekranı artık sunucu tamamlandı dediğinde animasyonu beklemeden yenilenir. İlerleme, sunucunun bildirdiği değerdir.
- `/result/…` ve `/api/task_status/…` isteklerinin uygulama süreleri loglarda `duration_ms` ve yanıtta `Server-Timing` olarak bulunur. 40–50 saniyelik beklemeyi incelerken bunları tarayıcının Network süreleriyle karşılaştırın. Bu ölçüm, uygulama öncesindeki sunucu kuyruğunu veya internet aktarımını kapsamaz.
- Denetim ve otomasyonlar artık ayrı `worker.py` sürecinde çalışır. Web süreci yalnızca kalıcı kuyruğa iş ekler. PythonAnywhere kurulumu aşağıdadır.

Resmi belgeler: [Statik dosya eşlemesi](https://help.pythonanywhere.com/pages/StaticFiles), [Arka plan işler](https://help.pythonanywhere.com/pages/AsyncInWebApps), [Yavaşlık teşhisi](https://help.pythonanywhere.com/pages/MySiteIsSlow/).


## Kalıcı işçi, kurtarma ve geçmiş

**Yerel kullanım:** `baslat.bat` veya `python start_local.py`, web sunucusunu ve işçiyi ayrı süreçler olarak açar. Yalnız `python flask_app.py` çalıştırılırsa işler kuyruğa alınır fakat işçi başlatılana kadar çalışmaz. İşçiyi ayrı terminalde `python worker.py` ile de başlatabilirsiniz.

**PythonAnywhere:**

1. Güncellemeyi uygulamadan önce eski web/otomasyon süreçlerini durdurun ve SQLite veritabanının tutarlı yedeğini alın. Mevcut `app.db` dosyasını silmeyin veya yeni boş dosyayla değiştirmeyin.
2. Yeni dosyaları yükleyin ve mevcut sanal ortamda bağımlılıkları kurun. WSGI dosyası sadece `from flask_app import app as application` ile web uygulamasını yüklemelidir. WSGI içinden `worker.py` veya eski zamanlayıcıyı başlatmayın.
3. Hesabınız Always-on Tasks destekliyorsa Tasks bölümünde, kendi kullanıcı/klasör/sanal ortam yollarınıza uyarlanmış şu komutu çalıştırın:

   ```bash
   /home/KULLANICI/.virtualenvs/ORTAM/bin/python /home/KULLANICI/mysite/worker.py
   ```

4. Web ve işçi aynı `app.db` dosyasını kullanmalıdır. Varsayılan konum proje köküdür. Farklı konum gerekiyorsa her iki süreçte de aynı mutlak `APP_DB_FILE` değerini tanımlayın. Ağ dosya sistemi için varsayılan SQLite günlük modu `DELETE` kullanılır; farklı makinelerde paylaşılan veritabanında `WAL` kullanmayın.
5. Web uygulamasını **Reload**, Always-on işçisini ayrıca yeniden başlatın. Web'i yeniden yüklemek işçi kodunu yenilemez. Aynı kuyruk için tek işçiyle başlayın. Sanal ortam ve proxy ayarları web ile işçide uyumlu olmalıdır.

İşçi yoksa talepler “İşçi bekleniyor” durumunda kalır. Geçici terminal işçisi test için kullanılabilir; kesintisiz işletim için denetlenen, sürekli çalışan süreç gerekir. [Always-on Tasks belgesi](https://help.pythonanywhere.com/pages/AlwaysOnTasks/)

- İşçi sahipliği 30 saniyelik sürelerle korunur ve çalışma sırasında yenilenir. Kesilen işler işçi yeniden çalışınca kurtarılır; toplam en fazla 3 deneme yapılır. Yeniden denemeler arasında 30/60 saniye beklenir. Bir iş için varsayılan üst süre 30 dakikadır (`worker.py --timeout 1800`).
- Zamanlayıcı, o günün kaçırılmış saatlerini de kuyruğa alır. Aynı grup/tarih/saat yeniden kuyruğa eklenmez. Önceki günlere otomatik telafi gönderimi yapılmaz. Yükseltme öncesindeki otomasyon kilitleri, eski mesajları tekrar göndermemek için korunur.
- Mesaj gönderiminden önceki hatalar yeniden denenir. Gönderim başladıktan sonraki hata veya kesilmede teslimat belirsiz olabileceği için iş “Gönderim kontrolü gerekli” olur. Geçmiş ekranından, mesajları kontrol ettikten sonra yeniden gönderim onaylanabilir. Bu durumda daha önce gönderilmiş mesajlar tekrar gönderilebilir; otomatik olarak tekrar gönderilmez.
- `/history` ekranında kontroller ayrı kimliklerle saklanır. Yeni kontrol öncekinin üzerine yazmaz. İki tamamlanmış kontrolün paylaşım bazında eski/yeni eksikleri karşılaştırılabilir. Önceki sürümde zaten üzerine yazılmış kayıtlar geri getirilemez. Eski kayıtların tarihi içe aktarma zamanıdır.
- Aynı IP adresinden 15 dakika içinde beş başarısız girişten sonra bekleme uygulanır. Başarılı giriş sayacı sıfırlar. Doğrudan bağlantı adresi kullanılır; tarayıcıdan gelen `X-Forwarded-For` başlığına güvenilmez. Barındırma ortamı tüm kullanıcıları aynı proxy adresiyle bildiriyorsa, gerçek istemci adresi yalnızca güvenilir sunucu yapılandırmasıyla iletilmelidir.

Doğrulama: `python -B -m unittest discover -s tests` ve `node tests/test_result_polling.cjs`.


### Denetimi iptal etme ve işçi göstergesi

- Bekleme ekranındaki **Denetimi İptal Et** veya geçmişteki **İptal Et** düğmesiyle işlem durdurulur. Sıradaki işler hemen iptal edilir. Çalışan işler önce “Durduruluyor” durumuna geçer; işçi alt süreci sonlandırınca “İptal edildi” olur. Tamamlanan sonuçlar iptal edilmez ve iptal edilen iş otomatik yeniden denenmez. Otomasyonda başlamış bir dış istek tamamlanmış olabilir; gönderilmiş mesajlar geri alınmaz.
- Ana sayfa, yönetim, geçmiş ve sonuç ekranlarında işçi göstergesi bulunur. Durum, son haberleşme zamanı (Türkiye saati), bekleyen ve çalışan iş sayıları 5 saniyede bir yenilenir. 30 saniye haber alınamazsa bağlantı kesilmiş görünür. Sunucuya ulaşılamadığında bu durum işçinin kapalı olmasından ayrı gösterilir. Gizli sekmelerde sorgular durur.
- Güncellemeden sonra hem web uygulamasını hem `worker.py` sürecini yeniden başlatın; yeni işçi bağlantı kayıtlarını yazmaya başlayacaktır.


### Yönetici şifresi

Sunucuda `ADMIN_PASSWORD` ortam değişkenini tanımlayın. Yerel kullanımda şifre, Git dışında tutulan `admin_password.txt` dosyasından okunur; dosya yoksa ilk açılışta rastgele oluşturulur. Bu dosyayı ve `secret.key`, token dosyaları, `.env` ve veritabanlarını depoya yüklemeyin.
