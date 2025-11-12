import os
import time
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
import requests
import json
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import redis
from prometheus_client import CollectorRegistry, Gauge, generate_latest
import warnings
warnings.filterwarnings("ignore")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PROMETHEUS_URL = os.getenv('PROMETHEUS_URL', 'http://prometheus.monitoring:9090')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis.database')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

# Redis connection with fallback
try:
    if REDIS_PASSWORD:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)
    else:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.ping()
    logger.info("Connected to Redis for caching predictions")
except Exception as e:
    logger.warning(f"Redis connection failed: {e}, using localhost fallback")
    redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Prometheus metrics for predictions
registry = CollectorRegistry()
prediction_gauge = Gauge('predicted_cpu_utilization', 'Predicted CPU utilization for next 5 minutes', 
                        ['service'], registry=registry)
confidence_gauge = Gauge('prediction_confidence', 'Confidence score of the prediction', 
                        ['service'], registry=registry)
scaling_recommendation = Gauge('scaling_recommendation', 'Recommended number of replicas',
                             ['service'], registry=registry)

class PredictiveScaler:
    def __init__(self):
        self.models = {}
        self.historical_data = {}
        self.prediction_cache = {}
        
    def get_prometheus_metrics(self, query, start_time, end_time):
        """Fetch historical metrics from Prometheus"""
        try:
            params = {
                'query': query,
                'start': start_time.isoformat() + 'Z',
                'end': end_time.isoformat() + 'Z',
                'step': '30s'
            }
            
            response = requests.get(f"{PROMETHEUS_URL}/api/v1/query_range", params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success' and data['data']['result']:
                    return data['data']['result'][0]['values']
            return []
        except Exception as e:
            logger.error(f"Failed to fetch Prometheus metrics: {e}")
            return []
    
    def prepare_time_series_data(self, service_name, hours_back=2):
        """Prepare time series data for prediction"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        # Query for CPU utilization
        cpu_query = f'rate(container_cpu_usage_seconds_total{{pod=~"{service_name}.*"}}[1m]) * 100'
        cpu_data = self.get_prometheus_metrics(cpu_query, start_time, end_time)
        
        # Query for request rate
        request_query = f'rate(flask_http_request_total{{service="{service_name}"}}[1m])'
        request_data = self.get_prometheus_metrics(request_query, start_time, end_time)
        
        if not cpu_data and not request_data:
            # Generate synthetic data for demo
            logger.info(f"No Prometheus data found for {service_name}, generating synthetic data")
            return self.generate_synthetic_data()
        
        # Convert to DataFrame
        df_data = []
        for timestamp, value in cpu_data:
            df_data.append({
                'timestamp': datetime.fromtimestamp(timestamp),
                'cpu_utilization': float(value),
                'hour_of_day': datetime.fromtimestamp(timestamp).hour,
                'minute_of_hour': datetime.fromtimestamp(timestamp).minute
            })
        
        return pd.DataFrame(df_data)
    
    def generate_synthetic_data(self):
        """Generate synthetic time series data for demonstration"""
        now = datetime.utcnow()
        data = []
        
        for i in range(240):  # 2 hours of data (30s intervals)
            timestamp = now - timedelta(seconds=i*30)
            hour = timestamp.hour
            minute = timestamp.minute
            
            # Simulate realistic CPU patterns
            base_cpu = 15 + 10 * np.sin(hour * np.pi / 12)  # Daily pattern
            noise = np.random.normal(0, 5)  # Random variation
            spike = 20 if (hour in [9, 12, 15, 18] and minute < 10) else 0  # Traffic spikes
            
            cpu_utilization = max(5, min(95, base_cpu + noise + spike))
            
            data.append({
                'timestamp': timestamp,
                'cpu_utilization': cpu_utilization,
                'hour_of_day': hour,
                'minute_of_hour': minute
            })
        
        return pd.DataFrame(data).sort_values('timestamp')
    
    def train_model(self, service_name):
        """Train ML model for CPU prediction"""
        try:
            df = self.prepare_time_series_data(service_name)
            if df.empty:
                logger.warning(f"No data available for {service_name}")
                return None
            
            # Feature engineering
            df['time_index'] = range(len(df))
            df['rolling_mean_5'] = df['cpu_utilization'].rolling(window=5).mean()
            df['rolling_std_5'] = df['cpu_utilization'].rolling(window=5).std()
            df['lag_1'] = df['cpu_utilization'].shift(1)
            df['lag_2'] = df['cpu_utilization'].shift(2)
            
            # Remove NaN values
            df = df.dropna()
            
            if len(df) < 10:
                logger.warning(f"Insufficient data points for {service_name}")
                return None
            
            # Prepare features
            feature_cols = ['time_index', 'hour_of_day', 'minute_of_hour', 
                          'rolling_mean_5', 'rolling_std_5', 'lag_1', 'lag_2']
            X = df[feature_cols]
            y = df['cpu_utilization']
            
            # Train model
            model = LinearRegression()
            model.fit(X, y)
            
            # Calculate model accuracy
            predictions = model.predict(X)
            mse = mean_squared_error(y, predictions)
            accuracy = max(0, 1 - (mse / np.var(y)))
            
            self.models[service_name] = {
                'model': model,
                'feature_cols': feature_cols,
                'accuracy': accuracy,
                'last_training': datetime.utcnow(),
                'data_shape': df.shape
            }
            
            logger.info(f"Trained model for {service_name} - Accuracy: {accuracy:.3f}, Data points: {len(df)}")
            return model
            
        except Exception as e:
            logger.error(f"Failed to train model for {service_name}: {e}")
            return None
    
    def predict_cpu_utilization(self, service_name, minutes_ahead=5):
        """Predict CPU utilization for the next N minutes"""
        try:
            # Check cache first
            cache_key = f"prediction:{service_name}:{minutes_ahead}"
            cached = redis_client.get(cache_key)
            if cached:
                logger.info(f"Using cached prediction for {service_name}")
                return json.loads(cached)
            
            # Train or retrain model if needed
            if (service_name not in self.models or 
                datetime.utcnow() - self.models[service_name]['last_training'] > timedelta(minutes=30)):
                self.train_model(service_name)
            
            if service_name not in self.models:
                logger.warning(f"No model available for {service_name}")
                return self.fallback_prediction(service_name)
            
            model_info = self.models[service_name]
            model = model_info['model']
            feature_cols = model_info['feature_cols']
            
            # Get recent data for prediction
            df = self.prepare_time_series_data(service_name, hours_back=1)
            if df.empty:
                return self.fallback_prediction(service_name)
            
            # Prepare features for prediction
            df['time_index'] = range(len(df))
            df['rolling_mean_5'] = df['cpu_utilization'].rolling(window=5).mean()
            df['rolling_std_5'] = df['cpu_utilization'].rolling(window=5).std()
            df['lag_1'] = df['cpu_utilization'].shift(1)
            df['lag_2'] = df['cpu_utilization'].shift(2)
            df = df.dropna()
            
            if df.empty:
                return self.fallback_prediction(service_name)
            
            # Predict future values
            future_time = datetime.utcnow() + timedelta(minutes=minutes_ahead)
            future_features = {
                'time_index': len(df) + minutes_ahead * 2,  # Assuming 30s intervals
                'hour_of_day': future_time.hour,
                'minute_of_hour': future_time.minute,
                'rolling_mean_5': df['cpu_utilization'].tail(5).mean(),
                'rolling_std_5': df['cpu_utilization'].tail(5).std(),
                'lag_1': df['cpu_utilization'].iloc[-1],
                'lag_2': df['cpu_utilization'].iloc[-2] if len(df) > 1 else df['cpu_utilization'].iloc[-1]
            }
            
            # Create prediction input
            X_pred = np.array([[future_features[col] for col in feature_cols]])
            predicted_cpu = model.predict(X_pred)[0]
            
            # Ensure prediction is within realistic bounds
            predicted_cpu = max(0, min(100, predicted_cpu))
            
            # Calculate confidence based on model accuracy and recent variance
            confidence = model_info['accuracy'] * 0.8  # Base confidence on model accuracy
            recent_variance = df['cpu_utilization'].tail(10).std()
            if recent_variance > 20:
                confidence *= 0.7  # Lower confidence for high variance periods
            
            result = {
                'service': service_name,
                'predicted_cpu': round(predicted_cpu, 2),
                'confidence': round(confidence, 3),
                'prediction_time': future_time.isoformat(),
                'current_cpu': round(df['cpu_utilization'].iloc[-1], 2),
                'model_accuracy': round(model_info['accuracy'], 3),
                'recommended_replicas': self.calculate_recommended_replicas(predicted_cpu, service_name)
            }
            
            # Cache the prediction for 1 minute
            redis_client.setex(cache_key, 60, json.dumps(result))
            
            # Update Prometheus metrics
            prediction_gauge.labels(service=service_name).set(predicted_cpu)
            confidence_gauge.labels(service=service_name).set(confidence)
            scaling_recommendation.labels(service=service_name).set(result['recommended_replicas'])
            
            return result
            
        except Exception as e:
            logger.error(f"Prediction failed for {service_name}: {e}")
            return self.fallback_prediction(service_name)
    
    def fallback_prediction(self, service_name):
        """Fallback prediction when ML model is not available"""
        current_time = datetime.utcnow()
        hour = current_time.hour
        
        # Simple heuristic based on time of day
        if 8 <= hour <= 18:  # Business hours
            predicted_cpu = 35 + np.random.normal(0, 5)
        else:  # Off hours
            predicted_cpu = 15 + np.random.normal(0, 3)
        
        predicted_cpu = max(5, min(95, predicted_cpu))
        
        return {
            'service': service_name,
            'predicted_cpu': round(predicted_cpu, 2),
            'confidence': 0.5,  # Low confidence for fallback
            'prediction_time': (current_time + timedelta(minutes=5)).isoformat(),
            'current_cpu': round(predicted_cpu * 0.9, 2),
            'model_accuracy': 0.5,
            'recommended_replicas': self.calculate_recommended_replicas(predicted_cpu, service_name),
            'fallback': True
        }
    
    def calculate_recommended_replicas(self, predicted_cpu, service_name):
        """Calculate recommended number of replicas based on predicted CPU"""
        target_cpu = 50  # Target 50% CPU utilization
        current_replicas = self.get_current_replicas(service_name)
        
        if predicted_cpu > 70:
            return min(10, current_replicas + 2)  # Scale up aggressively
        elif predicted_cpu > target_cpu:
            return min(10, current_replicas + 1)  # Scale up moderately
        elif predicted_cpu < 20 and current_replicas > 1:
            return max(1, current_replicas - 1)  # Scale down
        else:
            return current_replicas  # No change needed
    
    def get_current_replicas(self, service_name):
        """Get current number of replicas (fallback to 2 if unable to determine)"""
        try:
            # This would typically query Kubernetes API
            # For now, return a default value
            return 2
        except:
            return 2

# Initialize the scaler
scaler = PredictiveScaler()

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/predict/<service_name>')
def predict_service(service_name):
    """Get prediction for a specific service"""
    minutes_ahead = request.args.get('minutes', 5, type=int)
    prediction = scaler.predict_cpu_utilization(service_name, minutes_ahead)
    return jsonify(prediction)

@app.route('/predict/all')
def predict_all_services():
    """Get predictions for all services"""
    services = ['user-service', 'catalog-service', 'order-service']
    predictions = {}
    
    for service in services:
        predictions[service] = scaler.predict_cpu_utilization(service)
    
    return jsonify({
        'predictions': predictions,
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/retrain/<service_name>', methods=['POST'])
def retrain_model(service_name):
    """Force retrain model for a service"""
    try:
        model = scaler.train_model(service_name)
        if model:
            return jsonify({
                'status': 'success',
                'message': f'Model retrained for {service_name}',
                'accuracy': scaler.models[service_name]['accuracy']
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Failed to retrain model for {service_name}'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/models/status')
def models_status():
    """Get status of all trained models"""
    status = {}
    for service, model_info in scaler.models.items():
        status[service] = {
            'accuracy': model_info['accuracy'],
            'last_training': model_info['last_training'].isoformat(),
            'data_points': model_info['data_shape'][0] if 'data_shape' in model_info else 0
        }
    
    return jsonify({
        'models': status,
        'total_models': len(scaler.models)
    })

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest(registry)

if __name__ == '__main__':
    logger.info("Starting Predictive Autoscaler Service")
    logger.info(f"Prometheus URL: {PROMETHEUS_URL}")
    logger.info(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    app.run(host='0.0.0.0', port=5000, debug=False)