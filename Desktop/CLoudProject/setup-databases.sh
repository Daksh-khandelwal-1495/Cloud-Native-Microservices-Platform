#!/bin/bash

# Database Setup Script for Cloud-Native Microservices Platform

echo "🚀 Setting up databases for microservices..."

# Create database namespace
echo "📁 Creating database namespace..."
kubectl create namespace database --dry-run=client -o yaml | kubectl apply -f -

# Create PostgreSQL secrets
echo "🔐 Creating PostgreSQL secrets..."
kubectl create secret -n database generic postgres-secrets \
  --from-literal=password=postgres \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic postgres-secrets \
  --from-literal=password=postgres \
  --dry-run=client -o yaml | kubectl apply -f -

# Deploy PostgreSQL
echo "🐘 Deploying PostgreSQL..."
kubectl apply -f postgres-deployment.yaml

# Deploy Redis
echo "🔴 Deploying Redis..."
kubectl apply -f redis-deployment.yaml

# Wait for databases to be ready
echo "⏳ Waiting for databases to be ready..."
kubectl wait --for=condition=Ready pod -l app=postgres -n database --timeout=120s
kubectl wait --for=condition=Ready pod -l app=redis -n database --timeout=120s

echo "✅ Database setup complete!"
echo ""
echo "🔍 Database Status:"
kubectl get pods -n database
echo ""
echo "🔍 Database Services:"
kubectl get svc -n database