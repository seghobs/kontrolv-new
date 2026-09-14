(() => {
    if (!window.postCode || !window.resultThreadId) return;
    const dialog = document.createElement('dialog');
    dialog.className = 'member-dialog daily-analysis-dialog';
    dialog.setAttribute('aria-labelledby','daily-analysis-title');
    dialog.innerHTML = `<form><header class="daily-heading"><span class="daily-icon"><i class="fas fa-user-check" aria-hidden="true"></i></span><div><span class="daily-eyebrow">ÜYEYE ÖZEL</span><h2 id="daily-analysis-title">Günlük analiz</h2></div><button type="button" class="daily-dismiss" aria-label="Kapat">×</button></header><div class="daily-member"><span class="member-name"></span><span class="daily-mode"><i class="fas fa-comment" aria-hidden="true"></i> Yorum <span>+</span> <i class="fas fa-heart" aria-hidden="true"></i> Beğeni</span></div><div class="daily-dates"><label>Başlangıç tarihi<input type="date" required name="date"></label><label>Bitiş tarihi <small>İsteğe bağlı</small><input type="date" name="end_date"></label></div><p class="daily-date-hint">Paylaşımların gruba gönderildiği tarihi seç.</p><label class="daily-owner"><input type="checkbox" name="skip_owner" checked><span><strong>Kendi paylaşımını hariç tut</strong><small>Üyenin kendi gönderileri analize dahil edilmez.</small></span></label><p class="daily-info"><i class="fas fa-circle-info" aria-hidden="true"></i><span>Seçilen tarihlerdeki gönderi ve Reels’ler kontrol edilir. Yorum ve beğeni eksiklerini ayrı ayrı kopyalayabilirsin.</span></p><p role="alert" class="member-error"></p><div class="member-actions"><button type="button" class="member-close">Vazgeç</button><button type="submit">Analizi başlat <i class="fas fa-arrow-right" aria-hidden="true"></i></button></div></form>`;
    document.body.append(dialog);
    let username = '';
    dialog.querySelector('.daily-dismiss').onclick = () => dialog.close();
    dialog.querySelector('.member-close').onclick = () => dialog.close();
    document.querySelectorAll('.eksikler-list li[data-username]').forEach(item => {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'member-analyze-button'; button.textContent = 'Günlük Analiz';
        button.onclick = event => {
            event.stopPropagation(); username = item.dataset.username;
            dialog.querySelector('.member-name').textContent = '@' + username;
            dialog.querySelector('.member-error').textContent = '';
            dialog.showModal();
        };
        item.append(button);
    });
    dialog.querySelector('form').onsubmit = async event => {
        event.preventDefault(); const button = dialog.querySelector('[type=submit]');button.disabled = true;
        try {
            const response = await fetch('/api/member_analysis/' + encodeURIComponent(window.postCode), {
                method:'POST',headers:{'Content-Type':'application/json'},
                body:JSON.stringify({username, date:dialog.querySelector('[name=date]').value,end_date:dialog.querySelector('[name=end_date]').value,skip_owner:dialog.querySelector('[name=skip_owner]').checked})
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'Analiz başlatılamadı.');
            window.location.assign(data.result_url);
        } catch(error) {dialog.querySelector('.member-error').textContent = error.message;}
        finally {button.disabled = false;}
    };
})();
