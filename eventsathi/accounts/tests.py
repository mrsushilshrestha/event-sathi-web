from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail
from accounts.models import UserProfile, EmailVerificationCode
from events.models import Event, Registration
from django.utils import timezone
from datetime import timedelta
import random

class AccountsAuthAndSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.forgot_password_url = reverse('forgot_password')
        self.force_change_password_url = reverse('force_change_password')
        self.home_url = reverse('home')
        self.profile_url = reverse('profile')

        # Test registration credentials
        self.register_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'testuser@example.com',
            'phone': '1234567890',
            'role': 'organizer',
            'password1': 'securepass123',
            'password2': 'securepass123',
        }

    def test_user_registration_creates_inactive_user_and_verification_code(self):
        """
        Verify that submitting valid registration data creates an inactive user, 
        a UserProfile, and a 6-digit EmailVerificationCode.
        """
        # Post to register view
        response = self.client.post(self.register_url, self.register_data)
        
        # Verify the user is created and inactive
        user = User.objects.filter(email='testuser@example.com').first()
        self.assertIsNotNone(user)
        self.assertFalse(user.is_active)
        self.assertEqual(user.username, 'testuser@example.com')
        
        # Verify associated UserProfile is created
        profile = UserProfile.objects.filter(user=user).first()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.role, 'organizer')
        self.assertEqual(profile.phone, '1234567890')
        
        # Verify EmailVerificationCode is created
        verification_code = EmailVerificationCode.objects.filter(user=user).first()
        self.assertIsNotNone(verification_code)
        self.assertEqual(len(verification_code.code), 6)
        self.assertTrue(verification_code.code.isdigit())

        # Verify email is sent to the outbox
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(verification_code.code, mail.outbox[0].body)
        
        # Verify redirected to verify email view
        self.assertRedirects(response, reverse('verify_email', kwargs={'user_id': user.id}))

    def test_email_verification_success_activates_user_and_logs_in(self):
        """
        Verify that submitting the correct verification code successfully activates the
        user account and logs them in.
        """
        # First register
        self.client.post(self.register_url, self.register_data)
        user = User.objects.get(email='testuser@example.com')
        verification_code = EmailVerificationCode.objects.get(user=user)

        # Post correct code to verify_email_view
        verify_url = reverse('verify_email', kwargs={'user_id': user.id})
        response = self.client.post(verify_url, {
            'code': verification_code.code,
            'action': 'verify'
        })

        # Verify redirection to home page after successful login
        self.assertRedirects(response, self.home_url)

        # Verify user is active now
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        # Verify verification code is deleted
        self.assertFalse(EmailVerificationCode.objects.filter(user=user).exists())

        # Verify client is logged in
        self.assertEqual(int(self.client.session['_auth_user_id']), user.id)

    def test_email_verification_failure_keeps_user_inactive(self):
        """
        Verify that submitting an incorrect verification code keeps the user inactive
        and returns a validation error.
        """
        self.client.post(self.register_url, self.register_data)
        user = User.objects.get(email='testuser@example.com')

        verify_url = reverse('verify_email', kwargs={'user_id': user.id})
        # Post incorrect code
        response = self.client.post(verify_url, {
            'code': '000000', # wrong code
            'action': 'verify'
        })

        # Verify user remains inactive
        user.refresh_from_db()
        self.assertFalse(user.is_active)

        # Verify verification code still exists
        self.assertTrue(EmailVerificationCode.objects.filter(user=user).exists())

        # Verify warning/error message in messages
        messages = list(response.context['messages'])
        self.assertTrue(any("Invalid verification code" in str(msg) for msg in messages))

    def test_email_verification_resend_clears_old_and_sends_new(self):
        """
        Verify that resending the verification code deletes old code, generates a fresh
        one, sends it to the test outbox, and redirects back.
        """
        self.client.post(self.register_url, self.register_data)
        user = User.objects.get(email='testuser@example.com')
        old_code = EmailVerificationCode.objects.get(user=user).code
        
        # Clear outbox so we can test the new mail count
        mail.outbox = []

        verify_url = reverse('verify_email', kwargs={'user_id': user.id})
        # Trigger resend
        response = self.client.post(verify_url, {
            'action': 'resend'
        })

        # Verify redirection to verify email page
        self.assertRedirects(response, verify_url)

        # Verify old code is gone and new one is generated
        self.assertFalse(EmailVerificationCode.objects.filter(user=user, code=old_code).exists())
        new_code_obj = EmailVerificationCode.objects.filter(user=user).first()
        self.assertIsNotNone(new_code_obj)
        self.assertNotEqual(new_code_obj.code, old_code)

        # Verify new email is sent to outbox
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(new_code_obj.code, mail.outbox[0].body)

    def test_forgot_password_valid_email_resets_password_and_sets_must_change(self):
        """
        Verify that requesting a reset for a valid email address resets password to a
        10-character temporary string, sets must_change_password=True, sends email, and redirects.
        """
        # Register and activate a user
        self.client.post(self.register_url, self.register_data)
        user = User.objects.get(email='testuser@example.com')
        user.is_active = True
        user.save()

        # Clear outbox
        mail.outbox = []

        # Request forgot password
        response = self.client.post(self.forgot_password_url, {
            'email': 'testuser@example.com'
        })

        # Verify redirection to login page
        self.assertRedirects(response, self.login_url)

        # Verify password flag on UserProfile
        profile = UserProfile.objects.get(user=user)
        self.assertTrue(profile.must_change_password)

        # Verify temporary password has been sent via email
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        self.assertIn("Your EventSathi Temporary Password", mail.outbox[0].subject)
        self.assertIn("Temporary Password:", email_body)

        # Parse temporary password from email body
        # e.g., "Temporary Password: ABCDEFGHIJ"
        parts = email_body.split("Temporary Password: ")
        temp_password = parts[1].split("\n")[0].strip()
        self.assertEqual(len(temp_password), 10)

        # Verify we can authenticate with the new temporary password
        user.refresh_from_db()
        self.assertTrue(user.check_password(temp_password))

    def test_forgot_password_invalid_email_returns_error(self):
        """
        Verify that requesting a password reset for a non-existent email returns an error message.
        """
        response = self.client.post(self.forgot_password_url, {
            'email': 'nonexistent@example.com'
        })
        
        # Verify page renders with error message (does not redirect)
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any("No account found with this email address" in str(msg) for msg in messages))

    def test_forced_password_change_middleware_redirects_and_allows_whitelist(self):
        """
        Verify that a user with must_change_password = True is blocked from other routes
        and redirected to the change-forced-password view, except for whitelisted paths.
        """
        # Register, activate, and set must_change_password
        self.client.post(self.register_url, self.register_data)
        user = User.objects.get(email='testuser@example.com')
        user.is_active = True
        user.save()
        
        profile = UserProfile.objects.get(user=user)
        profile.must_change_password = True
        profile.save()

        # Log in the user
        login_success = self.client.login(username='testuser@example.com', password='securepass123', role='organizer')
        self.assertTrue(login_success)

        # Attempt to access standard routes (e.g. profile, home, network)
        # Profile is @login_required, but first hits PasswordChangeMiddleware
        response = self.client.get(self.profile_url)
        self.assertRedirects(response, self.force_change_password_url)

        response_home = self.client.get(self.home_url)
        # Home page also triggers redirect since it's not whitelisted
        self.assertRedirects(response_home, self.force_change_password_url)

        # Attempt to access whitelisted routes (logout, force_change_password)
        response_force = self.client.get(self.force_change_password_url)
        self.assertEqual(response_force.status_code, 200)

        response_logout = self.client.get(self.logout_url)
        self.assertRedirects(response_logout, self.home_url) # Logout redirects to home and logs out user

    def test_successful_password_change_clears_must_change_password(self):
        """
        Verify that changing password via ForceChangePasswordForm clears must_change_password flag,
        updates session auth hash, and restores full access.
        """
        self.client.post(self.register_url, self.register_data)
        user = User.objects.get(email='testuser@example.com')
        user.is_active = True
        user.save()
        
        profile = UserProfile.objects.get(user=user)
        profile.must_change_password = True
        profile.save()

        self.client.login(username='testuser@example.com', password='securepass123', role='organizer')

        # Change forced password
        response = self.client.post(self.force_change_password_url, {
            'new_password1': 'brandnewpass123',
            'new_password2': 'brandnewpass123',
        })

        # Verify redirect to home
        self.assertRedirects(response, self.home_url)

        # Verify must_change_password flag is cleared
        profile.refresh_from_db()
        self.assertFalse(profile.must_change_password)

        # Verify password is updated on user
        user.refresh_from_db()
        self.assertTrue(user.check_password('brandnewpass123'))

        # Verify full access is restored (no longer redirected from profile)
        response_profile = self.client.get(self.profile_url)
        self.assertEqual(response_profile.status_code, 200)

    def test_login_validation_non_existent_user(self):
        """
        Verify that attempting to log in with a non-existent email returns the specific error:
        "No account found with this email. Please sign up as an Attendee." (or "Organizer.")
        """
        # Select Attendee role
        response = self.client.post(self.login_url, {
            'username': 'nonexistent@example.com',
            'password': 'somepassword',
            'role': 'attendee'
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn("No account found with this email. Please sign up as an Attendee.", form.non_field_errors())

        # Select Organizer role
        response_org = self.client.post(self.login_url, {
            'username': 'nonexistent@example.com',
            'password': 'somepassword',
            'role': 'organizer'
        })
        self.assertEqual(response_org.status_code, 200)
        form_org = response_org.context['form']
        self.assertFalse(form_org.is_valid())
        self.assertIn("No account found with this email. Please sign up as an Organizer.", form_org.non_field_errors())

    def test_login_validation_role_mismatch(self):
        """
        Verify that attempting to log in with a role that doesn't match the profile role returns:
        "This account is registered as an Organizer, not an Attendee. Please select the correct role or sign up."
        """
        # Register an organizer
        self.client.post(self.register_url, self.register_data)
        user = User.objects.get(email='testuser@example.com')
        user.is_active = True
        user.save()

        # Try logging in as Attendee
        response = self.client.post(self.login_url, {
            'username': 'testuser@example.com',
            'password': 'securepass123',
            'role': 'attendee'
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn(
            "This account is registered as an Organizer, not an Attendee. Please select the correct role or sign up.",
            form.non_field_errors()
        )

    def test_login_validation_incorrect_password(self):
        """
        Verify that attempting to log in with an incorrect password returns:
        "Incorrect password. Please try again."
        """
        # Register and activate organizer
        self.client.post(self.register_url, self.register_data)
        user = User.objects.get(email='testuser@example.com')
        user.is_active = True
        user.save()

        # Try logging in with wrong password
        response = self.client.post(self.login_url, {
            'username': 'testuser@example.com',
            'password': 'wrongpassword',
            'role': 'organizer'
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn("Incorrect password. Please try again.", form.non_field_errors())


class CustomAdministrativePortalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_login_url = reverse('admin_login')
        self.admin_dashboard_url = reverse('admin_dashboard')
        
        # Create standard organizer and attendee
        self.organizer_user = User.objects.create_user(
            username='organizer@example.com',
            email='organizer@example.com',
            password='password123',
            first_name='Org',
            last_name='User'
        )
        self.organizer_profile = UserProfile.objects.create(
            user=self.organizer_user,
            role='organizer',
            phone='9876543210',
            is_verified=False
        )

        self.attendee_user = User.objects.create_user(
            username='attendee@example.com',
            email='attendee@example.com',
            password='password123',
            first_name='Att',
            last_name='User'
        )
        self.attendee_profile = UserProfile.objects.create(
            user=self.attendee_user,
            role='attendee',
            phone='9876543211',
            is_verified=False
        )

        # Create admin user
        self.admin_user = User.objects.create_superuser(
            username='admin@eventsathi.com',
            email='admin@eventsathi.com',
            password='adminpassword',
            first_name='Admin',
            last_name='Portal'
        )

        # Create a test event
        self.event = Event.objects.create(
            organizer=self.organizer_user,
            title='Epic Tech Conference',
            slug='epic-tech-conference',
            description='Tech discussions and networking.',
            category='conference',
            start_date=timezone.now() + timedelta(days=5),
            end_date=timezone.now() + timedelta(days=6),
            venue='Tech Hub Auditorium',
            city='Boston',
            max_capacity=100,
            status='published',
            is_featured=False
        )

    def test_standard_users_denied_admin_access(self):
        """
        Verify that non-staff/non-superuser cannot access the admin login page
        or the admin dashboard (are redirected or rejected).
        """
        # Try as organizer
        self.client.login(username='organizer@example.com', password='password123', role='organizer')
        
        response_login = self.client.get(self.admin_login_url)
        # admin_login_view has: if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser): redirect dashboard.
        # But if standard authenticated user accesses it, it renders the admin login page with the form.
        self.assertEqual(response_login.status_code, 200)

        response_dashboard = self.client.get(self.admin_dashboard_url)
        # admin_dashboard_view has decorator: @user_passes_test(lambda u: u.is_authenticated and (u.is_staff or u.is_superuser), login_url='admin_login')
        # So it should redirect to admin_login
        self.assertRedirects(response_dashboard, f"{self.admin_login_url}?next={self.admin_dashboard_url}")

    def test_admin_successful_login_and_dashboard_statistics(self):
        """
        Verify that a superuser can log in via admin_login and view the dashboard statistics.
        """
        # Verify admin login view
        response = self.client.post(self.admin_login_url, {
            'username': 'admin@eventsathi.com',
            'password': 'adminpassword'
        })
        self.assertRedirects(response, self.admin_dashboard_url)

        # Access dashboard
        response_dashboard = self.client.get(self.admin_dashboard_url)
        self.assertEqual(response_dashboard.status_code, 200)
        
        # Verify stats in context
        self.assertEqual(response_dashboard.context['total_events'], 1)
        self.assertEqual(response_dashboard.context['total_users'], 3) # admin, organizer, attendee
        self.assertEqual(response_dashboard.context['total_registrations'], 0)

    def test_admin_dashboard_search_and_filtering(self):
        """
        Verify that search ('q') and filter ('status', 'tab') query parameters work on the dashboard.
        """
        self.client.login(username='admin@eventsathi.com', password='adminpassword')

        # 1. Search for event by title
        response = self.client.get(self.admin_dashboard_url, {'q': 'Epic'})
        self.assertIn(self.event, response.context['events'])

        # Search for non-existent event
        response_empty = self.client.get(self.admin_dashboard_url, {'q': 'NonExistentTitle'})
        self.assertNotIn(self.event, response_empty.context['events'])

        # 2. Filter by status
        response_status_pub = self.client.get(self.admin_dashboard_url, {'status': 'published'})
        self.assertIn(self.event, response_status_pub.context['events'])

        response_status_draft = self.client.get(self.admin_dashboard_url, {'status': 'draft'})
        self.assertNotIn(self.event, response_status_draft.context['events'])

        # 3. Tab routing
        response_tab_org = self.client.get(self.admin_dashboard_url, {'tab': 'organizers'})
        self.assertEqual(response_tab_org.context['active_tab'], 'organizers')

    def test_admin_toggle_organizer_verification(self):
        """
        Verify that admins can toggle an organizer's verification status (is_verified).
        """
        self.client.login(username='admin@eventsathi.com', password='adminpassword')

        toggle_url = reverse('admin_organizer_toggle_verification', kwargs={'user_id': self.organizer_user.id})
        
        # Initial status is False
        self.assertFalse(self.organizer_profile.is_verified)

        # Toggle via POST
        response = self.client.post(toggle_url)
        self.assertRedirects(response, '/adminlogin/dashboard/?tab=organizers')

        # Verify updated status
        self.organizer_profile.refresh_from_db()
        self.assertTrue(self.organizer_profile.is_verified)

        # Toggle back to False
        self.client.post(toggle_url)
        self.organizer_profile.refresh_from_db()
        self.assertFalse(self.organizer_profile.is_verified)

    def test_admin_toggle_event_featured_and_change_status(self):
        """
        Verify that admins can toggle an event's featured status and modify its status.
        """
        self.client.login(username='admin@eventsathi.com', password='adminpassword')

        # 1. Toggle featured status
        toggle_feature_url = reverse('admin_event_toggle_feature', kwargs={'slug': self.event.slug})
        self.assertFalse(self.event.is_featured)

        response_feat = self.client.post(toggle_feature_url)
        self.assertRedirects(response_feat, self.admin_dashboard_url)
        self.event.refresh_from_db()
        self.assertTrue(self.event.is_featured)

        # 2. Change status
        change_status_url = reverse('admin_event_change_status', kwargs={'slug': self.event.slug})
        response_status = self.client.post(change_status_url, {'status': 'completed'})
        self.assertRedirects(response_status, self.admin_dashboard_url)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, 'completed')

        # Change to invalid status
        response_invalid = self.client.post(change_status_url, {'status': 'super_invalid_status'})
        self.assertRedirects(response_invalid, self.admin_dashboard_url)
        # Status should remain 'completed'
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, 'completed')

    def test_admin_delete_organizer_and_cascade_events(self):
        """
        Verify that admins can delete an organizer, which successfully deletes the organizer 
        profile, their user account, and cascades to permanently delete all of their events.
        """
        self.client.login(username='admin@eventsathi.com', password='adminpassword')
        delete_url = reverse('admin_organizer_delete', kwargs={'user_id': self.organizer_user.id})

        # Check organizer exists before delete
        self.assertTrue(User.objects.filter(id=self.organizer_user.id).exists())
        self.assertTrue(Event.objects.filter(id=self.event.id).exists())

        # Perform deletion
        response = self.client.post(delete_url)
        self.assertRedirects(response, '/adminlogin/dashboard/?tab=organizers')

        # Verify cascade deletions
        self.assertFalse(User.objects.filter(id=self.organizer_user.id).exists())
        self.assertFalse(UserProfile.objects.filter(user_id=self.organizer_user.id).exists())
        self.assertFalse(Event.objects.filter(id=self.event.id).exists())
