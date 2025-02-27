from flask import Flask, render_template, request, jsonify, redirect, url_for
import gspread
import os
import json
import base64
import hashlib
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from flask_cors import CORS
import logging

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Завантаження змінних середовища
load_dotenv()

app = Flask(__name__)
CORS(app)

# Підключення до Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
client = gspread.authorize(creds)

# Відкриття таблиці (заміни "SHEET_ID" на свій)
SHEET_ID = os.getenv("SHEET_ID")
sheet = client.open_by_key(SHEET_ID).sheet1

# LiqPay ключі
LIQPAY_PUBLIC_KEY = os.getenv("LIQPAY_PUBLIC_KEY")
LIQPAY_PRIVATE_KEY = os.getenv("LIQPAY_PRIVATE_KEY")

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json

    name = data.get("name")
    surname = data.get("surname")
    phone = data.get("phone")
    address = data.get("address")

    amount = 100  # Фіксована сума (можна змінювати динамічно)

    # Генерація параметрів для LiqPay
    params = {
        "version": "3",
        "public_key": LIQPAY_PUBLIC_KEY,
        "action": "pay",
        "amount": str(amount),
        "currency": "UAH",
        "description": f"Оплата за товар: {name} {surname}, {phone}, {address}",
        "order_id": f"order_{phone}",
        "sandbox": 0  # 0 для реального платежу
    }

    # Кодування у Base64
    data_str = base64.b64encode(json.dumps(params).encode()).decode()
    signature_str = base64.b64encode(
        hashlib.sha1((LIQPAY_PRIVATE_KEY + data_str + LIQPAY_PRIVATE_KEY).encode()).digest()
    ).decode()

    return jsonify({
        "message": "Дані збережено! Перенаправлення на оплату...",
        "data": data_str,
        "signature": signature_str,
        "name": name,
        "surname": surname,
        "phone": phone,
        "address": address,
    }), 200

@app.route('/payment_callback', methods=['POST'])
def payment_callback():
    try:
        # Отримуємо JSON-дані з запиту
        data = request.get_json().get('data')
        signature = request.get_json().get('signature')
        status = request.get_json().get('status')
        name = request.get_json().get('name')
        surname = request.get_json().get('surname')
        phone = request.get_json().get('phone')
        address = request.get_json().get('address')
        print(status)
        print(name, surname, phone, address)

        if not data or not signature:
            logging.error("Немає необхідних даних або підпису в запиті.")
            return jsonify({"error": "Missing data or signature"}), 400

        logging.info(f"Отримано callback: data={data}, signature={signature}")

        # Перерахунок підпису
        calculated_signature = base64.b64encode(
            hashlib.sha1((LIQPAY_PRIVATE_KEY + data + LIQPAY_PRIVATE_KEY).encode()).digest()
        ).decode()

        # Перевіряємо, чи підпис збігається
        if signature != calculated_signature:
            logging.error("Невірний підпис платежу!")
            return jsonify({"error": "Invalid signature"}), 400

        # Декодуємо JSON-дані
        decoded_data = json.loads(base64.b64decode(data).decode())
        print(decoded_data)
    except Exception as e:
        logging.error(f"Помилка під час обробки запиту: {e}")
        return jsonify({"error": "Invalid request format"}), 400

    #status = decoded_data.get('status')
    order_id = decoded_data.get('order_id')
    amount = decoded_data.get('amount')
    description = decoded_data.get('description')

    logging.info(f"Статус платежу: {status}, Order ID: {order_id}, Сума: {amount}, Опис: {description}")

    # Якщо статус успішний, записуємо у таблицю
    if status == 'success':
        sheet.append_row([name, surname, phone, address, amount, status])
        logging.info("Платіж успішно записано в таблицю")
        return jsonify({"message": "Платіж успішний, дані записано в таблицю."}), 200

    return jsonify({"message": "Платіж не успішний."}), 400





if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
