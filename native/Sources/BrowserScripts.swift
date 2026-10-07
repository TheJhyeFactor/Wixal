import Foundation

enum BrowserScripts {
    static let collect = #"""
function collect({ token, offset, max_chars, filter }) {
  const text = document.body?.innerText || '';
  if (offset > text.length) throw new Error('offset exceeds the current page text length. Read again from offset 0.');
  const visible = el => { const style = getComputedStyle(el), rect = el.getBoundingClientRect(); return style.display !== 'none' && style.visibility !== 'hidden' && (rect.width > 0 || rect.height > 0); };
  const label = el => (el.getAttribute('aria-label') || el.labels?.[0]?.innerText || (['INPUT','SELECT','TEXTAREA'].includes(el.tagName) ? el.getAttribute('placeholder') || el.getAttribute('name') : el.innerText) || '').trim().slice(0, 200);
  const signature = el => JSON.stringify([el.tagName, el.getAttribute('type'), el.getAttribute('href'), el.getAttribute('name'), label(el), el.disabled, el.getAttribute('aria-disabled')]);
  const sensitive = el => /password|file|hidden/.test(el.type || '') || /password|credential|secret|token|one.?time|otp|card.?number|credit.?card|cvc|cvv|captcha/i.test([el.name, el.id, el.autocomplete, label(el)].join(' '));
  const all = [...document.querySelectorAll('a[href],button,input,textarea,select,summary,[role="button"],[role="tab"]')].slice(0, 3000).filter(visible).filter(el => !filter || label(el).toLowerCase().includes(filter.toLowerCase()));
  const nodes = all.slice(0, 120);
  const refs = new Map();
  const controls = nodes.map((el, i) => {
    const ref = `${token}:e${i + 1}`; refs.set(ref, { element: el, signature: signature(el) });
    const href = el.tagName === 'A' ? el.href : undefined;
    const protectedInput=sensitive(el);
    return { ref, kind: el.tagName.toLowerCase(), label: label(el), ...(href ? { url: href } : {}), ...(el.type ? { type: el.type } : {}), disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true', protected: protectedInput, ...(!protectedInput && ['INPUT','TEXTAREA','SELECT'].includes(el.tagName) ? {value: String(el.value).slice(0,2000), ...(['checkbox','radio'].includes(el.type) ? {checked:el.checked} : {})} : {}), ...(el.tagName === 'SELECT' && !protectedInput ? { options: [...el.options].slice(0, 30).map(o => ({ value: o.value, label: o.text, selected:o.selected, disabled:o.disabled })) } : {}) };
  });
  globalThis.__wixalBrowser = { refs, signature, sensitive, visible };
  return { title: document.title, url: location.href, headings: [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(visible).slice(0, 60).map(el => ({ level: Number(el.tagName.slice(1)), text: el.innerText.trim().slice(0, 200) })), text: text.slice(offset, offset + max_chars), offset, next_offset: Math.min(text.length, offset + max_chars), total_characters: text.length, more: offset + max_chars < text.length, controls, controls_more: all.length > nodes.length, links: controls.filter(c => c.kind === 'a').map(c => ({ ref: c.ref, text: c.label, url: c.url })), forms: [...document.forms].slice(0, 30).map(f => ({ action: f.action, method: f.method, fields: [...f.elements].slice(0, 50).map(e => ({ name: e.name, type: e.type })) })), scripts: [...document.scripts].map(s => s.src).filter(Boolean).slice(0, 50) };
}
return collect(options);
"""#
    static let action = #"""
return (({ ref, action, value, apply, interactive }) => {
    const state = globalThis.__wixalBrowser, record = state?.refs.get(ref), el = record?.element;
    if (!el?.isConnected || !state.visible(el) || state.signature(el) !== record.signature) throw new Error('Control changed since the snapshot. Use browser_read.');
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') throw new Error('Control is disabled.');
    if (state.sensitive(el)) throw new Error('Credentials, payment details, files and verification controls are unsupported.');
    if (action === 'click') {
      if (!interactive && el.closest('form') && (el.tagName === 'BUTTON' && el.type !== 'button' || el.tagName === 'INPUT' && ['submit', 'image'].includes(el.type))) throw new Error('Form submission is unsupported.');
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) && !['checkbox', 'radio', 'button'].includes(el.type)) throw new Error('Use fill or select for this control.');
      if (el.tagName === 'A') return { navigate: el.href, label: record.signature };
    } else if (action === 'fill') {
      if (!['INPUT', 'TEXTAREA'].includes(el.tagName) || ['checkbox', 'radio', 'button', 'submit'].includes(el.type)) throw new Error('This control does not accept text.');
    } else if (el.tagName !== 'SELECT' || ![...el.options].some(o => o.value === value)) throw new Error('Choose an option value from the latest snapshot.');
    if (apply) {
      if (action === 'click') setTimeout(()=>el.click(),50);
      else { const setter = Object.getOwnPropertyDescriptor(el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : el.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype, 'value').set; setter.call(el, value); el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }
    }
    return { action, label: el.getAttribute('aria-label') || el.innerText || el.name || el.tagName, url: location.href };
  })(options);
"""#
    static let settle = #"""
const start=Date.now(); let previous='', quiet=start;
while (true) {
 const text=document.body?.innerText || '';
 if(text!==previous){previous=text;quiet=Date.now()}
 if(options.wait_for && text.includes(options.wait_for)) return {matched:true,waited_ms:Date.now()-start};
 if(Date.now()-start>=options.wait_ms) return {matched:!options.wait_for && !!text.trim(),settled:Date.now()-quiet>=250,waited_ms:Date.now()-start};
 await new Promise(resolve=>setTimeout(resolve,100));
}
"""#
}
