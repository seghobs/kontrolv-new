# Sonuçtan forma geri dönüş — 18.09.2026

Kontrol tamamlandığında ana formun geçmiş kaydında `?task=...` kalması, tarayıcı geri düğmesinin aynı sonucu yeniden açmasına neden oluyordu. Sonuca yönlendirmeden önce görev parametresi kaldırılır, formun meşgul durumu ve ilerleme yazısı temizlenir. Devam eden görevlerin yenileme sonrası takibi korunur. Diğer URL parametreleri korunur.

Doğrulama:
- 179 backend testi geçti.
- `tests/test_result_polling.cjs`: terminal sonuçlarda ve istek içinde çalıştırmada bitiş callback'i tam bir kez çağrılır; devam eden görevlerde çağrılmaz. Mevcut yeniden deneme testleri geçti.
- `tests/browser/back_navigation.py`: tamamlanan, istek içinde çalıştırılan, başarısız ve iptal edilen görevlerde form → sonuç → tarayıcı geri → yenile → yeni kontrol akışı geçti. Bekleyen görev bağlantısının takibi ve diğer sorgu parametrelerinin korunması doğrulandı.
- Aynı tarayıcı testi canlı sitede kullanıcının 8bf17476450d46808001989bc98145d0 raporu üzerinden de geçti. Başlatma/çalıştırma/durum istekleri tarayıcıda taklit edildi; gerçek rapor sayfası kullanıldı, yeni denetim veya DM gönderilmedi.
- Şablon/katılım tablosu tarayıcı regresyon testleri geçti.

Canlı dosyalar yedeklendi ve yükleme doğrulandı. GitHub ve canlı sürüm güncellendi. Veritabanı ve 18092026.zip değiştirilmedi.


## Önbellek regresyonu

İlk düzeltmeden sonra kullanıcıdaki eski `result_polling.js?v=web-execution-1` dosyasının bir saatlik HTTP önbelleğinde kalabildiği görüldü. Form ve sonuç şablonlarındaki sabit sürüm kaldırıldı; mevcut içerik hash mekanizması bu dosyada da kullanılıyor.

`tests/browser/back_navigation_cache.py` gerçek HTTP önbelleği açıkken (Playwright routing kullanılmadan) eski sabit URL ile hatayı yeniden üretti. Aynı tarayıcı bağlamında içerik hash adresine geçilince eski önbellek temizlenmeden geri dönüş ve yeni kontrol geçti. 179 backend testi ve önceki navigasyon senaryoları tekrar geçti.

Canlıda iki şablonun dosya hash'i doğrulandı. Kullanıcının 414ba2c129ee40f295d1e12591406cf9 kaydının gerçek durum/sonuç yanıtlarıyla geri dönüş ve yenileme doğrulandı; yalnız yeni denetim oluşturacak POST yanıtı tarayıcıda değiştirildi. Veritabanına yeni denetim yazılmadı.
