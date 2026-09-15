# Şablonlar ve üye–paylaşım tablosu — test kaydı

Tarih: 15 Eylül 2026

## Eklenenler

- Şablonda yorum + beğeni kontrolü; ayrı sonuç görünümleri ve ayrı eksik listesi kopyalama.
- Şablonu kimliğini ve geçmiş raporlarını koruyarak düzenleme.
- Bugün, dün ve özel takvim tarihiyle başlatma (İstanbul tarihi).
- Raporun özgün üye kapsamını koruyarak yalnız yeni paylaşımları yeni bir rapora ekleme.
- Üye–paylaşım tablosu, arama, yalnız eksikler filtresi ve her kontrol türünün kontrol zamanı.

## Otomatik doğrulamalar

179 arka uç testi geçti. Yeni testler: iki modun ayrılması, ayrı kopyalama içeriği, bağlantı normalizasyonu, yalnız yeni paylaşımların taranması, kaynak raporun değişmemesi, sonuçların ayrı güncellenmesi, bilinmeyen/muaf/kontrol edilmemiş durumlar, tarih doğrulaması, şablon düzenleme, tekrar tıklama ve gerçek HTTP yürütme akışı.

Tarayıcı kontrolleri: 390 ve 1440 pikselde tarih seçimi ve form gönderimi, düzenleme, gerçek pano kopyalama, iki sonuç görünümü, ekleme penceresi, tablo araması, eksik filtresi, yatay kaydırma ve sayfa taşması. Önceki yorum penceresi, seçim kutusu, takip işlemleri, rapor yoklama ve güvenilirlik testleri de geçti.

## Gerçek veri kontrolleri

- Önce yerel, yalıtılmış veritabanında gerçek kayıtlı 11 paylaşım ve 23 üyeyle ekleme akışı tekrarlandı; kaynak kayıt değiştirilmedi.
- Canlı sunucuda geçici şablon oluşturuldu, düzenlendi ve 14 Eylül tarihiyle çalıştırıldı. Gerçek Instagram okuma istekleriyle 11 paylaşım ve 23 üyelik yorum + beğeni raporu tamamlandı.
- Canlıda tek paylaşımlık kaynak rapora 10 yeni paylaşım eklendi. Kaynak rapor tek paylaşım olarak kaldı; yeni rapor 11 paylaşım içerdi.
- Genişletilmiş rapora tekrar ekleme: 0 yeni paylaşım, toplam yine 11.
- Canlı gerçek raporda pano içerikleri, tablo hücre sayısı, arama ve 390/1440 piksel görünümü doğrulandı. Windows pano satır sonları karşılaştırmada normalize edildi.
- Geçici test şablonu çöp kutusuna kaldırıldı. Önceki şablonlar ve raporlar korundu. DM gönderilmedi.

## Sınırlar

Instagram'ın doğrulanamayan beğeni/yorum verileri başarı veya eksik olarak uydurulmaz; tabloda ayrı gösterilir. Ekleme işlemi önceki sonuçları yeniden doğrulamaz; bunun için Hızlı Güncelle veya Tam Yeniden Tara kullanılmalıdır. Testler belirtilen senaryoları kapsar, tüm olası dış servis davranışları için hatasızlık garantisi değildir.
