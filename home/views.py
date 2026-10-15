from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import admin_required
from .models import Profile, get_profile


def index(request):
    """Sign in"""
    if request.user.is_authenticated and get_profile(request.user).status == 'approved':
        return redirect('admin_dashboard' if get_profile(request.user).role == 'admin' else 'dashboard')
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        user = authenticate(request, username=email, password=request.POST.get('password', ''))
        if user is None:
            messages.error(request, 'Invalid email or password.')
        else:
            p = get_profile(user)
            if p.status == 'pending':
                messages.warning(request, 'Your account is waiting for admin confirmation.')
            elif p.status == 'rejected':
                messages.error(request, 'Your sign-up request was rejected by the admin.')
            else:
                login(request, user)
                if not request.POST.get('remember'):
                    request.session.set_expiry(0)
                return redirect('admin_dashboard' if p.role == 'admin' else 'dashboard')
    return render(request, 'home/index.html')


def sign(request):
    """Sign up -> creates a *pending* account that an admin must approve."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        pw = request.POST.get('password', '')
        if not email or len(pw) < 6:
            messages.error(request, 'Enter an email and a password of at least 6 characters.')
        elif User.objects.filter(username=email).exists():
            messages.error(request, 'An account with this email already exists.')
        else:
            u = User.objects.create_user(username=email, email=email, password=pw, first_name=name)
            Profile.objects.create(user=u, role='viewer', status='pending')
            messages.success(request, 'Account created! You can sign in once an admin approves your request.')
            return redirect('index')
    return render(request, 'home/sign.html')


def logout_view(request):
    logout(request)
    return redirect('index')


# ----------------------------------------------------------------- admin area
@admin_required
def admin_dashboard(request):
    profiles = (Profile.objects.exclude(status='pending').select_related('user')
                .annotate(bots=Count('user__chatbots')).order_by('created'))
    return render(request, 'home/admin_users.html', {'profiles': profiles, 'page': 'users',
                                                      'pending_count': Profile.objects.filter(status='pending').count()})


@admin_required
def admin_requests(request):
    pending = Profile.objects.filter(status='pending').select_related('user')
    return render(request, 'home/admin_requests.html', {'pending': pending, 'page': 'requests',
                                                         'pending_count': pending.count()})


@admin_required
@require_POST
def admin_action(request, pk, action):
    p = get_object_or_404(Profile, pk=pk)
    if p.user_id == request.user.id:
        messages.error(request, "You can't change your own account.")
    elif action == 'approve':
        p.status = 'approved'
        p.save()
        messages.success(request, f'{p.user.email} approved.')
    elif action == 'reject':
        p.status = 'rejected'
        p.save()
        messages.info(request, f'{p.user.email} rejected.')
    elif action == 'delete':
        p.user.delete()
        messages.info(request, 'User deleted.')
    elif action == 'makeadmin':
        p.role = 'admin' if p.role != 'admin' else 'viewer'
        p.save()
    return redirect(request.POST.get('next') or 'admin_dashboard')
