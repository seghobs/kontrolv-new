import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
const elements={};let copied='';const buttons=['-comments','-likes'].map(suffix=>({dataset:{memberCopy:suffix},addEventListener(event,fn){this.click=fn;}}));
for(const suffix of ['-comments','-likes']){elements['member-missing-text'+suffix]={value:suffix+' links',hidden:true,focus(){},select(){}};elements['member-copy-feedback'+suffix]={textContent:''};}
const ctx={document:{querySelectorAll:()=>buttons,getElementById:id=>elements[id]},navigator:{clipboard:{writeText:async text=>{copied=text;}}}};
vm.runInNewContext(fs.readFileSync('static/js/member_report.js','utf8'),ctx);
await buttons[0].click();assert.equal(copied,'-comments links');assert.equal(elements['member-copy-feedback-likes'].textContent,'');
await buttons[1].click();assert.equal(copied,'-likes links');
ctx.navigator.clipboard.writeText=async()=>{throw Error('denied');};await buttons[1].click();assert.equal(elements['member-missing-text-likes'].hidden,false);assert.equal(elements['member-missing-text-comments'].hidden,true);
console.log('Independent copy buttons and isolated fallback passed');
