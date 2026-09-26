(() => {
  const panel = document.getElementById('geminiSettings');
  const input = document.getElementById('geminiApiKey');
  const reveal = document.getElementById('geminiReveal');
  const save = document.getElementById('geminiSave');
  const reload = document.getElementById('geminiReload');
  const feedback = document.getElementById('geminiFeedback');
  let loaded = false;
  let busy = false;
  function hide() {input.type='password';reveal.setAttribute('aria-pressed','false');reveal.querySelector('span').textContent='Göster';}
  function lock(value) {busy=value;input.disabled=value||!loaded;reveal.disabled=value||!loaded;save.disabled=value||!loaded;reload.disabled=value;}
  async function fetchKey() {
    if (busy) return;
    lock(true);hide();feedback.textContent='Kayıtlı anahtar yükleniyor…';
    try {
      const response=await fetch('/admin/gemini_settings',{cache:'no-store'});
      const data=await response.json();
      if(!response.ok||!data.success) throw new Error(data.message||'Anahtar alınamadı. Admin oturumunu kontrol edin.');
      input.value=data.api_key||'';input.placeholder='Gemini API anahtarını gir';loaded=true;
      feedback.textContent=data.configured?'Kayıtlı anahtar yüklendi. Görmek için Göster düğmesine basabilirsin.':'Henüz API anahtarı kayıtlı değil.';
    } catch(e){feedback.textContent=e.message;} finally {lock(false);}
  }
  panel.addEventListener('toggle',()=>{if(panel.open&&!loaded) fetchKey();if(!panel.open) hide();});
  reload.addEventListener('click',fetchKey);
  reveal.addEventListener('click',()=>{const showing=input.type==='password';input.type=showing?'text':'password';reveal.setAttribute('aria-pressed',String(showing));reveal.querySelector('span').textContent=showing?'Gizle':'Göster';});
  document.getElementById('geminiSettingsForm').addEventListener('submit',async event=>{
    event.preventDefault();if(busy)return;
    const key=input.value.trim();
    if(!key){feedback.textContent='Boş anahtar kaydedilmez; mevcut anahtar korunur.';return;}
    lock(true);hide();feedback.textContent='Kaydediliyor…';
    try{
      const response=await fetch('/admin/gemini_settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_key:key})});
      const data=await response.json();
      if(!response.ok||!data.success)throw new Error(data.message||'Anahtar kaydedilemedi.');
      input.value=key;feedback.textContent=data.message;
    }catch(e){feedback.textContent=e.message;}finally{lock(false);}
  });
})();
