from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import pickle
import numpy as np
import requests
import os
from urllib.parse import quote



# ------------------ CONFIG ------------------

app = Flask(__name__)
app.secret_key = "mysecretkey123"       # change in production

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# ML Model Load
model = pickle.load(open("crop_model.pkl", "rb"))

# Static Upload Folder
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# WhatsApp Cloud API Setup --------------⚠️ UPDATE THESE⚠️-----------------
WHATSAPP_NUMBER = "919130537754"  # Customer send-to chat
WHATSAPP_API_URL = "https://graph.facebook.com/v18.0/PHONE_NUMBER_ID/messages"   # <-- CHANGE
ACCESS_TOKEN = "YOUR_WHATSAPP_CLOUD_API_TOKEN"                                   # <-- CHANGE
ADMIN_NUMBER = "919130537754"  # Your admin WhatsApp number


def notify_admin(order_message):
    """Send notification to admin using WhatsApp Cloud API"""
    data = {
        "messaging_product": "whatsapp",
        "to": ADMIN_NUMBER,
        "type": "text",
        "text": {"body": order_message}
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    r = requests.post(WHATSAPP_API_URL, headers=headers, json=data)
    print("Admin notification:", r.status_code, r.text)
# --------------------------------------------------------------------------


# ------------------ DATABASE SETUP ------------------

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tools.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Tool(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.String(50), nullable=False)
    img = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    rating = db.Column(db.Integer, default=4)

    def __repr__(self):
        return f"<Tool {self.name}>"


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    items = db.Column(db.Text, nullable=False)
    total = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default="Pending")


with app.app_context():
    db.create_all()


# ------------------ ROUTES ------------------

API_KEY = "9c0c2542dea2526a323458a1e649491b"


@app.route("/")
def home():
    crops = [
        {"name": "Rice", "img": "rice.jpg"},
        {"name": "Wheat", "img": "wheat.jpg"},
        {"name": "Maize", "img": "maize.jpg"},
        {"name": "Sugarcane", "img": "sugarcane.jpg"}
    ]
    tools = Tool.query.limit(3).all()  # Show first 3 products only
    return render_template("index.html", crops=crops, tools=tools)


# ---------- Crop Recommendation ----------

@app.route("/crop", methods=["GET", "POST"])
def crop():
    if request.method == "POST":
        try:
            data = [
                float(request.form['N']),
                float(request.form['P']),
                float(request.form['K']),
                float(request.form['temp']),
                float(request.form['humidity']),
                float(request.form['ph']),
                float(request.form['rain'])
            ]
            prediction = model.predict([data])[0]
            return render_template("crop_result.html", crop=prediction)
        except:
            return "❌ Error: please enter valid numbers"

    return render_template("crop_form.html")


# ---------- Weather ----------

@app.route("/weather", methods=["GET", "POST"])
def weather():
    weather_data = None
    city = None

    if request.method == "POST":
        city = request.form["city"]
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric"
        res = requests.get(url)

        if res.status_code == 200:
            data = res.json()
            weather_data = [
                {
                    "date": data["list"][i]["dt_txt"].split(" ")[0],
                    "temp": data["list"][i]["main"]["temp"],
                    "humidity": data["list"][i]["main"]["humidity"],
                    "description": data["list"][i]["weather"][0]["description"]
                }
                for i in range(0, 40, 8)
            ]
        else:
            weather_data = "error"

    return render_template("weather.html", weather_data=weather_data, city=city)


# ---------- Tools Shop ----------

@app.route("/equipment")
def equipment():
    tools = Tool.query.all()
    categories = sorted({t.category for t in tools})
    return render_template("equipment.html", tools=tools, categories=categories)


@app.route("/about")
def about():
    return render_template("about.html")


# ---------- Admin Auth ----------

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form["username"] == ADMIN_USERNAME and request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))

        error = "Invalid username or password"
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin")


# ---------- Admin Tools Management ----------

@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))
    return render_template("admin_dashboard.html")


@app.route("/admin/tools")
def admin_tools():
    if "admin" not in session:
        return redirect("/admin")
    tools = Tool.query.all()
    return render_template("admin_tools.html", tools=tools)


