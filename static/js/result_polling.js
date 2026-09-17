// Keep the status message current and open results as soon as the server finishes.
function startResultPolling(postCode, onMissing, onFinished) {
    const loadingMsg = document.getElementById('loading-message');
    let finished = false;
    let retryDelay = 1000;

    async function pollStatus() {
        if (finished) return;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(`/api/task_status/${encodeURIComponent(postCode)}`, {
                cache: 'no-store', signal: controller.signal,
            });
            if (!response.ok) throw new Error('Status request failed');
            const data = await response.json();
            retryDelay = 1000;
            if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
                finished = true;
                if (data.status === 'completed') {
                    if (loadingMsg) loadingMsg.textContent = 'Denetim tamamlandı, sonuçlar açılıyor...';
                }
                if (onFinished) onFinished();
                window.location.assign('/result/' + encodeURIComponent(postCode));
                return;
            }
            if (data.status === 'not_found') {
                finished = true;
                if (loadingMsg) loadingMsg.textContent = 'Denetim bulunamadı. Yeniden başlatabilirsiniz.';
                if (onMissing) onMissing();
                return;
            }
            if (loadingMsg && data.message) loadingMsg.textContent = data.message;
            if (data.execute_in_request && data.status === 'running') {
                if (loadingMsg) loadingMsg.textContent = 'Denetim çalıştırılıyor…';
                const runController = new AbortController();
                const runTimeout = setTimeout(() => runController.abort(), 165000);
                try {
                    const run = await fetch(`/api/task_run/${encodeURIComponent(postCode)}`, {
                        method: 'POST', signal: runController.signal,
                        headers: {'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''},
                    });
                    if (!run.ok) throw new Error('Denetim başlatılamadı.');
                    const outcome = await run.json();
                    if (['completed', 'failed', 'cancelled'].includes(outcome.status)) {
                        finished = true;
                        if (onFinished) onFinished();
                        window.location.assign('/result/' + encodeURIComponent(postCode));
                        return;
                    }
                } finally { clearTimeout(runTimeout); }
            }
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
