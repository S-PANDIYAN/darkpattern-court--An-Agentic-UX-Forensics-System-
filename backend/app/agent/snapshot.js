// Injected into every page state. Returns a structured "UI component" snapshot:
// interactive elements, text blocks, overlays and page metrics, with computed styles
// and page-coordinate bounding boxes. Elements get a data-dpc-id for later clicks.
// Supports Shadow DOM traversal, accessible iframes, and semantic icon-button labels.
() => {
  const sx = window.scrollX || window.pageXOffset || 0;
  const sy = window.scrollY || window.pageYOffset || 0;
  const vw = window.innerWidth || 1280;
  const vh = window.innerHeight || 800;

  const isTransparent = c => !c || c === 'transparent' || /rgba\([^)]*,\s*0(\.0+)?\)$/.test(c);

  const effectiveBg = el => {
    let e = el;
    while (e && e.nodeType === 1) {
      try {
        const c = getComputedStyle(e).backgroundColor;
        if (!isTransparent(c)) return c;
      } catch (err) {}
      e = e.parentElement || (e.getRootNode && e.getRootNode().host);
    }
    return 'rgb(255, 255, 255)';
  };

  const visible = el => {
    try {
      const s = getComputedStyle(el), r = el.getBoundingClientRect();
      return s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity || '1') > 0.05 && r.width > 1 && r.height > 1;
    } catch (err) {
      return false;
    }
  };

  const box = el => {
    try {
      const r = el.getBoundingClientRect();
      return {
        x: Math.round(r.x + sx),
        y: Math.round(r.y + sy),
        w: Math.round(r.width),
        h: Math.round(r.height)
      };
    } catch (err) {
      return { x: 0, y: 0, w: 0, h: 0 };
    }
  };

  const labelFor = el => {
    if (el.id) {
      try {
        const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
        if (l) return l.innerText;
      } catch (e) {}
    }
    const p = el.closest ? el.closest('label') : null;
    if (p) return p.innerText;
    const sib = el.parentElement ? el.parentElement.innerText : '';
    return el.getAttribute('aria-label') || sib || '';
  };

  // Helper to extract semantic text or infer icon meaning
  const getSemanticLabel = (el) => {
    let text = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder') || '').trim();
    if (text) return text;

    // 1. Check child elements (SVG, images, tooltips)
    try {
      const img = el.querySelector('img[alt], img[title]');
      if (img) {
        text = (img.getAttribute('alt') || img.getAttribute('title') || '').trim();
        if (text) return text;
      }

      const svg = el.querySelector('svg');
      if (svg) {
        const svgLabel = svg.getAttribute('aria-label') || svg.getAttribute('data-icon') || '';
        if (svgLabel) return svgLabel.trim();
        const svgTitle = svg.querySelector('title');
        if (svgTitle && svgTitle.textContent) return svgTitle.textContent.trim();
      }
    } catch (e) {}

    // 2. Infer from identifiers & class names for icon-only buttons
    const idHint = [
      el.getAttribute('id') || '',
      el.getAttribute('data-testid') || '',
      el.getAttribute('name') || '',
      el.getAttribute('aria-description') || '',
      el.className && typeof el.className === 'string' ? el.className : ''
    ].join(' ').toLowerCase();

    if (idHint.includes('cart') || idHint.includes('basket') || idHint.includes('bag')) return '[Cart]';
    if (idHint.includes('close') || idHint.includes('dismiss') || idHint.includes('cross')) return '[Close]';
    if (idHint.includes('search')) return '[Search]';
    if (idHint.includes('account') || idHint.includes('profile') || idHint.includes('user') || idHint.includes('avatar')) return '[Account]';
    if (idHint.includes('menu') || idHint.includes('hamburger')) return '[Menu]';
    if (idHint.includes('location') || idHint.includes('pincode') || idHint.includes('address')) return '[Location]';
    if (idHint.includes('delete') || idHint.includes('trash') || idHint.includes('remove')) return '[Remove]';
    if (idHint.includes('filter')) return '[Filter]';

    return '';
  };

  const elements = [];
  let id = 0;
  const sel = 'a[href], button, input, select, textarea, summary, [role=button], [role=switch], [role=checkbox], [role=tab], [role=link], [onclick]';

  // Recursive element collector: pierces open Shadow DOM and accessible iframes
  const collectCandidates = (root, depth = 0) => {
    if (!root || depth > 5) return;
    try {
      if (root.querySelectorAll) {
        root.querySelectorAll(sel).forEach(el => processElement(el));
      }
    } catch (e) {}

    // Traverse children looking for shadow roots or iframes
    try {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
      while (walker.nextNode() && elements.length < 400) {
        const node = walker.currentNode;
        if (node.shadowRoot) {
          collectCandidates(node.shadowRoot, depth + 1);
        }
        if (node.tagName === 'IFRAME') {
          try {
            if (node.contentDocument && node.contentDocument.body) {
              collectCandidates(node.contentDocument.body, depth + 1);
            }
          } catch (crossOriginErr) {
            // Cross-origin iframe boundaries cannot be pierced
          }
        }
      }
    } catch (e) {}
  };

  const processElement = (el) => {
    if (!el || el.nodeType !== 1) return;
    const type = (el.getAttribute('type') || '').toLowerCase();
    const isToggle = type === 'checkbox' || type === 'radio' || ['switch', 'checkbox'].includes(el.getAttribute('role'));
    const vis = visible(el);
    if (!vis && !isToggle) return;
    if (type === 'hidden') return;

    let s;
    try {
      s = getComputedStyle(el);
    } catch (e) {
      return;
    }

    let text = isToggle ? labelFor(el).trim() : getSemanticLabel(el);
    const dpc = String(id++);
    try {
      el.setAttribute('data-dpc-id', dpc);
    } catch (e) {}

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
      id: dpc,
      tag: el.tagName.toLowerCase(),
      type,
      role: el.getAttribute('role') || '',
      text: text.slice(0, 200),
      href: el.getAttribute('href') || '',
      abs: el.href || '',
      checked: isToggle ? (el.checked === true || el.getAttribute('aria-checked') === 'true') : null,
      disabled: !!el.disabled,
      visible: vis,
      bbox: box(el),
      color: s.color,
      bg: effectiveBg(el),
      ownBg: s.backgroundColor,
      fontSize: parseFloat(s.fontSize) || 14,
      fontWeight: parseInt(s.fontWeight) || 400,
      textDecoration: s.textDecorationLine || 'none',
      cursor: s.cursor,
      sameOrigin: sameOrigin,
      sameDomain: sameDomain,
    });
  };

  // Start collection from root
  const rootNode = document.body || document.documentElement;
  if (rootNode) {
    collectCandidates(rootNode);
  }

  // Text walker for readability & OCR comparison
  const texts = [];
  if (rootNode) {
    try {
      const walker = document.createTreeWalker(rootNode, NodeFilter.SHOW_TEXT);
      const seen = new Set();
      while (walker.nextNode() && texts.length < 500) {
        const node = walker.currentNode;
        const t = (node.textContent || '').replace(/\s+/g, ' ').trim();
        if (t.length < 2) continue;
        const el = node.parentElement;
        if (!el || seen.has(el) || ['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG'].includes(el.tagName)) continue;
        seen.add(el);
        if (!visible(el)) continue;
        let s;
        try {
          s = getComputedStyle(el);
        } catch (e) {
          continue;
        }
        texts.push({
          text: (el.innerText || t).replace(/\s+/g, ' ').trim().slice(0, 400),
          tag: el.tagName.toLowerCase(),
          fontSize: parseFloat(s.fontSize) || 14,
          color: s.color,
          bg: effectiveBg(el),
          bbox: box(el)
        });
      }
    } catch (e) {}
  }

  // Overlays, Modals, and Blocking Backdrops
  const overlays = [];
  try {
    document.querySelectorAll('body *').forEach(el => {
      try {
        const s = getComputedStyle(el);
        const isFloating = ['fixed', 'sticky'].includes(s.position);
        const isDialog = el.getAttribute('role') === 'dialog' || el.getAttribute('role') === 'alertdialog' || el.getAttribute('aria-modal') === 'true';
        if ((!isFloating && !isDialog) || !visible(el)) return;
        const r = el.getBoundingClientRect();
        const cover = (Math.min(r.width, vw) * Math.min(r.height, vh)) / (vw * vh);
        if (cover > 0.08 || isDialog) {
          overlays.push({
            text: (el.innerText || '').replace(/\s+/g, ' ').slice(0, 300),
            cover: Math.round(cover * 100) / 100,
            bbox: box(el),
            isDialog: isDialog
          });
        }
      } catch (err) {}
    });
  } catch (e) {}

  const fullText = (document.body ? document.body.innerText : (document.documentElement ? document.documentElement.innerText : '')) || '';

  return {
    url: location.href,
    title: document.title || '',
    viewport: { w: vw, h: vh },
    scrollHeight: (document.documentElement ? document.documentElement.scrollHeight : 800),
    text: fullText.slice(0, 25000),
    elements,
    texts,
    overlays,
  };
}