from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm


class ImpostaPasswordForm(PasswordResetForm):
    """Come il reset standard, ma vale anche per chi non ha ancora una password (primo accesso)."""

    def get_users(self, email):
        return get_user_model()._default_manager.filter(email__iexact=email, is_active=True)
