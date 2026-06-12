from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from accounts.models import UserProfile
from events.models import Event

class EventsSecurityAndAdminTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create two organizers
        self.organizer1 = User.objects.create_user(
            username='org1@example.com',
            email='org1@example.com',
            password='password123',
            first_name='Organizer',
            last_name='One'
        )
        self.profile1 = UserProfile.objects.create(
            user=self.organizer1,
            role='organizer',
            phone='1111111111'
        )

        self.organizer2 = User.objects.create_user(
            username='org2@example.com',
            email='org2@example.com',
            password='password123',
            first_name='Organizer',
            last_name='Two'
        )
        self.profile2 = UserProfile.objects.create(
            user=self.organizer2,
            role='organizer',
            phone='2222222222'
        )

        # Create an administrative user
        self.admin_user = User.objects.create_superuser(
            username='admin@eventsathi.com',
            email='admin@eventsathi.com',
            password='adminpassword',
            first_name='Admin',
            last_name='User'
        )

        # Create a test event owned by organizer1
        self.event = Event.objects.create(
            organizer=self.organizer1,
            title='Future Tech Summit',
            slug='future-tech-summit',
            description='Discussing the future of AI and tech.',
            category='conference',
            start_date=timezone.now() + timedelta(days=10),
            end_date=timezone.now() + timedelta(days=11),
            venue='Silicon Expo Center',
            city='San Jose',
            max_capacity=200,
            status='published',
            is_featured=False
        )

        # URLs
        self.delete_url = reverse('event_delete', kwargs={'slug': self.event.slug})
        self.admin_edit_url = reverse('admin_event_edit', kwargs={'slug': self.event.slug})
        self.admin_delete_url = reverse('admin_event_delete', kwargs={'slug': self.event.slug})
        self.my_events_url = reverse('my_events')
        self.admin_dashboard_url = reverse('admin_dashboard')

    def test_delete_event_access_permissions(self):
        """
        Verify that only the organizer of the event or a staff member can access the delete page.
        """
        # 1. Unauthenticated user is redirected to login
        response = self.client.get(self.delete_url)
        self.assertRedirects(response, f"/accounts/login/?next={self.delete_url}")

        # 2. Non-organizer is redirected to event detail with error message
        self.client.login(username='org2@example.com', password='password123', role='organizer')
        response_non_owner = self.client.get(self.delete_url)
        self.assertRedirects(response_non_owner, reverse('event_detail', kwargs={'slug': self.event.slug}))
        
        # Verify access permission error
        messages = list(response_non_owner.cookies.values()) # or check session messages
        # Let's inspect context messages or response redirects
        # Since it redirects, we can check messages in the redirected request or from self.client session messages.
        # Standard way is checking follow=True or looking at client session messages.
        response_non_owner_follow = self.client.get(self.delete_url, follow=True)
        messages_list = list(response_non_owner_follow.context['messages'])
        self.assertTrue(any("You do not have permission" in str(msg) for msg in messages_list))

        # 3. Organizer can access the delete page successfully
        self.client.login(username='org1@example.com', password='password123', role='organizer')
        response_owner = self.client.get(self.delete_url)
        self.assertEqual(response_owner.status_code, 200)

        # 4. Staff/Admin can access the delete page successfully
        self.client.login(username='admin@eventsathi.com', password='adminpassword')
        response_admin = self.client.get(self.delete_url)
        self.assertEqual(response_admin.status_code, 200)

    def test_delete_event_with_incorrect_password_fails(self):
        """
        Verify that entering an incorrect password fails to delete the event and yields a validation error message.
        """
        self.client.login(username='org1@example.com', password='password123', role='organizer')

        # Try to delete with incorrect password
        response = self.client.post(self.delete_url, {
            'password': 'wrongpassword'
        })
        
        # Verify event still exists
        self.assertTrue(Event.objects.filter(id=self.event.id).exists())

        # Verify error message
        messages = list(response.context['messages'])
        self.assertTrue(any("Incorrect password" in str(msg) for msg in messages))

    def test_delete_event_with_empty_password_fails(self):
        """
        Verify that entering an empty password fails to delete the event and yields a validation error message.
        """
        self.client.login(username='org1@example.com', password='password123', role='organizer')

        # Try to delete with empty password
        response = self.client.post(self.delete_url, {
            'password': ''
        })
        
        # Verify event still exists
        self.assertTrue(Event.objects.filter(id=self.event.id).exists())

        # Verify error message
        messages = list(response.context['messages'])
        self.assertTrue(any("Password is required" in str(msg) for msg in messages))

    def test_delete_event_with_correct_password_succeeds(self):
        """
        Verify that the organizer providing their correct password successfully deletes the event and redirects.
        """
        self.client.login(username='org1@example.com', password='password123', role='organizer')

        # Try to delete with correct password
        response = self.client.post(self.delete_url, {
            'password': 'password123'
        })
        
        # Verify redirect to my events page
        self.assertRedirects(response, self.my_events_url)

        # Verify event is deleted
        self.assertFalse(Event.objects.filter(id=self.event.id).exists())

    def test_administrative_event_editing(self):
        """
        Verify that administrators can edit event details through the administrative event form.
        """
        self.client.login(username='admin@eventsathi.com', password='adminpassword')

        # Get request to admin edit view
        response_get = self.client.get(self.admin_edit_url)
        self.assertEqual(response_get.status_code, 200)
        self.assertIn('form', response_get.context)

        # Post valid form data to modify the event
        updated_data = {
            'title': 'Stunning Future Tech Summit',
            'description': 'An updated description for AI and ML developments.',
            'category': 'hackathon',
            'start_date': (timezone.now() + timedelta(days=12)).strftime('%Y-%m-%dT%H:%M'),
            'end_date': (timezone.now() + timedelta(days=13)).strftime('%Y-%m-%dT%H:%M'),
            'venue': 'Tech Hub Hall A',
            'city': 'San Francisco',
            'max_capacity': 250,
            'status': 'published',
            'tags': 'AI, ML, Hackathon',
            'is_featured': True,
        }

        response_post = self.client.post(self.admin_edit_url, updated_data)
        
        # Verify redirect back to admin dashboard
        self.assertRedirects(response_post, self.admin_dashboard_url)

        # Refresh event from DB and assert updated properties
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'Stunning Future Tech Summit')
        self.assertEqual(self.event.description, 'An updated description for AI and ML developments.')
        self.assertEqual(self.event.category, 'hackathon')
        self.assertEqual(self.event.venue, 'Tech Hub Hall A')
        self.assertEqual(self.event.city, 'San Francisco')
        self.assertEqual(self.event.max_capacity, 250)
        self.assertTrue(self.event.is_featured)

    def test_administrative_event_deletion(self):
        """
        Verify that administrators can delete any event directly from the dashboard without entering passwords.
        """
        self.client.login(username='admin@eventsathi.com', password='adminpassword')

        # Get request to delete confirmation page
        response_get = self.client.get(self.admin_delete_url)
        self.assertEqual(response_get.status_code, 200)

        # Post request to execute deletion directly
        response_post = self.client.post(self.admin_delete_url)
        
        # Verify redirect to dashboard
        self.assertRedirects(response_post, self.admin_dashboard_url)

        # Verify event is deleted
        self.assertFalse(Event.objects.filter(id=self.event.id).exists())
