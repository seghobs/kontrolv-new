(() => {
    const panel = document.querySelector('.worker-status');
    if (!panel) return;
    const state = panel.querySelector('[data-worker-state]');
    let busy = false;
    let stopped = false;
    let timer;
    async function refresh() {
        if (busy || stopped || document.hidden) return;
        busy = true;
        clearTimeout(timer);
        const controller = new AbortController();
        const deadline = setTimeout(() => controller.abort(), 5000);
        try {
            const response = await fetch('/api/worker_status', {cache: 'no-store', signal: controller.signal});
            if (response.status === 401) {
                state.textContent = 'İşçi durumunu görmek için yeniden giriş yapın.';
                stopped = true;
                return;
            }
            if (!response.ok) throw new Error('Status unavailable');
            const data = await response.json();
            state.textContent = data.online
                ? (data.running || data.cancelling ? 'İşçi çalışıyor' : 'İşçi hazır')
                : (data.last_seen ? 'İşçi bağlantısı kesildi' : 'İşçi henüz bağlanmadı');
            panel.querySelector('[data-worker-queued]').textContent = data.queued;
            panel.querySelector('[data-worker-running]').textContent = data.running + data.cancelling;
            const seen = panel.querySelector('[data-worker-seen]');
            seen.textContent = data.last_seen ? new Date(data.last_seen * 1000).toLocaleString('tr-TR', {timeZone:'Europe/Istanbul'}) : 'Henüz yok';
        } catch (_) {
            state.textContent = 'Sunucuya ulaşılamıyor; işçi durumu doğrulanamadı.';
            panel.querySelector('[data-worker-queued]').textContent = '—';
            panel.querySelector('[data-worker-running]').textContent = '—';
        } finally {
            clearTimeout(deadline);
            busy = false;
            if (!stopped) timer = setTimeout(refresh, 5000);
        }
    }
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) clearTimeout(timer);
        else refresh();
    });
    refresh();
})();
