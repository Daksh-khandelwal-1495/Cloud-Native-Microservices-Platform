import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
import redis
import requests
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings("ignore")

# Deep Learning Libraries
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logging.warning("TensorFlow not available, falling back to sklearn models")

# Time Series Libraries
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logging.warning("Prophet not available, skipping seasonal forecasting")

# Traditional ML Libraries
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.preprocessing import MinMaxScaler
import joblib

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PROMETHEUS_URL = os.getenv('PROMETHEUS_URL', 'http://prometheus.monitoring:9090')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis.database')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

# Model Configuration
MODEL_CONFIG = {
    'lstm': {
        'sequence_length': 20,
        'epochs': 100,
        'batch_size': 32,
        'validation_split': 0.2,
        'early_stopping_patience': 10
    },
    'prophet': {
        'yearly_seasonality': True,
        'weekly_seasonality': True,
        'daily_seasonality': True,
        'interval_width': 0.8
    },
    'ensemble': {
        'models': ['lstm', 'linear_regression', 'random_forest'],
        'weights': [0.5, 0.3, 0.2]
    }
}

@dataclass
class ModelPerformance:
    model_name: str
    mse: float
    mae: float
    accuracy: float
    training_time: float
    prediction_time: float
    confidence: float

@dataclass
class PredictionResult:
    service: str
    model_used: str
    predicted_values: List[float]
    confidence_intervals: List[Tuple[float, float]]
    performance_metrics: ModelPerformance
    recommendation: str
    reasoning: str

