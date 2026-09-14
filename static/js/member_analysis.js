(() => {
    if (!window.postCode || !window.resultThreadId) return;
    const dialog = document.createElement('dialog');
    dialog.className = 'member-dialog daily-analysis-dialog';
    dialog.setAttribute('aria-labelledby','daily-analysis-title');
    dialog.innerHTML = `<form><header class="daily-heading"><span class="daily-icon"><i class="fas fa-user-check" aria-hidden="true"></i></span><div><span class="daily-eyebrow">ÜYEYE ÖZEL</span><h2 id="daily-analysis-title">Günlük analiz</h2></div><button type="button" class="daily-dismiss" aria-label="Kapat">×</button></header><div class="daily-member"><span class="member-name"></span><span class="daily-mode"><i class="fas fa-comment" aria-hidden="true"></i> Yorum <span>+</span> <i class="fas fa-heart" aria-hidden="true"></i> Beğeni</span></div><div class="daily-presets" aria-label="Hazır tarihler"><button type="button" data-preset="yesterday">Dün</button><button type="button" data-preset="today">Bugün</button><button type="button" data-preset="custom"><i class="fas fa-calendar-days" aria-hidden="true"></i> Tarih seç</button></div><input type="hidden" name="date"><input type="hidden" name="end_date"><div class="daily-dates"><div><span class="daily-field-label">Başlangıç tarihi</span><button type="button" class="daily-date-button" data-date-field="date" aria-expanded="false"><span></span><i class="fas fa-calendar" aria-hidden="true"></i></button></div><div><span class="daily-field-label">Bitiş tarihi <small>İsteğe bağlı</small></span><button type="button" class="daily-date-button" data-date-field="end_date" aria-expanded="false"><span></span><i class="fas fa-calendar" aria-hidden="true"></i></button></div></div><section class="daily-calendar" hidden aria-label="Tarih takvimi"><div class="daily-calendar-head"><button type="button" data-month-step="-1" aria-label="Önceki ay">‹</button><strong aria-live="polite"></strong><button type="button" data-month-step="1" aria-label="Sonraki ay">›</button></div><div class="daily-weekdays" aria-hidden="true"><span>Pt</span><span>Sa</span><span>Ça</span><span>Pe</span><span>Cu</span><span>Ct</span><span>Pa</span></div><div class="daily-days"></div><div class="daily-calendar-footer"><span></span><button type="button" data-clear-end>Bitişi kaldır</button><button type="button" data-calendar-close>Tamam</button></div></section><p class="daily-date-hint">Paylaşımların gruba gönderildiği tarihi seç.</p><label class="daily-owner"><input type="checkbox" name="skip_owner" checked><span><strong>Kendi paylaşımını hariç tut</strong><small>Üyenin kendi gönderileri analize dahil edilmez.</small></span></label><p class="daily-info"><i class="fas fa-circle-info" aria-hidden="true"></i><span>Seçilen tarihlerdeki gönderi ve Reels’ler kontrol edilir. Yorum ve beğeni eksiklerini ayrı ayrı kopyalayabilirsin.</span></p><p role="alert" class="member-error"></p><div class="member-actions"><button type="button" class="member-close">Vazgeç</button><button type="submit">Analizi başlat <i class="fas fa-arrow-right" aria-hidden="true"></i></button></div></form>`;
    document.body.append(dialog);
    const startDate=dialog.querySelector('[name=date]'), endDate=dialog.querySelector('[name=end_date]');
    const calendar=dialog.querySelector('.daily-calendar');
    let editing='date', month;
    const iso=date=>date.getFullYear()+'-'+String(date.getMonth()+1).padStart(2,'0')+'-'+String(date.getDate()).padStart(2,'0');
    const parse=value=>new Date(value+'T12:00:00');
    const today=()=>{const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Istanbul',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());return ['year','month','day'].map(key=>parts.find(p=>p.type===key).value).join('-');};
    const yesterday=()=>{const d=parse(today());d.setDate(d.getDate()-1);return iso(d);};
    const display=value=>value?parse(value).toLocaleDateString('tr-TR'):'Tek gün';
    function syncDates(){
        dialog.querySelectorAll('[data-date-field]').forEach(button=>{const value=button.dataset.dateField==='date'?startDate.value:endDate.value;button.querySelector('span').textContent=display(value);button.setAttribute('aria-label',(button.dataset.dateField==='date'?'Başlangıç: ':'Bitiş: ')+display(value));});
        const single=!endDate.value||endDate.value===startDate.value;
        dialog.querySelectorAll('[data-preset]').forEach(button=>{const name=button.dataset.preset;const selected=name==='today'?single&&startDate.value===today():name==='yesterday'?single&&startDate.value===yesterday():!single||![today(),yesterday()].includes(startDate.value);button.setAttribute('aria-pressed',String(selected));});
        dialog.querySelector('.member-error').textContent='';
    }
    function closeCalendar(){calendar.hidden=true;dialog.querySelectorAll('[data-date-field]').forEach(b=>b.setAttribute('aria-expanded','false'));}
    function drawCalendar(){
        calendar.querySelector('strong').textContent=month.toLocaleDateString('tr-TR',{month:'long',year:'numeric'});
        calendar.querySelector('.daily-calendar-footer span').textContent=editing==='date'?'Başlangıç gününü seç':'Bitiş gününü seç';
        calendar.querySelector('[data-clear-end]').hidden=editing!=='end_date';
        const grid=calendar.querySelector('.daily-days');grid.replaceChildren();
        const first=new Date(month.getFullYear(),month.getMonth(),1,12), offset=(first.getDay()+6)%7;
        for(let index=0;index<42;index++){
            const date=new Date(month.getFullYear(),month.getMonth(),1-offset+index,12),value=iso(date);
            const day=document.createElement('button');day.type='button';day.textContent=date.getDate();day.dataset.day=value;
            day.classList.toggle('outside',date.getMonth()!==month.getMonth());
            day.classList.toggle('in-range',!!endDate.value&&value>startDate.value&&value<endDate.value);
            day.setAttribute('aria-label',date.toLocaleDateString('tr-TR',{day:'numeric',month:'long',year:'numeric'}));
            day.setAttribute('aria-pressed',String(value===startDate.value||value===endDate.value));
            if(value===today())day.setAttribute('aria-current','date');
            day.disabled=editing==='end_date'&&!!startDate.value&&value<startDate.value;
            day.onclick=()=>{(editing==='date'?startDate:endDate).value=value;if(endDate.value&&endDate.value<startDate.value)endDate.value='';syncDates();closeCalendar();dialog.querySelector('[data-date-field="'+editing+'"]').focus();};
            grid.append(day);
        }
    }
    function openCalendar(field){editing=field;month=parse((field==='date'?startDate.value:endDate.value)||startDate.value||today());month.setDate(1);calendar.hidden=false;dialog.querySelectorAll('[data-date-field]').forEach(b=>b.setAttribute('aria-expanded',String(b.dataset.dateField===field)));drawCalendar();calendar.querySelector('[aria-pressed=true]:not(:disabled)')?.focus();}
    dialog.querySelectorAll('[data-date-field]').forEach(b=>b.onclick=()=>calendar.hidden||editing!==b.dataset.dateField?openCalendar(b.dataset.dateField):closeCalendar());
    dialog.querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>{if(b.dataset.preset==='custom'){openCalendar('date');return;}startDate.value=b.dataset.preset==='today'?today():yesterday();endDate.value=startDate.value;syncDates();closeCalendar();});
    dialog.querySelectorAll('[data-month-step]').forEach(b=>b.onclick=()=>{month.setMonth(month.getMonth()+Number(b.dataset.monthStep));drawCalendar();});
    dialog.querySelector('[data-clear-end]').onclick=()=>{endDate.value='';syncDates();closeCalendar();dialog.querySelector('[data-date-field=end_date]').focus();};
    dialog.querySelector('[data-calendar-close]').onclick=()=>{closeCalendar();dialog.querySelector('[data-date-field="'+editing+'"]').focus();};
    calendar.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();closeCalendar();dialog.querySelector('[data-date-field="'+editing+'"]').focus();return;}const steps={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7};if(event.target.matches('[data-day]')&&steps[event.key]){event.preventDefault();const days=[...calendar.querySelectorAll('[data-day]')];const next=days[days.indexOf(event.target)+steps[event.key]];if(next&&!next.disabled)next.focus();}});
    startDate.addEventListener('change',syncDates);endDate.addEventListener('change',syncDates);
    startDate.value=today();syncDates();

    let username = '';
    dialog.querySelector('.daily-dismiss').onclick = () => dialog.close();
    dialog.querySelector('.member-close').onclick = () => dialog.close();
    document.querySelectorAll('.eksikler-list li[data-username]').forEach(item => {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'member-analyze-button'; button.textContent = 'Günlük Analiz';
        button.onclick = event => {
            event.stopPropagation(); username = item.dataset.username;
            dialog.querySelector('.member-name').textContent = '@' + username;
            dialog.querySelector('.member-error').textContent = '';
            closeCalendar();syncDates();dialog.showModal();
        };
        item.append(button);
    });
    dialog.querySelector('form').onsubmit = async event => {
        event.preventDefault();
        if(!startDate.value||(endDate.value&&endDate.value<startDate.value)){dialog.querySelector('.member-error').textContent='Bitiş tarihi başlangıçtan önce olamaz. Tarih aralığını kontrol et.';return;}
        const button = dialog.querySelector('[type=submit]');button.disabled = true;
        try {
            const response = await fetch('/api/member_analysis/' + encodeURIComponent(window.postCode), {
                method:'POST',headers:{'Content-Type':'application/json'},
                body:JSON.stringify({username, date:dialog.querySelector('[name=date]').value,end_date:dialog.querySelector('[name=end_date]').value,skip_owner:dialog.querySelector('[name=skip_owner]').checked})
            });
            let data;
            try {data=await response.json();}catch{throw new Error('Sunucudan geçerli yanıt alınamadı. Biraz sonra tekrar dene.');}
            if (!response.ok || !data || !data.success) throw new Error(data?.error || 'Analiz başlatılamadı.');
            window.location.assign(data.result_url);
        } catch(error) {dialog.querySelector('.member-error').textContent = error.message;}
        finally {button.disabled = false;}
    };
})();
