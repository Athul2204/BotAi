from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from .models import get_profile


def approved_required(view):
    @wraps(view)
    def wrapper(request, *a, **kw):
        if not request.user.is_authenticated:
            return redirect('index')
        if get_profile(request.user).status != 'approved':
            logout(request)
            messages.warning(request, 'Your account is not approved yet.')
            return redirect('index')
        return view(request, *a, **kw)
    return wrapper


def admin_required(view):
    @wraps(view)
    @approved_required
    def wrapper(request, *a, **kw):
        if get_profile(request.user).role != 'admin':
            return redirect('dashboard')
        return view(request, *a, **kw)
    return wrapper
