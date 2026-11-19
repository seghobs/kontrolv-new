# Instagram APK yorum incelemesi — 20 Kasım 2026

İncelenen yerel APK: AndroidManifest.xml versionName `425.0.0.0.0`,
versionCode `383100026`. Dosyanın en güncel resmi Instagram sürümü olduğu iddia
edilmez. SHA-256:
`B9105790D0AAA9BA0A8606E6E87345577CFF2579606A85401FD651C1D67E0B9A`.

APK içindeki classes5.dex ve classes9.dex, JADX 1.5.5 ile ilgili sınıflar
seçilerek yeniden çözümlendi; daha önce atlanmış metot gövdeleri incelendi.

## Koddan doğrulanan fark

`MediaHiddenCommentNetworkFetcherKt.A00` normal medya yorum listesinden ayrı
`hidden_comments/%s/hidden_comments/` yolunu çağırıyor. İlk istekte
`directly_hidden_only=1`, sonraki sayfalarda `next_min_id` kullanıyor.
`min_id` ile devam eden normal yorum sayfalamasıyla aynı değildir.

`DEd` yanıt ayrıştırıcısında kayıt alanı `comments`, devam alanı `next_min_id`,
devam bayrağı `has_more_headload_comments`. `MediaParentCommentNetworkFetcherKt`
normal liste için `media/%s/comments/`, `can_support_threading`, `sort_order`,
`comment_filter_param` ve `min_id` kullanıyor.

## Uygulanan değişiklik

Sayaç farkı olduğunda APK'daki ayrı salt-okuma gizli yorum yolu da denenir.
Medya info yanıtındaki PK+owner kimliği, aynı gönderiye ait olduğu doğrulanarak
kullanılır. Gerçek yorumlar PK ile birleştirilir; cursor döngüsü ve mevcut
istek/süre bütçesi korunur. 401/403/429 alındığında kurtarma durur. Yorum gizleme,
gizlilik ayarı değiştirme, onaylama veya görünür yapma isteği gönderilmez.

Bu istek sunucunun mevcut hesaba tanıdığı izinlerle çalışır; APK'da bir uç nokta
bulunması, mevcut hesabın gizli yorumlara erişebildiğini kanıtlamaz. Kullanıcı,
gönderi sahibinin hesabının uygulamadaki token havuzuna bağlı olmadığını bildirdi.
Bu nedenle sahibin görebildiği yorumları aynı yetkiyle karşılaştırma yapılamadı.

## Test

300 otomatik test geçti. Yeni testler ayrı API kökü, tam medya kimliği,
`directly_hidden_only=1`, `next_min_id` ile devam, kimlik birleştirme ve izin
reddinde durma davranışını kontrol ediyor.

Ham APK/DEX, çıkarılmış üçüncü taraf Java kodları, kullanıcı yorumları ve oturum
bilgileri repoya eklenmedi.

## Canlı sonuç

Aynı gönderi 16,5 saniyede yeniden denetlendi: Instagram toplamı 87, elde edilen
86 benzersiz yorum. APK'dan doğrulanan gizli yorum isteği mevcut hesapla HTTP400
döndürdü. Normal stream ve comments istekleri HTTP200 döndürdü ve ek kimlik
getirmedi. Güncel web doc_id bağlantısı da HTTP400 döndürdü.

Bir yorumluk fark devam ediyor; bu kaydın kurtarıldığı iddia edilmez. HTTP400'ün
tek başına nedeninin yetki eksikliği olduğu kanıtlanmış değildir. Gönderi sahibinin
yetkili hesabıyla gizli yorum listesini karşılaştırmak bir sonraki doğrulama adımıdır;
bunun da kaydı mutlaka getireceği garanti edilemez.

Sonuç `verification_pending=true` ve boş kesin eksik listesiyle kaydedildi:
https://kontrolyeni.pythonanywhere.com/result/468e493837f4458cb654851151785310
