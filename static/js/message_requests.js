(() => {
 if(!window.postCode || !window.resultThreadId || !/^[a-f0-9]{32}$/.test(window.postCode))return;
 const root=document.createElement('section');root.className='request-report';root.id='requestReport';
 root.innerHTML='<header><div><h2>Üyelerin paylaşım talepleri</h2><p>Mesajlar ayrı analiz edilir. Kontrol sonuçların hazır; talepler otomatik muafiyet oluşturmaz.</p></div><button type="button" data-request-retry hidden>Tekrar dene</button></header><p role="status" data-request-status>Grup mesajları inceleniyor…</p><div data-request-rows></div>';
 document.querySelector('.result-card')?.append(root);
 const status=root.querySelector('[data-request-status]'),rows=root.querySelector('[data-request-rows]'),retry=root.querySelector('[data-request-retry]');
 const api='/api/message-requests/'+window.postCode;let timer;
 function node(tag,text){const n=document.createElement(tag);n.textContent=text;return n;}
 function render(data){
  rows.replaceChildren();retry.hidden=true;
  if(data.state==='complete'){
   status.textContent=data.requests.length?'Talep adaylarını orijinal mesajlarıyla birlikte inceleyebilirsin.':'İncelenen mesajlarda açık bir paylaşım talebi bulunmadı.';
   if(data.scope) status.textContent+=' İncelenen tarihler: '+data.scope.start+' — '+data.scope.end+(data.scope.fallback?' (Paylaşım tarihi kayıtlı olmadığından kontrol günü tarandı.)':'');
   for(const entry of data.requests){
    const card=node('article','');card.append(node('h3','@'+entry.username),node('p',entry.summary),node('blockquote',entry.text));
    card.append(node('small',new Date(entry.time).toLocaleString('tr-TR')+' · '+(entry.association==='reply'?'Paylaşıma doğrudan yanıt':'Sonraki mesaj · paylaşım ilişkisini kontrol et')));
    for(const url of entry.urls){const line=node('div','');line.className='request-post';const link=node('a',url);link.href=url;link.target='_blank';link.rel='noopener noreferrer';line.append(link);
     if(entry.kind==='likes_only' && !data.check_likes){
      const button=node('button',entry.approved_url===url?'Bu raporda yorum muafiyeti uygulandı':'Bu paylaşımı yorumdan muaf tut');button.type='button';button.disabled=!!entry.approved_url;
      button.onclick=async()=>{if(button.dataset.confirm!=='yes'){button.dataset.confirm='yes';button.textContent='Mesaj bu paylaşıma ait: muafiyeti onayla';return;}button.disabled=true;try{const r=await fetch(api+'/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:entry.id,url})});const d=await r.json();if(!r.ok)throw Error(d.error||'Muafiyet uygulanamadı.');location.reload();}catch(e){status.textContent=e.message;button.disabled=false;}};
      line.append(button);
     }card.append(line);
    }rows.append(card);
   }return;
  }
  if(data.state==='running'){status.textContent='Grup mesajları inceleniyor… Kontrol sonuçlarını kullanmaya devam edebilirsin.';timer=setTimeout(()=>load('GET'),2500);return;}
  if(data.state==='idle'){load('POST');return;}
  status.textContent=data.error||'Mesaj analizi tamamlanamadı. Kontrol sonuçların korunuyor.';retry.hidden=false;
 }
 async function load(method){clearTimeout(timer);retry.hidden=true;try{const r=await fetch(api,{method,cache:'no-store'});const data=await r.json();if(!r.ok&&r.status!==409)throw Error('Bu raporun grup mesajları şu anda analiz edilemiyor.');render(data);}catch(e){status.textContent=e.message;retry.hidden=false;}}
 retry.onclick=()=>load('POST');load('GET');
})();
