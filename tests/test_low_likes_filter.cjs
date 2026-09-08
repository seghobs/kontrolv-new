const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/js/form.js'), 'utf8');
function extract(name) {
    const start = source.indexOf(`function ${name}(`);
    const end = source.indexOf('\nfunction ', start + 1);
    // These functions have no top-level statements before the next function except renderPosts.
    return source.slice(start, end < 0 ? undefined : end).split('\nwindow.')[0];
}
function element() {
    return {
        value: '', textContent: '', children: [], dataset: {}, style: {},
        classList: {add() {}, remove() {}},
        set innerHTML(value) { this.children = []; },
        get options() { return this.children; },
        appendChild(child) { this.children.push(child); },
        querySelectorAll(selector) { return selector === 'option' ? this.children : []; },
        dispatchEvent() {},
    };
}
const ids = Object.fromEntries(['postSelect', 'post_link_single', 'post_link_multi', 'checkForm', 'lowLikesCheck', 'grup_uye'].map(id => [id, element()]));
const dropdownText = element(), dropdownOptions = element();
const context = {
    window: {_checkMode: 'single', postFilterSettings: {}},
    document: {
        getElementById: id => ids[id],
        querySelector: selector => selector.endsWith('.dropdown-text') ? dropdownText : dropdownOptions,
        createElement: () => element(),
    },
    Event: class {}, validateForm() {},
};
vm.createContext(context);
vm.runInContext(['handleLowLikesCheckbox', 'renderPosts', 'selectPostInUI', 'addAllPosts'].map(extract).join('\n'), context);
const post = (url, count) => ({url, like_count: count, username: 'alice', date: 'Bugün'});
context.window.allFetchedPosts = [post('https://post/high', 91), post('https://post/limit', 90), post('https://post/zero', 0), post('https://post/unknown', -1), post('https://post/missing', null)];
ids.grup_uye.value = 'alice\nbob';
ids.post_link_single.value = 'https://post/high';
ids.lowLikesCheck.checked = true;
vm.runInContext('handleLowLikesCheckbox()', context);
assert.deepEqual(ids.postSelect.options.map(o => o.value), ['https://post/limit', 'https://post/zero']);
assert.equal(ids.post_link_single.value, 'https://post/limit');
assert.equal(ids.postSelect.value, 'https://post/limit');
assert.equal(ids.grup_uye.value, 'alice\nbob');
vm.runInContext('selectPostInUI("https://post/high")', context);
assert.equal(ids.post_link_single.value, 'https://post/limit');
ids.post_link_single.value = 'https://post/zero';
vm.runInContext('handleLowLikesCheckbox()', context);
assert.equal(ids.post_link_single.value, 'https://post/zero');
context.window._checkMode = 'multi';
vm.runInContext('handleLowLikesCheckbox()', context);
assert.equal(ids.post_link_multi.value, 'https://post/limit\nhttps://post/zero');
context.window.allFetchedPosts = [post('https://post/high', 120)];
vm.runInContext('handleLowLikesCheckbox()', context);
assert.equal(ids.post_link_single.value, '');
assert.equal(ids.post_link_multi.value, '');
assert.equal(dropdownText.textContent, 'Filtreye uygun paylaşım yok');
ids.lowLikesCheck.checked = false;
vm.runInContext('handleLowLikesCheckbox()', context);
assert.equal(ids.post_link_multi.value, 'https://post/high');
console.log('Low likes filter: immediate selection, boundaries, unknown counts, empty results, multi mode, and stale selections OK');
