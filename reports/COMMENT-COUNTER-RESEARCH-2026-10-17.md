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

## Gerçek Android uygulamasıyla karşılaştırma

MEmu'daki Instagram Android 449.0.0.52.84 uygulamasının mitmweb trafiği incelendi. Kullanıcı aynı paylaşımı açıp yorum listesini yükledi.

Üç gerçek HTTP 200 yanıtı:

1. stream_comments: üç NDJSON parçası, 5 + 5 + 4 yorum.
2. stream_comments: iki NDJSON parçası, 5 + 5 yorum.
3. stream_comments: 0 yorum, has_more_comments=false, has_more_headload_comments=false.

Toplam 24 benzersiz yorum kimliği, web uygulamasının aldığı kimliklerle birebir aynı. Android yanıtında da comment_count=25. Dolayısıyla sayaç ile döndürülen liste farkı resmi mobil istemciye de geliyor. Bu kanıt, 25. kaydın hangi nedenle görünmediğini açıklamaz; 25. yorumu kurtardığımız iddia edilmez.

ADB ile APK alındı ve ilgili DEX sınıfları incelendi. MediaHiddenCommentNetworkFetcherKt ayrı hidden_comments/%s/hidden_comments/ yolu kullanıyor. Mevcut yetkili web hesabıyla bu okuma isteği HTTP400 Invalid request verdi. Gizli yorum elde edilmedi; izin aşma veya yorum gizliliğini değiştirme işlemi yapılmadı.

Uygulama API parametreleri: should_fetch_creator_comment_nudge, can_support_threading, page_type, is_carousel_bumped_post, feed_position; sonraki sayfalarda min_id ve popular sort_order. Kaynakta olmayan farklı bir 'oldest' yöntemi bulunmadı.

Ham trafik, oturum başlıkları ve APK repoya eklenmedi. Yalnızca kimliksizleştirilmiş NDJSON yapısı ve gizli bilgi içermeyen kanıt özeti eklendi. Regresyon testi tüm NDJSON parçalarının korunmasını ve caption kaydının yorum sayılmamasını kontrol eder.

### Meta Verified ve diğer APK sıralamaları

APK'da 0DdW filtre enum'u: no_filter, subscriber_comments_only, meta_verified_comments_only, people_you_follow_comments_only. 0Ddt sıralama enum'u: popular, recent, meta_verified, followers, following, questions, follower_count.

Canlı salt-okuma denemesinde meta_verified, following, questions ve follower_count 24 aynı kimliği ve doğru sort_order karşılığını verdi. followers karşılığı geçerli yorum bağlantısı vermedi; üretimde eklenmedi. Meta Verified-only filtresi 13 yorum döndürdü, yeni kimlik getirmedi; tüm yorumların yerine kullanılmıyor.

Sayaç farkı devam ederse dört ek sıralama yalnızca kurtarma görünümü olarak taranıyor. Elde edilen doğrulanabilir yeni yorum kimlikleri birleştiriliyor. Daraltıcı Verified-only filtresi ana denetim kapsamını değiştirmiyor. Ek tarama başarısızlığı mevcut pozitif yorum kanıtlarını silmiyor; yeni kimlikler bulunduğunda eski iki listenin eşitliği üzerinden görünür liste tamamlandı varsayılmıyor.

### Tarama sırasında değişen sayaç hatası

Araştırma sırasında yeni bir yorum geldi: aynı taramanın ilk recent sayfasında sayaç25, sonraki sayfalarda26 görüldü. Birleşik listede25 yorum vardı. Eski media/info sayacı25 ile kıyaslama bu taramayı yeterli sayabiliyordu. Bu yerel hata düzeltildi: iki ana sıralamadan gözlenen en yüksek geçerli sayaç, daha düşük eski media/info sayacını yükseltir; yeniden doğrulama gerekir. Geçersiz/tek sıralama/başarısız yanıt bu kararı veremez. Açık FB sayacı bulunduğunda belirsiz bir ikinci çıkarma/yükseltme uygulanmaz.

Sonraki kararlı canlı tarama: Instagram26, mobil ve web25, dört ek Android sıralaması da25. Eski bir yorumluk fark sürüyor; yeni yerel yarış durumu düzeltildiği için bu farkın gizlendiği veya kayıp kaydın kurtarıldığı iddia edilmiyor.
