const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/js/result.js'), 'utf8');
const code = source.slice(source.indexOf("let currentInteractionsType ="), source.indexOf('function closeInteractionsModal'));
const elements = {};
const payload = '<img src=x onerror="alert(1)">';
const context = {
 window:{currentActivePostIndex:1,postDetailsData:{1:{like_count:251,likers_list:['alice'],comments_list:[{username:'alice',text:payload}]}}},
 document:{getElementById:id => elements[id] ||= {classList:{add(){}},innerHTML:'',textContent:''}},
 currentInteractionsData:[],
 fetch(){throw Error('Saved data should not fetch');}
};
vm.createContext(context);vm.runInContext(code,context);
vm.runInContext("openInteractionsModal('comments')",context);
assert.ok(!elements.interactionsListContainer.innerHTML.includes('<img'));
assert.ok(elements.interactionsListContainer.innerHTML.includes('&lt;img'));
assert.ok(elements.interactionsListContainer.innerHTML.includes('&quot;'));
vm.runInContext("openInteractionsModal('likes')",context);
assert.ok(elements.interactionsListContainer.innerHTML.includes('yalnız bir kısmını'));
console.log('Interaction text escaping and partial liker warning passed');
