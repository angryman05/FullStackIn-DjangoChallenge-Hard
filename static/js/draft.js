/**
 * Phase 2 Soldier Drafting War Room
 * Handles: Live batch telemetry polling (/draft/status/), triggering draft tasks,
 * rendering batch status cards, and updating military rank distribution.
 */

document.addEventListener('DOMContentLoaded', () => {
  const startDraftBtn = document.getElementById('start-draft-btn');
  const statusBadge = document.getElementById('draft-status-badge');
  const counterDrafted = document.getElementById('counter-draft-drafted');
  const counterRegistered = document.getElementById('counter-draft-registered');
  const batchContainer = document.getElementById('batch-cards-container');
  const ranksContainer = document.getElementById('rank-breakdown-container');

  let pollInterval = null;

  function updateStatus(status) {
    if (!statusBadge) return;
    statusBadge.className = `badge badge-${status.toLowerCase()}`;
    statusBadge.textContent = status.toUpperCase();
  }

  function renderBatches(batches) {
    if (!batchContainer) return;
    
    if (!batches || batches.length === 0) {
      batchContainer.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1; padding: 2rem;">
          <p style="color: var(--text-muted);">No drafting batches initiated yet. Click "Mobilize Army & Start Drafting" above.</p>
        </div>
      `;
      return;
    }

    // Safely update DOM using elements
    batchContainer.textContent = ''; // Clear container safely
    batches.forEach(b => {
      const card = document.createElement('div');
      card.className = 'batch-card';

      const top = document.createElement('div');
      top.className = 'batch-top';

      const numSpan = document.createElement('span');
      numSpan.className = 'batch-num';
      numSpan.textContent = `Batch #${b.number}`;

      const badge = document.createElement('span');
      badge.className = `badge badge-${b.status}`;
      badge.textContent = b.status.toUpperCase();

      top.appendChild(numSpan);
      top.appendChild(badge);
      card.appendChild(top);

      const details = document.createElement('div');
      details.className = 'batch-details';
      
      const attemptsP = document.createElement('p');
      attemptsP.textContent = `Attempts: ${b.attempts}`;
      const countP = document.createElement('p');
      countP.textContent = `Soldiers: ${b.people_count}`;

      details.appendChild(attemptsP);
      details.appendChild(countP);
      card.appendChild(details);

      if (b.error) {
        const errDiv = document.createElement('div');
        errDiv.className = 'batch-error';
        errDiv.textContent = b.error;
        card.appendChild(errDiv);
      }

      batchContainer.appendChild(card);
    });
  }

  function renderRanks(ranks) {
    if (!ranksContainer) return;
    ranksContainer.textContent = '';

    if (!ranks || ranks.length === 0) {
      const p = document.createElement('p');
      p.className = 'text-dim';
      p.textContent = 'No ranks assigned yet.';
      ranksContainer.appendChild(p);
      return;
    }

    ranks.forEach(r => {
      const chip = document.createElement('div');
      chip.className = 'filter-chip active';
      chip.textContent = `${r.rank}: ${r.count} soldiers`;
      ranksContainer.appendChild(chip);
    });
  }

  async function pollStatus() {
    try {
      const res = await fetch('/draft/status/', {
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();

      if (counterRegistered) counterRegistered.textContent = data.registered ?? 0;
      if (counterDrafted) counterDrafted.textContent = data.drafted ?? 0;

      renderBatches(data.batches);
      renderRanks(data.ranks);

      const isBusy = data.batches && data.batches.some(b => 
        ['downloading', 'retrying', 'downloaded'].includes(b.status)
      );

      if (isBusy) {
        updateStatus('running');
        if (startDraftBtn) startDraftBtn.disabled = true;
      } else if (data.batches && data.batches.length > 0) {
        const hasFailed = data.batches.some(b => b.status === 'failed');
        if (hasFailed) {
          updateStatus('error');
        } else {
          updateStatus('done');
        }
        if (startDraftBtn) startDraftBtn.disabled = false;
      } else {
        updateStatus('idle');
        if (startDraftBtn) startDraftBtn.disabled = false;
      }
    } catch (err) {
      console.error('Draft status polling error:', err);
    }
  }

  async function startDrafting() {
    if (startDraftBtn) startDraftBtn.disabled = true;
    updateStatus('running');

    try {
      const csrf = window.getCsrfToken ? window.getCsrfToken() : '';
      const res = await fetch('/draft/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      });

      if (!res.ok && res.status !== 202) {
        throw new Error(`Server returned ${res.status}`);
      }

      window.Toast?.show('Soldier drafting initiated in the background.', 'success');
      
      if (pollInterval) clearInterval(pollInterval);
      pollInterval = setInterval(pollStatus, 1500);
      pollStatus();
    } catch (err) {
      if (startDraftBtn) startDraftBtn.disabled = false;
      updateStatus('error');
      window.Toast?.show(`Failed to start draft: ${err.message}`, 'error');
    }
  }

  if (startDraftBtn) {
    startDraftBtn.addEventListener('click', (e) => {
      e.preventDefault();
      startDrafting();
    });
  }

  // Poll immediately on view load
  pollStatus();
  pollInterval = setInterval(pollStatus, 2000);
});
