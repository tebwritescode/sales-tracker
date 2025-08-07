from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, FloatField, IntegerField, SelectField, DateField, PasswordField, BooleanField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, Email, Length, EqualTo, Optional, ValidationError
import re
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import json
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
import os
import tempfile
from functools import wraps

# Application version and metadata
__version__ = "1.1.0"
__author__ = "tebwritescode"
__website__ = "https://tebwrites.code"
__docker_hub__ = "tebwritescode"

app = Flask(__name__)

# Configuration from environment variables
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///sales_tracker.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.environ.get('SQLALCHEMY_TRACK_MODIFICATIONS', 'False').lower() == 'true'
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', '16777216'))  # 16MB default

db = SQLAlchemy(app)

# Custom email validator that only validates when email is provided
def validate_email_if_present(form, field):
    """Custom validator for optional email fields"""
    if field.data and field.data.strip():
        # Simple email regex pattern
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, field.data.strip()):
            raise ValidationError('Invalid email address format')

# Custom coerce function for SelectField that handles empty strings
def coerce_int_or_none(value):
    """Convert value to int, treating empty strings as None/0"""
    if value == '' or value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), nullable=True)  # Made optional
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False) 
    role = db.Column(db.String(20), default='viewer')  # viewer, user, manager, admin
    permission_level = db.Column(db.Integer, default=1)  # 1=viewer, 2=user, 3=manager, 4=admin
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Employee-specific fields (for viewer/employee role)
    hire_date = db.Column(db.Date, nullable=True)
    base_salary = db.Column(db.Float, default=0.0)
    commission_rate = db.Column(db.Float, default=0.05)  # 5% default
    draw_amount = db.Column(db.Float, default=0.0)
    
    # Relationships
    sales = db.relationship('Sales', backref='user', lazy=True)
    goals = db.relationship('Goals', backref='user', lazy=True)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def has_permission(self, required_level):
        return self.active and self.permission_level >= required_level
    
    def get_role_display(self):
        role_map = {
            'viewer': 'Viewer',
            'user': 'User', 
            'manager': 'Manager',
            'admin': 'Administrator'
        }
        return role_map.get(self.role, 'Unknown')


