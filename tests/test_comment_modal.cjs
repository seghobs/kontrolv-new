const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/js/result.js'), 'utf8');
const code = source.slice(source.indexOf('function showCommentModal('), source.indexOf('function closeCommentModal('));
function element() {
    return {
        style: {}, children: [], textContent: '', classList: {add() {}},
        set innerHTML(value) { throw new Error('Unsafe HTML assignment'); },
        replaceChildren() { this.children = []; },
        appendChild(child) { this.children.push(child); }
    };
}
const elements = Object.fromEntries(['commentModalUsername', 'commentModalContent', 'commentModalWarning', 'commentDetailModal'].map(id => [id, element()]));
const payload = '<img src=x onerror="globalThis.compromised=true">';
const context = {
    window: {userComments: {alice: [payload, 'Second comment']}, invalidCommentUsers: []},
    document: {getElementById: id => elements[id], createElement: () => element()}
};
vm.createContext(context);
vm.runInContext(code + ';showCommentModal("alice");', context);
assert.equal(elements.commentModalContent.children.length, 2);
assert.equal(elements.commentModalContent.children[0].textContent, '1. ' + payload);
assert.equal(context.compromised, undefined);
context.window.userComments.alice = [payload];
vm.runInContext('showCommentModal("alice");', context);
assert.equal(elements.commentModalContent.textContent, payload);
console.log('Comment modal XSS regression: OK');
