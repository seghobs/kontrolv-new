# Özellik genişletme doğrulama listesi

14 Eylül 2026: 145 Python testi ve beş JavaScript test grubu geçti. Chrome üzerinde 390 px mobil / 1440 px masaüstü ve etkileşim kontrolleri yapıldı. Aşağıdaki durumlar yerel doğrulamadır; canlı kurulumun sonucu ayrıca raporlanır.

| İstek | Mevcut durum / yapılacak iş | Doğrulama |
|---|---|---|
| Yalnız eksikler | Var; hedefli yeniden kontrol ve kaynak zamanını koruma | Test geçti |
| Değişiklik özeti | Geçmişte var; rapora eklenecek | Test geçti |
| Belirsizleri ayır / tekrar dene | Kısmen var; raporda ayrı liste | Test geçti |
| Son kontrol / önbellek bilgisi | Eklenecek | Test geçti |
| Kurulum sağlık kontrolü ve önizleme | Genişletilecek | Test geçti |
| Yedek yönetimi | Admin erişimli liste / indirme | Test geçti |
| Üye takip kartı | Geçmiş kayıtlarından günlük / haftalık görünüm | Test geçti |
| Tarih aralığı / toplu üye analizi | Günlük analizin genişletilmesi | Test geçti |
| Kendi paylaşımını hariç tut | Normal kontrolde var; kişisel analize seçenek | Test geçti |
| Grup kuralları / minimum kelime / muafiyet | Eklenecek | Test geçti |
| Hatırlatma / kopyalama biçimleri | Eklenecek; otomatik gönderim yok | Test geçti |
| Excel matrisi | Eklenecek | Test geçti |
| Kaldığın rapor / kesintiden devam | Kalıcı ara sonuçlar | Test geçti |
| Silinen / düzeltilen yorumlar | Karşılaştırmalı, kesinlik sınırlarıyla | Test geçti |
| Tekrarlanan paylaşım / metinden bağlantı | Ortak normalleştirme | Test geçti |
| Kapsam özeti | Göndermeden önce gösterim | Test geçti |
| Neden / zaman / inceleme notu | Eklenecek | Test geçti |
| Çöp kutusu | Silinen ayar / şablonları geri alma | Test geçti |
| Üye listesi farkı / kullanıcı adı takibi | Kimlik varsa otomatik; yoksa tahmin yok | Test geçti |
| Paylaşım önizlemesi / şablon | Var, korunacak | Test geçti |
| Mobil kompakt / sabit filtre | Ortak tema içinde | Test geçti |
| Katılım tarihi / telafi süresi / izin takvimi | Grup kuralları içinde | Test geçti |
| Kapsam dışı gönderi / eksikleri sıralama | Eklenecek | Test geçti |


## Test kanıtları ve sınırlar

- `tests/test_followup.py`: tarih kuralları ve Türkiye saat dilimi, muafiyetlerin tamamlanma sayılmaması, gerçek hesap kimliğiyle ad eşleştirme, eski adla kayıtlı geçmiş, güvenli not gösterimi, Excel içeriği, yedek yetkisi, çöp kutusu çakışması, grup silme/geri alma, aralık sınırı, eksik API yanıtı, kendi paylaşımı, ara kayıt, hedefli tekrar kontrol, iptalde yeni istek başlatmama, minimum kelime ve kapsam dışı gönderi.
- `tests/test_audit_regressions.py` ve `tests/test_security_regressions.py`: hata artık tüm raporu kesmek yerine belirsiz kayıt oluşturur. Eksik ve tamamlanan listelerinin boş kaldığı ve hata günlüğünün doğru olduğu ayrıca doğrulanır.
- `tests/test_pythonanywhere_setup.py`, `tests/test_sqlite_upgrade.py`: veri koruma, tekrar kurulum, geri dönüş ve eklemeli SQLite güncelleme.
- `tests/browser/layout.py`: yeni ekranların HTTP açılışı, taşma, filtre ve kompakt görünüm, JavaScript hataları.
- `tests/browser/interactions.py`: panoya kopyalama, hatırlatma, sıralama, sırayla toplu analiz, tekli/toplu bağlantı aktarımı ve kapsam ekranından vazgeçme.
- Tarayıcıdaki Instagram analiz yanıtları kontrollü test yanıtlarıdır. Gerçek Instagram API hizmetinin sürekli erişilebilir olduğu veya eksiksiz yanıt vereceği garanti edilmez. Süre sınırı ve erişim sorunları açık durumlarla gösterilir.
- Eski raporda olmayan kaynak/zaman bilgisi uydurulmaz. Eski yorumun görünmemesi kesin silinme, metin farkı kesin düzenlenme olarak sunulmaz.
- Grup sorumluluk kuralları normal/şablon kontrollerinde; kendi paylaşımı seçeneği kişisel analizde uygulanır.
