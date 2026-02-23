/**
 * deck.js
 * Deck component utilities and tree handlers
 */

class DeckComponent {
  /**
   * Toggle deck tree expansion
   * @param {HTMLElement} toggleBtn - Toggle button element
   */
  static toggleTree(toggleBtn) {
    const nodeId = toggleBtn.getAttribute('data-node-id');
    const isExpanded = toggleBtn.getAttribute('data-expanded') === 'true';
    
    // Find all child rows for this node
    const deckList = document.getElementById('deck-list');
    const allRows = deckList.querySelectorAll('[data-parent-id]');
    
    allRows.forEach(row => {
      if (row.getAttribute('data-parent-id') === nodeId) {
        if (isExpanded) {
          row.style.display = 'none';
        } else {
          row.style.display = 'flex';
        }
      }
    });

    // Toggle button state
    const newState = !isExpanded;
    toggleBtn.setAttribute('data-expanded', newState);
    toggleBtn.textContent = newState ? '−' : '+';
  }

  /**
   * Click handler for deck rows
   * @param {HTMLElement} row - Deck row element
   */
  static selectDeck(row) {
    const url = row.getAttribute('data-open-url');
    if (url) {
      window.location.href = url;
    }
  }

  /**
   * Start create deck flow
   */
  static startCreateDeck() {
    ModalComponent.show('createDeckModal');
  }

  /**
   * Submit create deck form
   * @param {string} deckPath - Deck path (e.g., "Parent::Child::Name")
   * @param {Function} onSuccess - Callback on success
   */
  static submitCreateDeck(deckPath, onSuccess) {
    const form = document.getElementById('create-deck-form');
    if (!form) return;

    // Parse deck path
    const parts = deckPath.split('::').map(p => p.trim());
    if (parts.length === 0) {
      ModalComponent.showAlert('Error', 'Invalid deck path', true);
      return;
    }

    // Set form values
    document.getElementById('create-deck-name').value = parts[parts.length - 1];
    document.getElementById('create-deck-path').value = deckPath;

    // Submit form
    form.submit();
    if (onSuccess) onSuccess();
  }
}

// Initialize deck event listeners
document.addEventListener('DOMContentLoaded', () => {
  // Tree toggle buttons
  document.querySelectorAll('.tree-toggle').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      DeckComponent.toggleTree(btn);
    });
  });

  // Deck row click handlers
  document.querySelectorAll('.deck-row').forEach(row => {
    row.addEventListener('click', () => {
      DeckComponent.selectDeck(row);
    });
  });

  // Create deck button
  const createDeckBtn = document.getElementById('create-deck-btn');
  if (createDeckBtn) {
    createDeckBtn.addEventListener('click', () => {
      DeckComponent.startCreateDeck();
    });
  }

  // Create deck confirm button
  const confirmBtn = document.getElementById('confirm-create-deck-btn');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', () => {
      const input = document.getElementById('deck-path-input');
      if (input) {
        DeckComponent.submitCreateDeck(input.value);
      }
    });
  }
});
