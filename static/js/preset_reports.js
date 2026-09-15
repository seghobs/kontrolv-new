(() => {
 document.querySelectorAll('[data-report-copy]').forEach(button=>button.addEventListener('click',async()=>{
  const data=JSON.parse(document.getElementById('report-copy-data').textContent);
  const text=data[button.dataset.reportCopy],original=button.textContent;
  try{await navigator.clipboard.writeText(text);button.textContent='Kopyalandı';}catch{button.textContent='Kopyalanamadı, tekrar deneyin';}
  setTimeout(()=>button.textContent=original,1800);
 }));
 const istanbulToday=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Istanbul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
 const parse=v=>new Date(v+'T12:00:00');
 function chooseDate(trigger, action) {
  const dialog=document.createElement('dialog');dialog.className='preset-dialog';
  dialog.innerHTML=`<span class="preset-kicker">DENETİM TARİHİ</span><h2></h2><p></p><div class="preset-date-presets"><button type="button" data-day="yesterday">Dün</button><button type="button" data-day="today">Bugün</button><button type="button" data-day="custom">Tarih seç</button></div><strong class="preset-date-value"></strong><section class="preset-calendar" hidden><div class="preset-calendar-head"><button type="button" data-month="-1" aria-label="Önceki ay">‹</button><strong></strong><button type="button" data-month="1" aria-label="Sonraki ay">›</button></div><div class="preset-calendar-grid"></div></section><p data-feedback role="status"></p><div class="preset-actions"><button type="button" data-close>Vazgeç</button><button type="button" class="preset-primary" data-submit>Kontrolü başlat</button></div>`;
  dialog.querySelector('h2').textContent=trigger.dataset.presetName || 'Yeni paylaşımları ekle';
  dialog.querySelector('p').textContent=action==='extend'?'Seçtiğin günün yeni paylaşımları eklenir. Önceki üyeler ve kontrol sonuçları korunur.':'Gruba paylaşım yapılan günü seç. Güncel yorum ve beğeniler kontrol edilir.';
  let selected=istanbulToday(), month=parse(selected),busy=false;
  const calendar=dialog.querySelector('.preset-calendar');
  function render(){
   dialog.querySelector('.preset-date-value').textContent=parse(selected).toLocaleDateString('tr-TR',{day:'numeric',month:'long',year:'numeric'});
   dialog.querySelector('.preset-calendar-head strong').textContent=month.toLocaleDateString('tr-TR',{month:'long',year:'numeric'});
   const grid=dialog.querySelector('.preset-calendar-grid');grid.replaceChildren();
   ['Pt','Sa','Ça','Pe','Cu','Ct','Pa'].forEach(day=>{const e=document.createElement('small');e.textContent=day;grid.append(e)});
   const first=new Date(month.getFullYear(),month.getMonth(),1), offset=(first.getDay()+6)%7;
   for(let i=0;i<offset;i++)grid.append(document.createElement('span'));
   for(let day=1;day<=new Date(month.getFullYear(),month.getMonth()+1,0).getDate();day++){
    const value=iso(new Date(month.getFullYear(),month.getMonth(),day)),button=document.createElement('button');button.type='button';button.textContent=day;button.dataset.date=value;button.disabled=value>istanbulToday();button.setAttribute('aria-pressed',String(value===selected));button.addEventListener('click',()=>{selected=value;render()});grid.append(button);
   }
  }
  dialog.querySelectorAll('[data-day]').forEach(button=>button.addEventListener('click',()=>{if(button.dataset.day==='custom'){calendar.hidden=false;}else{const day=parse(istanbulToday());if(button.dataset.day==='yesterday')day.setDate(day.getDate()-1);selected=iso(day);month=day;calendar.hidden=true;}render()}));
  dialog.querySelectorAll('[data-month]').forEach(button=>button.addEventListener('click',()=>{month=new Date(month.getFullYear(),month.getMonth()+Number(button.dataset.month),1);render()}));
  dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{dialog.remove();trigger.focus()});
  dialog.querySelector('[data-submit]').onclick=async()=>{
   if(busy)return;busy=true;dialog.querySelector('[data-submit]').disabled=true;
   try{
    if(action==='start'){
     const form=document.createElement('form');form.method='post';form.action=trigger.dataset.presetStart;
     const input=document.createElement('input');input.name='date';input.value=selected;form.append(input);document.body.append(form);form.submit();return;
    }
    const response=await fetch(trigger.dataset.extend,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({date:selected})});const data=await response.json();
    if(!response.ok||!data.success)throw Error(data.message||'Yeni paylaşımlar alınamadı.');
    const match=/^\/result\/([a-f0-9]{32})$/.exec(data.result_url);if(!match)throw Error('Sonuç bağlantısı alınamadı.');
    const pending=new URL(location.href);pending.searchParams.set('recheck',match[1]);history.replaceState(null,'',pending);dialog.close();startResultPolling(match[1]);
   }catch(error){dialog.querySelector('[data-feedback]').textContent=error.message;busy=false;dialog.querySelector('[data-submit]').disabled=false;}
  };
  document.body.append(dialog);render();dialog.showModal();
 }
 document.querySelectorAll('[data-preset-start]').forEach(button=>button.addEventListener('click',()=>chooseDate(button,'start')));
 document.querySelectorAll('[data-extend]').forEach(button=>button.addEventListener('click',()=>chooseDate(button,'extend')));
 const search=document.querySelector('[data-matrix-search]'),missing=document.querySelector('[data-matrix-missing]');
 function filter(){let visible=0;document.querySelectorAll('[data-matrix-user]').forEach(row=>{row.hidden=!row.dataset.matrixUser.toLowerCase().includes(search.value.trim().replace(/^@/,'').toLowerCase())||(missing.checked&&row.dataset.hasMissing!=='yes');if(!row.hidden)visible++});const empty=document.querySelector('[data-matrix-empty]');if(empty)empty.hidden=visible>0;}
 search?.addEventListener('input',filter);missing?.addEventListener('change',filter);
 document.querySelectorAll('[data-matrix-time]').forEach(el=>{const date=new Date(Number(el.dataset.matrixTime)*1000);if(!isNaN(date))el.textContent=date.toLocaleString('tr-TR',{timeZone:'Europe/Istanbul'})});
})();
