from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from home.models import get_profile


class Command(BaseCommand):
    help = 'Create the first admin account (default admin@gmail.com / admin123)'

    def add_arguments(self, parser):
        parser.add_argument('--email', default='admin@gmail.com')
        parser.add_argument('--password', default='admin123')

    def handle(self, *a, **o):
        u, created = User.objects.get_or_create(username=o['email'], defaults={
            'email': o['email'], 'first_name': 'Admin', 'is_staff': True, 'is_superuser': True})
        u.set_password(o['password'])
        u.is_staff = u.is_superuser = True
        u.save()
        get_profile(u)
        self.stdout.write(self.style.SUCCESS(f"Admin ready: {o['email']} / {o['password']}"))
