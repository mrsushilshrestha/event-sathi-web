// EventSathi - Main JavaScript

// ── Theme Toggle ────────────────────────────────────────────
(function () {
    var saved = localStorage.getItem('es-theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
})();

function updateThemeIcon(theme) {
    var icon = document.getElementById('themeIcon');
    if (!icon) return;
    if (theme === 'light') {
        icon.className = 'bi bi-moon-stars-fill';
    } else {
        icon.className = 'bi bi-sun-fill';
    }
}

document.addEventListener('DOMContentLoaded', function () {
    var current = document.documentElement.getAttribute('data-theme') || 'light';
    updateThemeIcon(current);

    var btn = document.getElementById('themeToggle');
    if (btn) {
        btn.addEventListener('click', function () {
            var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('es-theme', next);
            updateThemeIcon(next);
        });
    }
});

// ── Navbar scroll effect ─────────────────────────────────────
window.addEventListener('scroll', function () {
    var nav = document.getElementById('mainNav');
    if (!nav) return;
    var isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    if (window.scrollY > 50) {
        nav.style.background = isDark ? 'rgba(8,8,18,0.98)' : 'rgba(255,255,255,0.98)';
        nav.style.boxShadow = '0 2px 24px rgba(0,0,0,0.18)';
    } else {
        nav.style.background = '';
        nav.style.boxShadow = 'none';
    }
});

// ── Auto-dismiss alerts ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            var bsAlert = new bootstrap.Alert(alert);
            if (alert.parentNode) bsAlert.close();
        }, 5000);
    });

    // Animate stat counters
    var counters = document.querySelectorAll('.stat-counter');
    counters.forEach(function (counter) {
        var target = parseInt(counter.getAttribute('data-target'));
        if (!target) return;
        var duration = 1500;
        var step = target / (duration / 16);
        var current = 0;
        var timer = setInterval(function () {
            current += step;
            if (current >= target) { current = target; clearInterval(timer); }
            counter.textContent = Math.floor(current).toLocaleString();
        }, 16);
    });

    // Poll option highlight
    document.querySelectorAll('.poll-option-radio').forEach(function (radio) {
        radio.addEventListener('change', function () {
            var pollId = this.name;
            document.querySelectorAll('input[name="' + pollId + '"]').forEach(function (r) {
                r.closest('.poll-option').classList.remove('selected');
            });
            this.closest('.poll-option').classList.add('selected');
        });
    });
});

// ── Utilities ────────────────────────────────────────────────
function printTicket() { window.print(); }

function copyTicketId(ticketId) {
    navigator.clipboard.writeText(ticketId).then(function () {
        var btn = document.getElementById('copyBtn');
        if (btn) {
            btn.innerHTML = '<i class="bi bi-check me-1"></i>Copied!';
            setTimeout(function () {
                btn.innerHTML = '<i class="bi bi-clipboard me-1"></i>Copy ID';
            }, 2000);
        }
    });
}

function scrollToSection(id) {
    var el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

