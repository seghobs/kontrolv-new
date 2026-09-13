(() => {
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
