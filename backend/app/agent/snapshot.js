// Injected into every page state. Returns a structured "UI component" snapshot:
// interactive elements, text blocks, overlays and page metrics, with computed styles
// and page-coordinate bounding boxes. Elements get a data-dpc-id for later clicks.
() => {
  const sx = window.scrollX, sy = window.scrollY;
  const isTransparent = c => !c || c === 'transparent' || /rgba\([^)]*,\s*0(\.0+)?\)$/.test(c);
  const effectiveBg = el => {
    let e = el;
    while (e && e.nodeType === 1) {
      const c = getComputedStyle(e).backgroundColor;
      if (!isTransparent(c)) return c;
      e = e.parentElement;
    }
    return 'rgb(255, 255, 255)';
  };
  const visible = el => {
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity || '1') > 0.05 && r.width > 1 && r.height > 1;
  };
  const box = el => { const r = el.getBoundingClientRect(); return {x: Math.round(r.x + sx), y: Math.round(r.y + sy), w: Math.round(r.width), h: Math.round(r.height)}; };
  const labelFor = el => {
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return l.innerText; }
    const p = el.closest('label'); if (p) return p.innerText;
    const sib = el.parentElement ? el.parentElement.innerText : '';
    return el.getAttribute('aria-label') || sib || '';
  };
  const elements = [];
  let id = 0;
  const sel = 'a[href], button, input, select, textarea, summary, [role=button], [role=switch], [role=checkbox], [onclick]';
  document.querySelectorAll(sel).forEach(el => {
    const type = (el.getAttribute('type') || '').toLowerCase();
    const isToggle = type === 'checkbox' || type === 'radio' || ['switch', 'checkbox'].includes(el.getAttribute('role'));
    const vis = visible(el);
    if (!vis && !isToggle) return;
    if (type === 'hidden') return;
    const s = getComputedStyle(el);
    let childLabel = '';
    try {
      const childWithLabel = el.querySelector('[aria-label], title, svg');
      if (childWithLabel) {
        childLabel = childWithLabel.getAttribute('aria-label') || childWithLabel.getAttribute('title') || childWithLabel.textContent || '';
      }
    } catch (e) {}
    let text = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder') || childLabel || '').trim();
    if (isToggle) text = labelFor(el).trim();
    const dpc = String(id++);
    el.setAttribute('data-dpc-id', dpc);

    let sameDomain = true;
    let sameOrigin = true;
    if (el.href) {
      try {
        const targetUrl = new URL(el.href, location.href);
        sameOrigin = targetUrl.origin === location.origin;
        const currParts = location.hostname.split('.');
        const tgtParts = targetUrl.hostname.split('.');
        const currBase = currParts.slice(-2).join('.');
        const tgtBase = tgtParts.slice(-2).join('.');
        sameDomain = sameOrigin || (currBase === tgtBase && currBase.length > 3);
      } catch (e) {}
    }

    elements.push({
      id: dpc, tag: el.tagName.toLowerCase(), type, role: el.getAttribute('role') || '',
      text: text.slice(0, 200), href: el.getAttribute('href') || '', abs: el.href || '',
      checked: isToggle ? (el.checked === true || el.getAttribute('aria-checked') === 'true') : null,
      disabled: !!el.disabled, visible: vis, bbox: box(el),
      color: s.color, bg: effectiveBg(el), ownBg: s.backgroundColor,
      fontSize: parseFloat(s.fontSize), fontWeight: parseInt(s.fontWeight) || 400,
      textDecoration: s.textDecorationLine, cursor: s.cursor,
      sameOrigin: sameOrigin,
      sameDomain: sameDomain,
    });
  });

  const texts = [];
  const rootNode = document.body || document.documentElement;
  if (rootNode) {
    const walker = document.createTreeWalker(rootNode, NodeFilter.SHOW_TEXT);
    const seen = new Set();
    while (walker.nextNode() && texts.length < 500) {
      const node = walker.currentNode;
      const t = node.textContent.replace(/\s+/g, ' ').trim();
      if (t.length < 2) continue;
      const el = node.parentElement;
      if (!el || seen.has(el) || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(el.tagName)) continue;
      seen.add(el);
      if (!visible(el)) continue;
      const s = getComputedStyle(el);
      texts.push({text: (el.innerText || t).replace(/\s+/g, ' ').trim().slice(0, 400), tag: el.tagName.toLowerCase(),
        fontSize: parseFloat(s.fontSize), color: s.color, bg: effectiveBg(el), bbox: box(el)});
    }
  }

  const vw = window.innerWidth, vh = window.innerHeight;
  const overlays = [];
  document.querySelectorAll('body *').forEach(el => {
    const s = getComputedStyle(el);
    if (!['fixed', 'sticky'].includes(s.position) || !visible(el)) return;
    const r = el.getBoundingClientRect();
    const cover = (Math.min(r.width, vw) * Math.min(r.height, vh)) / (vw * vh);
    if (cover > 0.08 || (el.getAttribute('role') === 'dialog')) {
      overlays.push({text: (el.innerText || '').replace(/\s+/g, ' ').slice(0, 300), cover: Math.round(cover * 100) / 100, bbox: box(el)});
    }
  });

  const fullText = (document.body ? document.body.innerText : (document.documentElement ? document.documentElement.innerText : '')) || '';
  return {
    url: location.href, title: document.title,
    viewport: {w: vw, h: vh}, scrollHeight: (document.documentElement ? document.documentElement.scrollHeight : 800),
    text: fullText.slice(0, 20000),
    elements, texts, overlays,
  };
}
