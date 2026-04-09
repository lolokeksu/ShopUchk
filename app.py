import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Ваши конфиденциальные данные будем хранить в переменных окружения
# В разделе "Переменные" на Amvera создайте две переменные: TG_TOKEN и TG_CHAT_ID
TOKEN = os.environ.get('TG_TOKEN')
CHAT_ID = os.environ.get('TG_CHAT_ID')

@app.route('/send_order', methods=['POST'])
def send_order():
    # Получаем данные из запроса от Android-приложения
    data = request.get_json()
    
    # Проверяем, что данные пришли
    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400

    # Формируем текст сообщения для Telegram
    message = f"📦 НОВЫЙ ЗАКАЗ\n"
    message += f"👤 Клиент: {data.get('client', 'Не указан')}\n"
    message += f"🛒 Заказ: {data.get('order_details', 'Нет данных')}\n"
    message += f"💰 Сумма: {data.get('total', '0')} ₽"

    # Отправляем запрос в Telegram API
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return jsonify({"status": "success", "message": "Order sent to Telegram"})
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)