"""Forms for account creation and management."""

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from apps.shared.forms import BootstrapFormMixin

User = get_user_model()


class TableOfficialCreationForm(BootstrapFormMixin, UserCreationForm):
    """Create a table official without allowing role escalation in the form."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.TABLE_OFFICIAL
        user.is_staff = False
        if commit:
            user.save()
            self.save_m2m()
        return user