@app.route("/admin/tools/add", methods=["GET", "POST"])
def add_tool():
    if "admin" not in session:
        return redirect("/admin")

    if request.method == "POST":
        image = request.files["img"]
        filename = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        tool = Tool(
            name=request.form["name"],
            price=request.form["price"],
            img=filename,
            category=request.form["category"],
            rating=request.form["rating"]
        )
        db.session.add(tool)
        db.session.commit()
        return redirect("/admin/tools")

    return render_template("add_tool.html")


@app.route("/admin/tools/edit/<int:id>", methods=["GET", "POST"])
def edit_tool(id):
    if "admin" not in session:
        return redirect("/admin")

    tool = Tool.query.get_or_404(id)

    if request.method == "POST":
        tool.name = request.form["name"]
        tool.price = request.form["price"]
        tool.category = request.form["category"]
        tool.rating = request.form["rating"]

        image = request.files["img"]
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            tool.img = filename

        db.session.commit()
        return redirect("/admin/tools")

    return render_template("edit_tool.html", tool=tool)


@app.route("/admin/tools/delete/<int:id>")
def delete_tool(id):
    if "admin" not in session:
        return redirect("/admin")

    tool = Tool.query.get_or_404(id)
    db.session.delete(tool)
    db.session.commit()
    return redirect("/admin/tools")


# ---------- Cart System ----------

def init_cart():
    if "cart" not in session:
        session["cart"] = []


@app.route("/cart/add/<int:id>")
def add_to_cart(id):
    init_cart()
    session["cart"].append(id)
    session.modified = True
    return redirect("/cart")


@app.route("/cart")
def view_cart():
    init_cart()
    items = Tool.query.filter(Tool.id.in_(session["cart"])).all()
    return render_template("cart.html", cart_items=items)


@app.route("/cart/remove/<int:id>")
def remove_from_cart(id):
    session["cart"].remove(id)
    session.modified = True
    return redirect("/cart")


@app.route("/cart/clear")
def clear_cart():
    session["cart"] = []
    return redirect("/cart")

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if "cart" not in session or not session["cart"]:
        return redirect("/cart")

    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        
        return redirect(f"/checkout/whatsapp?name={name}&phone={phone}")

    return render_template("checkout.html")



# ---------- Checkout With WhatsApp + Save Order ----------

@app.route("/checkout/whatsapp")
def whatsapp_checkout():
    if "cart" not in session or not session["cart"]:
        return redirect("/cart")

    name = request.args.get("name", "").strip()
    phone = request.args.get("phone", "").strip()

    tools = Tool.query.filter(Tool.id.in_(session["cart"])).all()

    items_list = [f"{t.name} - {t.price}" for t in tools]
    total = sum(int("".join(filter(str.isdigit, t.price))) for t in tools)

    new_order = Order(
        customer_name=name,
        customer_phone=phone,
        items="\n".join(items_list),
        total=f"₹{total}"
    )
    db.session.add(new_order)
    db.session.commit()

    admin_msg = f"""
🚨 *New Order Received*

👤 Customer: {name}
📞 Phone: {phone}

🛒 *Items Ordered:*
{chr(10).join(items_list)}

Total: ₹{total}
⚡ Please contact the customer to confirm.
"""
    notify_admin(admin_msg)

    wa_msg = admin_msg.replace("🚨 *New Order Received*", "").strip()
    encoded_msg = quote(wa_msg)
    wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded_msg}"
    return redirect(wa_link)


@app.route("/order/confirmation")
def order_confirmation():
    session["cart"] = []
    return render_template("order_confirmation.html")

@app.route("/admin/orders")
def admin_orders():
    # Check login
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    # Fetch all orders from database
    orders = Order.query.all()

    # Render page
    return render_template("admin_orders.html", orders=orders)

@app.route("/admin/orders/update/<int:id>", methods=["GET", "POST"])
def update_order(id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    order = Order.query.get_or_404(id)

    if request.method == "POST":
        order.status = request.form["status"]
        db.session.commit()
        return redirect(url_for("admin_orders"))

    return render_template("order_update.html", order=order)

@app.route("/admin/orders/delete/<int:id>")
def delete_order(id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    order = Order.query.get_or_404(id)

    db.session.delete(order)
    db.session.commit()

    return redirect(url_for("admin_orders"))


# ---------- Run Server ----------

if __name__ == "__main__":
    app.run(debug=True)
