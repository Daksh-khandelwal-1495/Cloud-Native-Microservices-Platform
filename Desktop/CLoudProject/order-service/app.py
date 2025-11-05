import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import redis

app = Flask(__name__)

# Configure PostgreSQL connection
db_host = os.environ.get('DB_HOST', 'localhost')
db_user = os.environ.get('DB_USER', 'postgres')
db_password = os.environ.get('DB_PASSWORD', 'postgres')
db_name = os.environ.get('DB_NAME', 'orderdb')

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure Redis connection
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = os.environ.get('REDIS_PORT', 6379)
redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

# Order model
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    customer_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total_amount": self.total_amount,
            "customer_id": self.customer_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

@app.before_first_request
def create_tables():
    db.create_all()

@app.route('/orders', methods=['GET'])
def get_orders():
    # Try to get orders from cache
    cached_orders = redis_client.get('orders_list')
    
    if cached_orders:
        return jsonify({"orders": json.loads(cached_orders), "source": "cache"})
    else:
        # If not in cache, get from database
        orders = Order.query.order_by(Order.created_at.desc()).all()
        orders_data = [order.to_dict() for order in orders]
        
        # Cache the results (expires in 60 seconds for faster updates)
        redis_client.setex('orders_list', 60, json.dumps(orders_data))
        return jsonify({"orders": orders_data, "source": "database"})

@app.route('/orders', methods=['POST'])
def add_order():
    data = request.get_json()
    
    # Calculate total amount
    unit_price = data.get("unit_price", 0.0)
    quantity = data.get("quantity", 1)
    total_amount = unit_price * quantity
    
    order = Order(
        product_name=data.get("product_name"),
        quantity=quantity,
        unit_price=unit_price,
        total_amount=total_amount,
        customer_id=data.get("customer_id"),
        status=data.get("status", "pending")
    )
    db.session.add(order)
    db.session.commit()
    
    # Invalidate the cache when a new order is added
    redis_client.delete('orders_list')
    
    return jsonify({"order": order.to_dict()}), 201

@app.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = Order.query.get_or_404(order_id)
    return jsonify({"order": order.to_dict()})

@app.route('/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    data = request.get_json()
    
    order.status = data.get("status", order.status)
    db.session.commit()
    
    # Invalidate cache
    redis_client.delete('orders_list')
    
    return jsonify({"order": order.to_dict()})

@app.route('/orders/stats', methods=['GET'])
def get_order_stats():
    # Check cache first
    cached_stats = redis_client.get('order_stats')
    
    if cached_stats:
        return jsonify({"stats": json.loads(cached_stats), "source": "cache"})
    else:
        total_orders = Order.query.count()
        pending_orders = Order.query.filter_by(status='pending').count()
        completed_orders = Order.query.filter_by(status='completed').count()
        total_revenue = db.session.query(db.func.sum(Order.total_amount)).scalar() or 0
        
        stats = {
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "completed_orders": completed_orders,
            "total_revenue": float(total_revenue)
        }
        
        # Cache stats for 300 seconds (5 minutes)
        redis_client.setex('order_stats', 300, json.dumps(stats))
        return jsonify({"stats": stats, "source": "database"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
