from flask import Flask, render_template, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Підключення до Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("hale-mantra-452117-n7-d894ab047cfb.json", scope)
client = gspread.authorize(creds)

# Відкриття таблиці (заміни "SHEET_ID" на свій)
SHEET_ID = "1p7kRq95xdeO-Ux9uA_Z6XD2-c-4lZ-vZO35XS7DUdJw"
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
