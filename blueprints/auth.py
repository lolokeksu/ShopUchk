from flask import Blueprint, render_template, redirect, url_for, session, request
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        password = request.form.get('password', '').strip()
        if not phone or not address or not password:
            return render_template('register.html', error='Заполните все поля')
        if User.query.filter_by(phone=phone).first():
            return render_template('register.html', error='Этот номер уже зарегистрирован')
        user = User(phone=phone, address=address)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session['user_phone'] = phone
        return redirect(url_for('shop.catalog'))
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(phone=phone).first()
        if user and user.check_password(password):
            session['user_phone'] = phone
            return redirect(url_for('shop.catalog'))
        return render_template('login.html', error='Неверный номер или пароль')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user_phone', None)
    return redirect(url_for('auth.login'))