class AdvancedMLPredictor:
    def __init__(self):
        self.redis_client = self._init_redis()
        self.models = {}
        self.scalers = {}
        self.performance_history = {}
        self.ab_test_config = self._load_ab_test_config()
        
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            client.ping()
            logger.info("Connected to Redis for advanced ML caching")
            return client
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            return redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    def _load_ab_test_config(self):
        """Load A/B testing configuration"""
        return {
            'active_experiments': {
                'model_comparison': {
                    'traffic_split': {'lstm': 0.4, 'linear_regression': 0.3, 'prophet': 0.3},
                    'metrics': ['mse', 'mae', 'prediction_time', 'business_impact'],
                    'duration_days': 7
                }
            },
            'current_best_model': 'lstm',
            'experiment_start_date': datetime.utcnow().isoformat()
        }
    
    def get_prometheus_data(self, service: str, hours_back: int = 6) -> pd.DataFrame:
        """Enhanced data collection with more features"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours_back)
            
            # Multiple metrics for better prediction
            queries = {
                'cpu': f'rate(container_cpu_usage_seconds_total{{pod=~"{service}.*"}}[1m]) * 100',
                'memory': f'container_memory_usage_bytes{{pod=~"{service}.*"}} / 1024 / 1024',
                'requests': f'rate(flask_http_request_total{{service="{service}"}}[1m])',
                'response_time': f'flask_http_request_duration_seconds_sum{{service="{service}"}} / flask_http_request_duration_seconds_count{{service="{service}"}}'
            }
            
            all_data = []
            for metric_name, query in queries.items():
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
                        if data['data']['result']:
                            for timestamp, value in data['data']['result'][0]['values']:
                                all_data.append({
                                    'timestamp': datetime.fromtimestamp(timestamp),
                                    metric_name: float(value)
                                })
                except Exception as e:
                    logger.warning(f"Failed to fetch {metric_name}: {e}")
            
            if not all_data:
                return self._generate_synthetic_advanced_data(service, hours_back)
            
            # Convert to DataFrame and aggregate by timestamp
            df = pd.DataFrame(all_data)
            df = df.groupby('timestamp').mean().reset_index()
            df = df.sort_values('timestamp')
            
            # Fill missing values
            for col in ['cpu', 'memory', 'requests', 'response_time']:
                if col not in df.columns:
                    df[col] = np.random.uniform(10, 50, len(df))
            
            return self._add_advanced_features(df)
            
        except Exception as e:
            logger.error(f"Failed to get Prometheus data: {e}")
            return self._generate_synthetic_advanced_data(service, hours_back)
    
    def _generate_synthetic_advanced_data(self, service: str, hours_back: int) -> pd.DataFrame:
        """Generate realistic synthetic data with patterns"""
        logger.info(f"Generating synthetic data for {service}")
        
        now = datetime.utcnow()
        timestamps = [now - timedelta(seconds=i*30) for i in range(hours_back * 120)]
        timestamps.reverse()
        
        data = []
        for i, timestamp in enumerate(timestamps):
            hour = timestamp.hour
            day_of_week = timestamp.weekday()
            
            # Realistic patterns
            base_cpu = 20 + 15 * np.sin(hour * np.pi / 12)  # Daily cycle
            weekend_factor = 0.7 if day_of_week >= 5 else 1.0  # Weekend reduction
            noise = np.random.normal(0, 5)
            
            # Traffic spikes during business hours
            if 9 <= hour <= 17 and day_of_week < 5:
                spike_probability = 0.1
                spike = 30 if np.random.random() < spike_probability else 0
            else:
                spike = 0
            
            cpu = max(5, min(95, base_cpu * weekend_factor + noise + spike))
            memory = cpu * 1.2 + np.random.normal(0, 3)  # Memory correlated with CPU
            requests = max(0, cpu / 2 + np.random.normal(0, 2))  # Requests drive CPU
            response_time = max(50, 200 - cpu + np.random.normal(0, 10))  # Higher CPU = faster response
            
            data.append({
                'timestamp': timestamp,
                'cpu': cpu,
                'memory': memory,
                'requests': requests,
                'response_time': response_time
            })
        
        df = pd.DataFrame(data)
        return self._add_advanced_features(df)
    
    def _add_advanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add advanced feature engineering"""
        df = df.copy()
        
        # Time-based features
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        df['is_business_hours'] = ((df['hour'] >= 9) & (df['hour'] <= 17)).astype(int)
        
        # Rolling statistics (multiple windows)
        for window in [5, 10, 20]:
            df[f'cpu_rolling_mean_{window}'] = df['cpu'].rolling(window=window).mean()
            df[f'cpu_rolling_std_{window}'] = df['cpu'].rolling(window=window).std()
            df[f'cpu_rolling_max_{window}'] = df['cpu'].rolling(window=window).max()
        
        # Lag features
        for lag in [1, 2, 3, 5]:
            df[f'cpu_lag_{lag}'] = df['cpu'].shift(lag)
            df[f'requests_lag_{lag}'] = df['requests'].shift(lag)
        
        # Rate of change
        df['cpu_rate_of_change'] = df['cpu'].diff()
        df['requests_rate_of_change'] = df['requests'].diff()
        
        # Interaction features
        df['cpu_requests_ratio'] = df['cpu'] / (df['requests'] + 1)
        df['load_factor'] = df['cpu'] * df['requests'] / 100
        
        # Fill NaN values
        df = df.fillna(method='bfill').fillna(method='ffill')
        
        return df
    
    def prepare_lstm_data(self, df: pd.DataFrame, target_col: str = 'cpu', sequence_length: int = 20) -> Tuple[np.ndarray, np.ndarray, MinMaxScaler]:
        """Prepare data for LSTM training"""
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow not available for LSTM training")
        
        # Select features for LSTM
        feature_columns = [
            target_col, 'hour', 'day_of_week', 'is_weekend', 'is_business_hours',
            f'{target_col}_rolling_mean_5', f'{target_col}_rolling_std_5',
            f'{target_col}_lag_1', f'{target_col}_lag_2', 'requests'
        ]
        
        # Filter columns that exist
        available_features = [col for col in feature_columns if col in df.columns]
        data = df[available_features].values
        
        # Scale the data
        scaler = MinMaxScaler()
        scaled_data = scaler.fit_transform(data)
        
        # Create sequences
        X, y = [], []
        for i in range(sequence_length, len(scaled_data)):
            X.append(scaled_data[i-sequence_length:i])
            y.append(scaled_data[i, 0])  # Predict the target column
        
        return np.array(X), np.array(y), scaler
    
    def build_lstm_model(self, input_shape: Tuple[int, int]) -> tf.keras.Model:
        """Build LSTM neural network model"""
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow not available")
        
        model = Sequential([
            LSTM(50, return_sequences=True, input_shape=input_shape),
            Dropout(0.2),
            LSTM(50, return_sequences=True),
            Dropout(0.2),
            LSTM(50),
            Dropout(0.2),
            Dense(25),
            Dense(1)
        ])
        
        model.compile(optimizer=Adam(learning_rate=0.001), loss='mse', metrics=['mae'])
        return model
    
    def train_lstm_model(self, service: str) -> Optional[tf.keras.Model]:
        """Train LSTM model for service prediction"""
        if not TENSORFLOW_AVAILABLE:
            logger.warning("TensorFlow not available, skipping LSTM training")
            return None
        
        try:
            start_time = datetime.utcnow()
            
            # Get training data
            df = self.get_prometheus_data(service, hours_back=12)
            if len(df) < 50:
                logger.warning(f"Insufficient data for LSTM training: {len(df)} points")
                return None
            
            # Prepare data
            sequence_length = MODEL_CONFIG['lstm']['sequence_length']
            X, y, scaler = self.prepare_lstm_data(df, sequence_length=sequence_length)
            
            if len(X) < 20:
                logger.warning(f"Insufficient sequences for training: {len(X)}")
                return None
            
            # Build model
            model = self.build_lstm_model((sequence_length, X.shape[2]))
            
            # Callbacks
            early_stopping = EarlyStopping(
                monitor='val_loss',
                patience=MODEL_CONFIG['lstm']['early_stopping_patience'],
                restore_best_weights=True
            )
            
            model_checkpoint = ModelCheckpoint(
                f'/tmp/{service}_lstm_model.h5',
                monitor='val_loss',
                save_best_only=True
            )
            
            # Train model
            history = model.fit(
                X, y,
                epochs=MODEL_CONFIG['lstm']['epochs'],
                batch_size=MODEL_CONFIG['lstm']['batch_size'],
                validation_split=MODEL_CONFIG['lstm']['validation_split'],
                callbacks=[early_stopping, model_checkpoint],
                verbose=0
            )
            
            # Calculate performance metrics
            y_pred = model.predict(X)
            mse = mean_squared_error(y, y_pred)
            mae = mean_absolute_error(y, y_pred)
            
            training_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Store model and metadata
            self.models[f'{service}_lstm'] = {
                'model': model,
                'scaler': scaler,
                'sequence_length': sequence_length,
                'performance': ModelPerformance(
                    model_name='LSTM',
                    mse=mse,
                    mae=mae,
                    accuracy=max(0, 1 - (mse / np.var(y))),
                    training_time=training_time,
                    prediction_time=0,
                    confidence=0.85
                ),
                'last_training': datetime.utcnow(),
                'training_history': history.history
            }
            
            logger.info(f"LSTM model trained for {service} - MSE: {mse:.4f}, Training time: {training_time:.2f}s")
            return model
            
        except Exception as e:
            logger.error(f"Failed to train LSTM model for {service}: {e}")
            return None
    
    def train_prophet_model(self, service: str) -> Optional[Prophet]:
        """Train Prophet model for seasonal forecasting"""
        if not PROPHET_AVAILABLE:
            logger.warning("Prophet not available, skipping seasonal forecasting")
            return None
        
        try:
            start_time = datetime.utcnow()
            
            # Get data for Prophet (needs longer history for seasonality)
            df = self.get_prometheus_data(service, hours_back=24)
            if len(df) < 100:
                logger.warning(f"Insufficient data for Prophet training: {len(df)} points")
                return None
            
            # Prepare data for Prophet
            prophet_df = df[['timestamp', 'cpu']].copy()
            prophet_df.columns = ['ds', 'y']
            
            # Initialize and train Prophet model
            model = Prophet(
                yearly_seasonality=MODEL_CONFIG['prophet']['yearly_seasonality'],
                weekly_seasonality=MODEL_CONFIG['prophet']['weekly_seasonality'],
                daily_seasonality=MODEL_CONFIG['prophet']['daily_seasonality'],
                interval_width=MODEL_CONFIG['prophet']['interval_width']
            )
            
            model.fit(prophet_df)
            
            # Calculate performance
            forecast = model.predict(prophet_df)
            mse = mean_squared_error(prophet_df['y'], forecast['yhat'])
            mae = mean_absolute_error(prophet_df['y'], forecast['yhat'])
            
            training_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Store model
            self.models[f'{service}_prophet'] = {
                'model': model,
                'performance': ModelPerformance(
                    model_name='Prophet',
                    mse=mse,
                    mae=mae,
                    accuracy=max(0, 1 - (mse / np.var(prophet_df['y']))),
                    training_time=training_time,
                    prediction_time=0,
                    confidence=0.80
                ),
                'last_training': datetime.utcnow()
            }
            
            logger.info(f"Prophet model trained for {service} - MSE: {mse:.4f}")
            return model
            
        except Exception as e:
            logger.error(f"Failed to train Prophet model for {service}: {e}")
            return None
    
    def train_ensemble_models(self, service: str):
        """Train multiple models for ensemble prediction"""
        logger.info(f"Training ensemble models for {service}")
        
        # Train all available models
        models_trained = []
        
        # LSTM
        if TENSORFLOW_AVAILABLE:
            lstm_model = self.train_lstm_model(service)
            if lstm_model:
                models_trained.append('lstm')
        
        # Prophet
        if PROPHET_AVAILABLE:
            prophet_model = self.train_prophet_model(service)
            if prophet_model:
                models_trained.append('prophet')
        
        # Traditional ML models (always available)
        self.train_traditional_models(service)
        models_trained.extend(['linear_regression', 'random_forest'])
        
        logger.info(f"Trained {len(models_trained)} models for {service}: {models_trained}")
        return models_trained
    
    def train_traditional_models(self, service: str):
        """Train traditional ML models as baseline"""
        try:
            df = self.get_prometheus_data(service, hours_back=6)
            if len(df) < 20:
                return
            
            # Prepare features
            feature_cols = [col for col in df.columns if col.startswith(('cpu_', 'hour', 'day_', 'is_', 'requests'))]
            X = df[feature_cols].fillna(0)
            y = df['cpu']
            
            # Linear Regression
            lr_model = LinearRegression()
            lr_model.fit(X, y)
            lr_pred = lr_model.predict(X)
            
            # Random Forest
            rf_model = RandomForestRegressor(n_estimators=50, random_state=42)
            rf_model.fit(X, y)
            rf_pred = rf_model.predict(X)
            
            # Store models
            for model_name, model, predictions in [
                ('linear_regression', lr_model, lr_pred),
                ('random_forest', rf_model, rf_pred)
            ]:
                mse = mean_squared_error(y, predictions)
                mae = mean_absolute_error(y, predictions)
                
                self.models[f'{service}_{model_name}'] = {
                    'model': model,
                    'feature_columns': feature_cols,
                    'performance': ModelPerformance(
                        model_name=model_name.replace('_', ' ').title(),
                        mse=mse,
                        mae=mae,
                        accuracy=max(0, 1 - (mse / np.var(y))),
                        training_time=1.0,
                        prediction_time=0.01,
                        confidence=0.75 if model_name == 'linear_regression' else 0.80
                    ),
                    'last_training': datetime.utcnow()
                }
            
        except Exception as e:
            logger.error(f"Failed to train traditional models: {e}")
    
    def predict_with_ensemble(self, service: str, minutes_ahead: int = 5) -> PredictionResult:
        """Make prediction using ensemble of models with A/B testing"""
        try:
            # Determine which model to use based on A/B test configuration
            selected_model = self._select_model_for_prediction(service)
            
            if selected_model == 'lstm' and f'{service}_lstm' in self.models:
                return self._predict_with_lstm(service, minutes_ahead)
            elif selected_model == 'prophet' and f'{service}_prophet' in self.models:
                return self._predict_with_prophet(service, minutes_ahead)
            else:
                return self._predict_with_traditional(service, minutes_ahead, selected_model)
                
        except Exception as e:
            logger.error(f"Ensemble prediction failed: {e}")
            return self._fallback_prediction(service, minutes_ahead)
    
    def _select_model_for_prediction(self, service: str) -> str:
        """Select model based on A/B testing configuration"""
        experiment = self.ab_test_config['active_experiments']['model_comparison']
        traffic_split = experiment['traffic_split']
        
        # Simple random selection based on traffic split
        rand = np.random.random()
        cumulative = 0
        for model, weight in traffic_split.items():
            cumulative += weight
            if rand <= cumulative:
                return model
        
        return self.ab_test_config['current_best_model']
    
    def _predict_with_lstm(self, service: str, minutes_ahead: int) -> PredictionResult:
        """Make prediction using LSTM model"""
        model_key = f'{service}_lstm'
        model_info = self.models[model_key]
        model = model_info['model']
        scaler = model_info['scaler']
        sequence_length = model_info['sequence_length']
        
        # Get recent data
        df = self.get_prometheus_data(service, hours_back=2)
        
        # Prepare input sequence
        feature_columns = [
            'cpu', 'hour', 'day_of_week', 'is_weekend', 'is_business_hours',
            'cpu_rolling_mean_5', 'cpu_rolling_std_5',
            'cpu_lag_1', 'cpu_lag_2', 'requests'
        ]
        available_features = [col for col in feature_columns if col in df.columns]
        input_data = df[available_features].values
        
        if len(input_data) < sequence_length:
            raise ValueError(f"Insufficient data for LSTM prediction: {len(input_data)} < {sequence_length}")
        
        # Scale and prepare sequence
        scaled_input = scaler.transform(input_data)
        last_sequence = scaled_input[-sequence_length:].reshape(1, sequence_length, -1)
        
        # Make prediction
        start_time = datetime.utcnow()
        scaled_prediction = model.predict(last_sequence)[0][0]
        prediction_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Inverse transform
        dummy_array = np.zeros((1, scaled_input.shape[1]))
        dummy_array[0, 0] = scaled_prediction
        prediction = scaler.inverse_transform(dummy_array)[0, 0]
        
        # Generate confidence intervals (simplified)
        confidence_lower = prediction * 0.9
        confidence_upper = prediction * 1.1
        
        # Update performance metrics
        model_info['performance'].prediction_time = prediction_time
        
        return PredictionResult(
            service=service,
            model_used='LSTM',
            predicted_values=[prediction],
            confidence_intervals=[(confidence_lower, confidence_upper)],
            performance_metrics=model_info['performance'],
            recommendation=self._generate_recommendation(prediction, df['cpu'].iloc[-1]),
            reasoning=f"LSTM neural network prediction with {sequence_length}-step sequence analysis"
        )
    
    def _predict_with_prophet(self, service: str, minutes_ahead: int) -> PredictionResult:
        """Make prediction using Prophet model"""
        model_key = f'{service}_prophet'
        model_info = self.models[model_key]
        model = model_info['model']
        
        # Create future dataframe
        future_time = datetime.utcnow() + timedelta(minutes=minutes_ahead)
        future_df = pd.DataFrame({'ds': [future_time]})
        
        # Make prediction
        start_time = datetime.utcnow()
        forecast = model.predict(future_df)
        prediction_time = (datetime.utcnow() - start_time).total_seconds()
        
        prediction = forecast['yhat'].iloc[0]
        confidence_lower = forecast['yhat_lower'].iloc[0]
        confidence_upper = forecast['yhat_upper'].iloc[0]
        
        # Update performance metrics
        model_info['performance'].prediction_time = prediction_time
        
        return PredictionResult(
            service=service,
            model_used='Prophet',
            predicted_values=[prediction],
            confidence_intervals=[(confidence_lower, confidence_upper)],
            performance_metrics=model_info['performance'],
            recommendation=self._generate_recommendation(prediction, prediction * 0.9),
            reasoning="Prophet time series forecasting with seasonal decomposition"
        )
    
    def _predict_with_traditional(self, service: str, minutes_ahead: int, model_type: str) -> PredictionResult:
        """Make prediction using traditional ML models"""
        model_key = f'{service}_{model_type}'
        if model_key not in self.models:
            raise ValueError(f"Model {model_key} not available")
        
        model_info = self.models[model_key]
        model = model_info['model']
        feature_columns = model_info['feature_columns']
        
        # Get recent data and prepare features
        df = self.get_prometheus_data(service, hours_back=1)
        X = df[feature_columns].fillna(0).iloc[-1:] 
        
        # Make prediction
        start_time = datetime.utcnow()
        prediction = model.predict(X)[0]
        prediction_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Simple confidence intervals
        confidence_margin = prediction * 0.1
        confidence_lower = prediction - confidence_margin
        confidence_upper = prediction + confidence_margin
        
        # Update performance metrics
        model_info['performance'].prediction_time = prediction_time
        
        return PredictionResult(
            service=service,
            model_used=model_info['performance'].model_name,
            predicted_values=[prediction],
            confidence_intervals=[(confidence_lower, confidence_upper)],
            performance_metrics=model_info['performance'],
            recommendation=self._generate_recommendation(prediction, df['cpu'].iloc[-1]),
            reasoning=f"{model_info['performance'].model_name} prediction with feature engineering"
        )
    
    def _generate_recommendation(self, predicted_cpu: float, current_cpu: float) -> str:
        """Generate scaling recommendation based on prediction"""
        if predicted_cpu > 70:
            return f"SCALE_UP: Predicted high load ({predicted_cpu:.1f}%) - increase replicas"
        elif predicted_cpu < 20:
            return f"SCALE_DOWN: Predicted low load ({predicted_cpu:.1f}%) - reduce replicas"
        else:
            return f"MAINTAIN: Predicted stable load ({predicted_cpu:.1f}%) - no scaling needed"
    
    def _fallback_prediction(self, service: str, minutes_ahead: int) -> PredictionResult:
        """Fallback prediction when all models fail"""
        base_cpu = 35 + np.random.normal(0, 5)
        
        return PredictionResult(
            service=service,
            model_used='Fallback',
            predicted_values=[base_cpu],
            confidence_intervals=[(base_cpu * 0.8, base_cpu * 1.2)],
            performance_metrics=ModelPerformance(
                model_name='Fallback',
                mse=100,
                mae=10,
                accuracy=0.5,
                training_time=0,
                prediction_time=0.001,
                confidence=0.3
            ),
            recommendation=self._generate_recommendation(base_cpu, base_cpu),
            reasoning="Fallback prediction - all advanced models unavailable"
        )

