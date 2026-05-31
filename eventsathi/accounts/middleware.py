from django.shortcuts import redirect
from django.urls import reverse

class PasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                profile = request.user.profile
                if profile.must_change_password:
                    # Allow user to access only logout and the forced password change URL
                    allowed_paths = [
                        reverse('force_change_password'),
                        reverse('logout'),
                    ]
                    # Also don't block static files or admin or other debugging resources
                    if request.path not in allowed_paths and not request.path.startswith('/static/') and not request.path.startswith('/media/'):
                        return redirect('force_change_password')
            except Exception:
                # If profile doesn't exist, proceed as normal
                pass

        return self.get_response(request)
