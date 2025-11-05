#!/bin/bash

# Monitoring Stack Setup Script

echo "📊 Installing Prometheus monitoring stack..."

# Add Prometheus Helm repository
echo "📦 Adding Helm repositories..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Create monitoring namespace
echo "📁 Creating monitoring namespace..."
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

# Install Prometheus stack
echo "🔧 Installing Prometheus, Grafana, and AlertManager..."
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set grafana.adminPassword=admin123 \
  --set grafana.service.type=NodePort \
  --set grafana.service.nodePort=30080 \
  --set prometheus.service.type=NodePort \
  --set prometheus.service.nodePort=30090

echo "⏳ Waiting for monitoring stack to be ready..."
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=grafana -n monitoring --timeout=300s

echo "✅ Monitoring stack installed successfully!"
echo ""
echo "🎯 Access Information:"
echo "📊 Grafana: http://localhost:30080 (admin/admin123)"
echo "🔍 Prometheus: http://localhost:30090"
echo ""
echo "🔍 Monitoring Pods:"
kubectl get pods -n monitoring