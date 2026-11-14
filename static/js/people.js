/**
 * Registered People Table Script
 * Handles: Client-side instant search, accessible table column sorting (Modern Web Guidance),
 * Hellstorm Fireburn row highlight, empty state toggling.
 */

document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('people-search-input');
  const table = document.getElementById('people-table');
  const tbody = table ? table.querySelector('tbody') : null;
  const statusAnnouncer = document.getElementById('table-status-announcer');
  const matchCountEl = document.getElementById('search-match-count');
  const noMatchesRow = document.getElementById('no-search-matches-row');

  if (!table || !tbody) return;

  const dataRows = Array.from(tbody.querySelectorAll('tr:not(.helper-row)'));

  // 1. Client-Side Instant Search
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase().trim();
      let matchCount = 0;

      dataRows.forEach(row => {
        const text = row.textContent.toLowerCase();
        const matches = text.includes(query);
        row.style.display = matches ? '' : 'none';
        if (matches) matchCount++;
      });

      if (matchCountEl) {
        matchCountEl.textContent = query ? `${matchCount} matches` : '';
      }

      if (noMatchesRow) {
        noMatchesRow.style.display = (matchCount === 0 && dataRows.length > 0) ? '' : 'none';
      }

      if (statusAnnouncer) {
        statusAnnouncer.textContent = `Showing ${matchCount} matching citizens.`;
      }
    });
  }

  // 2. Client-Side Accessible Column Sorting (complies with Modern Web Guidance)
  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

  const headers = table.querySelectorAll('th:has(> button)');
  headers.forEach(th => {
    const btn = th.querySelector('button');
    btn.addEventListener('click', () => {
      const colIndex = th.cellIndex;
      const colType = th.dataset.type || 'text';
      const currentSort = th.getAttribute('aria-sort');
      const newDirection = currentSort === 'ascending' ? 'descending' : 'ascending';

      // Remove aria-sort from all headers
      table.querySelectorAll('th').forEach(h => h.removeAttribute('aria-sort'));
      th.setAttribute('aria-sort', newDirection);

      const factor = newDirection === 'ascending' ? 1 : -1;

      // Stable sort of rows
      const sortedRows = [...dataRows].sort((rowA, rowB) => {
        const cellA = rowA.cells[colIndex];
        const cellB = rowB.cells[colIndex];
        const valA = cellA?.dataset.value ?? cellA?.textContent.trim() ?? '';
        const valB = cellB?.dataset.value ?? cellB?.textContent.trim() ?? '';

        if (colType === 'number') {
          const numA = parseFloat(valA) || 0;
          const numB = parseFloat(valB) || 0;
          return factor * (numA - numB);
        }
        return factor * collator.compare(valA, valB);
      });

      // Move existing rows in DOM order without rebuilding innerHTML
      sortedRows.forEach(row => tbody.appendChild(row));

      if (statusAnnouncer) {
        statusAnnouncer.textContent = `Sorted by ${btn.textContent.trim()}, ${newDirection}.`;
      }
    });
  });
});
