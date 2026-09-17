# Tema ve mobil görünüm doğrulaması — 18.09.2026

Ana sayfa paylaşım ve üye seçimine odaklandı. Üye düzenleme ile ek filtre/bağlantı araçları açılır alanlara taşındı. Geçmiş, şablonlar ve yönetim gezinmeden erişilebilir. Ortak kahve/karamel tema katmanı kartlar, alanlar, düğmeler, mobil gezinme ve modal boyutlarını birleştirir. Mobil yakınlaştırma yeniden kullanılabilir; azaltılmış hareket tercihi desteklenir.

## Testler

- Backend: 179 test geçti (`python -B -m unittest discover -s tests -q`).
- Tarayıcı: layout, interactions, select_modal, control_scope, daily_modal, daily_calendar, checkbox, audit_regressions, reliability, report_details, preset_reports geçti.
- Yeni `tests/browser/theme_refresh.py`: 320, 390, 768, 1440 pikselde 14 rota; 56 yerleşim kontrolü. Dört boyutta elle üye ekleme ve kapalı ana sayfa bölümleri doğrulandı.
- JavaScript: comment_modal, interactions, low_likes_filter, result_polling testleri geçti.
- Canlı: ana sayfa, geçmiş, araçlar, mevcut sonuç, üye analizi ve katılım tablosunda 24 ekran kontrolü; yönetim, grup kuralları, yedekler ve çöp kutusunda 12 oturumlu ekran kontrolü geçti. JavaScript hatası ve yatay belge taşması görülmedi.
- Canlı yorum/beğeni kopyalama ve 23 üyeli, 11 paylaşımlı tablonun araması/yatay kaydırması ayrıca doğrulandı.

## Koruma

Canlı dosyalar değiştirilmeden önce yedeklendi ve yüklenen dosyalar byte düzeyinde doğrulandı. Canlı veritabanı yüklenmedi veya değiştirilmedi. Gerçek raporlar okunarak test edildi; DM gönderilmedi ve yeni denetim başlatılmadı. Yeniden başlatma sırasında geçici 502 sonrasında ana sayfa HTTP 200 döndü.

`18092026.zip` SHA-256 değişmedi: `B5393E1C40B2A737B5FD270B7088676B2E01C2228DCABB5E53100A3DF47E57E2`.

Bu kontroller belirtilen ekran boyutları ve Chrome kapsamındadır; her fiziksel cihazda ayrı test yapılmış değildir.
