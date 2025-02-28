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
import requests

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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

app.config['UPLOAD_FOLDER'] = 'static/uploads'

app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Перевірка чи є файл з дозволеним розширенням
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Перевірка наявності products.json, створення порожнього файлу, якщо він не існує
def init_products():
    if not os.path.exists('products.json'):
        with open('products.json', 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=4)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route('/add_product' , methods = ['POST'])
def add_product():
    if 'photo' not in request.files:
        return "Фото не вибрано" , 400

    file = request.files['photo']

    if file.filename == '':
        return 'Фото не вибрано' , 400

    if file and allowed_file(file.filename):
        # Генеруємо унікальне ім'я для файлу
        filename = f"{len(os.listdir(app.config['UPLOAD_FOLDER'])) + 1}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'] , filename)

        # Зберігаємо файл
        file.save(filepath)

        # Отримуємо дані з форми
        name = request.form['name']
        description = request.form['description']
        size = request.form['size']

        # Перевіряємо наявність файлу JSON, якщо його немає, створюємо
        init_products()

        # Завантажуємо поточний асортимент з JSON
        with open('products.json' , 'r' , encoding = 'utf-8') as f:
            products = json.load(f)

        # Додаємо новий товар
        new_product = {
            "id": str(len(products) + 1) ,
            "name": name ,
            "description": description ,
            "photo": f"/static/uploads/{filename}" ,  # Зберігаємо шлях до фото
            "sizes": [size]
        }

        products.append(new_product)

        # Зберігаємо оновлений асортимент у JSON
        with open('products.json' , 'w' , encoding = 'utf-8') as f:
            json.dump(products , f , ensure_ascii = False , indent = 4)

        return redirect('/admin')  # Перенаправляємо назад до адмін панелі


def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    return response.json()

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json

    name = data.get("name")
    surname = data.get("surname")
    phone = data.get("phone")
    address = data.get("address")
    chat_id = data.get("chat_id")

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
        "chat_id": chat_id
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
        chat_id = request.get_json().get('chat_id')
        print("chat_id:", chat_id)
        if chat_id:
            message = "🎉 Дякуємо за ваше замовлення! Оплата пройшла успішно. Очікуйте доставку. 🚀"
            send_telegram_message(chat_id , message)
        return jsonify({"message": "Платіж успішний, дані записано в таблицю."}), 200

    return jsonify({"message": "Платіж не успішний."}), 400



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
