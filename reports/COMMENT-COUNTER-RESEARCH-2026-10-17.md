# Yorum sayacı farkı araştırması — 17 Ekim 2026

İncelenen paylaşım: `DekE1Imo4To`.

## Canlı bulgular

- Mobil recent: 15 + 9 = 24 farklı yorum kimliği.
- Mobil popular: 14 + 10 + 0 = aynı 24 kimlik.
- Stream: 24 kimlik; son sayfa tamamlandı.
- Instaloader mobil yaklaşımı (threading=true, permalink_enabled=false): aynı 24 kimlik.
- Instaloader GraphQL sorgusu (97b41c52301f77ce508f55e66d17620e): count=25, edges=24, has_next_page=false. Mobil listede bulunmayan kimlik yok.
- Yeni GraphQL doc_id denemeleri HTTP 400 döndürdü; başarısız yanıtlar yorum yok diye yorumlanmadı.
- Çocuk yorum ve Facebook listeleri boş. Bu paylaşımda fb_comment_count raporlanmıyor; fark Facebook sayılarak düşülmedi.
- Caption ayrı bir type=1 kayıt. Bir yorum daha elde edilmiş gibi sayılmadı.

25. kaydın sahibi veya görünmeme sebebi doğrulanamadı. Gizli/silinmiş yorum iddiası kanıtlanmış değildir. Erişilemeyen kaydı geri getirdiğimiz veya sayaç farkının Instagram tarafında giderildiği iddia edilmiyor.

## Uygulama değişikliği

Mobil iki sıralama bitmesine rağmen sayaç farkı kalırsa bağımsız web GraphQL bağlantısı taranır. Yeni yorumlar kimlikle birleştirilir; sayfalama sınırlı ve döngü korumalıdır. Web erişim hatası mobilde bulunan yorumları silmez. Yarım web taraması tam liste kanıtı sayılmaz.

Sonuç kartındaki sürekli sayaç açıklaması kaldırıldı. Kontrol kapsamı bilgisi mevcut Detaylar penceresinde korunur. Gerçek erişim/kimlik/sayfalama hataları başarıya çevrilmez. Eksik listesi API ile erişilebilen yorumlar kapsamındadır; görünmeyen kaydın sahibine dair kesinlik sağlanamaz.

284 otomatik test geçti. Yeni testler: web ile eksik kaydı tamamlama, aynı 24 kimliğin bağımsız doğrulaması, web hata toleransı, web sayfalama, cursor döngüsü, detay bilgisinin görünmesi ve farklı paylaşımda temizlenmesi.

## İncelenen birincil kaynaklar

- https://github.com/instaloader/instaloader/blob/master/instaloader/structures.py
- https://github.com/subzeroid/instagrapi/blob/master/instagrapi/mixins/comment.py
- https://github.com/ping/instagram_private_api/blob/master/instagram_private_api/endpoints/media.py
- https://github.com/dilame/instagram-private-api/blob/master/src/feeds/media-comments.feed.ts

GitHub'daki bütün depoların tarandığı iddia edilmiyor; ilgili yaygın istemcilerin kaynakları karşılaştırıldı.
