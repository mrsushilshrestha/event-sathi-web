from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from .models import UserProfile


class RegisterForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    phone = forms.CharField(
        max_length=20,
        required=True,
        label='Contact Number',
        widget=forms.TextInput(attrs={'placeholder': 'Enter your contact number'})
    )
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES)
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'placeholder': 'Create secure password'}),
        min_length=6,
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'placeholder': 'Confirm your password'}),
        min_length=6,
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'role']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'role':
                existing_attrs = field.widget.attrs
                existing_attrs['class'] = 'form-control ' + existing_attrs.get('class', '')
                field.widget.attrs = existing_attrs

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Passwords do not match.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = False
        if commit:
            user.save()
            UserProfile.objects.filter(user=user).delete()
            UserProfile.objects.create(
                user=user,
                role=self.cleaned_data['role'],
                phone=self.cleaned_data['phone']
            )
        return user


class SetRegistrationPasswordForm(forms.Form):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        min_length=1,
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        min_length=1,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            existing_attrs = field.widget.attrs
            existing_attrs['class'] = 'form-control ' + existing_attrs.get('class', '')
            field.widget.attrs = existing_attrs

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Passwords do not match.')
        return cleaned_data


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your email address'})
    )
    role = forms.ChoiceField(
        choices=[('attendee', 'Attendee'), ('organizer', 'Organizer')],
        required=False,
        initial='attendee'
    )


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'role':
                existing_attrs = field.widget.attrs
                existing_attrs['class'] = 'form-control ' + existing_attrs.get('class', '')
                field.widget.attrs = existing_attrs

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        selected_role = self.cleaned_data.get('role') or 'attendee'
        role_display = "Attendee" if selected_role == "attendee" else "Organizer"

        if username and password:
            from django.db.models import Q
            # Check if user exists in db
            user = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()
            if not user:
                raise forms.ValidationError(
                    f"No account found with this email. Please sign up as an {role_display}."
                )

            # Block admin accounts from normal login — must use /adminlogin/
            if user.is_superuser or user.is_staff:
                raise forms.ValidationError(
                    "Admin accounts cannot log in here. Please use the Admin Login page at /adminlogin/."
                )

            # Check role match for regular users
            profile = getattr(user, 'profile', None)
            if profile:
                if profile.role != selected_role:
                    other_role = "Attendee" if profile.role == "attendee" else "Organizer"
                    raise forms.ValidationError(
                        f"This account is registered as an {other_role}, not an {role_display}. Please select the correct role or sign up."
                    )
            else:
                raise forms.ValidationError(
                    f"No profile found for this user. Please sign up as an {role_display}."
                )

            # Check password
            if not user.check_password(password):
                raise forms.ValidationError(
                    "Incorrect password. Please try again."
                )

            # Check if active
            if not user.is_active:
                raise forms.ValidationError(
                    "This account is inactive. Please verify your email first."
                )

            self.user_cache = user

        return self.cleaned_data




class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your registered email', 'class': 'form-control'})
    )


class ForceChangePasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            existing_attrs = field.widget.attrs
            existing_attrs['class'] = 'form-control ' + existing_attrs.get('class', '')
            field.widget.attrs = existing_attrs


class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()

    class Meta:
        model = UserProfile
        fields = ['bio', 'phone', 'organization', 'designation', 'photo', 'linkedin', 'twitter', 'website', 'interests']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'interests': forms.TextInput(attrs={'placeholder': 'e.g. AI, Blockchain, Design'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            profile.user.first_name = self.cleaned_data['first_name']
            profile.user.last_name = self.cleaned_data['last_name']
            profile.user.email = self.cleaned_data['email']
            profile.user.save()
            profile.save()
        return profile


class MessageForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write your message...'}),
        max_length=1000
    )


from events.models import Event
from django.utils.text import slugify

class AdminLoginForm(LoginForm):
    def clean(self):
        # Skip LoginForm.clean() to avoid the "admin blocked" check.
        # Call the grandparent (AuthenticationForm) directly and do our own validation.
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            from django.db.models import Q
            user = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()
            if not user:
                raise forms.ValidationError("No admin account found with this email.")
            if not user.check_password(password):
                raise forms.ValidationError("Incorrect password. Please try again.")
            if not user.is_active:
                raise forms.ValidationError("This account is inactive.")
            if not (user.is_staff or user.is_superuser):
                raise forms.ValidationError("You do not have administrative privileges.")
            self.user_cache = user

        return self.cleaned_data


class AdminEventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'category', 'banner',
            'start_date', 'end_date',
            'registration_start', 'registration_end',
            'venue', 'city',
            'is_virtual', 'virtual_link', 'max_capacity', 'price', 'tags', 'is_featured', 'status',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Describe the event…'}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'registration_start': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'registration_end': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'tags': forms.TextInput(attrs={'placeholder': 'e.g. AI, Tech, Innovation'}),
            'virtual_link': forms.URLInput(attrs={'placeholder': 'https://meet.google.com/...'}),
            'title': forms.TextInput(attrs={'placeholder': 'Give the event a catchy title'}),
            'venue': forms.TextInput(attrs={'placeholder': 'Auditorium, Hall, Building name…'}),
            'city': forms.TextInput(attrs={'placeholder': 'Mumbai'}),
            'price': forms.NumberInput(attrs={'placeholder': 'Leave blank for free event', 'min': 0, 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ['start_date', 'end_date', 'registration_start', 'registration_end']:
            self.fields[f].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['registration_start'].required = False
        self.fields['registration_end'].required = False
        self.fields['is_featured'].required = False
        self.fields['virtual_link'].required = False
        self.fields['banner'].required = False
        self.fields['price'].required = False
        
        # Apply bootstrap styling class to all form controls except checkboxes
        for field_name, field in self.fields.items():
            if field_name not in ['is_featured', 'is_virtual']:
                existing_attrs = field.widget.attrs
                existing_attrs['class'] = 'form-control ' + existing_attrs.get('class', '')
                field.widget.attrs = existing_attrs

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        reg_start = cleaned_data.get('registration_start')
        reg_end = cleaned_data.get('registration_end')
        max_capacity = cleaned_data.get('max_capacity')
        is_virtual = cleaned_data.get('is_virtual', False)
        virtual_link = cleaned_data.get('virtual_link', '').strip()
        venue = cleaned_data.get('venue', '').strip()
        city = cleaned_data.get('city', '').strip()

        if max_capacity is not None and max_capacity <= 0:
            self.add_error('max_capacity', 'Maximum capacity must be a positive number.')

        if end_date and start_date and end_date <= start_date:
            self.add_error('end_date', 'End date must be after the start date.')
        if reg_end and reg_start and reg_end <= reg_start:
            self.add_error('registration_end', 'Registration end must be after registration start.')
        if reg_end and start_date and reg_end > start_date:
            self.add_error('registration_end', 'Registration must close before or at the start time of the event.')

        if is_virtual:
            if not virtual_link:
                self.add_error('virtual_link', 'Virtual link is required for virtual events.')
            if not venue:
                cleaned_data['venue'] = 'Virtual / Online'
            if not city:
                cleaned_data['city'] = 'Online'
        else:
            if not venue:
                self.add_error('venue', 'Venue is required for in-person events.')
            if not city:
                self.add_error('city', 'City is required for in-person events.')

        return cleaned_data

    def save(self, commit=True):
        event = super().save(commit=False)
        if not event.slug:
            base_slug = slugify(event.title)
            slug = base_slug
            counter = 1
            while Event.objects.filter(slug=slug).exclude(pk=event.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            event.slug = slug
        if commit:
            event.save()
        return event

