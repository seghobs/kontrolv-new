(() => {
    if (!window.postCode || !window.resultThreadId) return;
    const dialog = document.createElement('dialog');
    dialog.className = 'member-dialog';
    dialog.innerHTML = `<form><h2>Üyeye özel günlük analiz</h2><p class="member-name"></p><label>Gruba paylaşım yapılan tarih<input type="date" required name="date"></label><p>Seçilen günün tüm gönderi ve Reels’leri, hem yorum hem beğeni için kontrol edilir. İki eksik listesi ayrı kopyalanabilir. Yeni bir sonuç açılır.</p><p role="alert" class="member-error"></p><div class="member-actions"><button type="button" class="member-close">Vazgeç</button><button type="submit">Analiz Et</button></div></form>`;
    document.body.append(dialog);
    let username = '';
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
                body:JSON.stringify({username, date:dialog.querySelector('[name=date]').value})
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'Analiz başlatılamadı.');
            window.location.assign(data.result_url);
        } catch(error) {dialog.querySelector('.member-error').textContent = error.message;}
        finally {button.disabled = false;}
    };
})();
