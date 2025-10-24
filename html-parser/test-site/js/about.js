// About page specific JavaScript
console.log('About.js loaded');

document.addEventListener('DOMContentLoaded', function() {
    console.log('About page ready');
    
    // Animate team member cards
    const teamMembers = document.querySelectorAll('.team-member');
    teamMembers.forEach((member, index) => {
        setTimeout(() => {
            member.style.opacity = '1';
            member.style.transform = 'translateY(0)';
        }, index * 100);
    });
});
