// Application logic
console.log('App.js loaded');

class App {
    constructor() {
        this.data = [];
        this.init();
    }

    init() {
        console.log('App instance created');
        this.loadData();
    }

    async loadData() {
        // Simulate API call
        console.log('Loading data...');
        this.data = [
            { id: 1, name: 'Item 1' },
            { id: 2, name: 'Item 2' },
            { id: 3, name: 'Item 3' }
        ];
        this.render();
    }

    render() {
        console.log('Rendering app with data:', this.data);
        // Render logic would go here
    }
}

// Initialize app
const app = new App();
