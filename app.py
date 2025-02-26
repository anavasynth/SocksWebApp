from flask import Flask, render_template, request, jsonify
import gspread
import os
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Підключення до Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH")

creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
client = gspread.authorize(creds)

# Відкриття таблиці (заміни "SHEET_ID" на свій)
SHEET_ID = os.getenv("SHEET_ID")
sheet = client.open_by_key(SHEET_ID).sheet1

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

    # Запис у таблицю
    sheet.append_row([name , surname , phone , address])

    return jsonify({"message": "Дані збережено!"}) , 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == '__main__':
    app.run()
