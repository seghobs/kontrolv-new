# Grup seçici mobil düzeltmesi

Mevcut grup listesinin görünümü korunarak Popover üst katmanı kullanıldı. Ekrandaki kullanılabilir yüksekliğe ve alt gezinme menüsüne göre yukarı/aşağı konumlanır. Arama sabit kalır; seçenekler tek kaydırma alanıdır. Kapalı menüler yatay taşmaya neden olmaz. Bootstrap d-flex kuralının arama sonuçlarını gizlemeyi engellemesi de düzeltildi.

Yerel ve canlı tarayıcı testi: 30 gruplu kontrollü yanıtla 320x568, 390x844, 390x420, 1440x900 ekranlarında menü sınırları, en son satıra kaydırma ve elementFromPoint tıklanabilirliği, arama, seçim, Escape ve yatay taşma doğrulandı. Grup tercihleri ve ortak seçim penceresi regresyon testleri geçti. Canlı testte grup/veri API yanıtları taklit edildi; gerçek tercihler değiştirilmedi, denetim/DM gönderilmedi.
