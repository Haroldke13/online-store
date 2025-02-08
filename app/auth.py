from .forms import LoginForm, SignUpForm, PasswordChangeForm
from .models import Customer
from flask_login import login_user, login_required, logout_user
import os
from flask import render_template, request, redirect, flash, url_for,Blueprint,current_app
from flask_login import current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from datetime import datetime
from . import db

auth = Blueprint('auth', __name__)




UPLOAD_FOLDER_ = 'static/profile_pics'

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    from werkzeug.utils import secure_filename
    from flask import flash, redirect, render_template, request, url_for, current_app
    from werkzeug.security import generate_password_hash
    from datetime import datetime
    from app.models import Customer
    from app import db
    
    form = SignUpForm()
    
    if form.validate_on_submit():
        email = form.email.data
        username = form.username.data
        password1 = form.password1.data
        password2 = form.password2.data
        profile_pic = request.files.get('profile_pic')  # Get file safely

        if password1 != password2:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('auth.signup'))

        # Hash password
        password_hash = generate_password_hash(password1)

        # Check if email already exists
        existing_user = Customer.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists!', 'danger')
            return redirect(url_for('auth.signup'))

        # Save profile picture
        if profile_pic and profile_pic.filename:
            filename = secure_filename(f"{username}_{profile_pic.filename}")
            file_path = os.path.join(current_app.root_path, 'static/profile_pics', filename)
            profile_pic.save(file_path)
            profile_pic_url = filename  # Store only filename in DB
        else:
            profile_pic_url = 'default.png'  # Default profile picture in static/profile_pics/

        # Create new user
        new_customer = Customer(
            email=email,
            username=username,
            password_hash=password_hash,
            date_joined=datetime.utcnow(),
            profile_picture=profile_pic_url  # Ensure model has this field
        )

        try:
            db.session.add(new_customer)
            db.session.commit()
            flash('Account created successfully! You can now login.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'danger')

    return render_template('signup.html', form=form)


from flask import current_app, send_from_directory
import os

@auth.route('/profile_pics/<path:filename>')
def profile_pics(filename):
    upload_folder = current_app.config['UPLOAD_FOLDER']  # Now safe to use
    return send_from_directory(upload_folder, filename)



@auth.route('/profile/<int:customer_id>')
@login_required
def profile(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    if customer.id != current_user.id:
        flash("You do not have permission to view this profile.", "danger")
        return redirect(url_for('views.home'))

    profile_picture = url_for('auth.profile_pics', filename=customer.profile_picture) if customer.profile_picture else url_for('static', filename='profile_pics/default.png')

    return render_template('profile.html', customer=customer, profile_picture=profile_picture)



@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        customer = Customer.query.filter_by(email=email).first()

        if customer:
            if customer.verify_password(password=password):
                login_user(customer)
                return redirect('/')
            else:
                flash('Incorrect Email or Password')

        else:
            flash('Account does not exist please Sign Up')

    return render_template('login.html', form=form)


@auth.route('/logout', methods=['GET', 'POST'])
@login_required
def log_out():
    logout_user()
    return redirect('/')






@auth.route('/change-password/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def change_password(customer_id):
    form = PasswordChangeForm()
    customer = Customer.query.get(customer_id)
    if form.validate_on_submit():
        current_password = form.current_password.data
        new_password = form.new_password.data
        confirm_new_password = form.confirm_new_password.data

        if customer.verify_password(current_password):
            if new_password == confirm_new_password:
                customer.password = confirm_new_password
                db.session.commit()
                flash('Password Updated Successfully')
                return redirect(f'/profile/{customer.id}')
            else:
                flash('New Passwords do not match!!')

        else:
            flash('Current Password is Incorrect')

    return render_template('change_password.html', form=form)







