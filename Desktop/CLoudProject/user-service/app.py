
import os
import json
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import redis

app = Flask(__name__)

# Configure PostgreSQL connection (update with your DB credentials)
# Get database config from environment variables or use defaults
db_host = os.environ.get('DB_HOST', 'localhost')
db_user = os.environ.get('DB_USER', 'postgres')
db_password = os.environ.get('DB_PASSWORD', 'postgres')
db_name = os.environ.get('DB_NAME', 'userdb')

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure Redis connection
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = os.environ.get('REDIS_PORT', 6379)
redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

# User model
class User(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(80), nullable=False)
	email = db.Column(db.String(120), unique=True, nullable=False)

	def to_dict(self):
		return {"id": self.id, "name": self.name, "email": self.email}

@app.before_first_request
def create_tables():
	db.create_all()

@app.route('/users', methods=['GET'])
def get_users():
    # Try to get users from cache
    cached_users = redis_client.get('users_list')
    
    if cached_users:
        return jsonify({"users": json.loads(cached_users), "source": "cache"})
    else:
        # If not in cache, get from database
        users = User.query.all()
        users_data = [user.to_dict() for user in users]
        
        # Cache the results (expires in 60 seconds)
        redis_client.setex('users_list', 60, json.dumps(users_data))
        return jsonify({"users": users_data, "source": "database"})

@app.route('/users', methods=['POST'])
def add_user():
    data = request.get_json()
    user = User(name=data.get("name"), email=data.get("email"))
    db.session.add(user)
    db.session.commit()
    
    # Invalidate the cache when a new user is added
    redis_client.delete('users_list')
    
    return jsonify({"user": user.to_dict()}), 201

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5000)
