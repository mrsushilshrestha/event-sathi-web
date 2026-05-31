import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def log_response(name, response):
    print(f"\n--- {name} ---")
    print(f"Status Code: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text[:200])

def run_tests():
    # 1. Register a new user
    email = f"testuser_{int(time.time())}@eventsathi.com"
    reg_data = {
        "email": email,
        "first_name": "Test",
        "last_name": "API User",
        "password": "testpassword123",
        "role": "user",
        "phone": "9876543210"
    }
    
    reg_resp = requests.post(f"{BASE_URL}/api/auth/register/", json=reg_data)
    log_response("Registration", reg_resp)
    
    if reg_resp.status_code != 201:
        print("Registration failed. Exiting.")
        return

    # 2. Login
    login_data = {
        "email_or_username": email,
        "password": "testpassword123"
    }
    login_resp = requests.post(f"{BASE_URL}/api/auth/login/", json=login_data)
    log_response("Login", login_resp)
    
    if login_resp.status_code != 200:
        print("Login failed. Exiting.")
        return
        
    res_data = login_resp.json()
    token = res_data["tokens"]["access"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 3. Get User Profile
    profile_resp = requests.get(f"{BASE_URL}/api/auth/profile/", headers=auth_headers)
    log_response("Get Profile", profile_resp)

    # 4. Get Events List
    events_resp = requests.get(f"{BASE_URL}/api/events/")
    log_response("Get Events", events_resp)
    
    events_data = events_resp.json().get("events", [])
    if not events_data:
        print("No events found to book. Attempting to create one as an organizer...")
        # Try to register as organizer
        org_email = f"org_{int(time.time())}@eventsathi.com"
        requests.post(f"{BASE_URL}/api/auth/register/", json={
            "email": org_email,
            "first_name": "Event",
            "last_name": "Organizer",
            "password": "orgpassword123",
            "role": "organizer",
            "org_name": "Sathi Events Inc.",
            "phone": "9876543211"
        })
        org_login = requests.post(f"{BASE_URL}/api/auth/login/", json={
            "email_or_username": org_email,
            "password": "orgpassword123"
        })
        org_token = org_login.json()["tokens"]["access"]
        org_headers = {"Authorization": f"Bearer {org_token}"}
        
        # Create an event
        create_resp = requests.post(f"{BASE_URL}/api/events/", headers=org_headers, json={
            "title": "API Launch Party",
            "description": "Launching the new API",
            "category": "conference",
            "venue": "Digital Space",
            "city": "Kathmandu",
            "start_date": "2026-06-01T18:00:00Z",
            "end_date": "2026-06-01T22:00:00Z",
            "max_capacity": 100
        })
        log_response("Create Event", create_resp)
        
        # Re-fetch events
        events_resp = requests.get(f"{BASE_URL}/api/events/")
        events_data = events_resp.json().get("events", [])
        
    if events_data:
        # Find an event that has ticket tiers
        event = None
        tiers = []
        for e in events_data:
            e_id = e["id"]
            e_detail_resp = requests.get(f"{BASE_URL}/api/events/{e_id}/")
            e_tiers = e_detail_resp.json().get("event", {}).get("ticket_tiers", [])
            if e_tiers:
                event = e
                tiers = e_tiers
                break
                
        if event and tiers:
            event_id = event["id"]
            tier_id = tiers[0]["id"]
            
            # 5. Book Event
            booking_data = {
                "event_id": event_id,
                "ticket_tier_id": tier_id
            }
            booking_resp = requests.post(f"{BASE_URL}/api/bookings/", headers=auth_headers, json=booking_data)
            log_response("Book Event", booking_resp)
            
            if booking_resp.status_code == 201:
                booking = booking_resp.json().get("booking", {})
                qr_code = booking.get("qr_code")
                
                # 6. Verify Ticket (as organizer)
                # We need organizer headers. Let's create one or reuse the one from above
                org_email = f"org_{int(time.time())}@eventsathi.com"
                requests.post(f"{BASE_URL}/api/auth/register/", json={
                    "email": org_email,
                    "first_name": "Event",
                    "last_name": "Organizer",
                    "password": "orgpassword123",
                    "role": "organizer",
                    "org_name": "Sathi Events Inc.",
                    "phone": "9876543211"
                })
                org_login = requests.post(f"{BASE_URL}/api/auth/login/", json={
                    "email_or_username": org_email,
                    "password": "orgpassword123"
                })
                org_token = org_login.json()["tokens"]["access"]
                org_headers = {"Authorization": f"Bearer {org_token}"}
                
                # Change the organizer of the event to this newly created organizer in the test so they can check it in
                # Actually, let's just create an event under this organizer, book it, and scan it!
                print("\nRunning full ticket scanner flow...")
                new_evt_resp = requests.post(f"{BASE_URL}/api/events/", headers=org_headers, json={
                    "title": "Scanner Test Event",
                    "description": "Testing ticket scanner endpoint",
                    "category": "conference",
                    "venue": "Tech Lab",
                    "city": "Kathmandu",
                    "start_date": "2026-07-01T18:00:00Z",
                    "end_date": "2026-07-01T22:00:00Z",
                    "max_capacity": 50
                })
                new_event = new_evt_resp.json().get("event", {})
                new_evt_id = new_event.get("id")
                new_tier_id = new_event.get("ticket_tiers", [{}])[0].get("id")
                
                # Book this event as user
                user_book_resp = requests.post(f"{BASE_URL}/api/bookings/", headers=auth_headers, json={
                    "event_id": new_evt_id,
                    "ticket_tier_id": new_tier_id
                })
                user_booking = user_book_resp.json().get("booking", {})
                user_qr = user_booking.get("qr_code")
                
                # Verify ticket
                verify_resp = requests.post(f"{BASE_URL}/api/bookings/verify/", headers=org_headers, json={
                    "qr_code": user_qr
                })
                log_response("Verify QR Ticket", verify_resp)

if __name__ == "__main__":
    run_tests()
