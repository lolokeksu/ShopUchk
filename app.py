import os
import requests
from utils import send_telegram_message, get_cart_details
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from functools import wraps
from urllib.parse import quote_plus

# Импорт моделей из отдельного файла
from models import db, User, Category, Product, ProductVariant

app = Flask(__name__)
app.debug = True 
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')

# ---------- Настройка базы данных PostgreSQL ----------
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')

encoded_password = quote_plus(DB_PASSWORD) if DB_PASSWORD else ''
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=disable'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,
    'pool_recycle': 280,
    'pool_pre_ping': True,
}
db.init_app(app)

# ---------- Создание таблиц и начальное заполнение ----------
with app.app_context():
    db.create_all()

    if not Category.query.first():
        veggies = Category(name='Овощи')
        fruits = Category(name='Фрукты и Ягоды')
        greens = Category(name='Зелень и Салаты')
        db.session.add_all([veggies, fruits, greens])
        db.session.commit()

        def add_product(cat, p_name, variants_dict):
            p = Product(name=p_name, category=cat, has_variants=bool(variants_dict))
            db.session.add(p)
            db.session.flush()
            for var_name, price in variants_dict.items():
                v = ProductVariant(product_id=p.id, name=var_name, price=price)
                db.session.add(v)

        # Овощи
        add_product(veggies, 'Помидоры', {'Азербайджан': 200, 'Дагестан': 180, 'Иран (красные)': 220})
        add_product(veggies, 'Огурцы', {'Дагестан': 150, 'Учкекен': 140})
        add_product(veggies, 'Картофель', {'Египет': 60, 'Азербайджан': 70, 'Местная': 50})
        add_product(veggies, 'Болгарский перец', {'Красный': 250, 'Желтый': 260})
        add_product(veggies, 'Морковь', {})
        add_product(veggies, 'Свекла', {})
        add_product(veggies, 'Капуста', {})
        add_product(veggies, 'Пекинская капуста', {})
        add_product(veggies, 'Лук репчатый', {})
        add_product(veggies, 'Чеснок', {})
        add_product(veggies, 'Кабачок', {})
        add_product(veggies, 'Баклажан', {})
        add_product(veggies, 'Редиска', {})

        # Фрукты
        add_product(fruits, 'Яблоки', {'Голден': 130, 'Фуджи': 150, 'Семерянка': 110, 'Грени Смит': 160, 'Айдарет': 120, 'Ред Чиф': 140})
        add_product(fruits, 'Виноград чёрный', {'Молдова': 300})
        add_product(fruits, 'Виноград красный', {'Кардинал': 320})
        add_product(fruits, 'Клубника', {'Азербайджан': 400, 'Турция': 450})
        add_product(fruits, 'Апельсины', {'Турция': 180, 'Египет': 170})
        add_product(fruits, 'Мандарины', {'Турция': 220})
        add_product(fruits, 'Гранат', {'Азербайджан': 280, 'Турция': 300})
        add_product(fruits, 'Бананы', {})
        add_product(fruits, 'Лимон', {})
        add_product(fruits, 'Киви', {'Иран': 350})
        add_product(fruits, 'Киви в лукошке', {'Иран (1 лукошко)': 250})

        # Зелень
        add_product(greens, 'Петрушка', {})
        add_product(greens, 'Кинза', {})
        add_product(greens, 'Укроп', {})

        db.session.commit()

# ---------- Telegram ----------
TG_TOKEN = os.environ.get('TG_TOKEN')
TG_CHAT_ID = os.environ.get('TG_CHAT_ID')

# ---------- Хранилище заказов (в памяти) ----------
orders = []

