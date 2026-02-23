/**
 * forms.js
 * Form component utilities and event handlers
 */

class FormComponent {
  /**
   * Validate required fields in a form
   * @param {HTMLElement} form - Form element
   * @returns {boolean} - True if valid
   */
  static validateRequired(form) {
    const inputs = form.querySelectorAll('[required]');
    let isValid = true;

    inputs.forEach(input => {
      if (!input.value.trim()) {
        input.classList.add('is-invalid');
        isValid = false;
      } else {
        input.classList.remove('is-invalid');
      }
    });

    return isValid;
  }

  /**
   * Validate email format
   * @param {string} email - Email to validate
   * @returns {boolean}
   */
  static validateEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
  }

  /**
   * Clear form fields
   * @param {HTMLElement} form - Form element
   */
  static clearForm(form) {
    form.reset();
    form.querySelectorAll('[required]').forEach(input => {
      input.classList.remove('is-invalid');
    });
  }

  /**
   * Show form error
   * @param {HTMLElement} field - Form field
   * @param {string} errorMsg - Error message
   */
  static showError(field, errorMsg) {
    field.classList.add('is-invalid');
    let feedback = field.nextElementSibling;
    if (!feedback || !feedback.classList.contains('invalid-feedback')) {
      feedback = document.createElement('div');
      feedback.className = 'invalid-feedback d-block';
      field.parentElement.appendChild(feedback);
    }
    feedback.textContent = errorMsg;
  }

  /**
   * Clear form error
   * @param {HTMLElement} field - Form field
   */
  static clearError(field) {
    field.classList.remove('is-invalid');
    const feedback = field.nextElementSibling;
    if (feedback && feedback.classList.contains('invalid-feedback')) {
      feedback.remove();
    }
  }
}

// Initialize form validation on page load
document.addEventListener('DOMContentLoaded', () => {
  // Add real-time validation to email inputs
  document.querySelectorAll('input[type="email"]').forEach(input => {
    input.addEventListener('blur', (e) => {
      if (!FormComponent.validateEmail(e.target.value)) {
        FormComponent.showError(e.target, 'Invalid email format');
      } else {
        FormComponent.clearError(e.target);
      }
    });
  });

  // Add real-time validation to required fields
  document.querySelectorAll('[required]').forEach(input => {
    input.addEventListener('blur', (e) => {
      if (!e.target.value.trim()) {
        FormComponent.showError(e.target, 'This field is required');
      } else {
        FormComponent.clearError(e.target);
      }
    });
  });
});
