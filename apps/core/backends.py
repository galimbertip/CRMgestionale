from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameOEmailBackend(ModelBackend):
    """Permette l'accesso sia con nome utente sia con email."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            u = get_user_model().objects.filter(email__iexact=username).order_by("id").first()
            if u:
                username = u.get_username()
        return super().authenticate(request, username=username, password=password, **kwargs)
