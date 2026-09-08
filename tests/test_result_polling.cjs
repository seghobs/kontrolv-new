const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/js/result_polling.js'), 'utf8');
async function scenario(status, httpStatus=200) {
    let reloads=0, destination=null;
    const timers=[];
    const elements={};
    const context={
        document: {getElementById(id) {return elements[id] ||= {style:{}, setAttribute(){}};}},
        window: {location: {reload(){reloads++;}, assign(url){destination=url;}}},
        AbortController,
        setTimeout(fn, delay) {const timer={fn,delay}; timers.push(timer); return timer;},
        clearTimeout(timer) {timers.splice(timers.indexOf(timer),1);},
        fetch: async () => ({ok:httpStatus===200, status:httpStatus, json:async()=>({status,progress:42,message:'Testing'})}),
    };
    vm.createContext(context);
    vm.runInContext(source+';startResultPolling("abc");',context);
    await new Promise(resolve=>setImmediate(resolve));
    return {reloads,destination,timers,elements};
}
(async()=>{
    for(const status of ['completed','failed','cancelled']) {
        const result=await scenario(status);
        assert.equal(result.reloads,1);
        assert.equal(result.timers.length,0,'Completion must not wait for animation or schedule more polling');
    }
    const running=await scenario('running');
    assert.equal(running.reloads,0);
    assert.equal(running.elements['loading-percent'].textContent,'%42 Tamamlandı');
    assert.equal(running.timers[0].delay,1000);
    assert.equal((await scenario('running',401)).destination,'/admin/login');
    assert.equal((await scenario('not_found')).timers.length,0);
    assert.equal((await scenario('running',503)).timers[0].delay,2000);
    console.log('Result polling: immediate completion, real progress, retry, expiry and missing task OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
