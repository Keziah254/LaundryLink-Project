import os
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from werkzeug.utils import send_file
from models import db, User, Order, Service
from flask_bcrypt import Bcrypt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime, timedelta

# App setup
app = Flask(__name__)
app.secret_key = "supersecretkey"
ADMIN_SECRET = "LaundryMaster2025"


# Path for SQLite
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(BASE_DIR, 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

# Use Render's PostgreSQL if available, otherwise fallback to SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(instance_path, 'laundry.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize DB + Bcrypt
db.init_app(app)
bcrypt = Bcrypt(app)

# --- DATABASE SETUP FUNCTION ---
def initialize_database():
    with app.app_context():
        db.create_all()
    if not Service.query.first():
        print("🧺 Adding default laundry services...")

        default_services = [
            {"name": "Basic Washing", "description": "Normal wash & dry, folded neatly.", "price": 200, "unit": "kg",
             "image": "images/washing.jpeg"},
            {"name": "Ironing / Pressing", "description": "Iron-only or iron + folding.", "price": 50, "unit": "item",
             "image": "images/ironing.jpeg"},
            {"name": "Dry Cleaning", "description": "Delicate fabrics (suits, gowns, jackets).", "price": 600,
             "unit": "item", "image": "images/drycleaning.jpeg"},
            {"name": "Wash & Iron Combo", "description": "Full wash, dry, and iron service.", "price": 350,
             "unit": "kg", "image": "images/combo.jpeg"},
            {"name": "Stain Removal", "description": "Targeted removal of tough stains.", "price": 150, "unit": "item",
             "image": "images/stain.jpeg"},
            {"name": "Special Fabric Care", "description": "Blankets, duvets, and curtains.", "price": 700,
             "unit": "item", "image": "images/special.jpeg"},
            {"name": "Pickup & Delivery", "description": "We collect and deliver laundry.", "price": 200,
             "unit": "order", "image": "images/pickup.jpeg"},
            {"name": "Subscription Packages", "description": "Weekly or monthly laundry plans.", "price": 2500,
             "unit": "month", "image": "images/subscription.jpeg"},
            {"name": "Express / Same-Day", "description": "Fast laundry service, delivered the same day.", "price": 400,
             "unit": "kg", "image": "images/express.jpeg"}
        ]
        for s in default_services:
            db.session.add(Service(**s))
        db.session.commit()
        print("Default laundry services added!")


# Run database initialization once on startup
initialize_database()
#  ROUTES

@app.route('/')
def index():
    return render_template('index.html')


#  Register
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]
        admin_code = request.form.get("admin_code", "")

        if role == "admin" and admin_code != ADMIN_SECRET:
            flash("Invalid Admin Access Code!", "danger")
            return redirect(url_for("register"))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        new_user = User(name=name, email=email, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


#  Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["role"] = user.role
            flash("Login successful!", "success")

            # Redirect based on role
            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            elif user.role == "staff":
                return redirect(url_for("staff_dashboard"))
            else:
                return redirect(url_for("client_dashboard"))
        else:
            flash("Invalid email or password", "danger")

    return render_template("login.html")


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Redirect according to role
    role = session.get('role')

    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'staff':
        return redirect(url_for('staff_dashboard'))
    else:
        return redirect(url_for('client_dashboard'))


#  Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for('index'))

# Staff Dashboard
@app.route('/staff/dashboard', methods=['GET', 'POST'])
def staff_dashboard():
    if 'user_id' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))

    staff_id = session['user_id']
    orders = Order.query.filter_by(staff_id=staff_id).order_by(Order.created_at.desc()).all()
    return render_template('staff_dashboard.html', orders=orders)

