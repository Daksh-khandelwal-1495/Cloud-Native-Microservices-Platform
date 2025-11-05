#!/usr/bin/env python3
"""
Load Generator for Cloud-Native Microservices Platform
Generates realistic traffic patterns to test autoscaling
"""

import requests
import time
import random
import threading
import json
from datetime import datetime

class LoadGenerator:
    def __init__(self):
        self.base_urls = {
            'user': 'http://localhost:5000',
            'catalog': 'http://localhost:5001', 
            'order': 'http://localhost:5002'
        }
        self.running = False
        
    def generate_user_traffic(self):
        """Generate traffic for user service"""
        while self.running:
            try:
                # GET users (cached request)
                response = requests.get(f"{self.base_urls['user']}/users", timeout=5)
                print(f"[{datetime.now()}] User GET: {response.status_code} - {response.json().get('source', 'unknown')}")
                
                # Occasionally add new users
                if random.random() < 0.1:  # 10% chance
                    user_data = {
                        "name": f"User{random.randint(1000, 9999)}",
                        "email": f"user{random.randint(1000, 9999)}@example.com"
                    }
                    response = requests.post(f"{self.base_urls['user']}/users", json=user_data, timeout=5)
                    print(f"[{datetime.now()}] User POST: {response.status_code}")
                    
            except Exception as e:
                print(f"[{datetime.now()}] User service error: {e}")
                
            time.sleep(random.uniform(0.5, 2.0))
    
    def generate_catalog_traffic(self):
        """Generate traffic for catalog service"""
        while self.running:
            try:
                # GET catalog (cached request)
                response = requests.get(f"{self.base_urls['catalog']}/catalog", timeout=5)
                print(f"[{datetime.now()}] Catalog GET: {response.status_code} - {response.json().get('source', 'unknown')}")
                
                # Occasionally add new products
                if random.random() < 0.05:  # 5% chance
                    product_data = {
                        "name": f"Product-{random.randint(100, 999)}",
                        "price": round(random.uniform(10, 500), 2),
                        "category": random.choice(["electronics", "clothing", "books", "home"]),
                        "inventory_count": random.randint(10, 100)
                    }
                    response = requests.post(f"{self.base_urls['catalog']}/catalog", json=product_data, timeout=5)
                    print(f"[{datetime.now()}] Catalog POST: {response.status_code}")
                    
            except Exception as e:
                print(f"[{datetime.now()}] Catalog service error: {e}")
                
            time.sleep(random.uniform(1.0, 3.0))
    
    def generate_order_traffic(self):
        """Generate traffic for order service"""
        while self.running:
            try:
                # GET orders
                response = requests.get(f"{self.base_urls['order']}/orders", timeout=5)
                print(f"[{datetime.now()}] Order GET: {response.status_code} - {response.json().get('source', 'unknown')}")
                
                # GET order stats
                if random.random() < 0.3:  # 30% chance
                    response = requests.get(f"{self.base_urls['order']}/orders/stats", timeout=5)
                    print(f"[{datetime.now()}] Order Stats: {response.status_code} - {response.json().get('source', 'unknown')}")
                
                # Occasionally add new orders
                if random.random() < 0.2:  # 20% chance
                    order_data = {
                        "product_name": f"Product-{random.randint(1, 100)}",
                        "quantity": random.randint(1, 5),
                        "unit_price": round(random.uniform(10, 200), 2),
                        "customer_id": random.randint(1, 50),
                        "status": random.choice(["pending", "processing", "shipped", "completed"])
                    }
                    response = requests.post(f"{self.base_urls['order']}/orders", json=order_data, timeout=5)
                    print(f"[{datetime.now()}] Order POST: {response.status_code}")
                    
            except Exception as e:
                print(f"[{datetime.now()}] Order service error: {e}")
                
            time.sleep(random.uniform(1.5, 4.0))
    
    def start_load_test(self, duration_minutes=10):
        """Start load test for specified duration"""
        print(f"🚀 Starting load test for {duration_minutes} minutes...")
        print("📊 Monitoring traffic patterns...")
        
        self.running = True
        
        # Start traffic generators in separate threads
        threads = [
            threading.Thread(target=self.generate_user_traffic),
            threading.Thread(target=self.generate_catalog_traffic),
            threading.Thread(target=self.generate_order_traffic)
        ]
        
        for thread in threads:
            thread.daemon = True
            thread.start()
        
        # Run for specified duration
        time.sleep(duration_minutes * 60)
        
        self.running = False
        print("🏁 Load test completed!")
    
    def burst_test(self, burst_duration=30):
        """Generate high-intensity burst traffic"""
        print(f"💥 Starting burst test for {burst_duration} seconds...")
        
        start_time = time.time()
        while time.time() - start_time < burst_duration:
            # High-frequency requests
            for service, url in self.base_urls.items():
                try:
                    response = requests.get(f"{url}/{service if service != 'user' else 'users'}", timeout=2)
                    print(f"[BURST] {service}: {response.status_code}")
                except:
                    pass
            time.sleep(0.1)  # Very short delay
        
        print("💥 Burst test completed!")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Load Generator for Microservices')
    parser.add_argument('--mode', choices=['steady', 'burst'], default='steady', help='Load test mode')
    parser.add_argument('--duration', type=int, default=5, help='Duration in minutes for steady mode')
    parser.add_argument('--burst-duration', type=int, default=30, help='Duration in seconds for burst mode')
    
    args = parser.parse_args()
    
    generator = LoadGenerator()
    
    if args.mode == 'steady':
        generator.start_load_test(args.duration)
    else:
        generator.burst_test(args.burst_duration)