(() => {
    const normalize = name => String(name || '').trim().replace(/^@/, '').toLowerCase();
    const previews = [...document.querySelectorAll('[data-comment-preview]')];
    if (!previews.length) return;
    window.userComments ||= {};
    function collect(comments) {
        for (const comment of comments || []) {
            const name = normalize(comment.username);
            if (!name || !comment.text || typeof comment.text !== 'string') continue;
            const stored = window.userComments[name] ||= [];
            if (!stored.includes(comment.text)) stored.push(comment.text);
        }
    }
    function render(final = false, failed = false) {
        let missing = false;
        for (const preview of previews) {
            const name = normalize(preview.closest('[data-username]').dataset.username);
            const comments = window.userComments[name] || [];
            if (comments.length) {
                const display = comments.map(text => text || 'Yorum mevcut; metni alınamadı.');
                preview.textContent = display.slice(0, 2).join(' • ') + (display.length > 2 ? ` · +${display.length - 2} yorum (görüntüle)` : '');
                preview.title = display.join('\n');
            } else {
                missing = true;
                preview.textContent = final ? (failed ? 'Yorumu yüklemek için tıklayın' : 'Yorum metni bulunamadı') : 'Yorum yükleniyor…';
            }
        }
        return missing;
    }
    const posts = Object.values(window.postDetailsData || {});
    posts.forEach(post => collect(post.comments_list));
    if (!render()) return;
    (async () => {
        let failed = false;
        for (const post of posts) {
            if (!post.link) continue;
            try {
                const response = await fetch(`/api/get_post_interactions?link=${encodeURIComponent(post.link)}&type=comments`);
                const data = await response.json();
                if (!response.ok || !data.ok) throw new Error('Comments unavailable');
                post.comments_list = data.comments || [];
                collect(post.comments_list);
                render();
            } catch (_) { failed = true; }
        }
        render(true, failed);
    })();
})();
