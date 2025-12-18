from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Create the database object
db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default="client")  # admin, staff, client

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

# ----------- Service Model -----------
class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), default="kg")  # kg or item
    image = db.Column(db.String(200), nullable=True)  # static path to image

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "unit": self.unit,
            "image": self.image
        }


# ----------- Extended Order Details -----------
class OrderDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    pickup_address = db.Column(db.String(255))
    delivery_address = db.Column(db.String(255))
    payment_method = db.Column(db.String(50))  # 'mpesa' or 'cod'
    payment_status = db.Column(db.String(50), default="pending")  # pending, paid, failed
    mpesa_phone = db.Column(db.String(20), nullable=True)
    receipt_filename = db.Column(db.String(200), nullable=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    order = db.relationship("Order", backref="details", uselist=False)

# ----------- Order Model -----------
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Assigned staff

    service_type = db.Column(db.String(50), nullable=False)
    items = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="Pending")

    payment_method = db.Column(db.String(20), default="cash")
    payment_status = db.Column(db.String(20), default="pending")
    pickup_address = db.Column(db.String(255))
    delivery_address = db.Column(db.String(255))
    mpesa_phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships (explicitly define which foreign key belongs to which)
    user = db.relationship("User", foreign_keys=[user_id], backref="orders")
    staff = db.relationship("User", foreign_keys=[staff_id], backref="assigned_orders")
