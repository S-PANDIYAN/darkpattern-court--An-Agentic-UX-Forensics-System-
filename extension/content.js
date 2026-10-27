/**
 * DarkShield — Content Script
 * Extracts visible text from the DOM, classifies each chunk using
 * ML inference (DistilBERT via ONNX) in the background worker,
 * highlights detected dark patterns, and reports results.
 *
 * False positive reduction is handled via ML-native techniques:
 *   1. DOM pre-filtering (feature engineering — curate model input)
 *   2. Per-category confidence thresholds (calibrated from test-set precision)
 *   3. Margin-based uncertainty filtering (model's own probability distribution)
 */

(() => {
  'use strict';

  // Prevent double-injection
  if (window.__darkshield_injected) return;
  window.__darkshield_injected = true;

  // ============================================================
  // CATEGORY METADATA & CALIBRATED THRESHOLDS
  // ============================================================

  /**
   * Per-category confidence thresholds, calibrated from the model's
   * test-set precision scores (FINAL_REPORT.md §4.3).
   *
   * Categories with lower precision need a higher bar to trigger,
   * reducing false positives where the model is weakest.
   *
   * Precision → Threshold mapping rationale:
   *   - High precision (>0.92):  keep threshold at 0.90 (model is reliable)
   *   - Medium precision (0.70–0.92): raise to 0.95
   *   - Low precision (<0.70):   raise to 0.97 (model struggles here)
   */
  const CATEGORY_METADATA = {
    'Urgency or Scarcity': {
      color: '#ef4444',
      explanation: 'Creates a false sense of urgency or scarcity to pressure you into making a quick decision.',
      threshold: 0.90   // Precision: 0.923 — high
    },
    'Confirmshaming': {
      color: '#22c55e',
      explanation: 'Uses guilt-laden or shame-inducing language to pressure you into accepting an offer.',
      threshold: 0.90   // Precision: 0.958 — high
    },
    'Hidden Costs': {
      color: '#f97316',
      explanation: 'Reveals hidden fees or charges late in the checkout process that were not disclosed upfront.',
      threshold: 0.97   // Precision: 1.000 — but only 0.500 recall, very few samples
    },
    'Trick Questions': {
      color: '#8b5cf6',
      explanation: 'Uses confusing double negatives or ambiguous phrasing to trick you into agreeing to something.',
      threshold: 0.95   // Precision: 0.800 — medium
    },
    'Roach Motel': {
      color: '#3b82f6',
      explanation: 'Makes it very easy to sign up but deliberately difficult to cancel or leave.',
      threshold: 0.97   // Precision: 0.667 — low
    },
    'Disguised Ads': {
      color: '#eab308',
      explanation: 'Disguises advertisements or promotional content to look like organic content or user activity.',
      threshold: 0.90   // Precision: 0.959 — high
    },
    'Misdirection': {
      color: '#ec4899',
      explanation: 'Directs your attention away from what you wanted to do, pushing you toward a different action.',
      threshold: 0.95   // Precision: 0.703 — low-medium
    }
  };

  /**
   * Minimum margin (gap) between the top predicted class score and
   * the Benign class score. If the model assigns a high probability
   * to both the dark pattern class AND Benign, it's uncertain —
   * the prediction is unreliable and should be suppressed.
   *
   * Example: if model says P(Urgency)=0.55, P(Benign)=0.35,
   * margin = 0.20 < 0.70 → suppressed (model is torn).
   *
   * A genuine dark pattern typically has margin > 0.80.
   */
  const MIN_MARGIN_OVER_BENIGN = 0.70;

  // ============================================================
  // DOM EXTRACTION (Feature Engineering — curate model input)
  // ============================================================

  function extractTextNodes() {
    const targetTags = ['p', 'span', 'h1', 'h2', 'h3', 'h4', 'a', 'button', 'label', 'li', 'div'];
    const elements = [];

    for (const tag of targetTags) {
      for (const el of document.querySelectorAll(tag)) {
        // Skip massive containers to avoid concatenating text across the whole page
        if (tag === 'div' && el.querySelectorAll('p, div, ul, li, h1, h2, h3, a').length > 0) {
          continue;
        }

        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;

        // Ensure element has physical dimensions and is not intentionally positioned off-screen (e.g. .a-offscreen)
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0 || rect.left < -999 || rect.top < -999) continue;

        // ── DOM pre-filtering: skip structural/non-content elements ──
        // These aren't the kind of text the model was trained on.
        // Sending navigation links, breadcrumbs, or header/footer chrome
        // to a dark-pattern classifier produces garbage-in/garbage-out.
        if (el.closest('nav, header, footer, script, style, noscript')) continue;
        if (el.closest('[role="navigation"], [role="banner"], [role="contentinfo"]')) continue;
        if (el.closest('[class*="breadcrumb"], [id*="breadcrumb"]')) continue;

        const text = el.textContent?.trim().replace(/\s+/g, ' ');
        if (!text || text.length < 10 || text.length > 300) continue;

        elements.push({ element: el, text });
      }
    }

    // Deduplicate: keep only the most specific element for a given text.
    // If an element contains another element with the exact same text, drop the parent.
    const elementsToScan = [];
    for (const item of elements) {
      const isDuplicateParent = elements.some(other => 
        other !== item && item.element.contains(other.element) && item.text === other.text
      );
      if (!isDuplicateParent) {
        elementsToScan.push(item);
      }
    }

    return elementsToScan;
  }

  // ============================================================
  // HIGHLIGHTING
  // ============================================================

  function highlightElement(element, detection) {
    element.style.outline = `3px solid ${detection.color}`;
    element.style.outlineOffset = '2px';
    element.style.backgroundColor = `${detection.color}22`; // Subtle background to ensure visibility if outline is clipped
    
    if (window.getComputedStyle(element).position === 'static') {
      element.style.position = 'relative';
    }
    
    element.style.transition = 'outline 0.3s ease, background-color 0.3s ease';
    element.dataset.darkshieldCategory = detection.category;
    element.dataset.darkshieldConfidence = detection.confidence;
    element.classList.add('darkshield-flagged');

    const badge = document.createElement('div');
    badge.className = 'darkshield-badge';
    badge.textContent = `⚠️ ${detection.category}`;
    badge.style.cssText = `
      position: absolute;
      top: -28px;
      right: 0;
      background: ${detection.color};
      color: white;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      z-index: 999999;
      white-space: nowrap;
      pointer-events: none;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      animation: darkshieldFadeIn 0.3s ease;
    `;
    element.appendChild(badge);
  }

  function clearHighlights() {
    for (const el of document.querySelectorAll('.darkshield-flagged')) {
      el.style.outline = '';
      el.style.outlineOffset = '';
      el.style.backgroundColor = '';
      if (el.style.position === 'relative' && !el.dataset.originalPosition) {
        el.style.position = '';
      }
      delete el.dataset.darkshieldCategory;
      delete el.dataset.darkshieldConfidence;
      el.classList.remove('darkshield-flagged');
    }
    for (const badge of document.querySelectorAll('.darkshield-badge')) {
      badge.remove();
    }
  }

  // ============================================================
  // SCAN ORCHESTRATION
  // ============================================================

  async function runScan() {
    clearHighlights();

    const textNodes = extractTextNodes();
    const detections = [];
    const BATCH_SIZE = 32;

    for (let i = 0; i < textNodes.length; i += BATCH_SIZE) {
      const batch = textNodes.slice(i, i + BATCH_SIZE);
      const texts = batch.map(b => b.text);

      try {
        const response = await chrome.runtime.sendMessage({ type: 'RUN_INFERENCE', texts });
        if (response && response.success && response.predictions) {
          response.predictions.forEach((prediction, index) => {
            const label = prediction.label;
            const score = prediction.score;
            const benignScore = prediction.benignScore ?? 0;
            
            if (label === 'Benign') return;

            const meta = CATEGORY_METADATA[label];
            if (!meta) return;

            // ── ML-native filter 1: Per-category calibrated threshold ──
            // Uses category-specific thresholds derived from test-set precision.
            if (score < meta.threshold) return;

            // ── ML-native filter 2: Margin over Benign class ──
            // If the model's own probability distribution shows it's
            // nearly as confident about Benign as the predicted class,
            // the prediction is unreliable. This uses the model's OWN
            // uncertainty — not an external rule.
            const margin = score - benignScore;
            if (margin < MIN_MARGIN_OVER_BENIGN) return;

            const result = {
              category: label,
              confidence: Math.round(score * 100) / 100,
              color: meta.color,
              explanation: meta.explanation,
              limeWords: prediction.limeWords || []
            };
            
            highlightElement(batch[index].element, result);
            detections.push({
              text: batch[index].text.substring(0, 200),
              category: result.category,
              confidence: result.confidence,
              color: result.color,
              explanation: result.explanation,
              limeWords: result.limeWords
            });
          });
        }
      } catch (err) {
        console.error('Inference error from background:', err);
      }
    }

    const scanData = {
      url: window.location.href,
      title: document.title,
      timestamp: new Date().toISOString(),
      totalTextChunks: textNodes.length,
      detections
    };

    try {
      await chrome.runtime.sendMessage({ type: 'SCAN_COMPLETE', data: scanData });
    } catch (e) {
      console.log('DarkShield: Could not report results:', e.message);
    }

    return scanData;
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'RUN_SCAN') {
      runScan().then(data => sendResponse(data)).catch(err => sendResponse({ error: err.message }));
      return true;
    }

    if (message.type === 'CLEAR_HIGHLIGHTS') {
      clearHighlights();
      sendResponse({ success: true });
      return true;
    }
  });

})();