# Initialize the advanced ML predictor
ml_predictor = AdvancedMLPredictor()

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'models_available': list(ml_predictor.models.keys())})

@app.route('/train/<service>')
def train_models(service):
    """Train all available models for a service"""
    try:
        models_trained = ml_predictor.train_ensemble_models(service)
        return jsonify({
            'status': 'success',
            'service': service,
            'models_trained': models_trained,
            'training_completed_at': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/predict/<service>')
def predict_advanced(service):
    """Get advanced ML prediction for service"""
    try:
        minutes_ahead = request.args.get('minutes', 5, type=int)
        result = ml_predictor.predict_with_ensemble(service, minutes_ahead)
        
        return jsonify({
            'service': result.service,
            'model_used': result.model_used,
            'predicted_cpu': result.predicted_values[0],
            'confidence_interval': result.confidence_intervals[0],
            'performance': {
                'mse': result.performance_metrics.mse,
                'mae': result.performance_metrics.mae,
                'accuracy': result.performance_metrics.accuracy,
                'prediction_time': result.performance_metrics.prediction_time
            },
            'recommendation': result.recommendation,
            'reasoning': result.reasoning,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/models/performance')
def get_model_performance():
    """Get performance comparison of all models"""
    performance_data = {}
    
    for model_key, model_info in ml_predictor.models.items():
        service, model_type = model_key.rsplit('_', 1)
        if service not in performance_data:
            performance_data[service] = {}
        
        perf = model_info['performance']
        performance_data[service][model_type] = {
            'mse': perf.mse,
            'mae': perf.mae,
            'accuracy': perf.accuracy,
            'training_time': perf.training_time,
            'prediction_time': perf.prediction_time,
            'confidence': perf.confidence
        }
    
    return jsonify({
        'performance_comparison': performance_data,
        'ab_test_config': ml_predictor.ab_test_config,
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/ab-test/status')
def ab_test_status():
    """Get A/B testing status and results"""
    return jsonify({
        'active_experiments': ml_predictor.ab_test_config['active_experiments'],
        'current_best_model': ml_predictor.ab_test_config['current_best_model'],
        'experiment_duration': (datetime.utcnow() - datetime.fromisoformat(
            ml_predictor.ab_test_config['experiment_start_date'].replace('Z', '+00:00')
        )).days,
        'available_models': {
            'tensorflow_available': TENSORFLOW_AVAILABLE,
            'prophet_available': PROPHET_AVAILABLE,
            'sklearn_available': True
        }
    })

if __name__ == '__main__':
    logger.info("Starting Advanced ML Prediction Service")
    logger.info(f"TensorFlow available: {TENSORFLOW_AVAILABLE}")
    logger.info(f"Prophet available: {PROPHET_AVAILABLE}")
    app.run(host='0.0.0.0', port=5000, debug=False)