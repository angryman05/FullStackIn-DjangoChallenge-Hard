/**
 * Django War Simulator - Global Frontend Utilities
 * Handles: Toasts, Copy-to-clipboard, CSRF cookie parsing, Safe text handling.
 */

// CSRF cookie helper
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta && meta.content) return meta.content;
  const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
  if (input && input.value) return input.value;
  const cookies = document.cookie.split(';');
  for (let cookie of cookies) {
    const [name, val] = cookie.trim().split('=');
    if (name === 'csrftoken') return decodeURIComponent(val);
  }
  return '';
}

// Global Toast System (accessible, untrusted-safe with textContent)
const Toast = {
  container: null,

  init() {
    if (!this.container) {
      this.container = document.getElementById('toast-container');
      if (!this.container) {
        this.container = document.createElement('div');
        this.container.id = 'toast-container';
        this.container.setAttribute('role', 'region');
        this.container.setAttribute('aria-label', 'System Notifications');
        this.container.setAttribute('aria-live', 'polite');
        document.body.appendChild(this.container);
      }
    }

    // Process server-rendered Django messages
    document.querySelectorAll('.django-message-init').forEach(el => {
      const msg = el.dataset.message || el.textContent.trim();
      const tag = el.dataset.tag || 'info';
      if (msg) {
        this.show(msg, tag);
      }
      el.remove();
    });
  },

  show(message, type = 'info', duration = 5000) {
    this.init();
    
    // Normalize Django tags
    if (type === 'debug') type = 'info';
    if (!['info', 'success', 'warning', 'error'].includes(type)) {
      type = 'info';
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'status');

    const msgSpan = document.createElement('span');
    msgSpan.textContent = message; // Safe: never innerHTML

    const dismissBtn = document.createElement('button');
    dismissBtn.type = 'button';
    dismissBtn.className = 'toast-dismiss';
    dismissBtn.setAttribute('aria-label', 'Dismiss notification');
    dismissBtn.textContent = '×';

    toast.appendChild(msgSpan);
    toast.appendChild(dismissBtn);

    const remove = () => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(12px) scale(0.95)';
      setTimeout(() => toast.remove(), 200);
    };

    dismissBtn.addEventListener('click', remove);

    if (duration > 0) {
      setTimeout(remove, duration);
    }

    this.container.appendChild(toast);
  }
};

// Clipboard Chip Initialization
function initCopyChips() {
  document.querySelectorAll('.copy-chip, [data-copy]').forEach(chip => {
    chip.addEventListener('click', async (e) => {
      e.preventDefault();
      const textToCopy = chip.dataset.copy || chip.dataset.value || chip.textContent.trim();
      if (!textToCopy) return;

      try {
        await navigator.clipboard.writeText(textToCopy);
        const originalText = chip.textContent;
        chip.classList.add('copied');
        chip.textContent = '✓ Copied';
        Toast.show(`Copied to clipboard: ${textToCopy}`, 'success', 3000);
        setTimeout(() => {
          chip.classList.remove('copied');
          chip.textContent = originalText;
        }, 2000);
      } catch (err) {
        Toast.show('Failed to copy to clipboard', 'error');
      }
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  Toast.init();
  initCopyChips();
});

window.Toast = Toast;
window.getCsrfToken = getCsrfToken;
