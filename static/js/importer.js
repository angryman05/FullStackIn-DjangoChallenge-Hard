/**
 * Peacetime Citizen Importer / Control Panel
 * Handles: Starting background import task, polling /people/import/status/ every 1s,
 * updating progress bar (determinate/indeterminate), counters, elapsed timer, error panel with retry.
 */

document.addEventListener('DOMContentLoaded', () => {
  const startBtn = document.getElementById('start-import-btn');
  const retryBtn = document.getElementById('retry-import-btn');
  const statusBadge = document.getElementById('import-status-badge');
  const progressBar = document.getElementById('import-progress-bar');
  const progressPercent = document.getElementById('progress-percent');
  const counterDownloaded = document.getElementById('counter-downloaded');
  const counterSaved = document.getElementById('counter-saved');
  const counterFailed = document.getElementById('counter-failed');
  const elapsedTimeEl = document.getElementById('elapsed-time');
  const errorPanel = document.getElementById('error-panel');
  const errorMsgText = document.getElementById('error-message-text');
  const keyBanner = document.getElementById('secret-key-banner');
  const keyChip = document.getElementById('secret-key-chip');

  let pollInterval = null;
  let timerInterval = null;
  let startTime = null;

  function formatTime(ms) {
    const totalSec = Math.floor(ms / 1000);
    const mins = Math.floor(totalSec / 60).toString().padStart(2, '0');
    const secs = (totalSec % 60).toString().padStart(2, '0');
    return `${mins}:${secs}`;
  }

  function startTimer() {
    startTime = Date.now();
    elapsedTimeEl.textContent = '00:00';
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      elapsedTimeEl.textContent = formatTime(Date.now() - startTime);
    }, 1000);
  }

  function stopTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function updateStatus(status) {
    statusBadge.className = `badge badge-${status.toLowerCase()}`;
    statusBadge.textContent = status.toUpperCase();
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    stopTimer();
  }

  async function pollStatus() {
    try {
      const res = await fetch('/people/import/status/', {
        headers: { 'Accept': 'application/json' }
      });

      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}: Failed to fetch status`);
      }

      const data = await res.json();
      
      // Update counters (textContent for safety)
      counterDownloaded.textContent = data.processed ?? 0;
      counterSaved.textContent = data.processed ?? 0;
      counterFailed.textContent = data.failed ?? 0;

      // Update progress bar
      if (data.total && data.total > 0) {
        progressBar.max = data.total;
        progressBar.value = data.processed || 0;
        const pct = Math.min(100, Math.round(((data.processed || 0) / data.total) * 100));
        progressPercent.textContent = `${pct}% (${data.processed}/${data.total})`;
      } else if (data.status === 'running') {
        progressBar.removeAttribute('value');
        progressPercent.textContent = 'Syncing...';
      }

      // Handle status states
      if (data.status === 'running') {
        updateStatus('running');
        startBtn.disabled = true;
      } else if (data.status === 'done') {
        updateStatus('done');
        startBtn.disabled = false;
        stopPolling();
        window.Toast?.show('Peacetime citizen import complete!', 'success');

        if (data.key_found && data.key_value && keyBanner && keyChip) {
          keyChip.textContent = data.key_value;
          keyChip.dataset.copy = data.key_value;
          keyBanner.style.display = 'block';
          window.Toast?.show(`Key discovered from Hellstorm Fireburn: ${data.key_value}`, 'warning');
        }
      } else if (data.status === 'error') {
        updateStatus('error');
        startBtn.disabled = false;
        stopPolling();
        showError(data.error || 'Import operation failed');
      }
    } catch (err) {
      stopPolling();
      startBtn.disabled = false;
      updateStatus('error');
      showError(err.message);
      window.Toast?.show(err.message, 'error');
    }
  }

  function showError(msg) {
    if (errorPanel && errorMsgText) {
      errorMsgText.textContent = msg;
      errorPanel.classList.add('visible');
    }
  }

  function hideError() {
    if (errorPanel) {
      errorPanel.classList.remove('visible');
    }
  }

  async function triggerImport() {
    hideError();
    startBtn.disabled = true;
    updateStatus('running');
    progressBar.removeAttribute('value'); // Indeterminate
    progressPercent.textContent = 'Initiating download...';
    startTimer();

    try {
      const csrf = window.getCsrfToken ? window.getCsrfToken() : '';
      const res = await fetch('/people/import/start/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      });

      if (!res.ok && res.status !== 202) {
        throw new Error(`Server returned ${res.status}: Import rejected.`);
      }

      window.Toast?.show('Background import job dispatched.', 'info');
      
      // Start polling every 1 second
      stopPolling();
      pollInterval = setInterval(pollStatus, 1000);
      pollStatus();
    } catch (err) {
      startBtn.disabled = false;
      updateStatus('error');
      stopTimer();
      showError(err.message);
      window.Toast?.show(err.message, 'error');
    }
  }

  if (startBtn) {
    startBtn.addEventListener('click', (e) => {
      e.preventDefault();
      triggerImport();
    });
  }

  if (retryBtn) {
    retryBtn.addEventListener('click', (e) => {
      e.preventDefault();
      triggerImport();
    });
  }

  // Initial check on load: if already running or has data, inspect once
  pollStatus();
});
