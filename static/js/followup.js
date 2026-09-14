(() => {
    const feedback = text => { const el=document.getElementById('followup-feedback'); if(el) el.textContent=text; };
    async function json(url, body) {
        const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        let data;
        try{data=await response.json();}catch{throw new Error('Sunucudan geçerli yanıt alınamadı. Biraz sonra tekrar dene.');}
        if(!data || typeof data!=='object')throw new Error('Sunucudan geçerli yanıt alınamadı.');
        if(!response.ok || data.success===false) throw new Error(data.error || data.message || 'İşlem tamamlanamadı.');
        return data;
    }
    document.querySelectorAll('[data-timestamp]').forEach(el=>{
        const value=Number(el.dataset.timestamp);
        if(value>0) el.textContent=new Date(value*1000).toLocaleString('tr-TR');
    });
    document.querySelectorAll('[data-recheck]').forEach(button=>button.addEventListener('click',async()=>{
        button.disabled=true;
        try { const data=await json('/api/recheck/'+button.dataset.recheck,{only_missing:button.dataset.mode==='missing',unknown_only:button.dataset.mode==='unknown'}); location.assign(data.result_url); }
        catch(error){feedback(error.message);button.disabled=false;}
    }));
    document.querySelector('[data-filter]')?.addEventListener('change',event=>{
        document.querySelectorAll('.followup-post').forEach(post=>post.hidden=event.target.value!=='all'&&post.dataset.state!==event.target.value);
        const empty=document.querySelector('[data-filter-empty]');if(empty)empty.hidden=[...document.querySelectorAll('.followup-post')].some(post=>!post.hidden);
    });
    document.querySelector('[data-sort]')?.addEventListener('change',event=>{
        const parent=document.querySelector('[data-posts]');
        const keys={missing:'missing',oldest:'time',original:'order'},key=keys[event.target.value];
        [...parent.children].sort((a,b)=>(Number(a.dataset[key])-Number(b.dataset[key]))*(key==='missing'?-1:1)).forEach(row=>parent.append(row));
    });
    document.querySelector('[data-compact]')?.addEventListener('change',event=>document.body.classList.toggle('compact',event.target.checked));
    document.querySelectorAll('[data-copy-post]').forEach(button=>button.addEventListener('click',async()=>{
        const users=button.dataset.users.split(' ').filter(Boolean).map(u=>'@'+u).join(', '),format=document.querySelector('[data-copy-format]').value;
        const text=format==='users'?users:format==='links'?button.dataset.url:`${users}\nBu paylaşımda ${button.dataset.kind} kaydınız bulunamadı. Kontrol edebilir misiniz?\n${button.dataset.url}`;
        if(!users){feedback('Bu paylaşımda doğrulanmış eksik bulunmuyor.');return;}
        try {await navigator.clipboard.writeText(text);feedback('Kopyalandı.');}
        catch{const field=document.createElement('textarea');field.value=text;button.after(field);field.focus();field.select();feedback('Otomatik kopyalanamadı. Seçili metni kopyalayabilirsiniz.');}
    }));
    document.querySelectorAll('[data-copy-user]').forEach(button=>button.addEventListener('click',async()=>{
        const text='@'+button.dataset.copyUser+'\nAşağıdaki paylaşımlarda '+button.dataset.kind+' kaydınız bulunamadı. Kontrol edebilir misiniz?\n'+button.dataset.links.split(' ').join('\n');
        try{await navigator.clipboard.writeText(text);feedback('Üyeye özel hatırlatma kopyalandı.');}
        catch{const field=document.createElement('textarea');field.value=text;button.after(field);field.select();feedback('Seçili hatırlatma metnini kopyalayabilirsiniz.');}
    }));
    document.querySelector('[data-batch]')?.addEventListener('submit',async event=>{
        event.preventDefault();const form=event.target;
        if(form.dataset.busy==='true')return;
        const button=form.querySelector('[data-batch-submit]'),data=new FormData(form),users=data.getAll('member');
        if(!users.length){feedback('En az bir üye seçin.');return;}
        form.dataset.busy='true';form.setAttribute('aria-busy','true');button.disabled=true;
        try {
            for(const username of users){
                const task=await json('/api/member_analysis/'+form.dataset.batch,{username,date:data.get('date'),end_date:data.get('end_date'),skip_owner:data.has('skip_owner')});
                const item=document.createElement('li'),link=document.createElement('a');link.href=task.result_url;link.textContent='@'+username+' — analiz kaydı';item.append(link);form.querySelector('[data-batch-results]').append(item);
                feedback('@'+username+' kontrol ediliyor…');
                const result=await json('/api/task_run/'+task.job_id,{});
                link.textContent='@'+username+' — '+(result.status==='completed'?'Tamamlandı':'Sonucu kontrol edin');
                if(result.status!=='completed'){feedback('Analiz tamamlanmadı; ilgili kayıttan devam edebilirsiniz.');return;}
            }
            feedback('Seçilen üyelerin analizleri tamamlandı. Sonuçları bağlantılardan açabilirsiniz.');
        }catch(error){feedback(error.message);}
        finally{button.disabled=false;delete form.dataset.busy;form.removeAttribute('aria-busy');}
    });
})();
