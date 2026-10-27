/**
 * DarkShield — Side Panel Script
 * Displays detailed detection results with category explanations.
 */

document.addEventListener('DOMContentLoaded', async () => {
  const pageUrl = document.getElementById('pageUrl');
  const totalDetections = document.getElementById('totalDetections');
  const totalChunks = document.getElementById('totalChunks');
  const scanTime = document.getElementById('scanTime');
  const detectionList = document.getElementById('detectionList');
  const emptyState = document.getElementById('emptyState');
  const refreshBtn = document.getElementById('refreshBtn');

  // Category icons
  const CATEGORY_ICONS = {
    'Urgency or Scarcity': '⏰',
    'Confirmshaming': '😢',
    'Hidden Costs': '💰',
    'Trick Questions': '❓',
    'Roach Motel': '🪤',
    'Disguised Ads': '📢',
    'Misdirection': '🎯'
  };

  async function loadResults() {
    const data = await chrome.storage.local.get('scanResults');
    const results = data.scanResults;

    if (!results) {
      emptyState.style.display = 'block';
      return;
    }

    emptyState.style.display = 'none';

    // Update header
    pageUrl.textContent = results.url || 'Unknown page';
    totalDetections.textContent = results.detections.length;
    totalChunks.textContent = results.totalTextChunks || '—';

    // Calculate time
    if (results.timestamp) {
      const scanDate = new Date(results.timestamp);
      scanTime.textContent = scanDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // Render detection cards
    detectionList.innerHTML = '';

    if (results.detections.length === 0) {
      detectionList.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">✅</div>
          <p>No dark patterns detected!</p>
          <p class="empty-hint">This page appears to be clean.</p>
        </div>
      `;
      return;
    }

    // Sort by confidence (highest first)
    const sorted = [...results.detections].sort((a, b) => b.confidence - a.confidence);

    for (const [idx, detection] of sorted.entries()) {
      const card = document.createElement('div');
      card.className = 'detection-card';
      card.style.animationDelay = `${idx * 0.05}s`;

      const icon = CATEGORY_ICONS[detection.category] || '⚠️';
      const confidencePct = Math.round(detection.confidence * 100);

      card.innerHTML = `
        <div class="detection-card-header">
          <span class="category-badge" style="background: ${detection.color}">
            ${icon} ${detection.category}
          </span>
          <span class="confidence-badge">${confidencePct}% confidence</span>
        </div>
        <div class="detection-text" style="border-left-color: ${detection.color}">
          "${detection.text}"
        </div>
        <div class="detection-explanation">
          <strong>Why this is a dark pattern:</strong> ${detection.explanation}
        </div>
        ${detection.limeWords && detection.limeWords.length > 0 ? `
        <div class="lime-explanation" style="margin-top: 8px; padding-top: 8px; border-top: 1px dashed #e2e8f0; font-size: 11px; color: #64748b;">
          <strong>Model Attention (LIME):</strong> The network flagged this primarily because of these words: 
          ${detection.limeWords.map(w => `<span style="background: #fef08a; color: #854d0e; padding: 2px 4px; border-radius: 4px; font-weight: 500; margin-right: 4px;">${w}</span>`).join('')}
        </div>
        ` : ''}
      `;

      detectionList.appendChild(card);
    }
  }

  // Load on open
  await loadResults();

  // Listen for storage changes (live updates)
  chrome.storage.onChanged.addListener((changes) => {
    if (changes.scanResults) {
      loadResults();
    }
  });

  // Refresh button
  refreshBtn.addEventListener('click', async () => {
    refreshBtn.style.transform = 'rotate(360deg)';
    refreshBtn.style.transition = 'transform 0.5s ease';
    await loadResults();
    setTimeout(() => {
      refreshBtn.style.transform = '';
    }, 500);
  });
});
