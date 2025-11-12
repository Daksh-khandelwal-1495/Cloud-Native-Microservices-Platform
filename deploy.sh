#!/bin/bash

# Complete Deployment Script for Cloud-Native Microservices Platform

echo "🚀 Deploying Cloud-Native Microservices Platform..."

# Step 1: Setup databases
echo "📋 Step 1: Setting up databases..."
bash setup-databases.sh

# Step 2: Build and push Docker images (if needed)
echo "📋 Step 2: Building and pushing Docker images..."
echo "🔨 Building user-service..."
docker build -t starlorddk7/user-service:v2 user-service/

echo "🔨 Building catalog-service..."
docker build -t starlorddk7/catalog-service:v2 catalog-service/

echo "🔨 Building order-service..."
docker build -t starlorddk7/order-service:v2 order-service/

# Step 3: Deploy microservices
echo "📋 Step 3: Deploying microservices..."
kubectl apply -f user-service/k8s/deployment.yaml
kubectl apply -f catalog-service/k8s/deployment.yaml
kubectl apply -f order-service/k8s/deployment.yaml

# Step 4: Deploy HPA
echo "📋 Step 4: Deploying autoscaling policies..."
kubectl apply -f user-service/k8s/hpa.yaml
kubectl apply -f catalog-service/k8s/hpa.yaml
kubectl apply -f order-service/k8s/hpa.yaml

# Step 5: Setup monitoring (optional)
echo "📋 Step 5: Setting up monitoring stack..."
read -p "Install Prometheus monitoring stack? (y/n): " install_monitoring
if [ "$install_monitoring" = "y" ]; then
    bash setup-monitoring.sh
fi

# Wait for deployments
echo "⏳ Waiting for all deployments to be ready..."
kubectl wait --for=condition=Ready pod -l app=user-service --timeout=300s
kubectl wait --for=condition=Ready pod -l app=catalog-service --timeout=300s
kubectl wait --for=condition=Ready pod -l app=order-service --timeout=300s

echo "✅ Deployment completed successfully!"
echo ""
echo "🎯 System Status:"
kubectl get pods
echo ""
kubectl get svc
echo ""
kubectl get hpa
echo ""
echo "🔗 To test the APIs:"
echo "kubectl port-forward svc/user-service 5000:5000 &"
echo "kubectl port-forward svc/catalog-service 5001:5000 &"
echo "kubectl port-forward svc/order-service 5002:5000 &"
echo ""
echo "📊 Access Grafana (if installed): http://localhost:30080 (admin/admin123)"