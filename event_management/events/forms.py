
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Username or email",
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "placeholder": "Enter username or email",
                "autocomplete": "username",
                "class": "form-control",
            }
        ),
    )

    def clean(self):
        identifier = self.cleaned_data.get("username", "").strip()

        if identifier and "@" in identifier:
            matching_users = User.objects.filter(email__iexact=identifier)

            if matching_users.count() > 1:
                raise ValidationError(
                    "Multiple accounts use this email. Contact support."
                )

            if matching_users.count() == 1:
                self.cleaned_data["username"] = (
                    matching_users.first().get_username()
                )

        return super().clean()
