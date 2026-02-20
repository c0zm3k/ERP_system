import os
from config import Config
from app import create_app
from extensions import db

# Calculate db_path without initializing the app context yet
db_uri = Config.SQLALCHEMY_DATABASE_URI
db_path = None
if db_uri.startswith('sqlite:///'):
    db_name = db_uri.split('sqlite:///')[1]
    # Standard Flask instance folder location
    db_path = os.path.join(os.getcwd(), 'instance', db_name)

if db_path and os.path.exists(db_path):
    try:
        os.remove(db_path)
        print(f"Removed existing database at {db_path}")
    except PermissionError:
        print(f"Could not remove {db_path} - it might be locked by another process.")

app = create_app()

with app.app_context():
    db.create_all()
    
    # Re-seed default admin
    from models import User
    if not User.query.filter_by(role='Admin').first():
        admin = User(username='admin', role='Admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Default admin created (admin/admin123)")

    print("Database recreated successfully with updated schema.")