# ---------- Декораторы ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_phone' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- Пользовательские маршруты ----------
@app.route('/')
def index():
    if 'user_phone' in session:
        return redirect(url_for('catalog'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
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
        return redirect(url_for('catalog'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(phone=phone).first()
        if user and user.check_password(password):
            session['user_phone'] = phone
            return redirect(url_for('catalog'))
        return render_template('login.html', error='Неверный номер или пароль')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_phone', None)
    return redirect(url_for('login'))

@app.route('/catalog')
@login_required
def catalog():
    categories = Category.query.all()
    categories_data = [{'id': c.id, 'name': c.name} for c in categories]

    cat_id = request.args.get('cat_id', type=int)
    if not cat_id and categories:
        cat_id = categories[0].id

    products = []
    if cat_id:
        products_query = Product.query.filter_by(category_id=cat_id).all()
        for p in products_query:
            variants = [{'id': v.id, 'name': v.name, 'price': v.price, 'unit': v.unit} for v in p.variants]
            if not variants:
                variants = [{'id': None, 'name': 'Стандарт', 'price': 0.0, 'unit': 'kg'}]
            products.append({'id': p.id, 'name': p.name, 'variants': variants, 'available': p.available})

    return render_template('catalog.html', categories=categories_data, products=products, current_cat_id=cat_id)

# ---------- Профиль ----------
@app.route('/profile', endpoint='user_profile_view')
@login_required
def user_profile():
    phone = session['user_phone']
    user = User.query.filter_by(phone=phone).first_or_404()
    user_orders = []
    if isinstance(orders, list):
        for o in orders:
            if isinstance(o, dict) and o.get('client_phone') == phone:
                user_orders.append(o)
        user_orders.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return render_template('profile.html', user=user, orders=user_orders)

@app.route('/profile/edit', methods=['POST'], endpoint='user_profile_edit_view')
@login_required
def user_profile_edit():
    phone = session['user_phone']
    user = User.query.filter_by(phone=phone).first_or_404()
    new_address = request.form.get('address', '').strip()
    if new_address:
        user.address = new_address
        db.session.commit()
    return redirect(url_for('user_profile_view'))


@app.route('/cart', endpoint='cart_view')
@login_required
def cart_view():
    items, total = get_cart_details(session, Product, ProductVariant)
    return render_template('cart.html', items=items, total=total)

@app.route('/cart/add', methods=['POST'], endpoint='cart_add')
@login_required
def cart_add():
    product_id = request.form.get('product_id')
    variant_id = request.form.get('variant_id') or 'None'
    quantity = float(request.form.get('quantity', 1))
    if quantity <= 0:
        return redirect(request.referrer or url_for('catalog'))
    key = f"{product_id}_{variant_id}"
    cart = session.get('cart', {})
    cart[key] = cart.get(key, 0) + quantity
    session['cart'] = cart
    return redirect(url_for('cart_view'))

@app.route('/cart/update', methods=['POST'], endpoint='cart_update')
@login_required
def cart_update():
    key = request.form.get('key')
    quantity = float(request.form.get('quantity', 0))
    cart = session.get('cart', {})
    if quantity <= 0:
        cart.pop(key, None)
    else:
        cart[key] = quantity
    session['cart'] = cart
    return redirect(url_for('cart_view'))

@app.route('/cart/remove', methods=['POST'], endpoint='cart_remove')
@login_required
def cart_remove():
    key = request.form.get('key')
    cart = session.get('cart', {})
    cart.pop(key, None)
    session['cart'] = cart
    return redirect(url_for('cart_view'))

@app.route('/cart/checkout', methods=['POST'], endpoint='cart_checkout')
@login_required
def cart_checkout():
    items, total = get_cart_details(session, Product, ProductVariant)
    if not items:
        return redirect(url_for('cart_view'))

    phone = session['user_phone']
    user = User.query.filter_by(phone=phone).first()
    address = user.address if user else 'Адрес не указан'

    order_items = []
    for item in items:
        order_items.append({
            'name': f"{item['product_name']} {item['variant_name']}",
            'quantity': item['quantity'],
            'price': item['price'],
            'sum': item['subtotal']
        })

    order_id = len(orders) + 1
    new_order = {
        'id': order_id,
        'client_phone': phone,
        'address': address,
        'items': order_items,
        'total': total,
        'status': 'Новый',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    orders.append(new_order)

    text = f"🛒 *Новый заказ!*\n📞 Клиент: {phone}\n🏠 Адрес: {address}\n\n*Состав заказа:*\n"
    for item in order_items:
        text += f"  • {item['name']} – {item['quantity']} кг × {item['price']} ₽ = {item['sum']} ₽\n"
    text += f"\n💰 *Итого: {total} ₽*"
    send_telegram_message(text)

    session.pop('cart', None)
    return render_template('order_success.html', order_id=order_id, total=total)

# ---------- API для каталога ----------
@app.route('/api/categories')
def api_categories():
    cats = Category.query.all()
    return jsonify([{'id': c.id, 'name': c.name} for c in cats])

@app.route('/api/products')
def api_products():
    cat_id = request.args.get('category_id', type=int)
    query = Product.query
    if cat_id:
        query = query.filter_by(category_id=cat_id)
    products = query.all()
    result = []
    for p in products:
        variants = [{'id': v.id, 'name': v.name, 'price': v.price} for v in p.variants]
        result.append({'id': p.id, 'name': p.name, 'variants': variants})
    return jsonify(result)

@app.route('/order', methods=['POST'])
@login_required
def order():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400

    phone = session['user_phone']
    user = User.query.filter_by(phone=phone).first()
    address = user.address if user else 'Адрес не указан'
    items = data.get('items', [])
    total = data.get('total', 0)

    clean_items = []
    for item in items:
        clean_items.append({
            'name': item.get('name', 'Без названия'),
            'quantity': item.get('quantity', 0),
            'price': item.get('price', 0),
            'sum': item.get('sum', 0)
        })

    order_id = len(orders) + 1
    new_order = {
        'id': order_id,
        'client_phone': phone,
        'address': address,
        'items': clean_items,
        'total': total,
        'status': 'Новый',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    orders.append(new_order)

    text = f"🛒 *Новый заказ!*\n📞 Клиент: {phone}\n🏠 Адрес: {address}\n\n*Состав заказа:*\n"
    for item in clean_items:
        text += f"  • {item['name']} – {item['quantity']} кг × {item['price']} ₽ = {item['sum']} ₽\n"
    text += f"\n💰 *Итого: {total} ₽*"

    success = send_telegram_message(text)
    if success:
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Telegram send failed'}), 500

# ---------- Админ-панель ----------
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin_panel'))
        return render_template('admin_login.html', error='Неверный пароль')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_required
def admin_panel():
    products = Product.query.options(db.joinedload(Product.variants)).all()
    categories = Category.query.all()
    return render_template('admin.html', products=products, categories=categories)

@app.route('/admin/add_product', methods=['POST'])
@admin_required
def admin_add_product():
    name = request.form.get('name', '').strip()
    category_id = request.form.get('category_id')
    variant_name = request.form.get('variant_name', '').strip()
    variant_price = request.form.get('variant_price')
    variant_unit = request.form.get('variant_unit', 'kg')
    if not name or not category_id:
        return redirect(url_for('admin_panel'))
    try:
        price = float(variant_price) if variant_price else 0.0
    except ValueError:
        price = 0.0
    product = Product(name=name, category_id=int(category_id), has_variants=True)
    db.session.add(product)
    db.session.flush()
    if variant_name:
        variant = ProductVariant(
            product_id=product.id,
            name=variant_name,
            price=price,
            unit=variant_unit
        )
        db.session.add(variant)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/variant/add', methods=['POST'])
@admin_required
def admin_add_variant():
    product_id = int(request.form.get('product_id'))
    name = request.form.get('name', '').strip()
    price_str = request.form.get('price', '0')
    unit = request.form.get('unit', 'kg')
    if not name:
        return redirect(url_for('admin_panel'))
    try:
        price = float(price_str)
    except ValueError:
        price = 0.0
    variant = ProductVariant(product_id=product_id, name=name, price=price, unit=unit)
    db.session.add(variant)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/variant/delete/<int:variant_id>', methods=['POST'])
@admin_required
def admin_delete_variant(variant_id):
    variant = ProductVariant.query.get_or_404(variant_id)
    product_id = variant.product_id
    remaining = ProductVariant.query.filter_by(product_id=product_id).count()
    if remaining <= 1:
        return "Нельзя удалить последний вариант товара.", 400
    db.session.delete(variant)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/product/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    ProductVariant.query.filter_by(product_id=product_id).delete()
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/save', methods=['POST'])
@admin_required
def admin_save():
    for key, value in request.form.items():
        if key.startswith('variant_name_'):
            variant_id = int(key.split('_')[2])
            variant = ProductVariant.query.get(variant_id)
            if variant:
                variant.name = value
        elif key.startswith('variant_price_'):
            variant_id = int(key.split('_')[2])
            variant = ProductVariant.query.get(variant_id)
            if variant:
                try:
                    variant.price = float(value)
                except ValueError:
                    pass
        elif key.startswith('variant_unit_'):
            variant_id = int(key.split('_')[2])
            variant = ProductVariant.query.get(variant_id)
            if variant:
                variant.unit = value

    for key in request.form:
        if key.startswith('new_variant_name_'):
            product_id = int(key.split('_')[3])
            name = request.form[key].strip()
            if not name:
                continue
            price_str = request.form.get(f'new_variant_price_{product_id}', '0')
            try:
                price = float(price_str)
            except ValueError:
                price = 0.0
            unit = request.form.get(f'new_variant_unit_{product_id}', 'kg')
            existing = ProductVariant.query.filter_by(product_id=product_id).first()
            if not existing:
                variant = ProductVariant(product_id=product_id, name=name, price=price, unit=unit)
                db.session.add(variant)

    all_product_ids = [p.id for p in Product.query.all()]
    for pid in all_product_ids:
        product = Product.query.get(pid)
        if product:
            product.available = (f'available_{pid}' in request.form)

    db.session.commit()
    return redirect(url_for('admin_panel'))

# ---------- Управление категориями ----------
@app.route('/admin/category/add', methods=['POST'])
@admin_required
def admin_add_category():
    name = request.form.get('name', '').strip()
    if name:
        cat = Category(name=name)
        db.session.add(cat)
        db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/category/edit/<int:category_id>', methods=['POST'])
@admin_required
def admin_edit_category(category_id):
    cat = Category.query.get_or_404(category_id)
    name = request.form.get('name', '').strip()
    if name:
        cat.name = name
        db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/category/delete/<int:category_id>', methods=['POST'])
@admin_required
def admin_delete_category(category_id):
    cat = Category.query.get_or_404(category_id)
    try:
        products = Product.query.filter_by(category_id=category_id).all()
        for product in products:
            for variant in product.variants:
                db.session.delete(variant)
            db.session.delete(product)
        db.session.delete(cat)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return f"Ошибка: {e}", 500
    return redirect(url_for('admin_panel'))

# ---------- Статистика ----------
@app.route('/admin/stats')
@admin_required
def admin_stats():
    try:
        if not orders:
            return render_template('admin_stats.html', total_orders=0, total_revenue=0, avg_check=0, top_products=[], daily_stats=[])
        total_orders = len(orders)
        total_revenue = sum(o.get('total', 0) for o in orders)
        avg_check = total_revenue / total_orders if total_orders else 0
        popularity = {}
        for o in orders:
            for item in o.get('items', []):
                name = item.get('name', '')
                qty = item.get('quantity', 0)
                popularity[name] = popularity.get(name, 0) + qty
        top = sorted(popularity.items(), key=lambda x: x[1], reverse=True)[:3]
        daily = {}
        for o in orders:
            date = o.get('created_at', '').split()[0]
            daily[date] = daily.get(date, 0) + 1
        daily_stats = sorted(daily.items(), reverse=True)
        return render_template('admin_stats.html', total_orders=total_orders, total_revenue=total_revenue, avg_check=avg_check, top_products=top, daily_stats=daily_stats)
    except Exception as e:
        return f"Ошибка: {e}", 500

@app.route('/admin/product/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.all()
    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        product.category_id = int(request.form.get('category_id', 0))
        product.available = 'available' in request.form
        for key, value in request.form.items():
            if key.startswith('variant_name_'):
                variant_id = int(key.split('_')[2])
                variant = ProductVariant.query.get(variant_id)
                if variant and variant.product_id == product.id:
                    variant.name = value
            elif key.startswith('variant_price_'):
                variant_id = int(key.split('_')[2])
                variant = ProductVariant.query.get(variant_id)
                if variant and variant.product_id == product.id:
                    try:
                        variant.price = float(value)
                    except ValueError:
                        pass
            elif key.startswith('variant_unit_'):
                variant_id = int(key.split('_')[2])
                variant = ProductVariant.query.get(variant_id)
                if variant and variant.product_id == product.id:
                    variant.unit = value
        db.session.commit()
        return redirect(url_for('admin_panel'))
    return render_template('admin_product_edit.html', product=product, categories=categories)

# ---------- Запуск ----------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)