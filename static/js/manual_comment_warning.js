(() => {
    const input = document.getElementById('post_link_single');
    if (!input) return;
    const notice = document.createElement('p');
    notice.id = 'manualCommentNotice';
    notice.className = 'mode-hint';
    notice.style.color = 'var(--accent-caramel)';
    notice.setAttribute('role', 'status');
    notice.setAttribute('aria-live', 'polite');
    notice.hidden = true;
    input.after(notice);
    input.setAttribute('aria-describedby', notice.id);
    let timer, active, revision = 0;
    const cache = new Map();
    const announced = new Set();
    let modalDone = null;
    function showClosedModal(likes) {
        if (modalDone) return modalDone;
        const link = currentLink();
        if (!link || announced.has(link)) return;
        announced.add(link);
        const dialog = document.createElement('dialog');
        dialog.id = 'closedCommentsDialog';
        dialog.className = 'member-dialog control-scope-dialog';
        dialog.setAttribute('aria-labelledby', 'closedCommentsTitle');
        dialog.setAttribute('aria-describedby', 'closedCommentsDescription');
        dialog.innerHTML = '<div class="scope-heading"><span class="scope-icon"><i class="fas fa-comment-slash" aria-hidden="true"></i></span><div><span class="scope-eyebrow">PAYLAŞIM BİLGİSİ</span><h2 id="closedCommentsTitle">Yorumlar kapalı</h2></div><button type="button" class="scope-close" aria-label="Kapat">×</button></div><p id="closedCommentsDescription" class="scope-description"></p><div class="scope-actions"><button type="button" class="scope-edit">Anladım</button><button type="button" class="scope-start"><i class="fas fa-heart" aria-hidden="true"></i> Beğeni kontrolüne geç</button></div>';
        dialog.querySelector('.scope-description').textContent = likes
            ? 'Bu paylaşım yorumlara kapalı. Seçili beğeni kontrolüne devam edebilirsin.'
            : 'Bu paylaşım yorumlara kapalı. Yorum kontrolüne dahil edilmeyecek ve üyelere eksik yazılmayacak. İstersen beğenileri kontrol edebilirsin.';
        const previousFocus = document.activeElement;
        document.body.append(dialog);
        modalDone = new Promise(resolve => {
            const close = () => { dialog.close(); dialog.remove(); modalDone = null; previousFocus?.focus(); resolve(); };
            dialog.querySelector('.scope-edit').onclick = close;
            dialog.querySelector('.scope-close').onclick = close;
            dialog.querySelector('.scope-start').hidden = likes;
            dialog.querySelector('.scope-start').onclick = () => { close(); window.setControlType('likes'); display(true); };
            dialog.oncancel = event => { event.preventDefault(); close(); };
            dialog.showModal();
            dialog.querySelector('.scope-edit').focus();
        });
        return modalDone;
    }
    function currentLink() {
        if (input.disabled) return '';
        try {
            const url = new URL(input.value.trim());
            if (!['https:', 'http:'].includes(url.protocol) || !['instagram.com','www.instagram.com'].includes(url.hostname)) return '';
            const match = url.pathname.match(/^\/(?:p|reels?|tv)\/([A-Za-z0-9_-]+)\/?$/);
            return match ? 'https://www.instagram.com/p/' + match[1] + '/' : '';
        } catch { return ''; }
    }
    function display(state) {
        const likes = document.getElementById('controlMode')?.value === 'likes';
        notice.textContent = state === true
            ? (likes ? 'Bu paylaşım yorumlara kapalı. Beğeni kontrolü yapılabilir.' : 'Bu paylaşım yorumlara kapalı. Yorum kontrolüne dahil edilmeyecek; üyelere eksik yazılmayacak.')
            : state === false ? '' : 'Paylaşımın yorum durumu doğrulanamadı. Kontrol sırasında yeniden değerlendirilecek.';
        notice.hidden = !notice.textContent;
        if (state === true) return showClosedModal(likes);
    }
    async function check() {
        clearTimeout(timer);
        const link = currentLink(), version = ++revision;
        active?.abort();
        notice.hidden = true;
        if (!link) return;
        const cached = cache.get(link);
        if (cached && Date.now() - cached.time < 30000) { return display(cached.state); }
        active = new AbortController();
        const controller = active;
        const timeout = setTimeout(() => controller.abort(), 12000);
        try {
            const response = await fetch('/api/get_post_thumbnail?link=' + encodeURIComponent(link), {signal: controller.signal});
            const data = await response.json();
            if (version !== revision || link !== currentLink()) return;
            const state = response.ok && data.ok && typeof data.comments_disabled === 'boolean' ? data.comments_disabled : null;
            if (state !== null) cache.set(link, {state, time: Date.now()});
            return display(state);
        } catch {
            if (version === revision && link === currentLink()) display(null);
        } finally { clearTimeout(timeout); }
    }
    input.addEventListener('input', () => {
        clearTimeout(timer); ++revision; active?.abort(); notice.hidden = true;
        timer = setTimeout(check, 500);
    });
    input.addEventListener('change', check);
    for (const id of ['controlComments','controlLikes','modeSingle','modeMulti']) {
        document.getElementById(id)?.addEventListener('click', check);
    }
    document.getElementById('groupDropdown')?.addEventListener('click', () => {
        if (!currentLink()) { ++revision; clearTimeout(timer); active?.abort(); notice.hidden = true; }
    });
    window.checkManualCommentWarning = check;
})();
