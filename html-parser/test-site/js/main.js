// Main JavaScript file
console.log('Main.js loaded');

// Initialize the application
function init() {
    console.log('Application initialized');
    setupEventListeners();
}

function setupEventListeners() {
    // Mobile menu toggle
    const menuBtn = document.querySelector('.menu-btn');
    if (menuBtn) {
        menuBtn.addEventListener('click', toggleMenu);
    }
}

function toggleMenu() {
    const nav = document.querySelector('nav');
    nav.classList.toggle('active');
}

// Run on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
