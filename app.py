from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/submit", methods=["POST"])
def submit():
    data = request.json
    print("Отримані дані:", data)
    return jsonify({"status": "success", "message": "Замовлення отримано!"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == '__main__':
    app.run()
