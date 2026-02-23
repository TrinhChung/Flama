/**
 * modals.js
 * Modal component utilities and handlers
 */

class ModalComponent {
  /**
   * Show a modal by ID
   * @param {string} modalId - ID of the modal to show
   */
  static show(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      const bsModal = new bootstrap.Modal(modal);
      bsModal.show();
    }
  }

  /**
   * Hide a modal by ID
   * @param {string} modalId - ID of the modal to hide
   */
  static hide(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      const bsModal = bootstrap.Modal.getInstance(modal);
      if (bsModal) bsModal.hide();
    }
  }

  /**
   * Attach event listener to confirm button
   * @param {string} confirmBtnId - ID of the confirm button
   * @param {Function} callback - Callback function on confirm
   */
  static onConfirm(confirmBtnId, callback) {
    const btn = document.getElementById(confirmBtnId);
    if (btn) {
      btn.addEventListener('click', callback);
    }
  }

  /**
   * Create and show alert modal
   * @param {string} title - Modal title
   * @param {string} message - Modal message
   * @param {boolean} isError - Is error alert
   */
  static showAlert(title, message, isError = false) {
    const alertId = 'alertModal_' + Date.now();
    const modal = document.createElement('div');
    modal.id = alertId;
    modal.className = 'modal fade';
    modal.innerHTML = `
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">${title}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            ${message}
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    this.show(alertId);
  }
}

// Initialize confirm buttons
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-confirm]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const confirmMsg = btn.getAttribute('data-confirm');
      if (!confirm(confirmMsg)) {
        e.preventDefault();
      }
    });
  });
});
