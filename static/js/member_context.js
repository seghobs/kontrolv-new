(() => {
 const menu=document.createElement('dialog');menu.className='member-dialog member-context';
 menu.innerHTML='<header><strong></strong><button type="button" data-close aria-label="Kapat">×</button></header><div class="member-context-actions"><button type="button" data-action="analysis">Üyenin eksiklerini kontrol et</button><button type="button" data-action="post">Bu üyenin paylaşımını kontrol et</button><button type="button" data-action="delete">Bu üyeyi sil</button></div><p role="status"></p><div class="member-context-posts"></div>';
 document.body.append(menu);let name='',index=-1;
 const say=text=>menu.querySelector('[role=status]').textContent=text;
 menu.querySelector('[data-close]').onclick=()=>menu.close();
 menu.addEventListener('click',e=>{if(e.target===menu){const r=menu.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)menu.close();}});
 window.openMemberContext=(user,userIndex)=>{name=user;index=userIndex;menu.querySelector('strong').textContent='@'+user;say('');menu.querySelector('.member-context-posts').replaceChildren();menu.showModal();};
 menu.querySelector('[data-action=delete]').onclick=e=>{removeUserTag(e,index);menu.close();};
 menu.querySelector('[data-action=analysis]').onclick=()=>{
  const group=document.getElementById('groupSelect').value;
  if(!group){say('Önce bir Instagram grubu seçin.');return;}
  let date=document.getElementById('dateFilter').value;
  if(!/^\d{4}-\d{2}-\d{2}$/.test(date)){
   const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Istanbul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
   const d=new Date(today+'T12:00:00Z');if(date==='yesterday')d.setUTCDate(d.getUTCDate()-1);date=d.toISOString().slice(0,10);
  }
  menu.close();window.openDailyMemberAnalysis(name,group,date);
 };
 menu.querySelector('[data-action=post]').onclick=()=>{
  if(window.isPostsLoading){say('Paylaşımlar yükleniyor; tamamlanınca tekrar deneyin.');return;}
  if(!document.getElementById('groupSelect').value){say('Önce bir Instagram grubu seçin.');return;}
  const normalize=s=>(s||'').replace(/^@/,'').trim().toLowerCase();
  const allowed=new Set([...document.getElementById('postSelect').options].map(o=>o.value));
  const posts=(window.allFetchedPosts||[]).filter(p=>normalize(p.username)===normalize(name)&&allowed.has(p.url));
  const list=menu.querySelector('.member-context-posts');list.replaceChildren();
  if(!posts.length){say('Seçilen tarih ve filtrelerde bu üyeye ait paylaşım bulunamadı.');return;}
  say('Kontrol edilecek paylaşımı seçin.');
  for(const post of posts){const button=document.createElement('button');button.type='button';button.textContent=post.date?name+' · '+post.date:post.url;button.onclick=()=>{setCheckMode('single');selectPostInUI(post.url);menu.close();document.getElementById('submitCheckBtn').click();};list.append(button);}
 };
})();
