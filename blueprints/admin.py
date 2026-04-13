from flask import Blueprint, render_template, redirect, url_for, session, request
from models import db, Category, Product, ProductVariant
from functools import wraps
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin.admin_panel'))
        return render_template('admin_login.html', error='Неверный пароль')
    return render_template('admin_login.html')

@admin_bp.route('/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/')
@admin_required
def admin_panel():
    products = Product.query.options(db.joinedload(Product.variants)).all()
    categories = Category.query.all()
    return render_template('admin.html', products=products, categories=categories)

# ... (скопируйте все остальные маршруты из текущего app.py, заменив @app на @admin_bp и поправив url_for)
# Я опускаю для краткости, но вы можете перенести их по аналогии.
