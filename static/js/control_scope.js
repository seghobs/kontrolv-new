(() => {
    const form=document.getElementById('checkForm');if(!form)return;
    const section=document.createElement('details');section.className='control-utility control-extractor';
    section.innerHTML='<summary><span class="control-utility-icon"><i class="fas fa-link" aria-hidden="true"></i></span><span class="control-utility-copy"><strong>Mesajdan bağlantı ekle</strong><small>Paylaşım bağlantılarını tek seferde ayıkla</small></span><i class="fas fa-chevron-down control-utility-arrow" aria-hidden="true"></i></summary><div class="control-extractor-body"><label for="control-pasted-message">Bağlantıları içeren mesaj</label><textarea id="control-pasted-message" class="form-control" data-pasted-message placeholder="Bağlantıları içeren mesajı buraya yapıştırın"></textarea><button type="button" class="btn btn-secondary" data-extract>Bağlantıları forma aktar</button><p data-extract-status role="status"></p></div>';
    form.prepend(section);
    section.querySelector('[data-extract]').onclick=()=>{
        const text=section.querySelector('textarea').value;
        const matches=[...text.matchAll(/https?:\/\/(?:www\.)?instagram\.com\/(?:p|reels?|tv)\/([\w-]+)/g)];
        const urls=[...new Set(matches.map(m=>'https://www.instagram.com/p/'+m[1]+'/'))];
        if(urls.length && window.setCheckMode) window.setCheckMode(urls.length>1?'multi':'single');
        const field=document.getElementById(urls.length>1?'post_link_multi':'post_link_single');
        if(field&&urls.length){field.value=urls.join('\n');field.dispatchEvent(new Event('input',{bubbles:true}));}
        section.querySelector('[data-extract-status]').textContent=urls.length+' paylaşım ayıklandı. '+(matches.length-urls.length)+' tekrar kaldırıldı.';
    };
    try{const last=localStorage.getItem('last-control');if(last&&/^[a-f0-9]{32}$/.test(last)){const link=document.createElement('a');link.href='/result/'+last;link.className='control-utility control-resume';link.innerHTML='<span class="control-utility-icon"><i class="fas fa-clock-rotate-left" aria-hidden="true"></i></span><span class="control-utility-copy"><strong>Son denetime geri dön</strong><small>Kaldığın raporu tekrar aç</small></span><i class="fas fa-arrow-right control-utility-arrow" aria-hidden="true"></i>';form.prepend(link);}}catch{}
    window.confirmControlScope=async form=>{
        const data=new FormData(form),links=[...new Set(String(data.get('post_link')||'').split(/\s+/).filter(Boolean))],members=[...new Set(String(data.get('grup_uye')||'').split(/\s+/).filter(Boolean))];
        const dialog=document.createElement('dialog');dialog.className='member-dialog';
        const message=document.createElement('p');message.textContent=links.length+' paylaşım · '+members.length+' üye · '+(data.get('check_likes')==='on'?'Beğeni':'Yorum')+' kontrolü. Gruba özel kayıtlı kurallar da uygulanır.';
        const title=document.createElement('h2');title.textContent='Kontrol kapsamı';
        const yes=document.createElement('button');yes.type='button';yes.textContent='Kontrolü başlat';
        const no=document.createElement('button');no.type='button';no.textContent='Düzenle';
        dialog.append(title,message,no,yes);document.body.append(dialog);
        return new Promise(resolve=>{yes.onclick=()=>{dialog.close();dialog.remove();resolve(true);};no.onclick=()=>{dialog.close();dialog.remove();resolve(false);};dialog.oncancel=()=>{dialog.remove();resolve(false);};dialog.showModal();});
    };
})();
