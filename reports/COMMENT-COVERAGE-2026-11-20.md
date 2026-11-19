# Tam yorum kapsamı — 20 Kasım 2026

## Sorun

`Df7nAs8RM_8` paylaşımında Instagram'ın bildirdiği toplam ile döndürdüğü yorum
kimlikleri eşleşmiyor. İlk canlı yeniden denetim: toplam 85, 84 gerçek yorum.
Eksik kaydın sahibini veya görünmeme nedenini doğrulayamadık. Silinmiş/gizlenmiş
bir yorum olduğu veya sayacın hatalı olduğu kesin olarak söylenemez.

İki sıralamanın aynı görünür kayıtları döndürmesi, görünmeyen kaydın gruptaki
herhangi bir üyeye ait olmadığını kanıtlamaz. Önceki görünür liste kapsamı,
istenen **tüm yorumlara göre kesin eksik listesi** için yeterli değildir.

## Değişiklikler

- Doğrulanmış medya toplamı daha küçük bir görünür listeye indirilmez. Tarama
  sırasında artan sayaç korunur; daha küçük sonraki medya yanıtı farkı silmez.
- Erken biten recent/popular sayfalaması en fazla üç ek geçişle tekrarlanır;
  kayıtlar metinle veya kullanıcı adıyla değil gerçek yorum kimliğiyle birleşir.
- Sayfa dışında kalan preview/hoisted/pinned kayıtları, NDJSON akışının tüm
  parçaları, iki cursor yönü ve ayrı yanıt sayfaları kurtarma için değerlendirilir.
- Güncel web doc_id yorum bağlantısı, eski query_hash bağlantısına eklenir.
  Captions ve yalnızca sayaç içeren kayıtlar yorum gibi sayılmaz.
- Gerektiğinde yalnızca zaten aktif olan diğer bir yetkili hesap denenir. Yeni
  giriş yapılmaz; 401/403/429 sonrasında hesap değiştirerek devam edilmez.
- Ek kurtarma taraması 24 istek ve 30 saniyeyle sınırlıdır. Kaynak hatası
  önceden bulunan gerçek yorumcuları silmez; hatalı/eksik yanıt yokluk kanıtı
  sayılmaz.
- Sayaç farkı sürerse kesin eksik listesi oluşturulmaz. Pozitif yorum kanıtı
  korunur. Eski görünür kapsam açıklaması taşıyan kayıtlar, hızlı güncelleme ve
  checkpoint kullanımında tam doğrulanmış sonuç gibi yeniden kullanılmaz.
- Eski raporların kapsam açıklaması sonuç kartında da görünür.

## Doğrulama

Kimlik birleştirme, ayrı yorumlarındaki aynı metin, NDJSON parçaları, iki cursor,
çocuk yanıtları, hoisted kayıtlar, caption/anonim kayıt reddi, döngü sonlandırma,
rate limitte durma, aktif ek hesap, sayaç düşürmeme ve arayüz kapsam açıklaması
otomatik testlerle kontrol edilir. Canlıda verilemeyen kaydın kurtarıldığı veya
Instagram'ın tüm içerikleri erişilebilir yaptığı iddia edilmez.

## İncelenen kaynaklar

- https://github.com/subzeroid/instagrapi/blob/master/instagrapi/mixins/comment.py
- https://github.com/subzeroid/instagrapi/blob/master/instagrapi/mixins/public.py
- https://github.com/instaloader/instaloader/blob/master/instaloader/structures.py

API anahtarları, oturumlar, veritabanları ve ham canlı yorumlar repoya eklenmedi.
