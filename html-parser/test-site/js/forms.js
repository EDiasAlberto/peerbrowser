// Form validation and handling
console.log('Forms.js loaded');

class FormValidator {
    constructor(formSelector) {
        this.form = document.querySelector(formSelector);
        if (this.form) {
            this.init();
        }
    }

    init() {
        this.form.addEventListener('submit', this.handleSubmit.bind(this));
    }

    handleSubmit(e) {
        e.preventDefault();
        console.log('Form submitted');
        
        if (this.validate()) {
            console.log('Form is valid');
            this.submitForm();
        } else {
            console.log('Form validation failed');
        }
    }

    validate() {
        const inputs = this.form.querySelectorAll('input[required]');
        let isValid = true;

        inputs.forEach(input => {
            if (!input.value.trim()) {
                isValid = false;
                input.classList.add('error');
            } else {
                input.classList.remove('error');
            }
        });

        return isValid;
    }

    async submitForm() {
        const formData = new FormData(this.form);
        console.log('Submitting form data:', Object.fromEntries(formData));
        
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000));
        alert('Form submitted successfully!');
    }
}

// Initialize form validator
document.addEventListener('DOMContentLoaded', () => {
    new FormValidator('form');
});