# Update Order Status (Staff)
@app.route('/staff/update_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    if 'user_id' not in session or session.get('role') != 'staff':
        return abort(403)

    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')

    if new_status not in ["Picked Up", "In Progress", "Completed"]:
        flash("Invalid status update!", "danger")
        return redirect(url_for('staff_dashboard'))

    order.status = new_status
    db.session.commit()
    flash(f"Order #{order.id} updated to {new_status}", "success")
    return redirect(url_for('staff_dashboard'))


@app.route("/admin/dashboard")
def admin_dashboard():
    # 1. Security Check
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Access denied! Admins only.", "danger")
        return redirect(url_for('login'))

    # 2. Get Filter Range from URL (e.g., /admin/dashboard?range=today)
    selected_range = request.args.get("range")
    query = Order.query

    # 3. Apply Date Filters
    if selected_range == "today":
        start_date = datetime.today().date()
        query = query.filter(db.func.date(Order.created_at) == start_date)
    elif selected_range in ["7", "30"]:
        days = int(selected_range)
        start_date = datetime.now() - timedelta(days=days)
        query = query.filter(Order.created_at >= start_date)

    # 4. Fetch Orders and Users
    orders = query.order_by(Order.created_at.desc()).all()
    users = User.query.order_by(User.role).all()

    # 5. Calculate Analytics
    total_orders = len(orders)
    total_clients = User.query.filter_by(role='client').count()
    total_staff = User.query.filter_by(role='staff').count()

    # Revenue only from 'paid' orders in the current list
    total_revenue = sum(o.price for o in orders if o.payment_status == "paid")

    # Status breakdown for the current filtered list
    status_counts = {
        "Pending": query.filter(Order.status == "Pending").count(),
        "In Progress": query.filter(Order.status == "In Progress").count(),
        "Completed": query.filter(Order.status == "Completed").count(),
        "Delivered": query.filter(Order.status == "Delivered").count(),
    }

    # Unique customers in this range
    active_customers = len(set([o.user_id for o in orders]))

    # 6. Return everything to the template
    return render_template(
        "admin_dashboard.html",
        total_orders=total_orders,
        total_clients=total_clients,
        total_staff=total_staff,
        total_revenue=total_revenue,
        active_customers=active_customers,
        status_counts=status_counts,
        users=users,
        orders=orders,
        selected_range=selected_range
    )

# Assign order to staff (Admin only)
@app.route('/admin/assign_order/<int:order_id>', methods=['GET', 'POST'])
def assign_order(order_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Access denied!", "danger")
        return redirect(url_for('login'))

    order = Order.query.get_or_404(order_id)
    staff_members = User.query.filter_by(role='staff').all()

    if request.method == 'POST':
        staff_id = int(request.form.get('staff_id'))
        staff = User.query.get(staff_id)

        if not staff or staff.role != 'staff':
            flash("Invalid staff selected!", "danger")
            return redirect(url_for('admin_dashboard'))

        # Assign the order to selected staff
        order.staff_id = staff.id
        order.status = "Assigned"
        db.session.commit()

        flash(f"Order #{order.id} assigned to {staff.name}", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('assign_order.html', order=order, staff_members=staff_members)

# Update Payment Status (Admin)
@app.route('/admin/update_payment/<int:order_id>', methods=['POST'])
def update_payment(order_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Access denied! Admins only.", "danger")
        return redirect(url_for('login'))

    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('payment_status')

    if new_status not in ['pending', 'paid', 'failed']:
        flash("Invalid payment status!", "danger")
        return redirect(url_for('admin_dashboard'))

    order.payment_status = new_status
    db.session.commit()

    flash(f"Payment status for Order #{order.id} updated to '{new_status.title()}'", "success")
    return redirect(url_for('admin_dashboard'))




# ✅ Client Dashboard
@app.route('/client/dashboard')
def client_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    services = Service.query.all()
    recent_orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).limit(5).all()
    return render_template('client_dashboard.html', user=user, services=services, recent_orders=recent_orders)


#  API: services as JSON
@app.route('/api/services')
def api_services():
    services = [s.as_dict() for s in Service.query.all()]
    return jsonify(services)


# Client Place Order
@app.route('/client/place_order', methods=['GET', 'POST'])
def place_order(total_price=None):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        service_id = int(request.form['service_id'])
        quantity = float(request.form['quantity'])
        pickup = request.form.get('pickup_address', user.address if hasattr(user, 'address') else "")
        delivery = request.form.get('delivery_address', user.address if hasattr(user, 'address') else "")
        payment_method = request.form['payment_method']
        mpesa_phone = request.form.get('mpesa_phone') if payment_method == 'mpesa' else None

        service = Service.query.get(service_id)
        if not service:
            flash("Selected service not found", "danger")
            return redirect(url_for('client_dashboard'))

        price = round(service.price * quantity, 2)  # total price for all items

        # payment method and status
        if payment_method == "mpesa":
            payment_status = "pending"
        else:
            payment_status = "pending"  # for COD too, but marked properly

        order = Order(
            user_id=user.id,
            service_type=service.name,
            items=quantity,
            price=price,
            pickup_address=pickup,
            delivery_address=delivery,
            payment_method=payment_method,
            mpesa_phone=mpesa_phone,
            payment_status=payment_status,
            status="Pending"
        )

        db.session.add(order)
        db.session.commit()


        return redirect(url_for('client_orders'))

    services = Service.query.all()
    return render_template('place_order.html', user=user, services=services)


# Client Order History
@app.route('/client/orders')
def client_orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()
    return render_template('order_history.html', orders=orders)


#  Poll order status
@app.route('/client/order_status/<int:order_id>')
def order_status(order_id):
    order = Order.query.get_or_404(order_id)
    if 'user_id' not in session or order.user_id != session['user_id']:
        return jsonify({"error": "unauthorized"}), 403
    return jsonify({
        "status": order.status,
        "payment_status": order.payment_status,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None
    })


@app.route('/client/receipt/<int:order_id>')
def download_receipt(order_id):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from flask import send_file as flask_send_file
    from io import BytesIO
    import hashlib
    import reportlab.pdfbase.pdfdoc as pdfdoc

    # Python 3.12+ MD5 issue
    def safe_md5(data=b"", **kwargs):
        return hashlib.md5(data)
    pdfdoc.md5 = safe_md5

    # Fetch order
    order = Order.query.get_or_404(order_id)
    if 'user_id' not in session or order.user_id != session['user_id']:
        return abort(403)

    # PDF buffer
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # ---------------- HEADER ----------------
    orange = colors.HexColor("#ff7b00")
    black = colors.HexColor("#111111")
    grey = colors.HexColor("#f5f5f5")

    p.setFillColor(black)
    p.rect(0, height - 100, width, 100, fill=True, stroke=False)

    p.setFillColor(orange)
    p.setFont("Helvetica-Bold", 30)
    p.drawString(50, height - 65, "LaundryLink")

    p.setFont("Helvetica-Bold", 14)
    p.setFillColor(colors.white)
    p.drawRightString(width - 50, height - 65, "OFFICIAL RECEIPT")

    # ---------------- RECEIPT INFO ----------------
    y = height - 130
    p.setFillColor(black)
    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, y, f"Receipt No: {order.id}")
    y -= 18
    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Date Issued: {order.created_at.strftime('%Y-%m-%d %H:%M')}")
    y -= 30

    # ---------------- CLIENT INFO ----------------
    p.setFillColor(orange)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, "Client Information")
    y -= 8
    p.setStrokeColor(orange)
    p.line(50, y, width - 50, y)
    y -= 20

    p.setFillColor(black)
    p.setFont("Helvetica", 12)
    p.drawString(60, y, f" Name: {order.user.name}")
    y -= 20
    p.drawString(60, y, f" Email: {order.user.email}")
    y -= 30

    # ---------------- ORDER DETAILS ----------------
    p.setFillColor(orange)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, "Order Details")
    y -= 8
    p.setStrokeColor(orange)
    p.line(50, y, width - 50, y)
    y -= 20

    p.setFillColor(black)
    p.setFont("Helvetica", 12)
    p.drawString(60, y, f" Service Type: {order.service_type}")
    y -= 18
    p.drawString(60, y, f" Quantity: {order.items} (kg/items)")
    y -= 18
    p.drawString(60, y, f" Pickup Address: {order.pickup_address or '-'}")
    y -= 18
    p.drawString(60, y, f" Delivery Address: {order.delivery_address or '-'}")
    y -= 18
    p.drawString(60, y, f" Payment Method: {order.payment_method.upper()}")
    y -= 18
    p.drawString(60, y, f" Payment Status: {order.payment_status.capitalize()}")
    y -= 18
    p.drawString(60, y, f" Order Status: {order.status.capitalize()}")
    y -= 40

    # ---------------- TOTAL SECTION ----------------
    p.setFillColor(grey)
    p.roundRect(45, y - 65, width - 90, 70, 10, stroke=True, fill=True)

    p.setFillColor(black)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(65, y - 30, "Total Amount")

    # Calculate total
    try:
        service = Service.query.filter_by(name=order.service_type).first()
        unit_price = service.price if service else (order.price / order.items if order.items else order.price)
        total_price = round(unit_price * order.items, 2)
    except Exception:
        total_price = order.price

    p.setFont("Helvetica-Bold", 20)
    p.setFillColor(orange)
    p.drawRightString(width - 65, y - 32, f"KES {total_price:,.2f}")

    y -= 90

    # ---------------- FOOTER ----------------
    p.setStrokeColor(orange)
    p.line(50, y, width - 50, y)
    y -= 25

    p.setFont("Helvetica-Oblique", 10)
    p.setFillColor(black)
    p.drawCentredString(width / 2, y, "Thank you for choosing LaundryLink — clean made easy ")
    y -= 15
    p.setFont("Helvetica", 10)
    p.setFillColor(orange)
    p.drawCentredString(width / 2, y, "Contact: support@laundrylink.com | +254 759 15 8858 | Nairobi, Kenya")

    p.showPage()
    p.save()
    buffer.seek(0)

    return flask_send_file(
        buffer,
        as_attachment=True,
        download_name=f"receipt_{order.id}.pdf",
        mimetype="application/pdf"
    )



