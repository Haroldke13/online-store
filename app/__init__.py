from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

# Load variables from a local .env file (never committed) so that secrets stay
# out of source control. Harmless when python-dotenv is not installed.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001 - dotenv is an optional convenience
    pass


db = SQLAlchemy()



#Function to create database
def create_database():
    db.create_all()
    print('Database Created')


def create_app():
    #Initialize the flask app
    app = Flask(__name__)

    
    
    # The session-signing key must never be hardcoded: it is read from the
    # environment (see .env.example). Fail loudly rather than silently falling
    # back to a guessable default, which would let anyone forge sessions.
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY is not set. Copy .env.example to .env and provide a "
            "value before starting the app."
        )
    app.config['SECRET_KEY'] = secret_key
    # Database URL comes from the environment so a hosted deployment can point
    # at a managed Postgres; the local SQLite file stays the fallback for dev.
    # Without this override a host with an ephemeral filesystem silently resets
    # accounts, products and orders on every restart.
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        os.environ.get('SQLALCHEMY_DATABASE_URI')
        or os.environ.get('DATABASE_URL')
        or 'sqlite:///database.sqlite3'
    )
    
    # Initialize configurations
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/profile_pics')

    # Initialize database
    db.init_app(app)

    #Error handlers
    
    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('404.html')


    #Login logic
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(id):
        return Customer.query.get(int(id))

    #Import blueprints
    from .views import views
    from .admin import admin
    from .models import Customer, Cart, Product, Order
    
    #Register blueprints

    # Import Blueprints inside function (avoids circular import)
    from .auth import auth
    app.register_blueprint(auth, url_prefix="/")

    app.register_blueprint(views, url_prefix='/') #
    app.register_blueprint(admin, url_prefix='/')

    #Instantiate the database. Creates /instance folfer containing the database file
    with app.app_context():
           create_database()

    return app

