"""Flask blueprints for Lumen ERP."""
from routes.auth import auth_bp
from routes.main import main_bp
from routes.admin import admin_bp
from routes.hod import hod_bp

__all__ = ['auth_bp', 'main_bp', 'admin_bp', 'hod_bp']
