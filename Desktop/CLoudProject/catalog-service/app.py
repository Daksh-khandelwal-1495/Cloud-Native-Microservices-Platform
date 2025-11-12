import os
import json
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import redis

app = Flask(__name__)

# Configure PostgreSQL connection
db_host = os.environ.get('DB_HOST', 'localhost')
db_user = os.environ.get('DB_USER', 'postgres')
db_password = os.environ.get('DB_PASSWORD', 'postgres')
db_name = os.environ.get('DB_NAME', 'catalogdb')

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure Redis connection
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = os.environ.get('REDIS_PORT', 6379)
redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

# Product model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), default='general')
    inventory_count = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id, 
            "name": self.name, 
            "price": self.price,
            "category": self.category,
            "inventory_count": self.inventory_count
        }

@app.before_first_request
def create_tables():
    db.create_all()

@app.route('/catalog', methods=['GET'])
def get_catalog():
    # Try to get catalog from cache
    cached_catalog = redis_client.get('catalog_list')
    
    if cached_catalog:
        return jsonify({"catalog": json.loads(cached_catalog), "source": "cache"})
    else:
        # If not in cache, get from database
        products = Product.query.all()
        catalog_data = [product.to_dict() for product in products]
        
        # Cache the results (expires in 120 seconds)
        redis_client.setex('catalog_list', 120, json.dumps(catalog_data))
        return jsonify({"catalog": catalog_data, "source": "database"})

@app.route('/catalog', methods=['POST'])
def add_product():
    data = request.get_json()
    product = Product(
        name=data.get("name"),
        price=data.get("price", 0),
        category=data.get("category", "general"),
        inventory_count=data.get("inventory_count", 0)
    )
    db.session.add(product)
    db.session.commit()
    
    # Invalidate the cache when a new product is added
    redis_client.delete('catalog_list')
    
    return jsonify({"product": product.to_dict()}), 201

@app.route('/catalog/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = Product.query.get_or_404(product_id)
    return jsonify({"product": product.to_dict()})

@app.route('/catalog/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json()
    
    product.name = data.get("name", product.name)
    product.price = data.get("price", product.price)
    product.category = data.get("category", product.category)
    product.inventory_count = data.get("inventory_count", product.inventory_count)
    
    db.session.commit()
    
    # Invalidate cache
    redis_client.delete('catalog_list')
    
    return jsonify({"product": product.to_dict()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
