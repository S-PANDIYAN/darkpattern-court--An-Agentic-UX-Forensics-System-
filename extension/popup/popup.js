/**
 * DarkPattern Court — Extension Popup Script
 * Real-time DOM text extraction, local DistilBERT ML inference, and Court PDF export.
 */

document.addEventListener('DOMContentLoaded', async () => {
  const scanBtn = document.getElementById('scanBtn');
  const statusCard = document.getElementById('statusCard');
  const statusIcon = document.getElementById('statusIcon');
  const statusText = document.getElementById('statusText');
  const resultsSection = document.getElementById('resultsSection');
  const resultsCount = document.getElementById('resultsCount');
  const resultsBreakdown = document.getElementById('resultsBreakdown');
  const detailsBtn = document.getElementById('detailsBtn');
  const courtBtn = document.getElementById('courtBtn');
  const clearBtn = document.getElementById('clearBtn');
  const courtCard = document.getElementById('courtCard');
  const courtBadge = document.getElementById('courtBadge');
  const courtVerdict = document.getElementById('courtVerdict');
  const courtScore = document.getElementById('courtScore');
  const courtPdfLink = document.getElementById('courtPdfLink');
  const courtHtmlLink = document.getElementById('courtHtmlLink');
  const statusPillRight = document.getElementById('statusPillRight');
  let currentScanData = null;

  // Category colors
  const CATEGORY_COLORS = {
    'Urgency or Scarcity': '#ef4444',
    'Confirmshaming': '#22c55e',
    'Hidden Costs': '#f97316',
    'Trick Questions': '#8b5cf6',
    'Roach Motel': '#3b82f6',
    'Disguised Ads': '#eab308',
    'Misdirection': '#ec4899'
  };

  // Check for existing results
  const data = await chrome.storage.local.get('scanResults');
  if (data.scanResults) {
    displayResults(data.scanResults);
  }

  // Scan Button
  scanBtn.addEventListener('click', async () => {
    scanBtn.disabled = true;
    if (statusPillRight) {
      statusPillRight.innerHTML = '<span class="active-dot" style="background:#0ea5e9;box-shadow:0 0 6px #0ea5e9;"></span><span class="active-text" style="color:#38bdf8;">Scanning</span>';
    }
    statusCard.className = 'status-card scanning';
    statusIcon.textContent = '🔄';
    statusText.textContent = 'Scanning page for dark patterns...';
    resultsSection.classList.add('hidden');

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      if (!tab || tab.url?.startsWith('chrome://') || tab.url?.startsWith('chrome-extension://')) {
        statusCard.className = 'status-card';
        statusIcon.textContent = '⚠️';
        statusText.textContent = 'Cannot scan browser internal pages';
        scanBtn.disabled = false;
        return;
      }

      // Inject content script if not already
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content.js']
        });
        await chrome.scripting.insertCSS({
          target: { tabId: tab.id },
          files: ['content.css']
        });
      } catch (e) {
        // Content script may already be injected
      }

      // Trigger scan
      const response = await chrome.tabs.sendMessage(tab.id, { type: 'RUN_SCAN' });
      
      if (response && !response.error) {
        displayResults(response);
      } else {
        statusCard.className = 'status-card';
        statusIcon.textContent = '❌';
        statusText.textContent = 'Scan failed. Try refreshing the page.';
      }
    } catch (err) {
      statusCard.className = 'status-card';
      statusIcon.textContent = '❌';
      statusText.textContent = 'Error: ' + err.message;
    }

    if (statusPillRight) {
      statusPillRight.innerHTML = '<span class="active-dot"></span><span class="active-text">Active</span>';
    }
    scanBtn.disabled = false;
  });

  // Display results
  function displayResults(data) {
    const count = data.detections.length;

    if (count === 0) {
      statusCard.className = 'status-card clean';
      statusIcon.textContent = '✅';
      statusText.textContent = `No dark patterns detected on this page!`;
      resultsSection.classList.add('hidden');
    } else {
      statusCard.className = 'status-card found';
      statusIcon.textContent = '⚠️';
      statusText.textContent = `Found ${count} dark pattern${count > 1 ? 's' : ''} on this page`;
      
      // Show results breakdown
      resultsSection.classList.remove('hidden');
      resultsCount.textContent = count;

      // Group by category
      const grouped = {};
      for (const d of data.detections) {
        grouped[d.category] = (grouped[d.category] || 0) + 1;
      }

      resultsBreakdown.innerHTML = '';
      for (const [category, num] of Object.entries(grouped).sort((a, b) => b[1] - a[1])) {
        const row = document.createElement('div');
        row.className = 'result-row';
        row.innerHTML = `
          <span class="result-label">
            <span class="result-dot" style="background: ${CATEGORY_COLORS[category] || '#64748b'}"></span>
            ${category}
          </span>
          <span class="result-number">${num}</span>
        `;
        resultsBreakdown.appendChild(row);
      }
    }

    currentScanData = data;
    detailsBtn.disabled = count === 0;
    if (courtBtn) courtBtn.disabled = count === 0;
    clearBtn.disabled = false;
  }

  // Details button — open side panel
  detailsBtn.addEventListener('click', async () => {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab) {
        await chrome.sidePanel.open({ windowId: tab.windowId });
      }
    } catch (e) {
      console.error('Failed to open side panel:', e);
    }
  });

  // Court Report button — send detections to DarkPattern Court backend
  if (courtBtn) {
    courtBtn.addEventListener('click', async () => {
      if (!currentScanData || !currentScanData.detections || currentScanData.detections.length === 0) return;
      courtBtn.disabled = true;
      courtBtn.textContent = '⏳ Generating PDF...';
      courtCard.classList.remove('hidden');
      courtVerdict.textContent = '⚖️ Building legal indictment...';
      courtScore.textContent = 'Contacting DarkPattern Court backend...';

      try {
        const payload = {
          url: currentScanData.url || 'https://live-website.com',
          title: currentScanData.title || 'Live Web Audit',
          detections: currentScanData.detections.map(d => ({
            category: d.category,
            text: d.text,
            confidence: d.confidence || 0.95,
            explanation: d.explanation || '',
            color: d.color || '',
            limeWords: d.limeWords || []
          }))
        };

        const res = await fetch('http://localhost:8000/api/cases/from_extension', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          throw new Error(`Server status ${res.status}: ${res.statusText}`);
        }

        const caseData = await res.json();
        if (courtBadge) {
          courtBadge.textContent = caseData.verdict.label;
          if (caseData.verdict.label === 'GUILTY') {
            courtBadge.style.background = 'rgba(239, 68, 68, 0.25)';
            courtBadge.style.color = '#fca5a5';
            courtBadge.style.borderColor = 'rgba(239, 68, 68, 0.4)';
          } else {
            courtBadge.style.background = 'rgba(16, 185, 129, 0.25)';
            courtBadge.style.color = '#6ee7b7';
            courtBadge.style.borderColor = 'rgba(16, 185, 129, 0.4)';
          }
        }
        courtVerdict.textContent = `⚖️ ${caseData.verdict.label}: ${caseData.verdict.summary}`;
        courtScore.textContent = `Score: ${caseData.verdict.manipulation_score}/100 (Grade ${caseData.verdict.grade}) · ${caseData.charges_count} charges filed`;
        courtPdfLink.href = `http://localhost:8000${caseData.report_pdf_url}`;
        courtHtmlLink.href = `http://localhost:8000${caseData.report_html_url}`;
        courtBtn.textContent = '✅ Court PDF Generated';

        // Open PDF in new browser tab
        chrome.tabs.create({ url: `http://localhost:8000${caseData.report_pdf_url}` });
      } catch (err) {
        if (courtBadge) courtBadge.textContent = 'OFFLINE';
        courtVerdict.textContent = '⚠️ Could not connect to backend';
        courtScore.textContent = 'Ensure backend is running: uvicorn app.main:app --port 8000';
        courtBtn.disabled = false;
        courtBtn.textContent = '⚖️ Export Court PDF';
        console.error('Court export error:', err);
      }
    });
  }

  // Clear button
  clearBtn.addEventListener('click', async () => {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab) {
        await chrome.tabs.sendMessage(tab.id, { type: 'CLEAR_HIGHLIGHTS' });
      }
      await chrome.storage.local.remove('scanResults');
      await chrome.action.setBadgeText({ text: '' });

      statusCard.className = 'status-card';
      statusIcon.textContent = '🔍';
      statusText.textContent = 'Ready to audit this webpage';
      resultsSection.classList.add('hidden');
      if (courtCard) courtCard.classList.add('hidden');
      currentScanData = null;
      detailsBtn.disabled = true;
      if (courtBtn) {
        courtBtn.disabled = true;
        courtBtn.textContent = '⚖️ Export Court PDF';
      }
      clearBtn.disabled = true;
    } catch (e) {
      console.error('Failed to clear:', e);
    }
  });
});
