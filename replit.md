# EventSathi

A comprehensive Django web application for end-to-end university event management. Handles smart ticketing with QR codes, event agenda/sessions, speaker directory, live Q&A & polls, networking hub, organizer analytics dashboard, announcements, sponsor management, and hybrid/virtual event support.

## Run & Operate

- **Start app**: workflow "Start application" → `cd eventsathi && python manage.py runserver 0.0.0.0:8000`
- **Migrations**: `cd eventsathi && python manage.py makemigrations && python manage.py migrate`
- **Seed data**: `cd eventsathi && python manage.py shell < seed_data.py`
- **Create superuser**: `cd eventsathi && python manage.py createsuperuser`

## Demo Credentials

| Role | Username | Password |
|------|----------|----------|
| Superuser/Admin | `admin` | `admin123` |
| Organizer | `rahul` | `demo123` |
| Attendee | `priya` | `demo123` |

## Stack

- Python 3.11, Django 5.2
- SQLite (dev) — switch to PostgreSQL for production via `DATABASE_URL`
- Bootstrap 5.3 (CDN), Bootstrap Icons, custom dark theme
- QR code generation: `qrcode` + Pillow
- Static files: WhiteNoise
- Forms: `django-crispy-forms` + `crispy-bootstrap5`, `django-widget-tweaks`

## Where things live

```
eventsathi/
├── eventsathi/         # Django project settings, urls, wsgi
├── accounts/           # User profiles, networking, messages, connections
├── events/             # Events, tickets, sessions, speakers, sponsors, polls, Q&A
├── templates/
│   ├── base.html       # Global layout with navbar, messages, JS helpers
│   ├── accounts/       # profile, network hub, messages, conversation, attendees
│   └── events/         # home, event CRUD, agenda, speakers, sponsors,
│                       # session detail (Q&A+polls), ticket, manage/*
├── static/
│   ├── css/style.css   # Dark theme — CSS vars, components, responsive
│   └── js/main.js      # QR copy, stat counters, tier selection, polls
└── media/              # Uploaded banners, speaker photos, sponsor logos
```

## Architecture decisions

- **Slug-based event URLs** — events are identified by slug (e.g. `/events/techfest-2024/`), never by numeric IDs in URLs
- **QR codes stored as Base64** in the `Registration.qr_code` field — no separate file, rendered directly in ticket template
- **UserProfile via signals** — auto-created on new User registration via `post_save` signal
- **PollVote deduplication** handled at view level (query before inserting), not via DB unique_together since that requires `choice__poll` traversal
- **CSRF trusted origins + proxy headers** set for Replit's mTLS proxy (`SECURE_PROXY_SSL_HEADER`, `CSRF_TRUSTED_ORIGINS`)

## Product

- **Attendees**: Browse events, register with tiered tickets, view QR ticket, build personal schedule, join Q&A, vote in polls, network with other attendees
- **Organizers**: Create & publish events, manage ticket tiers/sessions/speakers/sponsors/announcements, QR check-in portal, analytics dashboard
- **Sessions**: Per-session Q&A with upvoting, live polls with real-time results, optional stream/recording links
- **Networking**: Connection requests, direct messaging, attendee directory with interest-based matching

## User preferences

- Dark purple/gold theme — `--es-primary: #6c3de1`, Inter/Poppins fonts, Bootstrap 5.3
- Indian locale: `TIME_ZONE = 'Asia/Kolkata'`, prices shown in ₹
- University project context — feature-rich but intentionally uses SQLite for simplicity

## Gotchas

- `ALLOWED_HOSTS = ['*']` and `CSRF_TRUSTED_ORIGINS` must include Replit's domains for the proxy to work
- Static files use WhiteNoise — run `collectstatic` before production deployment
- QR code generation requires `qrcode[pil]` (Pillow) — already installed
- The `accounts` app imports from `events.models` (Registration) — migration order matters: migrate `accounts` first, then `events`

## Pointers

- Admin panel: `/admin/` (login as `admin` / `admin123`)
- See the `pnpm-workspace` skill for workspace structure details
