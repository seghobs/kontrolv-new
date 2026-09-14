# DM, oturum ve analiz doğruluğu — doğrulama sonuçları

14 Eylül 2026 tarihli güncelleme.

## Değişiklikler

- DM gönderimi artık yalnız HTTP 200 ile başarılı sayılmıyor. Uygulama hata alanlarını ve mesaj kimliğini denetliyor; kabul, ret ve belirsizlik ayrılıyor. Sonucu belirsiz gönderim otomatik tekrarlanmıyor. Yönetici test bildirimi de ilk başarısız gönderimde duruyor.
- Ağ zaman aşımı ve tanınmayan doğrulama yanıtı, geçerli/geçersiz yerine doğrulanamadı sonucuna dönüşüyor. Bu nedenle hesap devre dışı bırakılmıyor ve olumlu doğrulama zamanı ilerletilmiyor.
- Oturum tokenı, yardımcı alanlar ve çerez güncellemeleri tek SQLite işlemiyle saklanıyor. Token ve kayıt sürümü kontrolü gecikmiş yanıtların güncel bilgileri ezmesini engelliyor. HTTP oturumu yeniden oluşturulunca kayıtlı çerezler geri yükleniyor; açık Authorization çerezleri diğer gerekli çerezleri gizlemiyor.
- Yorum yanıtlarındaki alınabilen alt yorumlar korunuyor. Görünmeyen alt yorumlar, hatalı yazar bilgisi veya toplam sayıdan az yorum alınması tam liste kabul edilmiyor. Günlük analizde bulunan üye, diğer kayıtlar bozuk olsa bile tamamlanan olarak gösteriliyor; metin yoksa bu açıkça belirtiliyor.
- Normal kontrol, günlük analiz ve eksik DM otomasyonu; liste tamlığı doğrulanmadan kesin yorum eksiği üretmiyor.
- Günlük analizde yalnız belirsiz sonuçlar yeniden kontrol edilebiliyor. Önceki doğrulanmış sonuçların yorumları ve kontrol zamanı korunuyor. Çift tıklama tek iş oluşturuyor. Eski raporlar değiştirilmeden yeni yöntemle yeniden doğrulanabiliyor.
- Gizli kopyalama metin alanının ortak stiller nedeniyle görünmesi düzeltildi.

## Yerel testler

| Kontrol | Sonuç |
|---|---|
| Backend testleri | 168 başarılı; önceki 147 teste 21 yeni test eklendi |
| Tarayıcı senaryoları | 9 başarılı |
| JavaScript test dosyaları | 4 başarılı |
| Mobil ve masaüstü yeni analiz görünümü | 390 ve 1440 pikselde başarılı |
| DM hata senaryoları | HTTP 200/hata, oturum reddi, challenge, kısıtlama, bozuk yanıt, eksik mesaj kimliği, timeout doğrulandı |
| Oturum senaryoları | Çerez geri yükleme, domain/path kapsamı, çerez silinmesi, hesap ayrımı, gecikmiş token/claim ve kayıt sürümü doğrulandı |
| Analiz senaryoları | Kısmi liste, toplam sayı uyuşmazlığı, boş metin, bozuk kayıt yanında bilinen yazar, alt yorum, belirsizleri yeniden kontrol ve eski raporu koruma doğrulandı |

Eksik listeyi doğrulayan eski test örneklerine, yeni sözleşmeye uygun doğrulanmış toplam yorum sayısı eklendi. Yorum sayısı 14 iken yalnız 11 kayıt dönen ayrı bir test, kesin eksik üretilmediğini kontrol ediyor.

## Canlı kontroller

- Canlı dosyalar yüklemeden önce önceki sürümle karşılaştırıldı ve yedeklendi. Yüklenen içerikler dosya düzeyinde doğrulandı. Ana sayfa yeniden yükleme sonrasında HTTP 200 döndü.
- Yönetici girişi, denetim geçmişi, araçlar, grup kuralları, yedekler, çöp kutusu, mevcut rapor ve Excel dışa aktarma kontrolleri geçti.
- [Yeniden doğrulanan @hellocurcu raporu](https://kontrolyeni.pythonanywhere.com/member-analysis/1fb8334997be44d4ae0ef92d7d43d9b2): yorumlarda 7 eksik, 3 belirsiz, 1 kapsam dışı. Eski raporda bu üç belirsiz paylaşım da eksik sayılıyordu. Üyeye ait yorumun gerçekten bulunduğuna ilişkin yeni kanıt elde edilmedi; belirsizlik eksik olarak sunulmadı.
- [Gerçek olumlu eşleşme raporu](https://kontrolyeni.pythonanywhere.com/member-analysis/972f1342dd13439e9bee30c9c25a284c): 11 tamamlanan yorum paylaşımı ve 11 yorum metni; beğenilerde 8 tamamlanan, 3 belirsiz.
- [Yalnız belirsizlerin yeniden kontrolü](https://kontrolyeni.pythonanywhere.com/member-analysis/8aa92f0ed7514571a5bd633b4c62f141): çift tıklama tek iş oluşturdu; önceki 11 yorum sonucu korundu.
- Canlı olumlu rapor 390 ve 1440 piksel genişliğinde tarayıcıda açıldı: yorum metinleri görünür, kopyalama tamponları gizli; yatay taşma veya JavaScript hatası yok.

## Sınırlar

Gerçek kişilere DM gönderilmedi. DM düzeltmeleri sentetik yanıtlar ve izole veritabanıyla test edildi; gerçek teslim/okunma iddiasında bulunulmuyor. Mesaj kimliğiyle doğrulanan sonuç Instagram'ın isteği kabul etmesidir, alıcının okuduğu anlamına gelmez.

Instagram erişimi veya verisi yetersizse belirsiz sonuç görülebilir. Bu davranış hatayı gizlemek yerine kesin olmayan eksikleri ayırır. Güncelleme Instagram'ın gerçekten iptal ettiği bir oturumun süresiz geçerliliğini garanti etmez.

Üretim veritabanı dosyası yüklenmedi, silinmedi veya başka bir dosyayla değiştirilmedi. SQLite bütünlük kontrolü başarılı; önceki 1 hesap ve 199 denetim kaydının tamamı korundu. Canlı kontrollerin ardından denetim sayısı 204 oldu. Normal canlı analizler kendi yeni rapor ve oturum güncelleme kayıtlarını oluşturdu.
