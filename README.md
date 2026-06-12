# 🎉 Event-Sathi — हरेक Event को साथी

Event-Sathi is a comprehensive web-based Event Management System designed to simplify event discovery, registration, ticketing, and event organization. The platform provides a centralized ecosystem where users can explore events, book tickets, receive QR-based digital passes, and interact with organizers, while organizers can efficiently manage events and attendees.

---

## 📸 Screenshots

### Home Page
![Home Page](https://github.com/user-attachments/assets/1a2c8b89-9c61-4227-bc46-5b32278138d1)

### Event Listing
![Event Listing](https://github.com/user-attachments/assets/8b026277-ada5-4aea-8707-edb615d463d4)

### Event Details
![Event Details](https://github.com/user-attachments/assets/2b53f68a-b978-4d9c-a89d-6eedbc03dc13)

### Ticket Booking
![Ticket Booking](https://github.com/user-attachments/assets/aee216ad-e828-47d4-ae7b-fdab301d1d81)

### User Dashboard
![Dashboard](https://github.com/user-attachments/assets/3cdd5d72-2e36-4fc7-9376-5d2b0d14a727)

### Organizer Panel
![Organizer Panel](https://github.com/user-attachments/assets/9880c614-f2a4-45b4-9095-214838460710)

---

## 📖 About the Project

Finding and managing events can be challenging due to scattered information, manual registration processes, and limited communication between organizers and attendees.

Event-Sathi addresses these challenges by providing a modern event management platform that connects event participants, organizers, and administrators through a single web application.

The system enables:

- Easy event discovery and registration
- QR-based ticket generation and verification
- Organizer event management tools
- Real-time attendee tracking
- User-organizer communication
- Centralized event administration

---

## ✨ Key Features

### 👥 User Features

- User Registration & Login
- Browse Upcoming Events
- Search & Filter Events
- Event Details View
- Event Registration
- QR Code Ticket Generation
- Save & Like Events
- Personal Dashboard
- View Booked Events
- Messaging with Organizers

### 🎯 Organizer Features

- Create Events
- Edit & Delete Events
- Manage Attendees
- Event Analytics
- Ticket Verification
- Session Management
- Speaker Management
- Sponsor Management
- Announcement System
- QR Check-In System

### 🛡️ Admin Features

- User Management
- Organizer Approval
- Event Monitoring
- Platform Moderation
- Dashboard Analytics
- Content Management

---

## 🏗️ System Architecture

The application follows Django's MTV (Model-Template-View) architecture.

```text
User Browser
      │
      ▼
Frontend (HTML, CSS, Bootstrap, JavaScript)
      │
      ▼
Django Backend
      │
      ├── Authentication
      ├── Event Management
      ├── Booking System
      ├── QR Ticketing
      └── Messaging System
      │
      ▼
SQLite Database
```

---

## 🛠️ Technology Stack

### Frontend

- HTML5
- CSS3
- Bootstrap 5
- JavaScript

### Backend

- Python
- Django
- Django REST Framework
- Channels

### Database

- SQLite

### Authentication

- Django Authentication
- JWT Authentication

### Other Libraries

- qrcode
- Pillow
- Crispy Forms
- Widget Tweaks
- WhiteNoise
- Daphne

### Version Control

- Git
- GitHub

---

## 📂 Project Structure

```bash
event-sathi/
│
├── accounts/
├── events/
├── api/
├── templates/
├── static/
├── media/
│
├── eventsathi/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── db.sqlite3
├── manage.py
├── requirements.txt
└── README.md
```

---

## 🚀 Installation Guide

### 1. Clone Repository

```bash
git clone https://github.com/mrsushilshrestha/event-sathi-web.git

cd event-sathi-web
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

### 3. Activate Virtual Environment

#### Windows

```bash
venv\Scripts\activate
```

#### Linux/Mac

```bash
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Apply Migrations

```bash
python manage.py makemigrations

python manage.py migrate
```

### 6. Create Superuser

```bash
python manage.py createsuperuser
```

### 7. Run Server

```bash
python manage.py runserver
```

Visit:

```text
http://127.0.0.1:8000
```

---

## 🔑 User Roles

| Role | Permissions |
|--------|------------|
| Guest | Browse Events |
| User | Register & Book Events |
| Organizer | Manage Events |
| Admin | Full System Control |

---

## 🎟️ QR Ticket System

Event-Sathi automatically generates unique QR-based digital tickets after successful registration.

Features:

- Unique Ticket ID
- Secure QR Code
- Event Verification
- Check-In Tracking
- Fraud Prevention

---

## 📊 Core Modules

- Authentication Module
- Event Management Module
- Ticket Management Module
- QR Verification Module
- Organizer Dashboard
- Messaging Module
- Analytics Module
- Announcement Module
- Session Management Module

---

## 🔒 Security Features

- Role-Based Access Control (RBAC)
- Secure Authentication
- CSRF Protection
- Password Validation
- JWT Authentication
- Protected Organizer Routes
- Secure Ticket Verification

---

## 🎯 Future Enhancements

- Android Application
- iOS Application
- eSewa Integration
- Khalti Integration
- Push Notifications
- SMS Notifications
- AI Event Recommendations
- Multi-language Support
- Cloud Deployment

---

## 📈 Development Methodology

The project follows the Agile Scrum SDLC model.

### Development Phases

1. Requirement Analysis
2. Sprint Planning
3. Design & Development
4. Testing
5. Review & Feedback
6. Deployment

---

## 👨‍💻 Team Members

### Event-Sathi Development Team

- **Ashish Thami** (380226)
- **Sailendra Bhattarai** (380236)
- **Sushil Shrestha** (380242)

### Supervisor

**Er. Samyog Adhikari**

### Institution

**Himalayan WhiteHouse International College**  
**Purbanchal University**  
Kathmandu, Nepal

---

## 🧪 Testing Summary

| Test Type | Status |
|------------|---------|
| Unit Testing | ✅ Passed |
| Integration Testing | ✅ Passed |
| System Testing | ✅ Passed |
| User Acceptance Testing | ✅ Passed |

**Total Test Cases:** 10  
**Passed:** 10  
**Failed:** 0

---

## 🤝 Contributing

Contributions, suggestions, and feature requests are welcome.

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to GitHub
5. Create a Pull Request

---

## 📄 License

This project was developed as a Bachelor of Information Technology (BIT) Major Project for academic purposes.

---

## ⭐ Support

If you like this project, don't forget to give it a ⭐ on GitHub.

### Team Event-Sathi
**"हरेक Event को साथी"**