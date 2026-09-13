(() => {
    let active = false;
    const button = () => document.getElementById('submitCheckBtn');
    const message = () => document.getElementById('loading-message');
    let originalLabel;
    function setBusy(busy) {
        active = busy;
        const btn = button();
        if (!btn) return;
        originalLabel ??= btn.innerHTML;
        btn.disabled = busy;
        btn.innerHTML = busy ? 'Kontrol ediliyor…' : originalLabel;
    }
    function follow(jobId) {
        setBusy(true);
        const url = new URL(window.location.href);
        url.searchParams.set('task', jobId);
        window.history.replaceState(null, '', url);
        startResultPolling(jobId, () => {
            setBusy(false);
            url.searchParams.delete('task');
            window.history.replaceState(null, '', url);
        });
    }
    window.submitControl = async (form) => {
        if (active) return;
        setBusy(true);
        message().textContent = 'Denetim başlatılıyor…';
        try {
            const response = await fetch(form.action, {
                method: 'POST', body: new FormData(form),
                headers: {'Accept': 'application/json'},
            });
            if (!(response.headers.get('content-type') || '').includes('application/json')) {
                throw new Error('Denetim başlatılamadı. Paylaşım bağlantısını kontrol edip tekrar deneyin.');
            }
            const data = await response.json();
            if (!response.ok || !data.success || !data.job_id) throw new Error(data.message || 'Denetim başlatılamadı.');
            follow(data.job_id);
        } catch (error) {
            setBusy(false);
            message().textContent = error.message || 'Bağlantı kurulamadı. Tekrar deneyin.';
        }
    };
    document.addEventListener('DOMContentLoaded', () => {
        const task = new URLSearchParams(window.location.search).get('task');
        if (task) follow(task);
    });
})();
