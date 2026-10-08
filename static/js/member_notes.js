document.addEventListener('click', async event => {
    const button = event.target.closest('[data-refresh-notes]');
    if (!button || button.disabled) return;
    const card = button.closest('.sortable-main-card');
    const slot = card?.querySelector('.member-note-slot');
    if (!slot) return;
    let status = card.querySelector('.member-note-refresh-status');
    if (!status) {
        status = document.createElement('small');
        status.className = 'member-note-refresh-status';
        status.setAttribute('role', 'status');
        slot.after(status);
    }
    button.disabled = true;
    const label = button.querySelector('span');
    label.textContent = 'Yenileniyor…';
    status.textContent = '';
    try {
        const response = await fetch(`/api/reports/${encodeURIComponent(button.dataset.refreshNotes)}/notes/refresh`, {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({link: button.dataset.link})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Notlar yenilenemedi.');
        slot.innerHTML = data.html;
        status.textContent = data.count ? '' : 'Bu paylaşıma yakın üye mesajı bulunamadı.';
    } catch (error) {
        status.textContent = error.message || 'Notlar yenilenemedi. Önceki notlar korundu.';
    } finally {
        button.disabled = false;
        label.textContent = 'Notları yenile';
    }
}, true);
