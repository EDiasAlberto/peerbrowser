// Utility functions
console.log('Utils.js loaded');

const Utils = {
    // Format date
    formatDate: function(date) {
        return new Date(date).toLocaleDateString();
    },

    // Debounce function
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Fetch helper
    async fetchData(url) {
        try {
            const response = await fetch(url);
            return await response.json();
        } catch (error) {
            console.error('Fetch error:', error);
            return null;
        }
    }
};

// Export for use in other modules
window.Utils = Utils;