#  Edit Profile
@app.route('/client/profile', methods=['GET', 'POST'])
def client_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        user.name = request.form.get('name')
        user.phone = request.form.get('phone')
        user.address = request.form.get('address')
        db.session.commit()
        flash("Profile updated", "success")
        return redirect(url_for('client_profile'))
    return render_template('profile.html', user=user)

@app.route('/pay/mpesa/<int:order_id>')
def initiate_mpesa_payment(order_id):
    return render_template("mpesa_pay.html", order_id=order_id)

@app.route('/admin/analytics')
def admin_analytics():
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    # --- PIE CHART: ORDER STATUS COUNTS ---
    status_data = db.session.query(
        Order.status, db.func.count(Order.id)
    ).group_by(Order.status).all()

    labels_status = [row[0] for row in status_data]
    values_status = [row[1] for row in status_data]

    # --- BAR CHART: DAILY ORDERS ---
    daily_data = db.session.query(
        db.func.date(Order.date_created),
        db.func.count(Order.id)
    ).group_by(db.func.date(Order.date_created)).all()

    labels_daily = [str(row[0]) for row in daily_data]
    values_daily = [row[1] for row in daily_data]

    return render_template(
        'admin_analytics.html',
        labels_status=labels_status,
        values_status=values_status,
        labels_daily=labels_daily,
        values_daily=values_daily
    )

@app.route("/admin/service_trends", endpoint="service_trends")
def service_trends():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    data = db.session.query(
        Order.service_type,
        db.func.count(Order.id)
    ).group_by(Order.service_type).all()

    labels = [d[0] for d in data]
    values = [d[1] for d in data]

    # 'datasets' list for the template to find
    datasets = [{
        "label": "Number of Orders",
        "data": values,
        "backgroundColor": "rgba(255, 123, 0, 0.2)",
        "borderColor": "#ff7b00",
        "borderWidth": 2,
        "fill": True,
        "tension": 0.4
    }]

    return render_template(
        "service_trends.html",
        labels=labels,
        datasets=datasets
    )


if __name__ == '__main__':
    # This block ONLY runs if you run 'python app.py' locally.
    # It is IGNORED by Gunicorn on Render.
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)