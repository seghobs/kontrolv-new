# Özellik genişletme doğrulama listesi

14 Eylül 2026: 145 Python testi ve beş JavaScript test grubu geçti. Chrome üzerinde 390 px mobil / 1440 px masaüstü ve etkileşim kontrolleri yapıldı. Aşağıdaki durumlar yerel doğrulamadır; canlı doğrulama sonucu aşağıda yer alır.

| İstek | Mevcut durum / yapılacak iş | Doğrulama |
|---|---|---|
| Yalnız eksikler | Var; hedefli yeniden kontrol ve kaynak zamanını koruma | Test geçti |
| Değişiklik özeti | Geçmişte var; rapora eklendi | Test geçti |
| Belirsizleri ayır / tekrar dene | Kısmen var; raporda ayrı liste | Test geçti |
| Son kontrol / önbellek bilgisi | Eklendi | Test geçti |
| Kurulum sağlık kontrolü ve önizleme | Genişletildi | Test geçti |
| Yedek yönetimi | Admin erişimli liste / indirme | Test geçti |
| Üye takip kartı | Geçmiş kayıtlarından günlük / haftalık görünüm | Test geçti |
| Tarih aralığı / toplu üye analizi | Günlük analizin genişletildi | Test geçti |
| Kendi paylaşımını hariç tut | Normal kontrolde var; kişisel analize seçenek | Test geçti |
| Grup kuralları / minimum kelime / muafiyet | Eklendi | Test geçti |
| Hatırlatma / kopyalama biçimleri | Eklendi; otomatik gönderim yok | Test geçti |
| Excel matrisi | Eklendi | Test geçti |
| Kaldığın rapor / kesintiden devam | Kalıcı ara sonuçlar | Test geçti |
| Silinen / düzeltilen yorumlar | Karşılaştırmalı, kesinlik sınırlarıyla | Test geçti |
| Tekrarlanan paylaşım / metinden bağlantı | Ortak normalleştirme | Test geçti |
| Kapsam özeti | Göndermeden önce gösterim | Test geçti |
| Neden / zaman / inceleme notu | Eklendi | Test geçti |
| Çöp kutusu | Silinen ayar / şablonları geri alma | Test geçti |
| Üye listesi farkı / kullanıcı adı takibi | Kimlik varsa otomatik; yoksa tahmin yok | Test geçti |
| Paylaşım önizlemesi / şablon | Var, korunacak | Test geçti |
| Mobil kompakt / sabit filtre | Ortak tema içinde | Test geçti |
| Katılım tarihi / telafi süresi / izin takvimi | Grup kuralları içinde | Test geçti |
| Kapsam dışı gönderi / eksikleri sıralama | Eklendi | Test geçti |


## Test kanıtları ve sınırlar

- `tests/test_followup.py`: tarih kuralları ve Türkiye saat dilimi, muafiyetlerin tamamlanma sayılmaması, gerçek hesap kimliğiyle ad eşleştirme, eski adla kayıtlı geçmiş, güvenli not gösterimi, Excel içeriği, yedek yetkisi, çöp kutusu çakışması, grup silme/geri alma, aralık sınırı, eksik API yanıtı, kendi paylaşımı, ara kayıt, hedefli tekrar kontrol, iptalde yeni istek başlatmama, minimum kelime ve kapsam dışı gönderi.
- `tests/test_audit_regressions.py` ve `tests/test_security_regressions.py`: hata artık tüm raporu kesmek yerine belirsiz kayıt oluşturur. Eksik ve tamamlanan listelerinin boş kaldığı ve hata günlüğünün doğru olduğu ayrıca doğrulanır.
- `tests/test_pythonanywhere_setup.py`, `tests/test_sqlite_upgrade.py`: veri koruma, tekrar kurulum, geri dönüş ve eklemeli SQLite güncelleme.
- `tests/browser/layout.py`: yeni ekranların HTTP açılışı, taşma, filtre ve kompakt görünüm, JavaScript hataları.
- `tests/browser/interactions.py`: panoya kopyalama, hatırlatma, sıralama, sırayla toplu analiz, tekli/toplu bağlantı aktarımı ve kapsam ekranından vazgeçme.
- Tarayıcıdaki Instagram analiz yanıtları kontrollü test yanıtlarıdır. Gerçek Instagram API hizmetinin sürekli erişilebilir olduğu veya eksiksiz yanıt vereceği garanti edilmez. Süre sınırı ve erişim sorunları açık durumlarla gösterilir.
- Eski raporda olmayan kaynak/zaman bilgisi uydurulmaz. Eski yorumun görünmemesi kesin silinme, metin farkı kesin düzenlenme olarak sunulmaz.
- Grup sorumluluk kuralları normal/şablon kontrollerinde; kendi paylaşımı seçeneği kişisel analizde uygulanır.


