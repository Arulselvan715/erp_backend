/* ============================================================
   MINI ERP — Client-Side JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initSidebar();
  initFlashMessages();
  initConfirmDialogs();
  initTableSearch();
  initDynamicLineItems();
  initModals();
});

/* ============================================================
   1. DARK / LIGHT THEME TOGGLE
   ============================================================ */
function initThemeToggle() {
  const toggle = document.getElementById('theme-toggle');
  if (!toggle) return;

  const saved = localStorage.getItem('erp-theme') || 'dark';
  applyTheme(saved);

  toggle.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem('erp-theme', next);
  });
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('theme-icon');
  if (icon) {
    icon.textContent = theme === 'dark' ? '☀️' : '🌙';
  }
}

/* ============================================================
   2. SIDEBAR TOGGLE (MOBILE)
   ============================================================ */
function initSidebar() {
  const btn = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');

  if (!btn || !sidebar) return;

  btn.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('active');
  });

  if (overlay) {
    overlay.addEventListener('click', () => {
      sidebar.classList.remove('open');
      overlay.classList.remove('active');
    });
  }
}

/* ============================================================
   3. FLASH MESSAGE AUTO-DISMISS
   ============================================================ */
function initFlashMessages() {
  const container = document.querySelector('.flash-container');
  if (!container) return;

  container.querySelectorAll('.flash-msg').forEach((msg, i) => {
    // Auto-dismiss after 5 seconds (staggered)
    setTimeout(() => dismissFlash(msg), 5000 + i * 500);

    // Click to dismiss
    msg.addEventListener('click', () => dismissFlash(msg));

    // Close button
    const closeBtn = msg.querySelector('.flash-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        dismissFlash(msg);
      });
    }
  });
}

function dismissFlash(el) {
  el.style.opacity = '0';
  el.style.transform = 'translateX(40px)';
  el.style.transition = 'all .3s ease';
  setTimeout(() => el.remove(), 300);
}

/* Show a flash message programmatically */
function showFlash(message, type = 'info') {
  let container = document.querySelector('.flash-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'flash-container';
    document.body.appendChild(container);
  }

  const icons = { success: '✓', error: '✗', warning: '⚠', info: 'ℹ' };
  const msg = document.createElement('div');
  msg.className = `flash-msg flash-${type}`;
  msg.innerHTML = `
    <span>${icons[type] || 'ℹ'}</span>
    <span>${message}</span>
    <button class="flash-close">&times;</button>
  `;

  container.appendChild(msg);

  msg.addEventListener('click', () => dismissFlash(msg));
  msg.querySelector('.flash-close').addEventListener('click', (e) => {
    e.stopPropagation();
    dismissFlash(msg);
  });

  setTimeout(() => dismissFlash(msg), 5000);
}

/* ============================================================
   4. CONFIRMATION DIALOGS
   ============================================================ */
function initConfirmDialogs() {
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', (e) => {
      const message = el.getAttribute('data-confirm') || 'Are you sure?';
      if (!confirm(message)) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    });
  });
}

/* ============================================================
   5. TABLE SEARCH / FILTER
   ============================================================ */
function initTableSearch() {
  document.querySelectorAll('[data-table-search]').forEach(input => {
    const tableId = input.getAttribute('data-table-search');
    const table = document.getElementById(tableId);
    if (!table) return;

    input.addEventListener('input', () => {
      const query = input.value.toLowerCase().trim();
      const rows = table.querySelectorAll('tbody tr');

      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
      });
    });
  });

  // Status filter dropdowns
  document.querySelectorAll('[data-status-filter]').forEach(select => {
    const tableId = select.getAttribute('data-status-filter');
    const table = document.getElementById(tableId);
    if (!table) return;

    select.addEventListener('change', () => {
      const status = select.value.toLowerCase();
      const rows = table.querySelectorAll('tbody tr');

      rows.forEach(row => {
        if (!status) {
          row.style.display = '';
          return;
        }
        const badge = row.querySelector('.badge');
        const rowStatus = badge ? badge.textContent.toLowerCase().trim() : '';
        row.style.display = rowStatus.includes(status) ? '' : 'none';
      });
    });
  });
}

