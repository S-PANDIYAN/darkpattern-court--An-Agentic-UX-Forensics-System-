/**
 * Set-of-Marks (SoM) Visual Annotation Script.
 * Overlays numbered, colored badges on all interactive controls (buttons, links, inputs)
 * directly in the browser DOM before taking screenshots for LLaVA-13B and Court exhibits.
 */
(() => {
  const OVERLAY_ID = '__dpc_som_overlay__';
  const existing = document.getElementById(OVERLAY_ID);
  if (existing) existing.remove();

  const container = document.createElement('div');
  container.id = OVERLAY_ID;
  container.style.position = 'absolute';
  container.style.top = '0';
  container.style.left = '0';
  container.style.width = '100%';
  container.style.height = document.documentElement.scrollHeight + 'px';
  container.style.pointerEvents = 'none';
  container.style.zIndex = '2147483647';
  container.style.fontFamily = 'monospace, sans-serif';

  // Distinct palette matching Set-of-Marks visual prompting
  const PALETTE = [
    { bg: '#ef4444', text: '#ffffff' }, // red
    { bg: '#22c55e', text: '#ffffff' }, // green
    { bg: '#3b82f6', text: '#ffffff' }, // blue
    { bg: '#f59e0b', text: '#000000' }, // amber
    { bg: '#8b5cf6', text: '#ffffff' }, // purple
    { bg: '#ec4899', text: '#ffffff' }, // pink
    { bg: '#06b6d4', text: '#000000' }, // cyan
    { bg: '#10b981', text: '#ffffff' }, // emerald
  ];

  const sx = window.scrollX, sy = window.scrollY;
  const elements = document.querySelectorAll('[data-dpc-id]');

  elements.forEach((el, index) => {
    const dpcId = el.getAttribute('data-dpc-id');
    const r = el.getBoundingClientRect();
    if (r.width <= 2 || r.height <= 2) return;
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity || '1') < 0.1) return;

    const color = PALETTE[index % PALETTE.length];

    // Bounding box border
    const box = document.createElement('div');
    box.style.position = 'absolute';
    box.style.left = (r.x + sx) + 'px';
    box.style.top = (r.y + sy) + 'px';
    box.style.width = r.width + 'px';
    box.style.height = r.height + 'px';
    box.style.border = '2px solid ' + color.bg;
    box.style.boxSizing = 'border-box';
    box.style.borderRadius = '3px';
    box.style.pointerEvents = 'none';

    // Numbered Badge in top-left or top-right
    const badge = document.createElement('span');
    badge.innerText = dpcId;
    badge.style.position = 'absolute';
    badge.style.top = '-12px';
    badge.style.left = '0px';
    badge.style.backgroundColor = color.bg;
    badge.style.color = color.text;
    badge.style.fontSize = '11px';
    badge.style.fontWeight = 'bold';
    badge.style.lineHeight = '14px';
    badge.style.padding = '0 4px';
    badge.style.borderRadius = '3px';
    badge.style.boxShadow = '0 1px 3px rgba(0,0,0,0.4)';
    badge.style.pointerEvents = 'none';

    box.appendChild(badge);
    container.appendChild(box);
  });

  document.body.appendChild(container);
  return { markedCount: elements.length };
})();
