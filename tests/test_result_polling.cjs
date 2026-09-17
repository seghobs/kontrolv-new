const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/js/result_polling.js'), 'utf8');
async function scenario(status, httpStatus=200, execute=false) {
    let reloads=0, destination=null, finishes=0; const calls=[];
    const timers=[];
    const elements={};
    const context={
        document: {querySelector(){return null;}, getElementById(id) {return elements[id] ||= {style:{}, setAttribute(){}};}},
        window: {location: {reload(){reloads++;}, assign(url){destination=url;}}},
        onFinished(){finishes++;},
        AbortController,
        setTimeout(fn, delay) {const timer={fn,delay}; timers.push(timer); return timer;},
        clearTimeout(timer) {timers.splice(timers.indexOf(timer),1);},
        fetch: async (url, options) => { calls.push({url, options}); return {ok:httpStatus===200, status:httpStatus, json:async()=>({status:url.includes('task_run')?'completed':status,execute_in_request:execute,progress:42,message:'Testing'})}; },
    };
    vm.createContext(context);
    vm.runInContext(source+';startResultPolling("abc", undefined, onFinished);',context);
    await new Promise(resolve=>setImmediate(resolve));
    return {reloads,destination,timers,elements,calls,finishes};
}
(async()=>{
    for(const status of ['completed','failed','cancelled']) {
        const result=await scenario(status);
        assert.equal(result.reloads,0);
        assert.equal(result.finishes,1);
        assert.equal(result.destination,'/result/abc');
        assert.equal(result.timers.length,0,'Completion must not wait for animation or schedule more polling');
    }
    const executed=await scenario('running',200,true);
    assert.equal(executed.destination,'/result/abc');
    assert.equal(executed.finishes,1);
    assert.equal(executed.calls[1].url,'/api/task_run/abc');
    assert.equal(executed.calls[1].options.method,'POST');
    const running=await scenario('running');
    assert.equal(running.reloads,0);
    assert.equal(running.finishes,0);
    assert.equal(running.elements['loading-message'].textContent,'Testing');
    assert.equal(running.timers[0].delay,1000);
    assert.equal((await scenario('running',401)).destination,null);
    assert.equal((await scenario('not_found')).timers.length,0);
    assert.equal((await scenario('running',503)).timers[0].delay,2000);
    console.log('Result polling: immediate completion, status message, retry, expiry and missing task OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
