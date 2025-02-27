from flask import Flask , render_template , request , jsonify
import gspread
import os
import json
import base64
import hashlib
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from liqpay import LiqPay
from flask_cors import CORS

# Завантаження змінних середовища
load_dotenv()

app = Flask(__name__)
CORS(app)

# Підключення до Google Sheets
scope = ["https://spreadsheets.google.com/feeds" , "https://www.googleapis.com/auth/drive"]
creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path , scope)
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


@app.route('/submit' , methods = ['POST'])
def submit():
    data = request.json
    name = data.get("name")
    surname = data.get("surname")
    phone = data.get("phone")
    address = data.get("address")
    amount = 100  # Фіксована сума (можна змінювати динамічно)

    # Запис у Google Sheets
    sheet.append_row([name , surname , phone , address , amount])

    # Генерація параметрів для LiqPay
    params = {
        "version": "3" ,
        "public_key": LIQPAY_PUBLIC_KEY ,
        "action": "pay" ,
        "amount": str(amount) ,
        "currency": "UAH" ,
        "description": f"Оплата за товар: {name} {surname}, {phone}, {address}" ,
        "order_id": f"order_{phone}" ,
        "sandbox": 0  # Видалити або змінити на 0 для продакшну
    }

    # Кодування у Base64
    data_str = base64.b64encode(json.dumps(params).encode()).decode()
    signature_str = base64.b64encode(
        hashlib.sha1((LIQPAY_PRIVATE_KEY + data_str + LIQPAY_PRIVATE_KEY).encode()).digest()).decode()

    return jsonify({
        "message": "Дані збережено! Перенаправлення на оплату..." ,
        "data": data_str ,
        "signature": signature_str
    }) , 200


@app.route('/payment_callback' , methods = ['POST'])
def payment_callback():
    data = request.form  # Отримуємо дані з LiqPay (POST)

    # Перевірка підпису
    data_str = base64.b64encode(json.dumps(data.to_dict()).encode()).decode()
    signature_str = base64.b64encode(
        hashlib.sha1((LIQPAY_PRIVATE_KEY + data_str + LIQPAY_PRIVATE_KEY).encode()).digest()).decode()

    if signature_str != data.get('signature'):
        return jsonify({"error": "Invalid signature"}) , 400

    # Отримуємо статус платежу
    status = data.get('status')
    order_id = data.get('order_id')
    amount = data.get('amount')
    description = data.get('description')

    # Якщо статус успішний, записуємо у таблицю
    if status == 'success':
        # Запис у Google Sheets
        sheet.append_row([order_id , status , amount , description])
        return jsonify({"message": "Платіж успішний, дані записано в таблицю."}) , 200

    # Якщо платіж не успішний
    return jsonify({"message": "Платіж не успішний."}) , 400


if __name__ == "__main__":
    app.run(host = "0.0.0.0" , port = 5000 , debug = True)
