/* Saved evidence audits use independent requests; no comments/likes are submitted. */
(() => {
  const root = document.getElementById('saveControl');
  if (!root) return;
  const feedback = document.getElementById('saveFeedback');
  const run = root.dataset.run;
  document.getElementById('saveCopyMissing')?.addEventListener('click',async event=>{
    const button=event.currentTarget, feedback=document.getElementById('saveCopyFeedback');
    const fallback=document.getElementById('saveCopyFallback');
    button.disabled=true;fallback.hidden=true;feedback.textContent='Güncel muafiyetlerle liste hazırlanıyor…';
    try {
      const response=await fetch('/api/save-control/'+run+'/missing-list',{cache:'no-store'});
      const data=await response.json();
      if(!response.ok)throw new Error(data.error||'Liste alınamadı.');
      if(!data.count){feedback.textContent='Kopyalanacak eksik veya kanıt bekleyen üye yok.';return;}
      try{await navigator.clipboard.writeText(data.text);feedback.textContent=data.count+' kullanıcı alt alta kopyalandı.';}
      catch(_){fallback.value=data.text;fallback.hidden=false;fallback.focus();fallback.select();feedback.textContent='Otomatik kopyalama kullanılamıyor. Seçili listeyi kopyalayabilirsin.';}
    }catch(e){feedback.textContent=e.message;}finally{button.disabled=false;}
  });
  const say = text => { feedback.textContent = text; };
  async function post(url, data = {}) {
    const response = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'İşlem tamamlanamadı. Yeniden deneyin.');
    return result;
  }
  const form = document.getElementById('saveStart');
  if (form) {
    const select = document.getElementById('saveGroup');
    const day = document.getElementById('saveDay');
    const queryDay = new URLSearchParams(location.search).get('day');
    if (/^\d{4}-\d{2}-\d{2}$/.test(queryDay || '')) day.value = queryDay;
    fetch('/api/get_groups').then(r=>r.json()).then(data=>{
      if (!data.ok) throw new Error('Gruplar alınamadı. Sayfayı yenileyerek tekrar deneyin.');
      select.replaceChildren(new Option('Instagram grubu seç', ''));
      for (const g of data.groups || data.threads || []) {
        select.add(new Option(g.thread_title || g.name || g.title || g.thread_id, g.thread_id || g.id));
      }
      select.value = form.dataset.group;
      select.dispatchEvent(new Event('change', {bubbles:true}));
    }).catch(e=>say(e.message));
    document.querySelectorAll('[data-date]').forEach(button=>button.addEventListener('click',()=>{
      const today = new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Istanbul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
      const date = new Date(today+'T12:00:00Z');
      if (button.dataset.date === 'yesterday') date.setUTCDate(date.getUTCDate()-1);
      day.value = date.toISOString().slice(0,10);
    }));
    form.addEventListener('submit', async event=>{
      event.preventDefault();
      const button = form.querySelector('[type=submit]'); button.disabled=true;
      say('Paylaşımlar ve ertesi güne uzanan ekran görüntüleri toplanıyor…');
      try { const data=await post('/api/save-control',{group:select.value,day:day.value}); location.assign(data.url); }
      catch(e){say(e.message);button.disabled=false;}
    });
  }
  document.querySelector('[data-refresh-day]')?.addEventListener('click',event=>{
    event.currentTarget.href += '&day='+encodeURIComponent(event.currentTarget.dataset.refreshDay);
  });
  document.getElementById('saveAnalyze')?.addEventListener('click',async event=>{
    const button=event.currentTarget;
    button.disabled=true;
    try {
      if(button.dataset.complete==='true'){
        await post('/api/save-control/'+run+'/reanalyze');
        button.dataset.complete='false';
      }
      while(true){
        say('Görseller karşılaştırılıyor. Tamamlanan adımlar kaydedilir; sayfa kapansa da devam edebilirsin.');
        const result=await post('/api/save-control/'+run+'/step');
        if(result.done){location.replace(location.pathname+'?results='+Date.now()+'#saveResults');break;}
        say(`${result.current}/${result.total} analiz adımı tamamlandı.`);
      }
    } catch(e){say(e.message);event.target.disabled=false;}
  });
  document.querySelectorAll('[data-review]').forEach(button=>button.addEventListener('click',async()=>{
    button.disabled=true;
    try{await post('/api/save-control/'+run+'/review',{member:button.dataset.member,ref:button.dataset.ref,state:button.dataset.review});location.reload();}
    catch(e){say(e.message);button.disabled=false;}
  }));
})();
