from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    ROLES = [('admin', 'admin'), ('viewer', 'viewer')]
    STATUSES = [('pending', 'pending'), ('approved', 'approved'), ('rejected', 'rejected')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLES, default='viewer')
    status = models.CharField(max_length=10, choices=STATUSES, default='pending')
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.email} ({self.role}/{self.status})'


def get_profile(user):
    """Superusers are always approved admins; everyone else defaults to pending."""
    if user.is_superuser:
        p, _ = Profile.objects.get_or_create(user=user, defaults={'role': 'admin', 'status': 'approved'})
        if p.role != 'admin' or p.status != 'approved':
            p.role, p.status = 'admin', 'approved'
            p.save()
        return p
    p, _ = Profile.objects.get_or_create(user=user)
    return p
