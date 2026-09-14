(() => {
    if (window.coffeeSelectInstalled) return;
    window.coffeeSelectInstalled = true;
    const controls = new Map();
    let active = null, returnFocus = null;
    const dialog = document.createElement('div');
    dialog.className = 'dropdown-menu coffee-select-dialog';
    dialog.setAttribute('popover','manual');
    dialog.setAttribute('role','group');
    dialog.setAttribute('aria-label', 'Seçenekler');
    dialog.innerHTML = '<input class="dropdown-search coffee-select-search" type="search" placeholder="Ara..." aria-label="Seçeneklerde ara" autocomplete="off"><div class="dropdown-options coffee-select-list" role="group" aria-label="Seçenekler"></div><p class="coffee-select-empty" hidden>Aramana uygun seçenek bulunamadı.</p><div class="coffee-select-footer" hidden><button type="button">Seçimi tamamla</button></div>';
    document.body.append(dialog);
    const search = dialog.querySelector('input'), list = dialog.querySelector('.coffee-select-list');
    function label(select) {
        const explicit = select.getAttribute('aria-label');
        if (explicit) return explicit;
        const node = select.labels?.[0];
        if (node) {
            const copy = node.cloneNode(true);
            copy.querySelectorAll('select,button,.coffee-select-trigger').forEach(el => el.remove());
            const text = copy.textContent.trim();
            if (text) return text;
        }
        return 'Seçim yap';
    }
    function sync(select) {
        const button = controls.get(select);
        if (!button) return;
        const chosen = [...select.selectedOptions].map(option => option.textContent.trim());
        button.querySelector('span').textContent = chosen.join(', ') || 'Seçim yap';
        button.disabled = select.disabled;
        button.setAttribute('aria-label', label(select) + ': ' + (chosen.join(', ') || 'Seçim yap'));
        button.title = chosen.join(', ');
    }
    function close() {
        if (!active) return;
        dialog.hidePopover();dialog.classList.remove('show');returnFocus?.classList.remove('active');
        returnFocus?.setAttribute('aria-expanded','false');active=null;
    }
    function position() {
        if (!active) return;
        const r=returnFocus.getBoundingClientRect();
        dialog.style.width=Math.min(r.width,innerWidth-16)+'px';
        dialog.style.left=Math.max(8,Math.min(r.left,innerWidth-dialog.offsetWidth-8))+'px';
        const below=innerHeight-r.bottom-16, above=r.top-16;
        const height=Math.min(320,Math.max(below,above));
        dialog.style.maxHeight=height+'px';
        dialog.style.top=(below>=Math.min(320,dialog.scrollHeight)||below>=above?r.bottom+8:Math.max(8,r.top-dialog.offsetHeight-8))+'px';
    }
    function draw() {
        if (!active) return;
        const query = search.value.trim().toLocaleLowerCase('tr');
        list.replaceChildren();
        let count = 0, lastGroup = null;
        [...active.options].forEach((option, index) => {
            if (option.hidden || !option.textContent.toLocaleLowerCase('tr').includes(query)) return;
            const group = option.parentElement.tagName === 'OPTGROUP' ? option.parentElement : null;
            if (group && group !== lastGroup) {
                const heading = document.createElement('p');heading.className = 'coffee-select-group';heading.textContent = group.label;list.append(heading);
            }
            lastGroup = group;
            const row = document.createElement('button');row.type = 'button';row.className = 'dropdown-option coffee-select-option';row.classList.toggle('selected',option.selected);
            row.disabled = active.disabled || option.disabled || !!group?.disabled;
            row.setAttribute('aria-pressed', String(option.selected));
            const text = document.createElement('span');text.className = 'coffee-select-option-label';text.textContent = option.textContent;
            const check = document.createElement('span');check.className = 'coffee-select-check';check.setAttribute('aria-hidden','true');check.textContent = option.selected ? '✓' : '';
            row.append(text,check);row.dataset.index = index;
            row.addEventListener('click', () => {
                const select = active;
                if (!select || select.disabled || option.disabled || group?.disabled) return;
                if (select.multiple) option.selected = !option.selected;
                else select.selectedIndex = index;
                select.dispatchEvent(new Event('input', {bubbles:true}));
                select.dispatchEvent(new Event('change', {bubbles:true}));
                sync(select);
                if (!select.multiple) {close();returnFocus?.focus();}
                else {draw();list.querySelector('[data-index="'+index+'"]')?.focus();}
            });
            list.append(row);count++;
        });
        dialog.querySelector('.coffee-select-empty').hidden = count !== 0;
    }
    function open(select) {
        if (select.disabled || !select.isConnected) return;
        active = select;returnFocus = controls.get(select);
        dialog.setAttribute('aria-label',label(select));
        search.value = '';
        dialog.querySelector('.coffee-select-footer').hidden = !select.multiple;
        draw();returnFocus.setAttribute('aria-expanded','true');returnFocus.classList.add('active');dialog.showPopover();dialog.classList.add('show');position();search.focus();
    }
    dialog.querySelector('.coffee-select-footer button').onclick = () => {close();returnFocus?.focus();};
    document.addEventListener('pointerdown',event=>{if(active&&!dialog.contains(event.target)&&!returnFocus.contains(event.target))close();});
    window.addEventListener('resize',position);
    document.addEventListener('scroll',event=>{if(active&&!dialog.contains(event.target))position();},true);
    search.addEventListener('input', draw);
    dialog.addEventListener('keydown', event => {
        if (event.key === 'Escape') {event.preventDefault();close();returnFocus?.focus();return;}
        if (!['ArrowDown','ArrowUp','Home','End'].includes(event.key) || (event.target === search && event.key !== 'ArrowDown')) return;
        const rows = [...list.querySelectorAll('button:not(:disabled)')];if (!rows.length) return;
        event.preventDefault();const index = rows.indexOf(document.activeElement);
        const next = event.key==='Home'?0:event.key==='End'?rows.length-1:event.key==='ArrowDown'?(index+1)%rows.length:(index-1+rows.length)%rows.length;
        rows[next].focus();
    });
    function enhance(select) {
        // Existing group/post pickers already have custom interfaces.
        if (controls.has(select) || select.matches('.hidden-select,[hidden],[data-native-select]') || getComputedStyle(select).display==='none') return;
        const button = document.createElement('button');button.type='button';button.className='dropdown-trigger coffee-select-trigger';
        const text=document.createElement('span');text.className='dropdown-text';const arrow=document.createElement('b');arrow.textContent='⌄';arrow.setAttribute('aria-hidden','true');button.append(text,arrow);
        button.setAttribute('aria-haspopup','true');button.setAttribute('aria-expanded','false');
        controls.set(select,button);select.after(button);select.classList.add('coffee-select-native');select.tabIndex=-1;select.setAttribute('aria-hidden','true');
        button.onclick=()=>active===select?close():open(select);
        select.addEventListener('change',()=>{sync(select);if(active===select)draw();});
        select.addEventListener('invalid',event=>{event.preventDefault();button.setAttribute('aria-invalid','true');if(!active)open(select);});
        select.addEventListener('change',()=>button.removeAttribute('aria-invalid'));
        select.addEventListener('focus',()=>button.focus());
        for (const key of ['value','selectedIndex']) {
            const property=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,key);
            if (!Object.hasOwn(select,key) && property?.set) Object.defineProperty(select,key,{configurable:true,get(){return property.get.call(this);},set(value){property.set.call(this,value);sync(this);}});
        }
        sync(select);
    }
    function scan() {
        document.querySelectorAll('select').forEach(enhance);
        for (const [select,button] of controls) {
            if(!select.isConnected){button.remove();controls.delete(select);if(active===select)close();}
            else sync(select);
        }
    }
    scan();
    const observer=new MutationObserver(records=>{
        if(records.every(record=>dialog.contains(record.target)||record.target.closest?.('.coffee-select-trigger')))return;
        scan();if(active)draw();
    });
    observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled','selected','label','hidden']});
    document.addEventListener('reset',()=>setTimeout(scan,0));
})();
