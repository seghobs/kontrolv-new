const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/js/worker_status.js'), 'utf8');
async function check(data, status=200) {
    const elements={};
    const panel={querySelector: selector => elements[selector] ||= {textContent:''}};
    const timers=new Map();let next=0;
    const context={
        document:{hidden:false, querySelector:()=>panel, addEventListener(){}},
        fetch:async()=>({ok:status===200,status,json:async()=>data}), AbortController,
        setTimeout(fn,ms){timers.set(++next,ms);return next;},
        clearTimeout(id){timers.delete(id);},
    };
    vm.createContext(context);vm.runInContext(source,context);
    await new Promise(resolve=>setImmediate(resolve));
    return {elements,timers};
}
(async()=>{
    const idle=await check({online:true,last_seen:100,queued:2,running:0,cancelling:0});
    assert.equal(idle.elements['[data-worker-state]'].textContent,'İşçi hazır');
    assert.equal(idle.elements['[data-worker-queued]'].textContent,2);
    assert.equal([...idle.timers.values()][0],5000);
    const busy=await check({online:true,last_seen:100,queued:1,running:1,cancelling:1});
    assert.equal(busy.elements['[data-worker-running]'].textContent,2);
    const offline=await check({online:false,last_seen:100,queued:0,running:0,cancelling:0});
    assert.equal(offline.elements['[data-worker-state]'].textContent,'İşçi bağlantısı kesildi');
    const error=await check({},503);
    assert.match(error.elements['[data-worker-state]'].textContent,/doğrulanamadı/);
    assert.equal((await check({},401)).timers.size,0);
    console.log('Worker indicator: idle, busy, disconnected, errors and session expiry OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
