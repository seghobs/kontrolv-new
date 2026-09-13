(() => {
    let busy = false;
    const buttons = () => [true, false].map(mode => document.querySelector(`button[onclick="triggerRecheck(${mode})"]`)).filter(Boolean);
    function setBusy(value) {
        busy = value;
        buttons().forEach(button => { button.disabled = value; });
    }
    function clearPending() {
        setBusy(false);
        const url = new URL(window.location.href);
        url.searchParams.delete('recheck');
        window.history.replaceState(null, '', url);
    }
    function follow(jobId) {
        setBusy(true);
        const url = new URL(window.location.href);
        url.searchParams.set('recheck', jobId);
        window.history.replaceState(null, '', url);
        startResultPolling(jobId, clearPending);
    }
    window.triggerRecheck = async (onlyMissing) => {
        if (busy || !window.postCode) return;
        setBusy(true);
        const status = document.getElementById('loading-message');
        status.textContent = onlyMissing ? 'Eksikler güncelleniyor… Mevcut sonuçlar aşağıda.' : 'Yeniden taranıyor… Mevcut sonuçlar aşağıda.';
        try {
            const response = await fetch(`/api/recheck/${encodeURIComponent(window.postCode)}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content'),
                },
                body: JSON.stringify({only_missing: onlyMissing}),
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.message || 'Güncelleme başlatılamadı.');
            const resultUrl = new URL(data.result_url, window.location.origin);
            const match = resultUrl.pathname.match(/^\/result\/([^/]+)$/);
            if (!match || resultUrl.origin !== window.location.origin) throw new Error('Sonuç bağlantısı alınamadı.');
            follow(decodeURIComponent(match[1]));
        } catch (error) {
            clearPending();
            status.textContent = error.message || 'İletişim hatası oluştu. Tekrar deneyin.';
        }
    };
    document.addEventListener('DOMContentLoaded', () => {
        const pending = new URLSearchParams(window.location.search).get('recheck');
        if (pending) follow(pending);
    });
})();
