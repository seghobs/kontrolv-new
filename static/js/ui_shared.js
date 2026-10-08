(() => {
    if (window.CoffeeUI) return;
    const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
    function panel(el, open) {
        if (!el) return;
        const start = el.getBoundingClientRect().height, css = getComputedStyle(el);
        const first = {height: start + 'px', opacity: css.opacity, paddingTop: css.paddingTop, paddingBottom: css.paddingBottom};
        el._panelAnimation?.cancel();
        el.classList.toggle('collapsed', !open);
        el.classList.add('ui-panel-moving');
        el.inert = !open;
        el.style.height = ''; el.style.maxHeight = 'none'; el.style.opacity = '';
        const natural = getComputedStyle(el);
        const last = {height: (open ? el.scrollHeight : 0) + 'px', opacity: open ? 1 : 0,
            paddingTop: open ? natural.paddingTop : '0px', paddingBottom: open ? natural.paddingBottom : '0px'};
        const finish = () => {
            el.classList.remove('ui-panel-moving');
            el.style.maxHeight = open ? 'none' : '';
            el._panelAnimation = null;
        };
        if (reduced() || !el.animate) {finish(); return;}
        const animation = el.animate([first, last], {duration: 260, easing: 'cubic-bezier(.2,.7,.2,1)', fill: 'both'});
        el._panelAnimation = animation;
        animation.onfinish = () => {if (el._panelAnimation === animation) {finish();animation.cancel();}};
        if (!el._panelObserver) {
            el._panelObserver = new MutationObserver(() => {
                if (el._panelAnimation && !el.classList.contains('collapsed')) panel(el, true);
            });
            el._panelObserver.observe(el, {childList: true, subtree: true, characterData: true});
        }
    }
    function position(menu, trigger) {
        const view = window.visualViewport;
        const top = (view?.offsetTop || 0) + 8, left = (view?.offsetLeft || 0) + 8;
        const width = Math.max(0, (view?.width || innerWidth) - 16);
        let bottom = top + (view?.height || innerHeight) - 16;
        const nav = document.querySelector('.mobile-bottom-nav');
        if (nav && getComputedStyle(nav).display !== 'none') {
            const rect = nav.getBoundingClientRect();
            if (rect.top > top && rect.top < bottom) bottom = rect.top - 8;
        }
        const anchor = trigger.getBoundingClientRect();
        const below = Math.max(0, bottom - anchor.bottom - 8), above = Math.max(0, anchor.top - top - 8);
        const up = below < 240 && above > below;
        const height = Math.min(360, bottom - top, up ? above : below);
        const menuWidth = Math.min(Math.max(anchor.width, 220), width);
        menu.style.width = menuWidth + 'px'; menu.style.maxHeight = Math.max(0, height) + 'px';
        menu.style.left = Math.max(left, Math.min(anchor.left, left + width - menuWidth)) + 'px';
        const actual = Math.min(menu.scrollHeight, Math.max(0, height));
        menu.style.top = Math.max(top, Math.min(up ? anchor.top - actual - 8 : anchor.bottom + 8, bottom - actual)) + 'px';
    }
    window.CoffeeUI = {panel, position};
    // Bootstrap delegates dropdown key events in capture phase on document.
    // Own these keys at window capture so only our picker handles them.
    window.addEventListener('keydown', event => {
        const menu=event.target.closest?.('.coffee-dropdown-menu,.coffee-select-dialog');
        if(!menu || !['ArrowDown','ArrowUp','Home','End','Escape'].includes(event.key))return;
        event.stopImmediatePropagation();
        if(menu.classList.contains('coffee-select-dialog'))window.CoffeeUI.selectKey?.(event);
        else menu._coffeeKey?.(event);
    },true);

    const pickers = new Map();
    const panelHeaders = new WeakSet();
    function closePicker(menu, trigger, focus = false) {
        menu.classList.remove('show');trigger.classList.remove('active');trigger.setAttribute('aria-expanded', 'false');
        if (menu.matches(':popover-open')) menu.hidePopover();
        if (focus) trigger.focus();
    }
    function scan() {
    document.querySelectorAll('.result-section-content.collapsed').forEach(el=>{if(!el.inert)el.inert=true;});
    document.querySelectorAll('.eksikler-section-header,.completed-section-header,.detayli-rapor-header').forEach(header=>{
        if(!header.hasAttribute('onclick') || panelHeaders.has(header))return;
        panelHeaders.add(header);
        header.setAttribute('role','button');header.tabIndex=0;
        header.addEventListener('keydown',event=>{
            if(event.target===header && ['Enter',' '].includes(event.key)){event.preventDefault();header.click();}
        });
    });

        document.querySelectorAll('.custom-dropdown').forEach(root => {
            const menu = root.querySelector('.dropdown-menu'), trigger = root.querySelector('.dropdown-trigger');
            if (!menu || !trigger || pickers.has(menu) || !menu.showPopover) return;
            menu.setAttribute('popover', 'manual');menu.classList.add('coffee-dropdown-menu');
            trigger.setAttribute('aria-haspopup', 'true');trigger.setAttribute('aria-expanded', 'false');
            if (trigger.tagName !== 'BUTTON') {
                trigger.setAttribute('role', 'button');trigger.tabIndex = 0;
                trigger.addEventListener('keydown', event => {
                    if (event.target === trigger && ['Enter',' '].includes(event.key)) {event.preventDefault();trigger.click();}
                });
            }
            const observer = new MutationObserver(() => {
                const open = menu.classList.contains('show');
                trigger.setAttribute('aria-expanded', String(open));
                if (open) {
                    for (const [other, t] of pickers) if (other !== menu) closePicker(other, t);
                    window.CoffeeUI.closeSelect?.();
                    if (!menu.matches(':popover-open')) menu.showPopover();
                    position(menu, trigger);
                } else if (menu.matches(':popover-open')) menu.hidePopover();
            });
            observer.observe(menu, {attributes: true, attributeFilter: ['class']});
            new ResizeObserver(() => {if(menu.matches(':popover-open'))position(menu,trigger);}).observe(menu);
            const menuKey = event => {
                event.stopPropagation();
                if (event.key === 'Escape') {event.preventDefault();event.stopPropagation();closePicker(menu,trigger,true);return;}
                const options = [...menu.querySelectorAll('.dropdown-option')].filter(e => e.getClientRects().length && !e.matches('[disabled],[aria-disabled=true]'));
                if (!options.length) return;
                if (['ArrowDown','ArrowUp','Home','End'].includes(event.key)) {
                    event.preventDefault();const i=options.indexOf(document.activeElement);
                    const next=event.key==='Home'?0:event.key==='End'?options.length-1:event.key==='ArrowUp'?(i-1+options.length)%options.length:(i+1)%options.length;
                    options[next].tabIndex=-1;options[next].focus();
                } else if (['Enter',' '].includes(event.key) && options.includes(event.target)) {event.preventDefault();event.target.click();}
            };
            menu._coffeeKey = menuKey;
            menu.addEventListener('keydown', menuKey);
            trigger.addEventListener('keydown',event=>{
                if(event.key==='ArrowDown'){event.preventDefault();if(!menu.classList.contains('show'))trigger.click();queueMicrotask(()=>{const first=menu.querySelector('input,.dropdown-option');if(first){if(first.tagName!=='INPUT')first.tabIndex=-1;first.focus();}});}
            });
            pickers.set(menu, trigger);
        });
        for (const [menu, trigger] of pickers) {
            if (!menu.isConnected) {pickers.delete(menu);continue;}
            if (menu.classList.contains('show') && (!trigger.getClientRects().length || trigger.closest('[inert]'))) closePicker(menu,trigger);
        }
    }
    document.addEventListener('pointerdown',event=>{
        for(const [menu, trigger] of pickers)if(!menu.contains(event.target)&&!trigger.contains(event.target))closePicker(menu,trigger);
    });
    const reposition = () => {for(const [menu,trigger]of pickers)if(menu.matches(':popover-open'))position(menu,trigger);};
    window.addEventListener('resize',reposition);document.addEventListener('scroll',reposition,true);
    window.visualViewport?.addEventListener('resize',reposition);window.visualViewport?.addEventListener('scroll',reposition);
    let queued = false;
    new MutationObserver(records=>{
        if(records.every(r=>r.target.closest?.('.coffee-select-dialog,.coffee-select-trigger')))return;
        if(!queued){queued=true;queueMicrotask(()=>{queued=false;scan();});}
    }).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['inert','hidden']});
    const modalMemory = new Map();
    const modalSelector = '.modal,.custom-modal,.modal-overlay,.success-modal';
    const closeSelector = '.modal-close,.modal-close-btn,.modal-close-icon-btn,.btn-close-modal,.post-modal-close-btn,[data-close],button[onclick*="close"],button[onclick*="Close"]';
    const focusable = root => [...root.querySelectorAll('a[href],button,input,textarea,select,[tabindex]')]
        .filter(el => !el.disabled && el.tabIndex >= 0 && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden');
    function syncModals() {
        document.querySelectorAll(modalSelector).forEach(modal => {
            const css = getComputedStyle(modal);
            const byClass = modal.matches('.modal-overlay,.custom-modal,.success-modal');
            const visible = css.display !== 'none' && (byClass ? (modal.matches('.show,.active') || modal.style.display === 'flex') : css.visibility !== 'hidden') && modal.getClientRects().length > 0;
            if (visible && !modalMemory.has(modal)) {
                modalMemory.set(modal, document.activeElement);
                const card = modal.querySelector('.modal-card,.modal-content,.modal-content-glass,.success-modal-content') || modal;
                card.setAttribute('role','dialog');card.setAttribute('aria-modal','true');
                const title = card.querySelector('h2,h3,h5,.modal-title');
                if(title && !card.hasAttribute('aria-labelledby') && !card.hasAttribute('aria-label'))card.setAttribute('aria-label',title.textContent.trim());
                if(modal.querySelector(closeSelector))focusable(card)[0]?.focus({preventScroll:true});
            } else if (!visible && modalMemory.has(modal)) {
                const previous=modalMemory.get(modal);modalMemory.delete(modal);
                if(previous?.isConnected && !previous.closest('[inert]'))previous.focus({preventScroll:true});
            }
        });
        for(const modal of modalMemory.keys())if(!modal.isConnected)modalMemory.delete(modal);
    }
    document.addEventListener('keydown',event=>{
        if(document.querySelector('dialog[open],:popover-open'))return;
        const modals=[...modalMemory.keys()].sort((a,b)=>(parseInt(getComputedStyle(a).zIndex)||0)-(parseInt(getComputedStyle(b).zIndex)||0));
        const modal=modals.at(-1);if(!modal)return;
        const close=modal.querySelector(closeSelector);
        if(event.key==='Escape' && close){event.preventDefault();event.stopImmediatePropagation();close.click();}
        if(event.key==='Tab'){
            const items=focusable(modal);if(!items.length)return;
            const first=items[0],last=items.at(-1);
            if(event.shiftKey && (document.activeElement===first || !modal.contains(document.activeElement))){event.preventDefault();last.focus();}
            else if(!event.shiftKey && (document.activeElement===last || !modal.contains(document.activeElement))){event.preventDefault();first.focus();}
        }
    },true);
    let modalQueued=false;
    new MutationObserver(records=>{
        if(!records.some(r=>r.target.matches?.(modalSelector)||[...r.addedNodes,...r.removedNodes].some(n=>n.matches?.(modalSelector))))return;
        if(!modalQueued){modalQueued=true;queueMicrotask(()=>{modalQueued=false;syncModals();});}
    }).observe(document.body,{attributes:true,attributeFilter:['class','style'],childList:true,subtree:true});
    syncModals();scan();
})();