class Sales(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    revenue_amount = db.Column(db.Float, nullable=False)
    number_of_deals = db.Column(db.Integer, default=1)
    commission_earned = db.Column(db.Float, default=0.0)
    draw_payment = db.Column(db.Float, default=0.0)
    period_type = db.Column(db.String(20), default='month')

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    default_analytics_period = db.Column(db.String(20), default='YTD')
    admin_username = db.Column(db.String(50), default='admin')
    admin_password_hash = db.Column(db.String(128))
    field_toggles = db.Column(db.Text, default='{}')
    color_scheme = db.Column(db.String(50), default='default')

class Goals(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    period_type = db.Column(db.String(20), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    revenue_goal = db.Column(db.Float, default=0.0)
    deals_goal = db.Column(db.Integer, default=0)

# Forms
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class SalesForm(FlaskForm):
    user_id = SelectField('Employee/User', coerce=coerce_int_or_none, validators=[Optional()])
    date = DateField('Date', validators=[Optional()])
    revenue_amount = FloatField('Revenue Amount ($)', validators=[Optional(), NumberRange(min=0)])
    number_of_deals = IntegerField('Number of Deals', validators=[Optional(), NumberRange(min=1)])
    draw_payment = FloatField('Draw Payment ($)', validators=[Optional(), NumberRange(min=0)])

class UserProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[Optional(), validate_email_if_present])
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=50)])
    current_password = PasswordField('Current Password')
    new_password = PasswordField('New Password', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', validators=[
        EqualTo('new_password', message='Passwords must match')
    ])
    
    # Employee fields (for viewer role users)
    hire_date = DateField('Hire Date', validators=[Optional()])
    base_salary = FloatField('Base Salary ($)', validators=[Optional(), NumberRange(min=0)])
    commission_rate = FloatField('Commission Rate (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    draw_amount = FloatField('Draw Amount ($)', validators=[Optional(), NumberRange(min=0)])

class SettingsForm(FlaskForm):
    default_analytics_period = SelectField('Default Analytics Period', 
                                         choices=[('YTD', 'Year to Date'), ('month', 'Monthly'), 
                                                ('quarter', 'Quarterly'), ('year', 'Yearly')])
    commission_display = SelectField('Commission Display', choices=[('percentage', 'Percentage'), ('dollar', 'Dollar Amount')])
    draw_display = SelectField('Draw Display', choices=[('dollar', 'Dollar Amount'), ('percentage', 'Percentage')])
    color_scheme = SelectField('Color Scheme', choices=[
        ('default', 'Default Blue'),
        ('dark', 'Dark Theme'),
        ('green', 'Nature Green'),
        ('purple', 'Royal Purple'),
        ('orange', 'Sunset Orange'),
        ('teal', 'Ocean Teal'),
        ('red', 'Corporate Red'),
        ('pink', 'Modern Pink')
    ])

class GoalsForm(FlaskForm):
    user_id = SelectField('Employee/User', coerce=coerce_int_or_none, validators=[DataRequired()])
    period_type = SelectField('Period Type', choices=[('week', 'Weekly'), ('month', 'Monthly'), ('quarter', 'Quarterly')])
    period_start = DateField('Period Start', validators=[DataRequired()])
    period_end = DateField('Period End', validators=[DataRequired()])
    revenue_goal = FloatField('Revenue Goal ($)', validators=[NumberRange(min=0)])
    deals_goal = IntegerField('Deals Goal', validators=[NumberRange(min=0)])

class BulkUploadForm(FlaskForm):
    file = FileField('CSV File', validators=[FileAllowed(['csv'], 'CSV files only!')])

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[Optional(), validate_email_if_present])
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=50)])
    role = SelectField('Role', choices=[
        ('viewer', 'Employee - Can view data and sales reports'),
        ('user', 'Data Entry - Can enter data and view reports'),
        ('manager', 'Manager - Can manage employees and access advanced features'),
        ('admin', 'Administrator - Full access to all features')
    ])
    active = BooleanField('Active', default=True)
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match')
    ])
    
    # Employee fields (shown when role is viewer/employee)
    hire_date = DateField('Hire Date', validators=[Optional()])
    base_salary = FloatField('Base Salary ($)', validators=[Optional(), NumberRange(min=0)])
    commission_rate = FloatField('Commission Rate (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    draw_amount = FloatField('Draw Amount ($)', validators=[Optional(), NumberRange(min=0)])

class UserEditForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[Optional(), validate_email_if_present])
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=50)])
    role = SelectField('Role', choices=[
        ('viewer', 'Employee - Can view data and sales reports'),
        ('user', 'Data Entry - Can enter data and view reports'),
        ('manager', 'Manager - Can manage employees and access advanced features'),
        ('admin', 'Administrator - Full access to all features')
    ])
    active = BooleanField('Active')
    new_password = PasswordField('New Password (leave blank to keep current)', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', validators=[
        EqualTo('new_password', message='Passwords must match')
    ])
    
    # Employee fields (shown when role is viewer/employee)
    hire_date = DateField('Hire Date', validators=[Optional()])
    base_salary = FloatField('Base Salary ($)', validators=[Optional(), NumberRange(min=0)])
    commission_rate = FloatField('Commission Rate (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    draw_amount = FloatField('Draw Amount ($)', validators=[Optional(), NumberRange(min=0)])

class NewLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

# Helper functions
def get_current_user():
    """Get the currently logged in user"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

def login_required(permission_level=1):
    """Decorator to require login with minimum permission level
    1=viewer, 2=user, 3=manager, 4=admin
    """
    def login_decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user or not user.has_permission(permission_level):
                flash('You need to login with sufficient permissions to access this page.', 'error')
                return redirect(url_for('analytics'))
            return f(*args, **kwargs)
        return wrapper
    return login_decorator

def admin_required(f):
    """Decorator specifically for admin-only functions"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or not user.has_permission(4):
            flash('Administrator access required.', 'error')
            return redirect(url_for('analytics'))
        return f(*args, **kwargs)
    return wrapper

def manager_required(f):
    """Decorator for manager-level functions"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or not user.has_permission(3):
            flash('Manager access or higher required.', 'error')
            return redirect(url_for('analytics'))
        return f(*args, **kwargs)
    return wrapper

def calculate_commission(revenue, commission_rate, field_toggles):
    toggles = json.loads(field_toggles) if field_toggles else {}
    if toggles.get('commission_display') == 'dollar':
        return commission_rate
    else:
        return revenue * (commission_rate / 100)

def get_current_color_scheme():
    try:
        settings = Settings.query.first()
        return settings.color_scheme if settings and settings.color_scheme else 'default'
    except Exception as e:
        print(f"Error getting color scheme: {e}")
        return 'default'

def get_period_dates(period_type, custom_start=None, custom_end=None):
    today = datetime.now().date()
    
    if period_type == 'YTD':
        start_date = datetime(today.year, 1, 1).date()
        end_date = today
    elif period_type == 'month':
        start_date = datetime(today.year, today.month, 1).date()
        end_date = today
    elif period_type == 'quarter':
        quarter = (today.month - 1) // 3 + 1
        start_date = datetime(today.year, 3 * quarter - 2, 1).date()
        end_date = today
    elif period_type == 'year':
        start_date = datetime(today.year, 1, 1).date()
        end_date = datetime(today.year, 12, 31).date()
    elif period_type == 'custom' and custom_start and custom_end:
        start_date = custom_start
        end_date = custom_end
    else:
        start_date = today
        end_date = today
    
    return start_date, end_date

# Context processor to make color scheme and user info available in all templates
@app.context_processor
def inject_template_vars():
    return {
        'current_color_scheme': get_current_color_scheme(),
        'current_user': get_current_user()
    }

# Routes
@app.route('/')
def index():
    return redirect(url_for('analytics'))

@app.route('/login', methods=['GET', 'POST'])
def new_login():
    form = NewLoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data) and user.active:
            session['user_id'] = user.id
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash(f'Welcome back, {user.first_name}!', 'success')
            
            # Redirect based on role
            if user.has_permission(4):  # Admin
                return redirect(url_for('management'))
            elif user.has_permission(3):  # Manager
                return redirect(url_for('analytics'))
            else:  # User/Viewer
                return redirect(url_for('analytics'))
        else:
            flash('Invalid username or password, or account is inactive.', 'error')
    
    # Redirect to analytics page which now contains the login form
    return redirect(url_for('analytics'))

# Keep old login for backward compatibility with Settings admin
@app.route('/admin_login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        settings = Settings.query.first()
        if not settings:
            settings = Settings(admin_password_hash=generate_password_hash('admin'))
            db.session.add(settings)
            db.session.commit()
        
        if (form.username.data == settings.admin_username and 
            check_password_hash(settings.admin_password_hash, form.password.data)):
            session['admin_logged_in'] = True
            flash('Login successful!', 'success')
            return redirect(url_for('management'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('admin_logged_in', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('analytics'))

@app.route('/test_login')
def test_login():
    return render_template('test_login.html')

@app.route('/management')
@login_required(3)  # Manager level required
def management():
    employees = User.query.filter_by(role='viewer').all()  # Show viewer/employee users
    return render_template('management.html', employees=employees)

@app.route('/analytics')
def analytics():
    user = get_current_user()
    is_logged_in = user is not None
    show_blur = not is_logged_in
    
    period_type = request.args.get('period', 'YTD')
    custom_start = request.args.get('start_date')
    custom_end = request.args.get('end_date')
    
    if custom_start:
        custom_start = datetime.strptime(custom_start, '%Y-%m-%d').date()
    if custom_end:
        custom_end = datetime.strptime(custom_end, '%Y-%m-%d').date()
    
    start_date, end_date = get_period_dates(period_type, custom_start, custom_end)
    
    # Get sales data for the period (but show demo data if not logged in)
    if is_logged_in:
        sales_data = db.session.query(
            (User.first_name + ' ' + User.last_name).label('name'),
            db.func.sum(Sales.revenue_amount).label('total_revenue'),
            db.func.sum(Sales.number_of_deals).label('total_deals'),
            db.func.sum(Sales.commission_earned).label('total_commission')
        ).join(Sales).filter(
            Sales.date >= start_date,
            Sales.date <= end_date,
            User.active == True
        ).group_by(User.id).all()
        
        employees = User.query.filter_by(active=True, role='viewer').all()  # Only viewer/employee users
    else:
        # Show demo data for logged out users
        from collections import namedtuple
        SalesData = namedtuple('SalesData', ['name', 'total_revenue', 'total_deals', 'total_commission'])
        sales_data = [
            SalesData('Demo User 1', 125000, 45, 6250),
            SalesData('Demo User 2', 98000, 32, 4900),
            SalesData('Demo User 3', 156000, 52, 7800)
        ]
        employees = []
    
    # Create login form for the blur overlay
    login_form = NewLoginForm()
    
    return render_template('analytics.html', 
                         sales_data=sales_data, 
                         employees=employees,
                         period_type=period_type,
                         start_date=start_date,
                         end_date=end_date,
                         show_blur=show_blur,
                         is_logged_in=is_logged_in,
                         login_form=login_form)

@app.route('/data_entry', methods=['GET', 'POST'])
@login_required(2)  # User level required
def data_entry():
    form = SalesForm()
    bulk_form = BulkUploadForm()
    
    # Populate user/employee choices (viewers and above who can have sales data)
    employees = User.query.filter_by(active=True, role='viewer').all()
    form.user_id.choices = [(0, 'Select Employee/User')] + [(e.id, f"{e.first_name} {e.last_name}") for e in employees]
    
    if form.validate_on_submit():
        # Handle optional fields with defaults
        if not form.user_id.data or form.user_id.data == 0:
            flash('Please select a user/employee for the sales entry', 'error')
            return render_template('data_entry.html', 
                                 form=form, 
                                 bulk_form=bulk_form,
                                 recent_sales=[])
        
        user = User.query.get(form.user_id.data)
        if not user:
            flash('Selected user not found', 'error')
            return render_template('data_entry.html', 
                                 form=form, 
                                 bulk_form=bulk_form,
                                 recent_sales=[])
        
        # Use defaults for optional fields
        date = form.date.data or datetime.utcnow().date()
        revenue_amount = form.revenue_amount.data or 0.0
        number_of_deals = form.number_of_deals.data or 1
        draw_payment = form.draw_payment.data or 0.0
        
        settings = Settings.query.first()
        field_toggles = settings.field_toggles if settings else '{}'
        
        commission = calculate_commission(revenue_amount, 
                                        user.commission_rate, 
                                        field_toggles)
        
        sale = Sales(
            user_id=form.user_id.data,
            date=date,
            revenue_amount=revenue_amount,
            number_of_deals=number_of_deals,
            commission_earned=commission,
            draw_payment=draw_payment
        )
        
        db.session.add(sale)
        db.session.commit()
        flash('Sales data added successfully!', 'success')
        return redirect(url_for('data_entry'))
    
    recent_sales = Sales.query.join(User).order_by(Sales.date.desc()).limit(10).all()
    
    return render_template('data_entry.html', 
                         form=form, 
                         bulk_form=bulk_form,
                         recent_sales=recent_sales)


@app.route('/profile', methods=['GET', 'POST'])
@login_required(1)  # Any logged-in user
def profile():
    """User profile page - allows users to change their own profile and password"""
    current_user_obj = get_current_user()
    form = UserProfileForm()
    
    # Populate form with current user data on GET
    if request.method == 'GET':
        form.username.data = current_user_obj.username
        form.email.data = current_user_obj.email
        form.first_name.data = current_user_obj.first_name
        form.last_name.data = current_user_obj.last_name
        # Populate employee fields if user is viewer/employee
        if current_user_obj.role == 'viewer':
            form.hire_date.data = current_user_obj.hire_date
            form.base_salary.data = current_user_obj.base_salary
            form.commission_rate.data = current_user_obj.commission_rate
            form.draw_amount.data = current_user_obj.draw_amount
    
    if form.validate_on_submit():
        # Check if username or email conflicts with other users
        existing_user = User.query.filter(
            ((User.username == form.username.data) | 
             (User.email == form.email.data)) &
            (User.id != current_user_obj.id)
        ).first()
        
        if existing_user:
            flash('Username or email already exists for another user', 'error')
            return render_template('profile.html', form=form)
        
        # Update basic profile information
        current_user_obj.username = form.username.data
        current_user_obj.email = form.email.data
        current_user_obj.first_name = form.first_name.data
        current_user_obj.last_name = form.last_name.data
        
        # Update employee fields if user is viewer/employee
        if current_user_obj.role == 'viewer':
            current_user_obj.hire_date = form.hire_date.data
            current_user_obj.base_salary = form.base_salary.data or 0.0
            current_user_obj.commission_rate = form.commission_rate.data or 0.05
            current_user_obj.draw_amount = form.draw_amount.data or 0.0
        
        # Handle password change
        if form.new_password.data:
            if not form.current_password.data:
                flash('Current password is required to set a new password', 'error')
                return render_template('profile.html', form=form)
            
            if not current_user_obj.check_password(form.current_password.data):
                flash('Current password is incorrect', 'error')
                return render_template('profile.html', form=form)
            
            current_user_obj.set_password(form.new_password.data)
            flash('Password updated successfully!', 'success')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile.html', form=form)

@app.route('/settings', methods=['GET', 'POST'])
@admin_required  # Admin only - for system-wide settings
def settings():
    settings_obj = Settings.query.first()
    if not settings_obj:
        settings_obj = Settings()
        db.session.add(settings_obj)
        db.session.commit()
    
    form = SettingsForm(obj=settings_obj)
    
    if form.validate_on_submit():
        settings_obj.default_analytics_period = form.default_analytics_period.data
        
        field_toggles = {
            'commission_display': form.commission_display.data,
            'draw_display': form.draw_display.data
        }
        settings_obj.field_toggles = json.dumps(field_toggles)
        settings_obj.color_scheme = form.color_scheme.data
        
        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings'))
    
    return render_template('settings.html', form=form)

@app.route('/users')
@admin_required
def users():
    """User management page - admin only"""
    users = User.query.all()
    return render_template('users.html', users=users)

@app.route('/add_user', methods=['GET', 'POST'])
@admin_required
def add_user():
    """Add new user - admin only"""
    form = UserForm()
    
    
    if form.validate_on_submit():
        # Check if username or email already exists
        existing_user = User.query.filter(
            (User.username == form.username.data) | 
            (User.email == form.email.data)
        ).first()
        
        if existing_user:
            flash('Username or email already exists', 'error')
            return render_template('add_user.html', form=form)
        
        # Set permission level based on role
        role_permissions = {
            'viewer': 1,
            'user': 2, 
            'manager': 3,
            'admin': 4
        }
        
        user = User(
            username=form.username.data,
            email=form.email.data if form.email.data else None,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role=form.role.data,
            permission_level=role_permissions[form.role.data],
            active=form.active.data,
            hire_date=form.hire_date.data,
            base_salary=form.base_salary.data or 0.0,
            commission_rate=(form.commission_rate.data / 100.0) if form.commission_rate.data else 0.05,
            draw_amount=form.draw_amount.data or 0.0
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        flash(f'User {user.username} created successfully!', 'success')
        return redirect(url_for('users'))
    
    return render_template('add_user.html', form=form)

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Edit user - admin only"""
    user = User.query.get_or_404(user_id)
    form = UserEditForm()
    
    # Manually populate form fields (excluding password fields)
    if request.method == 'GET':
        form.username.data = user.username
        form.email.data = user.email
        form.first_name.data = user.first_name
        form.last_name.data = user.last_name
        form.role.data = user.role
        form.active.data = user.active
        form.hire_date.data = user.hire_date
        form.base_salary.data = user.base_salary
        form.commission_rate.data = (user.commission_rate * 100) if user.commission_rate else 5.0
        form.draw_amount.data = user.draw_amount
    
    if form.validate_on_submit():
        # Check if username or email conflicts with other users
        existing_user = User.query.filter(
            ((User.username == form.username.data) | 
             (User.email == form.email.data)) &
            (User.id != user_id)
        ).first()
        
        if existing_user:
            flash('Username or email already exists for another user', 'error')
            return render_template('edit_user.html', form=form, user=user)
        
        # Set permission level based on role
        role_permissions = {
            'viewer': 1,
            'user': 2,
            'manager': 3, 
            'admin': 4
        }
        
        user.username = form.username.data
        user.email = form.email.data if form.email.data else None
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.role = form.role.data
        user.permission_level = role_permissions[form.role.data]
        user.active = form.active.data
        user.hire_date = form.hire_date.data
        user.base_salary = form.base_salary.data or 0.0
        user.commission_rate = (form.commission_rate.data / 100.0) if form.commission_rate.data else 0.05
        user.draw_amount = form.draw_amount.data or 0.0
        
        # Update password if provided
        if form.new_password.data:
            user.set_password(form.new_password.data)
        
        db.session.commit()
        flash(f'User {user.username} updated successfully!', 'success')
        return redirect(url_for('users'))
    
    return render_template('edit_user.html', form=form, user=user)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete user - admin only"""
    user = User.query.get_or_404(user_id)
    current_user = get_current_user()
    
    # Prevent deleting yourself
    if user.id == current_user.id:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('users'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {username} deleted successfully', 'success')
    return redirect(url_for('users'))

@app.route('/api/sales_data')
@login_required(1)  # Viewer level required
def api_sales_data():
    period_type = request.args.get('period', 'YTD')
    
    start_date, end_date = get_period_dates(period_type)
    
    sales_data = db.session.query(
        (User.first_name + ' ' + User.last_name).label('name'),
        db.func.sum(Sales.revenue_amount).label('revenue'),
        db.func.sum(Sales.number_of_deals).label('deals'),
        db.func.sum(Sales.commission_earned).label('commission')
    ).join(Sales).filter(
        Sales.date >= start_date,
        Sales.date <= end_date,
        User.active == True
    ).group_by(User.id).all()
    
    data = {
        'labels': [row.name for row in sales_data],
        'revenue': [float(row.revenue) for row in sales_data],
        'deals': [int(row.deals) for row in sales_data],
        'commission': [float(row.commission) for row in sales_data]
    }
    
    return jsonify(data)

@app.route('/api/trends_data')
@login_required(1)  # Viewer level required
def api_trends_data():
    period_type = request.args.get('period', 'month')
    
    # Get monthly trends for the past 12 months
    sales_trends = db.session.query(
        db.func.strftime('%Y-%m', Sales.date).label('month'),
        db.func.sum(Sales.revenue_amount).label('revenue'),
        db.func.sum(Sales.number_of_deals).label('deals')
    ).filter(
        Sales.date >= datetime.now().date() - timedelta(days=365)
    ).group_by(db.func.strftime('%Y-%m', Sales.date)).all()
    
    data = {
        'labels': [row.month for row in sales_trends],
        'revenue': [float(row.revenue) for row in sales_trends],
        'deals': [int(row.deals) for row in sales_trends]
    }
    
    return jsonify(data)

@app.route('/bulk_upload', methods=['POST'])
@login_required(2)  # User level required
def bulk_upload():
    if not PANDAS_AVAILABLE:
        flash('Pandas library is not installed. Bulk upload is disabled.', 'error')
        return redirect(url_for('data_entry'))
        
    form = BulkUploadForm()
    if form.validate_on_submit():
        file = form.file.data
        if file:
            try:
                df = pd.read_csv(file)
                required_columns = ['employee_name', 'date', 'revenue_amount', 'number_of_deals']
                
                if not all(col in df.columns for col in required_columns):
                    flash('CSV must contain columns: employee_name, date, revenue_amount, number_of_deals', 'error')
                    return redirect(url_for('data_entry'))
                
                settings = Settings.query.first()
                field_toggles = settings.field_toggles if settings else '{}'
                
                for _, row in df.iterrows():
                    # Try to find user by full name or first/last name combination
                    full_name = row['employee_name']
                    name_parts = full_name.split(' ', 1)
                    if len(name_parts) == 2:
                        user = User.query.filter_by(first_name=name_parts[0], last_name=name_parts[1]).first()
                    else:
                        user = User.query.filter_by(first_name=full_name).first()
                    
                    if user:
                        commission = calculate_commission(row['revenue_amount'], 
                                                        user.commission_rate, 
                                                        field_toggles)
                        
                        sale = Sales(
                            user_id=user.id,
                            date=datetime.strptime(row['date'], '%Y-%m-%d').date(),
                            revenue_amount=row['revenue_amount'],
                            number_of_deals=row['number_of_deals'],
                            commission_earned=commission,
                            draw_payment=row.get('draw_payment', 0.0)
                        )
                        db.session.add(sale)
                
                db.session.commit()
                flash('Bulk upload completed successfully!', 'success')
                
            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'error')
    
    return redirect(url_for('data_entry'))

@app.route('/api/save_theme', methods=['POST'])
@admin_required
def save_theme():
    try:
        data = request.get_json()
        theme = data.get('theme', 'default')
        
        # Validate theme
        valid_themes = ['default', 'dark', 'green', 'purple', 'orange', 'teal', 'red', 'pink']
        if theme not in valid_themes:
            return jsonify({'error': 'Invalid theme'}), 400
        
        # Update settings
        settings = Settings.query.first()
        if settings:
            settings.color_scheme = theme
            db.session.commit()
            return jsonify({'success': True, 'theme': theme})
        else:
            return jsonify({'error': 'Settings not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for diagnosing issues"""
    try:
        # Check database connection
        with app.app_context():
            db.session.execute(db.text('SELECT 1'))
            
        # Check if settings exist
        settings = Settings.query.first()
        
        # Basic status available to everyone
        status = {
            'status': 'healthy',
            'version': __version__,
            'author': __author__,
            'website': __website__,
            'database': 'connected',
            'settings': 'found' if settings else 'missing'
        }
        
        # Add sensitive information only for authenticated admin users
        current_user = get_current_user()
        if current_user and current_user.has_permission(4):
            status.update({
                'database_uri': app.config['SQLALCHEMY_DATABASE_URI'],
                'current_theme': get_current_color_scheme()
            })
        
        return jsonify(status)
        
    except Exception as e:
        status = {
            'status': 'unhealthy',
            'version': __version__,
            'author': __author__,
            'website': __website__,
            'database': 'disconnected',
            'error': str(e)
        }
        
        # Add sensitive information only for authenticated admin users
        current_user = get_current_user()
        if current_user and current_user.has_permission(4):
            status['database_uri'] = app.config['SQLALCHEMY_DATABASE_URI']
        
        return jsonify(status), 500

@app.route('/api/version')
def api_version():
    """Version information endpoint"""
    return jsonify({
        'version': __version__,
        'author': __author__,
        'website': __website__,
        'docker_hub': __docker_hub__,
        'application': 'Sales Tracker'
    })

@app.route('/init_db')
@admin_required
def reinit_database():
    """Re-initialize database if needed"""
    try:
        result = init_db()
        if result:
            flash('Database reinitialized successfully!', 'success')
        else:
            flash('Database reinitialization failed!', 'error')
    except Exception as e:
        flash(f'Database reinitialization error: {str(e)}', 'error')
    
    return redirect(url_for('settings'))


# Initialize database
def init_db():
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            print(f"Database initialization attempt {retry_count + 1}/{max_retries}")
            
            # Get current database URI
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
            print(f"Using database URI: {db_uri}")
            
            if db_uri.startswith('sqlite:///'):
                db_path = db_uri.replace('sqlite:///', '')
                db_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else '.'
                
                print(f"Database path: {db_path}")
                print(f"Database directory: {db_dir}")
                
                # Ensure directory exists
                if db_dir and db_dir != '.' and db_dir != '':
                    try:
                        os.makedirs(db_dir, mode=0o755, exist_ok=True)
                        print(f"✓ Directory {db_dir} created/verified")
                    except Exception as e:
                        print(f"✗ Failed to create directory {db_dir}: {e}")
                        # Fall back to current directory
                        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sales_tracker.db'
                        db_path = 'sales_tracker.db'
                        db_dir = '.'
                        print("Falling back to current directory")
                
                # Test write permissions
                test_file = os.path.join(db_dir, '.write_test')
                try:
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    print(f"✓ Directory {db_dir} is writable")
                except (IOError, OSError) as e:
                    print(f"✗ Directory {db_dir} is not writable: {e}")
                    if retry_count < max_retries - 1:
                        # Try different fallback paths
                        fallback_paths = [
                            'sqlite:///sales_tracker.db',
                            'sqlite:////tmp/sales_tracker.db',
                            'sqlite:///:memory:'
                        ]
                        if retry_count < len(fallback_paths):
                            app.config['SQLALCHEMY_DATABASE_URI'] = fallback_paths[retry_count]
                            print(f"Trying fallback URI: {fallback_paths[retry_count]}")
                            retry_count += 1
                            continue
            
            # Recreate SQLAlchemy engine with new URI
            db.engine.dispose()
            
            with app.app_context():
                print("Creating database tables...")
                db.create_all()
                print("✓ Database tables created")
                
                # Test database connection
                print("Testing database connection...")
                db.session.execute(db.text('SELECT 1'))
                print("✓ Database connection successful")
                
                # Create default admin user if not exists
                print("Checking for default admin user...")
                admin_user = User.query.filter_by(role='admin').first()
                if not admin_user:
                    admin_user = User(
                        username='admin',
                        email='admin@salestracker.local',
                        first_name='System',
                        last_name='Administrator',
                        role='admin',
                        permission_level=4,
                        active=True
                    )
                    admin_user.set_password('admin')
                    db.session.add(admin_user)
                    print("✓ Default admin user created (username: admin, password: admin)")
                else:
                    print("✓ Admin user already exists")
                
                # Create default settings if not exists
                settings = Settings.query.first()
                if not settings:
                    settings = Settings(
                        admin_username='admin',
                        admin_password_hash=generate_password_hash('admin'),
                        color_scheme='default'
                    )
                    db.session.add(settings)
                    print("✓ Default settings created")
                else:
                    print("✓ Settings already exist")
                
                db.session.commit()
                
                print("✓ Database initialization completed successfully!")
                return True
                
        except Exception as e:
            print(f"✗ Database initialization attempt {retry_count + 1} failed: {e}")
            print(f"Error type: {type(e).__name__}")
            
            retry_count += 1
            
            if retry_count < max_retries:
                # Try different database configurations
                if retry_count == 1:
                    # Try current directory
                    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sales_tracker.db'
                    print("Retrying with current directory database...")
                elif retry_count == 2:
                    # Try in-memory database as last resort
                    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
                    print("Retrying with in-memory database...")
                
                # Recreate the database object
                try:
                    db.engine.dispose()
                except:
                    pass
            else:
                print("✗ All database initialization attempts failed!")
                print("The application will continue but may not function properly.")
                print("Please check file permissions and disk space.")
                return False
    
    return False

# Global flag to track database initialization
_db_initialized = False

def ensure_database():
    """Ensure database is initialized (thread-safe)"""
    global _db_initialized
    if not _db_initialized:
        try:
            # Test if database is working
            with app.app_context():
                db.session.execute(db.text('SELECT 1'))
                Settings.query.first()
                _db_initialized = True
        except Exception as e:
            print(f"Database not working, initializing: {e}")
            if init_db():
                _db_initialized = True

# Initialize database on startup (only when not running under Gunicorn)
if __name__ == '__main__':
    init_db()
else:
    # For Gunicorn, initialize on first request
    @app.before_request
    def check_database():
        ensure_database()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)