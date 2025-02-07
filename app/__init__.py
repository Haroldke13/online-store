from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os


db = SQLAlchemy()



#Function to create database
def create_database():
    db.create_all()
    print('Database Created')


def create_app():
    #Initialize the flask app
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = 'do_not_show_this_to_anyone_100'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///database.sqlite3'
    

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
    from .auth import auth
    from .admin import admin
    from .models import Customer, Cart, Product, Order
    
    #Register blueprints

    app.register_blueprint(views, url_prefix='/') # localhost:5000/about-us
    app.register_blueprint(auth, url_prefix='/') # localhost:5000/auth/change-password
    app.register_blueprint(admin, url_prefix='/')

    #Instantiate the database. Creates /instance folfer containing the database file
    with app.app_context():
           create_database()

    return app

