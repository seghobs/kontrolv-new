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
