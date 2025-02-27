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
    try:
        data = request.json
        name = data.get("name")
        surname = data.get("surname")
        phone = data.get("phone")
        address = data.get("address")
        amount = 100  # Фіксована сума

        # Запис у Google Sheets (до підтвердження платежу)
        sheet.append_row([name, surname, phone, address, amount, "Очікується оплата"])

        # Генерація параметрів для LiqPay
        params = {
            "version": "3",
            "public_key": LIQPAY_PUBLIC_KEY,
            "action": "pay",
            "amount": str(amount),
            "currency": "UAH",
            "description": f"Оплата за товар: {name} {surname}, {phone}, {address}",
            "order_id": f"order_{phone}",
            "sandbox": 1,  # Використовуй 0 для продакшну
            "result_url": "http://127.0.0.1:5000/",  # Куди поверне після оплати
            "server_url": "http://127.0.0.1:5000/payment_callback",  # Куди LiqPay відправить статус
        }

        # Кодування у Base64
        data_str = base64.b64encode(json.dumps(params).encode()).decode()
        signature_str = base64.b64encode(
            hashlib.sha1((LIQPAY_PRIVATE_KEY + data_str + LIQPAY_PRIVATE_KEY).encode()).digest()).decode()

        # Формуємо URL для редіректу
        payment_url = f"https://www.liqpay.ua/api/3/checkout?data={data_str}&signature={signature_str}"

        return jsonify({"redirect_url": payment_url}), 200

    except Exception as e:
        logging.error(f"Помилка при обробці запиту: {e}")
        return jsonify({"error": "Помилка при обробці запиту"}), 500

@app.route('/payment_callback', methods=['POST'])
def payment_callback():
    try:
        data = request.form
        if not data:
            return jsonify({"error": "Немає даних у запиті"}), 400

        received_data = data.get("data")
        received_signature = data.get("signature")

        if received_data is None or received_signature is None:
            return jsonify({"error": "Відсутні обов'язкові параметри"}), 400

        computed_signature = base64.b64encode(
            hashlib.sha1((LIQPAY_PRIVATE_KEY + received_data + LIQPAY_PRIVATE_KEY).encode()).digest()
        ).decode()

        if computed_signature != received_signature:
            return jsonify({"error": "Невірний підпис"}), 403

        decoded_data = json.loads(base64.b64decode(received_data).decode("utf-8"))
        status = decoded_data.get("status")
        order_id = decoded_data.get("order_id")
        amount = decoded_data.get("amount")
        description = decoded_data.get("description")

        if status == "success":
            # Оновлення статусу в Google Sheets
            cell = sheet.find(order_id)
            if cell:
                sheet.update_cell(cell.row, cell.col + 5, "Оплачено")
            return jsonify({"message": "Платіж успішний, дані оновлено в таблиці."}), 200

        return jsonify({"message": "Платіж не успішний."}), 400

    except Exception as e:
        logging.error(f"Помилка при обробці колбеку: {e}")
        return jsonify({"error": "Помилка при обробці колбеку"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
