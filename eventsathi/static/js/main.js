// EventSathi - Main JavaScript

// Navbar scroll effect
window.addEventListener('scroll', function() {
    const nav = document.getElementById('mainNav');
    if (nav) {
        if (window.scrollY > 50) {
            nav.style.background = 'rgba(15, 15, 26, 0.98)';
            nav.style.boxShadow = '0 2px 30px rgba(0,0,0,0.3)';
        } else {
            nav.style.background = 'rgba(15, 15, 26, 0.95)';
            nav.style.boxShadow = 'none';
        }
    }
});

// Auto-dismiss alerts
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            if (alert.parentNode) bsAlert.close();
        }, 5000);
    });

    // Animate stat counters
    const counters = document.querySelectorAll('.stat-counter');
    counters.forEach(counter => {
        const target = parseInt(counter.getAttribute('data-target'));
        const duration = 1500;
        const step = target / (duration / 16);
        let current = 0;
        const timer = setInterval(() => {
            current += step;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            counter.textContent = Math.floor(current).toLocaleString();
        }, 16);
    });

    // Poll selection highlighting
    document.querySelectorAll('.poll-option-radio').forEach(radio => {
        radio.addEventListener('change', function() {
            const pollId = this.name;
            document.querySelectorAll(`input[name="${pollId}"]`).forEach(r => {
                r.closest('.poll-option').classList.remove('selected');
            });
            this.closest('.poll-option').classList.add('selected');
        });
    });
});

// Print ticket
function printTicket() {
    window.print();
}

// Copy ticket ID
function copyTicketId(ticketId) {
    navigator.clipboard.writeText(ticketId).then(() => {
        const btn = document.getElementById('copyBtn');
        if (btn) {
            btn.innerHTML = '<i class="bi bi-check me-1"></i>Copied!';
            setTimeout(() => {
                btn.innerHTML = '<i class="bi bi-clipboard me-1"></i>Copy ID';
            }, 2000);
        }
    });
}

// Scroll to section
function scrollToSection(id) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
