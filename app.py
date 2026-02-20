"""Lumen ERP - Flask application factory and entry point."""
import os

from flask import Flask
from config import Config
from extensions import db, login_manager, migrate

# Import all models to register them with SQLAlchemy metadata
from models import (User, HODDetails, FacultyDetails, StudentDetails, Attendance, 
                    Leaves, Event, Fee, Certificate, TimeSlot, ClassAllotment, 
                    ClassAllotmentRequest, Broadcast)
from routes import auth_bp, main_bp, admin_bp, hod_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    migrate.init_app(app, db)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        if not os.path.exists(app.instance_path):
            os.makedirs(app.instance_path)
        db.create_all()

        # Add new columns to class_allotment if missing (for existing DBs)
        try:
            from sqlalchemy import text
            result = db.session.execute(text("PRAGMA table_info(class_allotment)"))
            columns = [row[1] for row in result]
            if 'slot_id' not in columns:
                db.session.execute(text("ALTER TABLE class_allotment ADD COLUMN slot_id INTEGER REFERENCES time_slot(id)"))
            if 'course' not in columns:
                db.session.execute(text("ALTER TABLE class_allotment ADD COLUMN course VARCHAR(100)"))
            if 'semester' not in columns:
                db.session.execute(text("ALTER TABLE class_allotment ADD COLUMN semester INTEGER"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Add course/semester to class_allotment_request if table exists
        try:
            from sqlalchemy import text
            result = db.session.execute(text("PRAGMA table_info(class_allotment_request)"))
            columns = [row[1] for row in result]
            if 'course' not in columns:
                db.session.execute(text("ALTER TABLE class_allotment_request ADD COLUMN course VARCHAR(100)"))
            if 'semester' not in columns:
                db.session.execute(text("ALTER TABLE class_allotment_request ADD COLUMN semester INTEGER"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Verify broadcast table exists (created by db.create_all() if missing)
        try:
            from sqlalchemy import text
            db.session.execute(text("SELECT 1 FROM broadcast LIMIT 1"))
        except Exception:
            # Table doesn't exist, but db.create_all() should have created it
            pass

        if not User.query.filter_by(role='Admin').first():
            admin = User(username='admin', role='Admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(hod_bp)

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
