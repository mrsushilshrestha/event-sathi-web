# Event-Sathi System Documentation

## 1. System Overview
Event-Sathi is a professional event management and social networking platform designed to bridge the gap between event organizers, attendees, speakers, and sponsors. It features a robust Django-based backend with a real-time communication layer and a comprehensive REST API for mobile app integration.

### Core Technologies
- **Backend**: Django 5.x
- **API**: Django REST Framework (DRF) + JWT Authentication
- **Real-time**: Django Channels (WebSockets) + Redis
- **Database**: SQLite (Development) / PostgreSQL (Production ready)
- **UI**: Bootstrap 5 + Custom CSS/JS (Social Media Style)
- **Analytics**: Geopy + Custom Tracking

---

## 2. Database Structure (Models)

### Accounts Module
- **User (Django Default)**: Auth, username, email, password.
- **UserProfile**: Extends User with role (Attendee, Organizer, Speaker), bio, location, interests, verification status, and profile/cover photos.
- **OrganizerProfile**: Specific details for verified organizations.
- **NetworkConnection**: Follow/Follower relationship and networking between users.
- **Message**: Peer-to-peer chat records.

### Events Module
- **Category**: Event categories (Tech, Music, etc.) with icons and slugs.
- **Event**: Core model containing title, description, venue, coordinates (Lat/Lng), start/end dates, banner, capacity, status (Draft/Published), and organizer link.
- **TicketTier**: Multiple pricing levels per event (Early Bird, VIP, etc.).
- **Registration**: Attendee bookings, status (Confirmed/Checked-in), and unique Alphanumeric Ticket IDs.
- **Speaker**: Guest speakers linked to specific events.
- **EventSession**: Agenda/Timeline items for an event.
- **EventImage**: Gallery images for an event.
- **EventLike/EventComment**: Social interactions.
- **EventAnalytics**: Tracking views, platform types, and user actions.
- **Notification**: In-app alerts for users.

---

## 3. API Documentation (for App Development)

### Base URL
`http://localhost:8000/api/`

### Authentication
**Header**: `Authorization: Bearer <access_token>`

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `auth/login/` | POST | Login with username/email and password. Returns JWT. |
| `auth/register/` | POST | Create a new user account. |
| `auth/profile/` | GET/PUT | View or update logged-in user profile. |
| `auth/token/refresh/` | POST | Get a new access token using a refresh token. |

### Events & Discovery
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `events/` | GET | List all published events (supports search `?q=` and filters). |
| `events/featured/` | GET | List top 10 featured events. |
| `events/nearby/` | GET | Get events within radius (requires `?lat=` and `?lng=`). |
| `categories/` | GET | List all available event categories. |
| `events/<id>/` | GET | Detailed event information including tiers and speakers. |
| `events/<id>/like/` | POST | Toggle like on an event. |
| `events/<id>/comments/` | GET | Fetch full comment thread for an event. |
| `events/<id>/delete/` | DELETE | Delete an event (organizer only). |
| `events/<id>/duplicate/` | POST | Duplicate an event (organizer only). |
| `organizer/<id>/follow/` | POST | Follow/unfollow an organizer. |
| `organizer/<id>/followers/` | GET | List of users following an organizer. |

### Organizer & Admin Tools
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `organizer/dashboard/` | GET | Comprehensive analytics for the organizer's events. |
| `organizer/events/` | GET | List of events owned by the organizer. |
| `organizer/events/<id>/export-attendees/` | GET | Export attendee list as CSV. |
| `organizer/events/<id>/export-revenue/` | GET | Export revenue report as CSV. |
| `admin/users/` | GET | List all users (staff only). |
| `admin/events/` | GET | List all events (staff only). |
| `admin/payments/` | GET | Financial summary (staff only). |

### Bookings & Tickets
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `book-ticket/` | POST | Register for an event (requires `event_id` and `ticket_tier_id`). |
| `my-bookings/` | GET | List all tickets booked by the user. |
| `ticket/<id>/qr/` | GET | Get QR code data/image for a specific ticket. |

### Real-time (WebSockets)
**Endpoints**:
- `ws/notifications/`: Live in-app alerts (likes, bookings, etc.).
- `ws/chat/`: Real-time peer-to-peer messaging.
- `ws/events/`: Global feed updates (new events, status changes).

---

## 4. Web Version Features
- **Social Feed**: 3-column responsive grid with Facebook/Instagram style comment modals.
- **Organizer Dashboard**: Professional analytics with Chart.js, attendee export (CSV), and event duplication.
- **Geolocation**: Automatic city detection and proximity-based event sorting.
- **Real-time Indicators**: Live API health circle and instant toast notifications.
- **Event Management**: Drag-and-drop banner uploads, agenda builder, and speaker management.

---

## 5. Integration Guide for Mobile App
1. **Connection**: Point the app to the API Base URL. Use the `/api/health/` endpoint to verify connectivity.
2. **Auth**: Store the JWT `access_token` securely. Refresh it periodically using the `refresh` token.
3. **Location**: Send device GPS coordinates to `/api/events/nearby/` for the "Events Near Me" feature.
4. **Social**: Use the WebSockets for instant chat and notifications to provide a seamless mobile experience.
5. **Tickets**: Use the `/api/ticket/<id>/qr/` endpoint to display QR codes in the app for physical check-ins.
