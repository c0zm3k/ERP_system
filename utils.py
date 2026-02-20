"""Shared utilities and decorators."""
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


def role_required(role):
    """Restrict route access to a single role. Redirects to dashboard if unauthorized."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
