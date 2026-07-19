/**
 * main.js
 * Global utilities and initialization
 */

// Utility functions
const Utils = {
  /**
   * Safely get element by ID with null check
   * @param {string} id - Element ID
   * @returns {HTMLElement|null}
   */
  getElement: (id) => {
    return document.getElementById(id) || null;
  },

  /**
   * Format date to locale string
   * @param {Date} date - Date object
   * @returns {string}
   */
  formatDate: (date) => {
    return new Date(date).toLocaleDateString('vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  },

  /**
   * Format number with comma thousands separators.
   * @param {number|string} value
   * @param {{minimumFractionDigits?: number, maximumFractionDigits?: number}} options
   * @returns {string}
   */
  formatNumber: (value, options = {}) => {
    if (value === null || value === undefined || value === '') return '';
    const normalized = typeof value === 'string' ? value.replace(/,/g, '').trim() : value;
    const numericValue = Number(normalized);
    if (!Number.isFinite(numericValue)) {
      return String(value);
    }
    const minimumFractionDigits = Number.isInteger(options.minimumFractionDigits)
      ? Math.max(0, options.minimumFractionDigits)
      : 0;
    const maximumFractionDigits = Number.isInteger(options.maximumFractionDigits)
      ? Math.max(minimumFractionDigits, options.maximumFractionDigits)
      : (Number.isInteger(numericValue) ? 0 : Math.max(minimumFractionDigits, 2));
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits,
      maximumFractionDigits,
    }).format(numericValue);
  },

  /**
   * Format an amount and append VND suffix.
   * @param {number|string} value
   * @returns {string}
   */
  formatVnd: (value) => {
    const formatted = Utils.formatNumber(value);
    return formatted ? `${formatted} VNĐ` : '';
  },

  /**
   * Preserve the existing currency/text wrapper while formatting the numeric part.
   * @param {string} value
   * @returns {string}
   */
  formatPriceDisplay: (value) => {
    const text = String(value || '').trim();
    if (!text) return '';
    const match = text.match(/^(\D*?)([-+]?\d[\d,]*(?:\.\d+)?)(\D*)$/);
    if (!match) return text;
    const [, prefix, rawNumber, suffix] = match;
    const fractionPart = rawNumber.includes('.') ? rawNumber.split('.', 2)[1] : '';
    const formattedNumber = Utils.formatNumber(rawNumber, {
      minimumFractionDigits: fractionPart.length,
      maximumFractionDigits: fractionPart.length,
    });
    return `${prefix}${formattedNumber}${suffix}`.trim();
  },

  /**
   * Debounce function
   * @param {Function} fn - Function to debounce
   * @param {number} delay - Delay in ms
   * @returns {Function}
   */
  debounce: (fn, delay = 300) => {
    let timeoutId;
    return function(...args) {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => fn(...args), delay);
    };
  },

  /**
   * Throttle function
   * @param {Function} fn - Function to throttle
   * @param {number} delay - Delay in ms
   * @returns {Function}
   */
  throttle: (fn, delay = 300) => {
    let lastCall = 0;
    return function(...args) {
      const now = Date.now();
      if (now - lastCall >= delay) {
        lastCall = now;
        fn(...args);
      }
    };
  },

  /**
   * Show loading spinner
   * @param {HTMLElement} element - Element to show spinner in
   */
  showLoading: (element) => {
    if (!element) return;
    element.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div>';
  },

  /**
   * Escape HTML
   * @param {string} str - String to escape
   * @returns {string}
   */
  escapeHtml: (str) => {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  },
};

window.Utils = Utils;

const Csrf = {
  getToken: () => {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? String(meta.getAttribute('content') || '').trim() : '';
  },

  isUnsafeMethod: (method) => {
    const normalized = String(method || 'GET').toUpperCase();
    return !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(normalized);
  },

  isSameOrigin: (url) => {
    try {
      return new URL(url, window.location.origin).origin === window.location.origin;
    } catch (_error) {
      return false;
    }
  },

  injectIntoForms: () => {
    const token = Csrf.getToken();
    if (!token) return;

    document.querySelectorAll('form[method]').forEach((form) => {
      const method = String(form.getAttribute('method') || 'GET').toUpperCase();
      if (!Csrf.isUnsafeMethod(method)) return;
      if (form.querySelector('input[name="_csrf_token"]')) return;

      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = '_csrf_token';
      input.value = token;
      form.prepend(input);
    });
  },

  patchFetch: () => {
    if (typeof window.fetch !== 'function' || window.fetch.__flamaCsrfPatched) return;

    const originalFetch = window.fetch.bind(window);
    const wrappedFetch = (input, init) => {
      const request = input instanceof Request ? input : null;
      const method = String((init && init.method) || (request && request.method) || 'GET').toUpperCase();
      const url = request ? request.url : String(input || '');

      if (!Csrf.isUnsafeMethod(method) || !Csrf.isSameOrigin(url)) {
        return originalFetch(input, init);
      }

      const token = Csrf.getToken();
      if (!token) {
        return originalFetch(input, init);
      }

      const options = init ? { ...init } : {};
      const headers = new Headers(options.headers || (request ? request.headers : undefined));
      if (!headers.has('X-CSRF-Token')) {
        headers.set('X-CSRF-Token', token);
      }
      options.headers = headers;

      if (request && !init) {
        return originalFetch(new Request(request, { headers }));
      }
      return originalFetch(input, options);
    };

    wrappedFetch.__flamaCsrfPatched = true;
    window.fetch = wrappedFetch;
  },
};

window.Csrf = Csrf;

// Global error handler
window.addEventListener('error', (event) => {
  console.error('Global error:', event.error);
  // Optionally show user-friendly error message
});

// Log initialization
document.addEventListener('DOMContentLoaded', () => {
  Csrf.patchFetch();
  Csrf.injectIntoForms();
  console.log('Application initialized');
});

if (document.readyState !== 'loading') {
  Csrf.patchFetch();
  Csrf.injectIntoForms();
}
