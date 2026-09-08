// Navigate as soon as the server finishes; visual progress never delays results.
function startResultPolling(postCode) {
    const progressBar = document.getElementById('loading-progress-bar');
    const loadingMsg = document.getElementById('loading-message');
    const loadingPercent = document.getElementById('loading-percent');
    let finished = false;
    let retryDelay = 1000;

    function showProgress(value) {
        const progress = Math.max(0, Math.min(100, Number(value) || 0));
        if (progressBar) {
            progressBar.style.width = progress + '%';
            progressBar.setAttribute('aria-valuenow', progress);
        }
        if (loadingPercent) loadingPercent.textContent = `%${progress} Tamamlandı`;
    }

    async function pollStatus() {
        if (finished) return;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(`/api/task_status/${encodeURIComponent(postCode)}`, {
                cache: 'no-store', signal: controller.signal,
            });
            if (response.status === 401) {
                finished = true;
                window.location.assign('/admin/login');
                return;
            }
            if (!response.ok) throw new Error('Status request failed');
            const data = await response.json();
            retryDelay = 1000;
            if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
                finished = true;
                if (data.status === 'completed') {
                    showProgress(100);
                    if (loadingMsg) loadingMsg.textContent = 'Denetim tamamlandı, sonuçlar açılıyor...';
                }
                window.location.reload();
                return;
            }
            if (data.status === 'not_found') {
                finished = true;
                if (loadingMsg) loadingMsg.textContent = 'Denetim bulunamadı. Ana sayfadan yeniden başlatın.';
                return;
            }
            showProgress(data.progress);
            if (loadingMsg && data.message) loadingMsg.textContent = data.message;
        } catch (error) {
            retryDelay = Math.min(retryDelay * 2, 5000);
            if (loadingMsg) loadingMsg.textContent = 'Sunucu yanıtı bekleniyor, tekrar bağlanılıyor...';
        } finally {
            clearTimeout(timeout);
        }
        if (!finished) setTimeout(pollStatus, retryDelay);
    }
    pollStatus();
}
