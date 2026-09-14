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
        const dialog=document.createElement('dialog');dialog.className='member-dialog control-scope-dialog';
        dialog.setAttribute('aria-labelledby','control-scope-title');
        dialog.setAttribute('aria-describedby','control-scope-description');
        dialog.innerHTML='<div class="scope-heading"><span class="scope-icon"><i class="fas fa-shield-halved" aria-hidden="true"></i></span><div><span class="scope-eyebrow">DENETİME HAZIR</span><h2 id="control-scope-title">Kontrol kapsamı</h2></div><button type="button" class="scope-close" aria-label="Kapat">×</button></div><p id="control-scope-description" class="scope-description">Başlamadan önce kontrol edilecek bilgileri gözden geçir.</p><div class="scope-stats"><div><i class="fas fa-link" aria-hidden="true"></i><strong data-scope-posts></strong><span>Paylaşım</span></div><div><i class="fas fa-users" aria-hidden="true"></i><strong data-scope-members></strong><span>Üye</span></div><div><i class="fas fa-comment" data-scope-type-icon aria-hidden="true"></i><strong data-scope-type></strong><span>Kontrol türü</span></div></div><p class="scope-note"><i class="fas fa-sliders" aria-hidden="true"></i><span>Gruba özel kayıtlı kurallar bu kontrolde de uygulanır.</span></p><div class="scope-actions"><button type="button" class="scope-edit"><i class="fas fa-pen" aria-hidden="true"></i> Düzenle</button><button type="button" class="scope-start">Kontrolü başlat <i class="fas fa-arrow-right" aria-hidden="true"></i></button></div>';
        dialog.querySelector('[data-scope-posts]').textContent=links.length;
        dialog.querySelector('[data-scope-members]').textContent=members.length;
        const likes=data.get('check_likes')==='on';
        dialog.querySelector('[data-scope-type]').textContent=likes?'Beğeni':'Yorum';
        dialog.querySelector('[data-scope-type-icon]').className=likes?'fas fa-heart':'fas fa-comment';
        const previousFocus=document.activeElement;
        document.body.append(dialog);
        return new Promise(resolve=>{
            const finish=value=>{dialog.close();dialog.remove();previousFocus?.focus();resolve(value);};
            dialog.querySelector('.scope-start').onclick=()=>finish(true);
            dialog.querySelector('.scope-edit').onclick=()=>finish(false);
            dialog.querySelector('.scope-close').onclick=()=>finish(false);
            dialog.oncancel=event=>{event.preventDefault();finish(false);};
            dialog.showModal();dialog.querySelector('.scope-edit').focus();
        });
    };
})();
