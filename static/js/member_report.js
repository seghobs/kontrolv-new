(() => {
    let retryPending = false;
    document.querySelectorAll('[data-retry-unknown], [data-member-refresh]').forEach(button => {
        button.addEventListener('click', async () => {
            if (retryPending) return;
            retryPending = true;
            const buttons = document.querySelectorAll('[data-retry-unknown], [data-member-refresh]');
            buttons.forEach(b => b.disabled = true);
            const feedback = button.closest('section').querySelector('[data-retry-feedback]');
            feedback.textContent = 'Yeni analiz hazırlanıyor…';
            try {
                const response = await fetch('/api/member_analysis/' + (button.dataset.retryUnknown || button.dataset.memberRefresh) + (button.dataset.memberRefresh ? '/refresh' : '/retry-unknown'), {method: 'POST'});
                const data = await response.json();
                if (!response.ok || !data.success || !/^\/member-analysis\/[a-f0-9]{32}$/.test(data.result_url || '')) {
                    throw new Error(data.error || 'Yeni analiz başlatılamadı.');
                }
                window.location.assign(data.result_url);
            } catch (error) {
                feedback.textContent = error instanceof SyntaxError ? 'Sunucudan geçerli yanıt alınamadı. Tekrar deneyebilirsiniz.' : error.message;
                retryPending = false;
                buttons.forEach(b => b.disabled = false);
            }
        });
    });
    document.querySelectorAll('[data-member-copy]').forEach(button => {
        if (button.disabled) return;
        button.addEventListener('click', async () => {
            const suffix = button.dataset.memberCopy;
            const text = document.getElementById('member-missing-text' + suffix);
            const feedback = document.getElementById('member-copy-feedback' + suffix);
            try {
                await navigator.clipboard.writeText(text.value.trim());
                feedback.textContent = 'Eksik paylaşım listesi kopyalandı.';
            } catch {
                text.hidden = false; text.focus(); text.select();
                feedback.textContent = 'Otomatik kopyalanamadı. Seçili listeyi kopyalayabilirsiniz.';
            }
        });
    });
})();
