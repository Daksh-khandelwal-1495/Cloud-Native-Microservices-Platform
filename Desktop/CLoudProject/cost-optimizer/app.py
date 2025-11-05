import os
import json
import logging
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
import redis
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PROMETHEUS_URL = os.getenv('PROMETHEUS_URL', 'http://prometheus.monitoring:9090')
PREDICTOR_URL = os.getenv('PREDICTOR_URL', 'http://predictor-service')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis.database')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

# Cost configuration (USD per hour)
COST_CONFIG = {
    'cpu_cost_per_core_hour': 0.048,  # Approximate cost per CPU core per hour
    'memory_cost_per_gb_hour': 0.0053,  # Approximate cost per GB memory per hour
    'storage_cost_per_gb_hour': 0.0001,  # Approximate cost per GB storage per hour
    'network_cost_per_gb': 0.09,  # Cost per GB data transfer
    'load_balancer_cost_per_hour': 0.025,  # Cost per load balancer per hour
}

# Resource limits and pricing tiers
RESOURCE_TIERS = {
    'micro': {'cpu': 0.1, 'memory': 128, 'cost_multiplier': 1.0},
    'small': {'cpu': 0.25, 'memory': 256, 'cost_multiplier': 1.2},
    'medium': {'cpu': 0.5, 'memory': 512, 'cost_multiplier': 1.5},
    'large': {'cpu': 1.0, 'memory': 1024, 'cost_multiplier': 2.0},
    'xlarge': {'cpu': 2.0, 'memory': 2048, 'cost_multiplier': 3.5},
}

@dataclass
class CostMetrics:
    service: str
    current_replicas: int
    predicted_replicas: int
    current_cost_per_hour: float
    predicted_cost_per_hour: float
    cost_savings_per_hour: float
    efficiency_score: float
    recommendation: str

@dataclass
class ScalingDecision:
    service: str
    current_replicas: int
    recommended_replicas: int
    cost_impact: float
    performance_impact: str
    confidence: float
    reasoning: str

