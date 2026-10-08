(() => {
 document.addEventListener('click', async event => {
  const trigger=event.target.closest('[data-change-group]');if(!trigger||changingCheckedPost)return;
  const dialog=document.createElement('dialog');dialog.className='result-group-dialog';
  dialog.innerHTML=`<header><strong>Grubu Değiştir</strong><button type="button" data-close aria-label="Kapat">×</button></header><p>Grubu, tarihi ve kontrol edeceğiniz paylaşımı seçin.</p><label>Instagram grubu<select data-group><option value="">Gruplar yükleniyor…</option></select></label><label>Gruba gönderildiği tarih<input type="date" data-date></label><label>Kontrol türü<select data-mode><option value="comments">Yorum</option><option value="likes">Beğeni</option><option value="" hidden>Kontrol türü seçin</option></select></label><small data-preferences></small><label>Paylaşım<select data-post><option value="">Önce grup seçin</option></select></label><p class="group-change-status" role="status" data-status></p><footer><button type="button" data-start disabled>Kontrol Et</button></footer>`;
  document.body.appendChild(dialog);dialog.showModal();
  const group=dialog.querySelector('[data-group]'),date=dialog.querySelector('[data-date]'),mode=dialog.querySelector('[data-mode]'),post=dialog.querySelector('[data-post]'),start=dialog.querySelector('[data-start]'),status=dialog.querySelector('[data-status]'),preferences=dialog.querySelector('[data-preferences]');
  date.value=document.getElementById('resultPostDate')?.value||getIstanbulDateStr();
  let revision=0,loaded=null;
  const close=()=>dialog.close();dialog.querySelector('[data-close]').onclick=close;
  dialog.addEventListener('close',()=>{++revision;dialog.remove();trigger.focus()});
  async function api(url){const r=await fetch(url,{cache:'no-store'});const data=await r.json();if(!r.ok||!data.ok)throw new Error('Grup bilgileri alınamadı. Yeniden seçim yaparak deneyebilirsiniz.');return data;}
  function renderPosts(){
   post.replaceChildren(new Option('-- Paylaşım Seç --',''));
   const rows=(loaded?.posts||[]).filter(p=>mode.value==='likes'?(loaded.lowLikes?p.like_count<=90:true):p.comments_disabled!==true);
   for(const p of rows)post.add(new Option('@'+(p.username||'Bilinmiyor')+' · '+(p.date||''),p.url));
   if(!rows.length)post.replaceChildren(new Option('Bu tarih ve kontrol türünde paylaşım yok',''));
   start.disabled=true;
  }
  async function load(changedGroup){
   const version=++revision;loaded=null;start.disabled=true;post.replaceChildren(new Option('Yükleniyor…',''));status.textContent='Grup üyeleri ve paylaşımlar alınıyor…';preferences.textContent='';
   if(!group.value||!date.value){status.textContent='Grup ve tarih seçin.';return;}
   const tid=group.value;
   try{
    const prefs=await api('/api/group_control_preferences/'+encodeURIComponent(tid));
    if(version!==revision||!dialog.isConnected)return;
    if(changedGroup){if(prefs.selected_date)date.value=prefs.selected_date;mode.value=prefs.control_mode==='saves'?'':prefs.control_mode;}
    const day=date.value;
    const [members,posts]=await Promise.all([api('/api/get_group_members/'+encodeURIComponent(tid)),api('/api/get_group_posts/'+encodeURIComponent(tid)+'?date='+encodeURIComponent(day))]);
    if(version!==revision||!dialog.isConnected)return;
    const names=members.usernames||(members.members||[]).map(m=>m.username).filter(Boolean);
    const sharers=new Set(Object.entries(posts.member_share_counts||{}).filter(([name,c])=>c.post+c.reels>0).map(([name])=>name.toLowerCase()));
    if(!posts.member_share_counts)(posts.posts||[]).forEach(p=>sharers.add((p.username||'').toLowerCase()));
    loaded={threadId:tid,date:day,members:prefs.preferences.only_sharers?names.filter(n=>sharers.has(n.toLowerCase())):names,posts:posts.posts||[],lowLikes:prefs.preferences.low_likes};
    preferences.textContent=(prefs.preferences.only_sharers?'Yalnız paylaşım gönderen üyeler':'Tüm grup üyeleri')+' · '+loaded.members.length+' üye'+(loaded.lowLikes?' · 90 ve altı beğeni filtresi':'');
    status.textContent=prefs.control_mode==='saves'&&!mode.value?'Bu grubun kayıtlı türü Kaydet. Bu raporda devam etmek için Yorum veya Beğeni seçin.':'';
    renderPosts();
   }catch(error){if(version===revision){status.textContent=error.message;post.replaceChildren(new Option('Paylaşımlar yüklenemedi',''));}}
  }
  group.onchange=()=>load(true);date.onchange=()=>load(false);mode.onchange=()=>{renderPosts();status.textContent='';};post.onchange=()=>{start.disabled=!loaded||!post.value||!mode.value||!loaded.members.length;};
  start.onclick=()=>{
   if(start.disabled||!loaded)return;
   const selected=loaded.posts.find(p=>p.url===post.value);if(!selected)return;
   const context={threadId:loaded.threadId,members:loaded.members,mode:mode.value,lowLikes:loaded.lowLikes,sender:selected.username||''};
   const day=loaded.date,url=selected.url;dialog.close();void changeCheckedPost(url,day,context);
  };
  try{const data=await api('/api/get_groups');if(!dialog.isConnected)return;group.replaceChildren(new Option('-- Grup Seç --',''));for(const g of data.groups||[]){const option=new Option(g.name+(g.member_count!=null?' ('+g.member_count+' üye)':''),String(g.id));if(g.group_pic_url)option.dataset.image=g.group_pic_url;group.add(option);}group.value=window.resultThreadId||'';if(group.value)await load(true);else status.textContent='Bir grup seçin.';}
  catch(error){status.textContent=error.message;group.replaceChildren(new Option('Gruplar yüklenemedi',''));}
 });
})();
