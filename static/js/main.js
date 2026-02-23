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

// Global error handler
window.addEventListener('error', (event) => {
  console.error('Global error:', event.error);
  // Optionally show user-friendly error message
});

// Log initialization
document.addEventListener('DOMContentLoaded', () => {
  console.log('Application initialized');
});
