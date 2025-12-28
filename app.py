from flask import Flask, render_template, request, redirect, url_for, session
from mongoengine import connect, Document, StringField, IntField
from werkzeug.utils import secure_filename
import pickle
import numpy as np
import requests
import os
from urllib.parse import quote

# ------------------ MONGO DB CONNECTION ------------------
connect(
    db="agrosmart",
    host="mongodb+srv://kunaladkine:tiger@kunaladkine.hndocoz.mongodb.net/agrosmart"
)

# ------------------ CONFIG ------------------
app = Flask(__name__)
app.secret_key = "mysecretkey123"   # change in production

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------ LOAD ML MODEL ------------------
model = pickle.load(open("crop_model.pkl", "rb"))

# ------------------ WHATSAPP API ⚠️ UPDATE THESE ------------------
WHATSAPP_NUMBER = "919130537754"   # customer chat destination
PHONE_ID = "123456789000000"  # e.g., 123456789000
WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
ACCESS_TOKEN = "EAAGwXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
ADMIN_NUMBER = "919130537754"

def notify_admin(order_message):
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
    try:
        requests.post(WHATSAPP_API_URL, headers=headers, json=data)
    except:
        print("⚠️ WhatsApp API error")

# ------------------ MONGO MODELS ------------------
class Tool(Document):
    name = StringField(required=True)
    price = StringField(required=True)
    img = StringField()
    category = StringField()
    rating = IntField(default=4)

class Order(Document):
    customer_name = StringField(required=True)
    customer_phone = StringField(required=True)
    items = StringField(required=True)
    total = StringField(required=True)
    status = StringField(default="Pending")


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
    tools = Tool.objects()[:3]  # show first 3
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
            return "❌ Please enter valid numbers."

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


# ---------- Equipment ----------
@app.route("/equipment")
def equipment():
    tools = Tool.objects()
    categories = sorted({t.category for t in tools})
    return render_template("equipment.html", tools=tools, categories=categories)


@app.route("/about")
def about():
    return render_template("about.html")


# ---------- Admin Login ----------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USERNAME and request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin/dashboard")
        return render_template("admin_login.html", error="Invalid Credentials")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin")


# ---------- Admin Dashboard ----------
@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin")
    total_tools = Tool.objects().count()
    total_orders = Order.objects().count()
    return render_template("admin_dashboard.html", total_tools=total_tools, total_orders=total_orders)


# ---------- Tools CRUD ----------
@app.route("/admin/tools")
def admin_tools():
    if "admin" not in session:
        return redirect("/admin")
    tools = Tool.objects()
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
            image.save(os.path.join(UPLOAD_FOLDER, filename))

        Tool(
            name=request.form["name"],
            price=request.form["price"],
            img=filename,
            category=request.form["category"],
            rating=int(request.form["rating"])
        ).save()

        return redirect("/admin/tools")

    return render_template("add_tool.html")


@app.route("/admin/tools/edit/<id>", methods=["GET", "POST"])
def edit_tool(id):
    if "admin" not in session:
        return redirect("/admin")

    tool = Tool.objects(id=id).first()

    if request.method == "POST":
        data = {
            "name": request.form["name"],
            "price": request.form["price"],
            "category": request.form["category"],
            "rating": int(request.form["rating"])
        }

        image = request.files["img"]
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(UPLOAD_FOLDER, filename))
            data["img"] = filename

        tool.update(**data)
        return redirect("/admin/tools")

    return render_template("edit_tool.html", tool=tool)


@app.route("/admin/tools/delete/<id>")
def delete_tool(id):
    if "admin" not in session:
        return redirect("/admin")

    Tool.objects(id=id).first().delete()
    return redirect("/admin/tools")


# ---------- Cart ----------
def init_cart():
    if "cart" not in session:
        session["cart"] = []


@app.route("/cart/add/<id>")
def add_to_cart(id):
    init_cart()
    session["cart"].append(id)
    session.modified = True
    return redirect("/cart")


@app.route("/cart")
def view_cart():
    init_cart()
    items = Tool.objects(id__in=session["cart"])
    return render_template("cart.html", cart_items=items)


@app.route("/cart/remove/<id>")
def remove_from_cart(id):
    session["cart"].remove(id)
    session.modified = True
    return redirect("/cart")


@app.route("/cart/clear")
def clear_cart():
    session["cart"] = []
    return redirect("/cart")


# ---------- Checkout ----------
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not session.get("cart"):
        return redirect("/cart")

    if request.method == "POST":
        return redirect(f"/checkout/whatsapp?name={request.form['name']}&phone={request.form['phone']}")

    return render_template("checkout.html")


# ---------- WhatsApp + Order Save ----------
@app.route("/checkout/whatsapp")
def whatsapp_checkout():
    if not session.get("cart"):
        return redirect("/cart")

    name = request.args.get("name")
    phone = request.args.get("phone")

    tools = Tool.objects(id__in=session["cart"])
    items = [f"{t.name} - {t.price}" for t in tools]
    total = sum(int(''.join(filter(str.isdigit, t.price))) for t in tools)

    Order(
        customer_name=name,
        customer_phone=phone,
        items="\n".join(items),
        total=f"₹{total}"
    ).save()

    # Notify Admin on WhatsApp
    message = f"""
🚨 *New Order Received*
👤 {name} | 📞 {phone}
🛒 Items:
{chr(10).join(items)}
💰 Total: ₹{total}
    """
    notify_admin(message)

    # Redirect Customer
    encoded = quote(message)
    return redirect(f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded}")


@app.route("/order/confirmation")
def order_confirmation():
    session["cart"] = []
    return render_template("order_confirmation.html")


# ---------- Admin Orders ----------
@app.route("/admin/orders")
def admin_orders():
    if "admin" not in session:
        return redirect("/admin")
    orders = Order.objects()
    return render_template("admin_orders.html", orders=orders)


@app.route("/admin/orders/update/<id>", methods=["GET", "POST"])
def update_order(id):
    if "admin" not in session:
        return redirect("/admin")

    order = Order.objects(id=id).first()

    if request.method == "POST":
        order.update(status=request.form["status"])
        return redirect("/admin/orders")

    return render_template("order_update.html", order=order)


@app.route("/admin/orders/delete/<id>")
def delete_order(id):
    if "admin" not in session:
        return redirect("/admin")
    Order.objects(id=id).first().delete()
    return redirect("/admin/orders")


# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)
