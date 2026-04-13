# utils.py
import os
import requests

def send_telegram_message(text):
    """Отправляет сообщение в Telegram администратору."""
    token = os.environ.get('TG_TOKEN')
    chat_id = os.environ.get('TG_CHAT_ID')
    if not token or not chat_id:
        print("Telegram токен или chat_id не заданы")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")
        return False


def get_cart_details(session, Product, ProductVariant):
    """
    Преобразует корзину из сессии в список словарей с полной информацией о товарах.
    Возвращает кортеж (items, total).
    """
    cart = session.get('cart', {})
    items = []
    total = 0
    for key, qty in cart.items():
        if not qty:
            continue
        parts = key.split('_')
        if len(parts) != 2:
            continue
        product_id, variant_id = parts
        variant = ProductVariant.query.get(int(variant_id)) if variant_id != 'None' else None
        product = Product.query.get(int(product_id)) if product_id != 'None' else None
        if not variant or not product:
            continue
        price = variant.price
        subtotal = price * qty
        total += subtotal
        items.append({
            'key': key,
            'product_id': product.id,
            'variant_id': variant.id,
            'product_name': product.name,
            'variant_name': variant.name,
            'price': price,
            'quantity': qty,
            'subtotal': subtotal,
            'unit': variant.unit
        })
    return items, total