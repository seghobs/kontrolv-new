# Gruba özel filtre tercihleri

İki filtre grup kimliğine göre mevcut SQLite key_value tablosunda ayrı kaydedilir. Kayıt yoksa iki seçenek de kapalıdır. İşaretleme ve işareti kaldırma anında kaydedilir; grup seçilirken tercihler okunmadan üye/paylaşım yükleme başlatılmaz. Hızlı değişiklikler grup bazında sıralanır, eski grup yanıtları yok sayılır. Okuma/yazma hataları kullanıcıya gösterilir. Şema veya mevcut kayıtlar silinmez.

Doğrulama: 184 backend testi geçti. Yeni API testleri varsayılanlar, grup izolasyonu, kapatma, bağımsız bayraklar, geçersiz veri, DB hatası ve mevcut kayıtların korunmasını kapsar. Tarayıcı testi gerçek yerel SQLite üzerinde yeni oturum, hızlı değişiklikler, grup değiştirme, filtrelerin uygulanması ve gecikmiş yanıtı kapsar. Önceki geri tuşu/sıfırlama ve düşük beğeni testleri geçti.

Canlı API ve mobil arayüz, gerçek bir grubun veritabanındaki tercihleriyle eşleştirilerek doğrulandı. Bu canlı testte Instagram üye/paylaşım yanıtları taklit edildi; tercih okuması gerçek API üzerinden yapıldı. Canlı grup tercihleri değiştirilmedi, denetim veya DM gönderilmedi.