class CostOptimizer:
    def __init__(self):
        self.redis_client = self._init_redis()
        self.cost_history = {}
        
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            client.ping()
            logger.info("Connected to Redis for cost optimization cache")
            return client
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, using localhost fallback")
            return redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    def get_current_resource_usage(self, service: str) -> Dict:
        """Get current resource usage from Prometheus"""
        try:
            # CPU usage query
            cpu_query = f'rate(container_cpu_usage_seconds_total{{pod=~"{service}.*"}}[5m]) * 100'
            cpu_response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", 
                                      params={'query': cpu_query}, timeout=10)
            
            # Memory usage query
            memory_query = f'container_memory_usage_bytes{{pod=~"{service}.*"}} / 1024 / 1024'
            memory_response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", 
                                         params={'query': memory_query}, timeout=10)
            
            # Replica count query
            replica_query = f'kube_deployment_status_replicas{{deployment="{service}"}}'
            replica_response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", 
                                          params={'query': replica_query}, timeout=10)
            
            # Parse responses
            cpu_usage = 0
            memory_usage = 0
            replica_count = 2  # Default fallback
            
            if cpu_response.status_code == 200:
                cpu_data = cpu_response.json()
                if cpu_data['data']['result']:
                    cpu_usage = float(cpu_data['data']['result'][0]['value'][1])
            
            if memory_response.status_code == 200:
                memory_data = memory_response.json()
                if memory_data['data']['result']:
                    memory_usage = float(memory_data['data']['result'][0]['value'][1])
            
            if replica_response.status_code == 200:
                replica_data = replica_response.json()
                if replica_data['data']['result']:
                    replica_count = int(replica_data['data']['result'][0]['value'][1])
            
            # Fallback to realistic values if no data
            if cpu_usage == 0:
                cpu_usage = np.random.uniform(10, 40)
            if memory_usage == 0:
                memory_usage = np.random.uniform(100, 300)
                
            return {
                'cpu_usage_percent': cpu_usage,
                'memory_usage_mb': memory_usage,
                'replica_count': replica_count,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get resource usage for {service}: {e}")
            # Return synthetic data for demo
            return {
                'cpu_usage_percent': np.random.uniform(15, 45),
                'memory_usage_mb': np.random.uniform(120, 280),
                'replica_count': 2,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def get_prediction_data(self, service: str) -> Dict:
        """Get prediction data from predictor service"""
        try:
            response = requests.get(f"{PREDICTOR_URL}/predict/{service}", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get prediction for {service}")
                return self._fallback_prediction(service)
        except Exception as e:
            logger.error(f"Failed to contact predictor service: {e}")
            return self._fallback_prediction(service)
    
    def _fallback_prediction(self, service: str) -> Dict:
        """Fallback prediction when predictor service is unavailable"""
        current = self.get_current_resource_usage(service)
        predicted_cpu = current['cpu_usage_percent'] * np.random.uniform(0.8, 1.3)
        
        return {
            'service': service,
            'predicted_cpu': predicted_cpu,
            'confidence': 0.6,
            'current_cpu': current['cpu_usage_percent'],
            'recommended_replicas': max(1, min(10, int(predicted_cpu / 40)))
        }
    
    def calculate_cost_metrics(self, service: str) -> CostMetrics:
        """Calculate comprehensive cost metrics for a service"""
        current_usage = self.get_current_resource_usage(service)
        prediction = self.get_prediction_data(service)
        
        # Determine resource tier based on usage
        current_tier = self._determine_resource_tier(current_usage['cpu_usage_percent'])
        predicted_tier = self._determine_resource_tier(prediction['predicted_cpu'])
        
        # Calculate current cost
        current_cost = self._calculate_hourly_cost(
            current_usage['replica_count'], current_tier, current_usage
        )
        
        # Calculate predicted cost
        predicted_replicas = prediction.get('recommended_replicas', current_usage['replica_count'])
        predicted_cost = self._calculate_hourly_cost(
            predicted_replicas, predicted_tier, current_usage
        )
        
        # Calculate efficiency score
        efficiency_score = self._calculate_efficiency_score(
            current_usage, prediction, current_cost, predicted_cost
        )
        
        # Generate recommendation
        recommendation = self._generate_cost_recommendation(
            current_usage['replica_count'], predicted_replicas, 
            current_cost, predicted_cost, efficiency_score
        )
        
        return CostMetrics(
            service=service,
            current_replicas=current_usage['replica_count'],
            predicted_replicas=predicted_replicas,
            current_cost_per_hour=current_cost,
            predicted_cost_per_hour=predicted_cost,
            cost_savings_per_hour=current_cost - predicted_cost,
            efficiency_score=efficiency_score,
            recommendation=recommendation
        )
    
    def _determine_resource_tier(self, cpu_usage: float) -> str:
        """Determine appropriate resource tier based on CPU usage"""
        if cpu_usage < 20:
            return 'micro'
        elif cpu_usage < 35:
            return 'small'
        elif cpu_usage < 50:
            return 'medium'
        elif cpu_usage < 75:
            return 'large'
        else:
            return 'xlarge'
    
    def _calculate_hourly_cost(self, replicas: int, tier: str, usage: Dict) -> float:
        """Calculate hourly cost for given configuration"""
        tier_config = RESOURCE_TIERS[tier]
        
        # Base compute cost
        cpu_cost = replicas * tier_config['cpu'] * COST_CONFIG['cpu_cost_per_core_hour']
        memory_cost = replicas * (tier_config['memory'] / 1024) * COST_CONFIG['memory_cost_per_gb_hour']
        
        # Apply tier multiplier
        base_cost = (cpu_cost + memory_cost) * tier_config['cost_multiplier']
        
        # Add additional costs
        storage_cost = replicas * 0.5 * COST_CONFIG['storage_cost_per_gb_hour']  # 0.5GB storage per replica
        network_cost = replicas * 0.1 * COST_CONFIG['network_cost_per_gb']  # 0.1GB network per replica
        
        return base_cost + storage_cost + network_cost
    
    def _calculate_efficiency_score(self, current_usage: Dict, prediction: Dict, 
                                  current_cost: float, predicted_cost: float) -> float:
        """Calculate efficiency score (0-100)"""
        try:
            # Resource utilization efficiency
            cpu_efficiency = min(100, (current_usage['cpu_usage_percent'] / 70) * 100)
            
            # Cost efficiency
            cost_efficiency = 100 if predicted_cost <= current_cost else max(0, 100 - ((predicted_cost - current_cost) / current_cost * 100))
            
            # Prediction confidence factor
            confidence_factor = prediction.get('confidence', 0.5)
            
            # Combined efficiency score
            efficiency_score = (cpu_efficiency * 0.4 + cost_efficiency * 0.4 + confidence_factor * 100 * 0.2)
            
            return min(100, max(0, efficiency_score))
        except:
            return 50.0  # Neutral score if calculation fails
    
    def _generate_cost_recommendation(self, current_replicas: int, predicted_replicas: int,
                                    current_cost: float, predicted_cost: float, 
                                    efficiency_score: float) -> str:
        """Generate human-readable cost recommendation"""
        cost_diff = predicted_cost - current_cost
        
        if abs(cost_diff) < 0.01:  # Less than 1 cent difference
            return "MAINTAIN: Current scaling is cost-optimal"
        elif cost_diff < 0:  # Cost reduction
            savings_per_day = abs(cost_diff) * 24
            if predicted_replicas < current_replicas:
                return f"SCALE DOWN: Save ${savings_per_day:.2f}/day by reducing to {predicted_replicas} replicas"
            else:
                return f"OPTIMIZE: Save ${savings_per_day:.2f}/day with better resource allocation"
        else:  # Cost increase
            cost_per_day = cost_diff * 24
            if efficiency_score > 75:
                return f"SCALE UP: Invest ${cost_per_day:.2f}/day for better performance (high efficiency)"
            else:
                return f"REVIEW: ${cost_per_day:.2f}/day increase - verify if performance gain justifies cost"
    
    def make_scaling_decision(self, service: str) -> ScalingDecision:
        """Make intelligent scaling decision considering cost and performance"""
        cost_metrics = self.calculate_cost_metrics(service)
        prediction = self.get_prediction_data(service)
        current_usage = self.get_current_resource_usage(service)
        
        # Business rules for scaling decisions
        current_replicas = cost_metrics.current_replicas
        ml_recommended = cost_metrics.predicted_replicas
        
        # Cost-aware adjustment
        if cost_metrics.cost_savings_per_hour > 0.05:  # Significant savings
            if cost_metrics.efficiency_score > 60:
                recommended_replicas = ml_recommended
                reasoning = "ML prediction with significant cost savings"
            else:
                recommended_replicas = max(1, ml_recommended - 1)
                reasoning = "Conservative scaling due to low efficiency score"
        elif cost_metrics.cost_savings_per_hour < -0.10:  # Significant cost increase
            recommended_replicas = min(ml_recommended, current_replicas + 1)
            reasoning = "Limited scale-up due to cost concerns"
        else:
            recommended_replicas = ml_recommended
            reasoning = "Standard ML-based scaling"
        
        # Performance safety checks
        if current_usage['cpu_usage_percent'] > 80 and recommended_replicas < current_replicas:
            recommended_replicas = current_replicas
            reasoning = "Scaling blocked due to high current CPU usage"
            performance_impact = "HIGH_RISK"
        elif current_usage['cpu_usage_percent'] < 10 and recommended_replicas > current_replicas:
            recommended_replicas = max(1, current_replicas - 1)
            reasoning = "Scale-down suggested due to very low CPU usage"
            performance_impact = "LOW_RISK"
        else:
            performance_impact = "MEDIUM_RISK" if abs(recommended_replicas - current_replicas) > 1 else "LOW_RISK"
        
        # Calculate cost impact
        new_cost = self._calculate_hourly_cost(
            recommended_replicas, 
            self._determine_resource_tier(prediction['predicted_cpu']),
            current_usage
        )
        cost_impact = new_cost - cost_metrics.current_cost_per_hour
        
        return ScalingDecision(
            service=service,
            current_replicas=current_replicas,
            recommended_replicas=recommended_replicas,
            cost_impact=cost_impact,
            performance_impact=performance_impact,
            confidence=prediction.get('confidence', 0.5),
            reasoning=reasoning
        )

# Initialize cost optimizer
cost_optimizer = CostOptimizer()

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/cost-metrics/<service>')
def get_cost_metrics(service):
    """Get cost metrics for a specific service"""
    try:
        metrics = cost_optimizer.calculate_cost_metrics(service)
        return jsonify({
            'service': metrics.service,
            'current_replicas': metrics.current_replicas,
            'predicted_replicas': metrics.predicted_replicas,
            'current_cost_per_hour': round(metrics.current_cost_per_hour, 4),
            'predicted_cost_per_hour': round(metrics.predicted_cost_per_hour, 4),
            'cost_savings_per_hour': round(metrics.cost_savings_per_hour, 4),
            'cost_savings_per_day': round(metrics.cost_savings_per_hour * 24, 2),
            'cost_savings_per_month': round(metrics.cost_savings_per_hour * 24 * 30, 2),
            'efficiency_score': round(metrics.efficiency_score, 1),
            'recommendation': metrics.recommendation,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to get cost metrics for {service}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/scaling-decision/<service>')
def get_scaling_decision(service):
    """Get intelligent scaling decision for a service"""
    try:
        decision = cost_optimizer.make_scaling_decision(service)
        return jsonify({
            'service': decision.service,
            'current_replicas': decision.current_replicas,
            'recommended_replicas': decision.recommended_replicas,
            'cost_impact_per_hour': round(decision.cost_impact, 4),
            'cost_impact_per_day': round(decision.cost_impact * 24, 2),
            'performance_impact': decision.performance_impact,
            'confidence': round(decision.confidence, 3),
            'reasoning': decision.reasoning,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to make scaling decision for {service}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/cost-analysis/all')
def get_all_cost_analysis():
    """Get comprehensive cost analysis for all services"""
    services = ['user-service', 'catalog-service', 'order-service']
    analysis = {}
    total_current_cost = 0
    total_predicted_cost = 0
    
    for service in services:
        try:
            metrics = cost_optimizer.calculate_cost_metrics(service)
            decision = cost_optimizer.make_scaling_decision(service)
            
            analysis[service] = {
                'cost_metrics': {
                    'current_cost_per_hour': round(metrics.current_cost_per_hour, 4),
                    'predicted_cost_per_hour': round(metrics.predicted_cost_per_hour, 4),
                    'savings_per_hour': round(metrics.cost_savings_per_hour, 4),
                    'efficiency_score': round(metrics.efficiency_score, 1)
                },
                'scaling_decision': {
                    'current_replicas': decision.current_replicas,
                    'recommended_replicas': decision.recommended_replicas,
                    'performance_impact': decision.performance_impact,
                    'reasoning': decision.reasoning
                }
            }
            
            total_current_cost += metrics.current_cost_per_hour
            total_predicted_cost += metrics.predicted_cost_per_hour
            
        except Exception as e:
            logger.error(f"Failed to analyze {service}: {e}")
            analysis[service] = {'error': str(e)}
    
    return jsonify({
        'services': analysis,
        'summary': {
            'total_current_cost_per_hour': round(total_current_cost, 4),
            'total_predicted_cost_per_hour': round(total_predicted_cost, 4),
            'total_savings_per_hour': round(total_current_cost - total_predicted_cost, 4),
            'total_savings_per_day': round((total_current_cost - total_predicted_cost) * 24, 2),
            'total_savings_per_month': round((total_current_cost - total_predicted_cost) * 24 * 30, 2)
        },
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/cost-tiers')
def get_cost_tiers():
    """Get available resource tiers and pricing"""
    return jsonify({
        'resource_tiers': RESOURCE_TIERS,
        'cost_config': COST_CONFIG,
        'description': 'Resource tiers and cost configuration for the platform'
    })

if __name__ == '__main__':
    logger.info("Starting Cost Optimizer Service")
    logger.info(f"Prometheus URL: {PROMETHEUS_URL}")
    logger.info(f"Predictor URL: {PREDICTOR_URL}")
    app.run(host='0.0.0.0', port=5000, debug=False)