/* ============================================================
   6. DYNAMIC LINE ITEMS (ORDER FORMS)
   ============================================================ */
function initDynamicLineItems() {
  document.querySelectorAll('[data-add-line]').forEach(btn => {
    btn.addEventListener('click', () => {
      const tbodyId = btn.getAttribute('data-add-line');
      const tbody = document.getElementById(tbodyId);
      if (!tbody) return;

      const rowCount = tbody.querySelectorAll('tr').length;
      const newIndex = rowCount;
      const template = btn.getAttribute('data-line-template') || 'sales';
      const row = createLineRow(newIndex, template);
      tbody.appendChild(row);
      updateLineNumbers(tbody);
    });
  });

  // Delegate remove buttons
  document.addEventListener('click', (e) => {
    if (e.target.closest('.btn-remove-line')) {
      const btn = e.target.closest('.btn-remove-line');
      const row = btn.closest('tr');
      const tbody = row.closest('tbody');
      row.remove();
      if (tbody) updateLineNumbers(tbody);
    }
  });

  // Auto-compute line totals
  document.addEventListener('input', (e) => {
    if (e.target.matches('.line-qty, .line-price')) {
      const row = e.target.closest('tr');
      if (!row) return;
      const qty = parseFloat(row.querySelector('.line-qty')?.value) || 0;
      const price = parseFloat(row.querySelector('.line-price')?.value) || 0;
      const totalEl = row.querySelector('.line-total');
      if (totalEl) {
        totalEl.textContent = (qty * price).toFixed(2);
      }
      updateOrderTotal();
    }
  });
}

function createLineRow(index, template) {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="line-num">${index + 1}</td>
    <td>
      <select name="lines-${index}-product_id" class="form-control" required>
        <option value="">Select product…</option>
      </select>
    </td>
    <td><input type="number" name="lines-${index}-qty" class="form-control line-qty" min="0.01" step="0.01" value="1" required></td>
    <td><input type="number" name="lines-${index}-unit_price" class="form-control line-price" min="0" step="0.01" value="0.00" required></td>
    <td class="line-total text-right">0.00</td>
    <td><button type="button" class="btn btn-ghost btn-sm btn-remove-line" title="Remove">✕</button></td>
  `;

  // Copy product options from the first row if available
  const firstSelect = document.querySelector('select[name="lines-0-product_id"]');
  const newSelect = tr.querySelector('select');
  if (firstSelect && newSelect) {
    newSelect.innerHTML = firstSelect.innerHTML;
    newSelect.value = '';
  }

  return tr;
}

function updateLineNumbers(tbody) {
  tbody.querySelectorAll('tr').forEach((row, i) => {
    const numCell = row.querySelector('.line-num');
    if (numCell) numCell.textContent = i + 1;

    // Update name attributes
    row.querySelectorAll('[name]').forEach(input => {
      input.name = input.name.replace(/lines-\d+-/, `lines-${i}-`);
    });
  });
}

function updateOrderTotal() {
  const totals = document.querySelectorAll('.line-total');
  let sum = 0;
  totals.forEach(el => { sum += parseFloat(el.textContent) || 0; });
  const orderTotal = document.getElementById('order-total');
  if (orderTotal) orderTotal.textContent = sum.toFixed(2);
}

/* ============================================================
   7. MODAL MANAGEMENT
   ============================================================ */
function initModals() {
  // Open modal
  document.querySelectorAll('[data-modal]').forEach(trigger => {
    trigger.addEventListener('click', () => {
      const modalId = trigger.getAttribute('data-modal');
      const modal = document.getElementById(modalId);
      if (modal) modal.classList.add('active');
    });
  });

  // Close modal
  document.querySelectorAll('.modal-close, [data-modal-close]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal-overlay');
      if (modal) modal.classList.remove('active');
    });
  });

  // Click overlay to close
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('active');
    });
  });

  // ESC to close
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    }
  });
}

/* Programmatic modal open/close */
function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('active');
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove('active');
}