## Canlı doğrulama

14 Eylül 2026: PythonAnywhere üzerinde ana sayfa, gerçek yönetici girişi, yetkisiz yedek erişiminin reddi, grup kuralları, yedekler, çöp kutusu, geçmiş, araçlar, kayıtlı gerçek rapor, takip ekranı ve XLSX indirme doğrulandı. Yayın öncesinde kod ve veritabanı kopyası özel yedek dizinine alındı; canlı veritabanı dosyası yükleme işlemine dahil edilmedi.

Ayrı yerel kopyada 30 gerçek kayıtlı rapor başarıyla görüntülendi. Aynı kopyanın yeni başlangıç şema kontrolü bütünlük ve kayıt sayısı kaybı olmadan geçti. Gerçek Instagram'a toplu istek yüklemesi yapılmadı; dış servis hata/eksik veri senaryoları kontrollü yanıtlarla test edildi. Toplu analizde ilk başarısız sonuçtan sonra durma ve yanlış tamamlandı mesajı göstermeme ayrıca tarayıcıda doğrulandı.


## Kaydet kontrolü — 26 Eylül 2026

### Güncel ayarlar ve doğrulama

- Kanıt aralığı paylaşım günü 20:00–ertesi gün 18:00; paylaşım kapanışı 22:30 olarak korunur.
- Admin panelindeki **Gemini API · Kaydet analizi** kartı etkin anahtarı yükler; Göster/Gizle ve Kaydet işlemleri desteklenir. Panelden kaydedilen anahtar veritabanında korunur ve ortam değişkeni/dosya ayarından önceliklidir. Sonraki analiz isteğinde yeniden başlatmadan kullanılır.
- 214 backend testi geçti. Admin dışında anahtar okuma/yazma engellenir; boş veya hatalı giriş eski anahtarı korur. Playwright ile masaüstü/mobil görünüm, göster/gizle, kaydetme, sayfa yenilendikten sonra kalıcılık ve JavaScript hataları test edildi. Arayüz testi ayrı veritabanında örnek anahtarla yapıldı; mevcut gerçek anahtar değiştirilmedi.

- Ana formda Yorum / Beğeni / Kaydet seçimi. Kaydet grubu varsayılanı sohbet ID'si `340282366841710301281157258447286771667` üzerinden belirlenir; kayıtlı son seçim önceliklidir.
- Ayrı `/save-control` akışı: post/Reels, grup gönderen ID'sine göre katılımcılar, kendi gönderileri hariç; 22:30 kapanış, ertesi gün 18:00 kanıt sonu (Europe/Istanbul).
- Normal medya ve generic_xma mesajlarının bütün görselleri alınır. Geçmiş tamamlanmazsa sonuç oluşturulmaz. Model hatası eksik kararına dönüşmez. Adımlar ve incelemeler SQLite key_value içinde yeni anahtarlarla saklanır.
- Model: gemma-4-26b-a4b-it. Sunucuda `GEMINI_API_KEY` ortam değişkeni veya proje kökündeki Git dışında tutulan `.gemini-api-key` dosyası gerekir. Anahtar tarayıcıya veya rapora gönderilmez.
- Benzer görsellerde yanlış eşleşme olabildiğinden sonuçlar onay bekleyen adaylardır. Görsellerin tamamı açılarak elle doğrulanabilir. Kanıt kaydetme zamanını ispatlamaz.
- 207 backend testi geçti (10 yeni kaydet testi dahil). Gerçek 25 Eylül grup verisi: 5 referans, 5 katılımcı, 2 ilgili ekran ve önceki güne ait 3 ekran. Yeni HTTP analiz yoluyla 2 gerçek model çağrısı HTTP 200; kendi paylaşımı hariç 8/8 görünür referans için eşleşme adayı çıktı.
- Playwright Chrome: ana formdan Kaydet akışına geçiş, grup seçimi, 20 yükümlülük kartında kendi paylaşımının bulunmaması, 390px ve 1280px genişliklerde taşma ve JavaScript hatası kontrolü geçti. Test veritabanı gerçek veritabanından ayrıdır.
- Dağıtım öncesi son kontrol: 214 backend testi geçti; canlı SQLite yedeği 12 tablo ve 4.488 kayıt ile doğrulandı. Canlı veritabanı yüklenmez veya değiştirilmez. ZIP yedeği değiştirilmedi.
