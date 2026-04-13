from flask import Blueprint, render_template, session, request, jsonify, redirect, url_for
from datetime import datetime
from models import db, User, Category, Product, ProductVariant
from utils import send_telegram_message, get_cart_details
from functools import wraps

shop_bp = Blueprint('shop', __name__)

# Локальный декоратор login_required для shop
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_phone' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- Каталог ----------
@shop_bp.route('/catalog')
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
@shop_bp.route('/profile', endpoint='user_profile_view')
@login_required
def user_profile():
    phone = session['user_phone']
    user = User.query.filter_by(phone=phone).first_or_404()
    # Пока заказы из памяти, но можно позже переделать на БД
    from app import orders   # временный импорт
    user_orders = []
    if isinstance(orders, list):
        for o in orders:
            if isinstance(o, dict) and o.get('client_phone') == phone:
                user_orders.append(o)
        user_orders.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return render_template('profile.html', user=user, orders=user_orders)

@shop_bp.route('/profile/edit', methods=['POST'], endpoint='user_profile_edit_view')
@login_required
def user_profile_edit():
    phone = session['user_phone']
    user = User.query.filter_by(phone=phone).first_or_404()
    new_address = request.form.get('address', '').strip()
    if new_address:
        user.address = new_address
        db.session.commit()
    return redirect(url_for('shop.user_profile_view'))

# ---------- Корзина ----------

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

    from app import orders   # временно, пока заказы в памяти
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

# ---------- API ----------
@shop_bp.route('/api/categories')
def api_categories():
    cats = Category.query.all()
    return jsonify([{'id': c.id, 'name': c.name} for c in cats])

@shop_bp.route('/api/products')
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

# ---------- Прямой заказ из каталога (если используется) ----------
@shop_bp.route('/order', methods=['POST'])
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

    from app import orders
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