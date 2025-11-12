#!/bin/bash

# Advanced Features Deployment Script for Cloud-Native Microservices Platform
# This script deploys predictive autoscaling, KEDA, ArgoCD, and cost optimization

set -e

echo "🚀 Deploying Advanced Cloud-Native Features..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for deployment to be ready
wait_for_deployment() {
    local namespace=$1
    local deployment=$2
    local timeout=${3:-300}
    
    print_status "Waiting for $deployment in namespace $namespace to be ready..."
    kubectl wait --for=condition=available --timeout=${timeout}s deployment/$deployment -n $namespace
}

# Function to check if namespace exists
namespace_exists() {
    kubectl get namespace "$1" >/dev/null 2>&1
}

# Verify prerequisites
print_status "Checking prerequisites..."

if ! command_exists kubectl; then
    print_error "kubectl is not installed. Please install kubectl first."
    exit 1
fi

if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command_exists helm; then
    print_warning "Helm is not installed. Installing Helm..."
    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

print_success "Prerequisites check completed"

# Step 1: Build and push predictor service
print_status "Building and pushing predictor service..."
cd predictor-service

# Build the image
print_status "Building predictor-service Docker image..."
docker build -t starlorddk7/predictor-service:latest .

# Push to Docker Hub (with fallback for connection issues)
print_status "Pushing predictor-service to Docker Hub..."
if ! docker push starlorddk7/predictor-service:latest; then
    print_warning "Failed to push to Docker Hub. Using local image..."
    # Load image into kind/minikube if using local cluster
    if command_exists kind; then
        kind load docker-image starlorddk7/predictor-service:latest
    elif command_exists minikube; then
        minikube image load starlorddk7/predictor-service:latest
    fi
fi

cd ..

# Step 2: Build and push cost optimizer service
print_status "Building and pushing cost optimizer service..."
cd cost-optimizer

print_status "Building cost-optimizer Docker image..."
docker build -t starlorddk7/cost-optimizer:latest .

print_status "Pushing cost-optimizer to Docker Hub..."
if ! docker push starlorddk7/cost-optimizer:latest; then
    print_warning "Failed to push to Docker Hub. Using local image..."
    if command_exists kind; then
        kind load docker-image starlorddk7/cost-optimizer:latest
    elif command_exists minikube; then
        minikube image load starlorddk7/cost-optimizer:latest
    fi
fi

cd ..

# Step 3: Install KEDA
print_status "Installing KEDA for event-driven autoscaling..."
if ! kubectl get namespace keda-system >/dev/null 2>&1; then
    helm repo add kedacore https://kedacore.github.io/charts
    helm repo update
    helm install keda kedacore/keda --namespace keda-system --create-namespace
    
    print_status "Waiting for KEDA to be ready..."
    wait_for_deployment keda-system keda-operator 300
    wait_for_deployment keda-system keda-metrics-apiserver 300
    print_success "KEDA installed successfully"
else
    print_success "KEDA is already installed"
fi

# Step 4: Install ArgoCD
print_status "Installing ArgoCD for GitOps..."
if ! namespace_exists argocd; then
    kubectl create namespace argocd
    kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
    
    print_status "Waiting for ArgoCD to be ready..."
    wait_for_deployment argocd argocd-server 600
    wait_for_deployment argocd argocd-application-controller 600
    wait_for_deployment argocd argocd-repo-server 600
    
    # Get ArgoCD admin password
    print_status "Getting ArgoCD admin password..."
    ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
    print_success "ArgoCD installed successfully"
    print_status "ArgoCD admin password: $ARGOCD_PASSWORD"
else
    print_success "ArgoCD is already installed"
fi

# Step 5: Deploy predictor service
print_status "Deploying predictor service..."
kubectl apply -f predictor-service/k8s/deployment.yaml
kubectl apply -f predictor-service/k8s/service.yaml

wait_for_deployment default predictor-service 300
print_success "Predictor service deployed successfully"

# Step 6: Deploy cost optimizer service
print_status "Creating cost optimizer Kubernetes manifests..."
cat <<EOF > cost-optimizer-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cost-optimizer
  namespace: default
  labels:
    app: cost-optimizer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: cost-optimizer
  template:
    metadata:
      labels:
        app: cost-optimizer
    spec:
      containers:
      - name: cost-optimizer
        image: starlorddk7/cost-optimizer:latest
        ports:
        - containerPort: 5000
        env:
        - name: PROMETHEUS_URL
          value: "http://prometheus.monitoring:9090"
        - name: PREDICTOR_URL
          value: "http://predictor-service"
        - name: REDIS_HOST
          value: "redis.database"
        resources:
          requests:
            memory: "128Mi"
            cpu: "50m"
          limits:
            memory: "256Mi"
            cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: cost-optimizer
  namespace: default
spec:
  selector:
    app: cost-optimizer
  ports:
    - port: 80
      targetPort: 5000
EOF

kubectl apply -f cost-optimizer-deployment.yaml
wait_for_deployment default cost-optimizer 300
print_success "Cost optimizer deployed successfully"

# Step 7: Install Prometheus Adapter for Custom Metrics
print_status "Installing Prometheus Adapter for custom metrics..."
if ! helm repo list | grep -q prometheus-community; then
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
fi

# Create custom values for prometheus adapter
cat <<EOF > prometheus-adapter-values.yaml
prometheus:
  url: http://prometheus.monitoring.svc
  port: 9090

rules:
  custom:
  - seriesQuery: 'predicted_cpu_utilization{service!=""}'
    resources:
      overrides:
        service:
          resource: "pod"
    name:
      matches: "predicted_cpu_utilization"
      as: "predicted_cpu_utilization"
    metricsQuery: 'predicted_cpu_utilization{service=<<.LabelMatchers>>}'
  - seriesQuery: 'scaling_recommendation{service!=""}'
    resources:
      overrides:
        service:
          resource: "pod"
    name:
      matches: "scaling_recommendation"
      as: "scaling_recommendation"
    metricsQuery: 'scaling_recommendation{service=<<.LabelMatchers>>}'
EOF

helm upgrade --install prometheus-adapter prometheus-community/prometheus-adapter \
    --namespace monitoring \
    --values prometheus-adapter-values.yaml

print_success "Prometheus Adapter installed"

# Step 8: Deploy KEDA scalers
print_status "Deploying KEDA scalers..."
kubectl apply -f keda-setup/keda-scalers.yaml

print_success "KEDA scalers deployed"

# Step 9: Deploy enhanced HPA with predictive metrics
print_status "Deploying enhanced HPA with predictive metrics..."
# First remove existing HPA
kubectl delete hpa user-service-hpa catalog-service-hpa order-service-hpa --ignore-not-found

# Apply new predictive HPA
kubectl apply -f custom-metrics/predictive-hpa.yaml

print_success "Enhanced HPA deployed"

# Step 10: Create service monitoring dashboard
print_status "Creating monitoring dashboard..."
cat <<EOF > advanced-monitoring-dashboard.json
{
  "dashboard": {
    "id": null,
    "title": "Advanced Microservices Platform",
    "tags": ["microservices", "predictive", "cost"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Predicted vs Actual CPU",
        "type": "graph",
        "targets": [
          {
            "expr": "predicted_cpu_utilization",
            "legendFormat": "Predicted CPU - {{service}}"
          },
          {
            "expr": "rate(container_cpu_usage_seconds_total{pod=~\".*-service.*\"}[5m]) * 100",
            "legendFormat": "Actual CPU - {{pod}}"
          }
        ]
      },
      {
        "id": 2,
        "title": "Cost Analysis",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(scaling_recommendation)",
            "legendFormat": "Total Recommended Replicas"
          }
        ]
      },
      {
        "id": 3,
        "title": "KEDA Scaling Events",
        "type": "graph",
        "targets": [
          {
            "expr": "keda_scaler_active",
            "legendFormat": "KEDA Scaler Active - {{scaledObject}}"
          }
        ]
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s"
  }
}
EOF

print_success "Monitoring dashboard configuration created"

# Step 11: Test the deployment
print_status "Testing the deployment..."

# Test predictor service
print_status "Testing predictor service..."
if kubectl exec -n default deployment/predictor-service -- curl -f http://localhost:5000/health; then
    print_success "Predictor service is healthy"
else
    print_warning "Predictor service health check failed"
fi

# Test cost optimizer service
print_status "Testing cost optimizer service..."
if kubectl exec -n default deployment/cost-optimizer -- curl -f http://localhost:5000/health; then
    print_success "Cost optimizer service is healthy"
else
    print_warning "Cost optimizer service health check failed"
fi

# Step 12: Create test script for advanced features
cat <<EOF > test-advanced-features.sh
#!/bin/bash

echo "🧪 Testing Advanced Features..."

# Test predictions
echo "Testing ML predictions:"
kubectl exec -n default deployment/predictor-service -- curl -s http://localhost:5000/predict/user-service | jq .

echo -e "\nTesting cost analysis:"
kubectl exec -n default deployment/cost-optimizer -- curl -s http://localhost:5000/cost-analysis/all | jq .summary

echo -e "\nTesting scaling decisions:"
kubectl exec -n default deployment/cost-optimizer -- curl -s http://localhost:5000/scaling-decision/order-service | jq .

echo -e "\nChecking HPA status:"
kubectl get hpa

echo -e "\nChecking KEDA scaled objects:"
kubectl get scaledobjects

echo -e "\nChecking ArgoCD applications:"
kubectl get applications -n argocd 2>/dev/null || echo "No ArgoCD applications deployed yet"

echo -e "\n✅ Advanced features test completed!"
EOF

chmod +x test-advanced-features.sh

# Step 13: Create cleanup script
cat <<EOF > cleanup-advanced.sh
#!/bin/bash

echo "🧹 Cleaning up advanced features..."

# Remove deployments
kubectl delete deployment predictor-service cost-optimizer --ignore-not-found
kubectl delete service predictor-service cost-optimizer --ignore-not-found

# Remove HPA
kubectl delete hpa user-service-hpa-predictive catalog-service-hpa-predictive order-service-hpa-predictive --ignore-not-found

# Remove KEDA scalers
kubectl delete scaledobjects --all --ignore-not-found

# Uninstall KEDA
helm uninstall keda -n keda-system --ignore-not-found

# Remove ArgoCD (optional - comment out if you want to keep it)
# kubectl delete namespace argocd --ignore-not-found

echo "✅ Cleanup completed!"
EOF

chmod +x cleanup-advanced.sh

# Final status report
print_success "🎉 Advanced features deployment completed!"
echo
echo "📊 Deployment Summary:"
echo "├── ✅ Predictive Autoscaler Service (ML-based CPU prediction)"
echo "├── ✅ Cost Optimizer Service (Cost-aware scaling decisions)"
echo "├── ✅ KEDA (Event-driven autoscaling)"
echo "├── ✅ ArgoCD (GitOps platform)"
echo "├── ✅ Prometheus Adapter (Custom metrics for HPA)"
echo "├── ✅ Enhanced HPA (Predictive + traditional metrics)"
echo "└── ✅ Monitoring dashboards and test scripts"
echo
echo "🔧 Next Steps:"
echo "1. Run './test-advanced-features.sh' to test all features"
echo "2. Access ArgoCD UI: kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo "3. Access Grafana: kubectl port-forward svc/grafana -n monitoring 3000:80"
echo "4. View cost analysis: kubectl port-forward svc/cost-optimizer 8082:80"
echo "5. Check predictions: kubectl port-forward svc/predictor-service 8081:80"
echo
if [ ! -z "$ARGOCD_PASSWORD" ]; then
    echo "🔑 ArgoCD Credentials:"
    echo "   Username: admin"
    echo "   Password: $ARGOCD_PASSWORD"
fi
echo
echo "🚀 Your Cloud-Native Microservices Platform with Predictive Autoscaling is ready!"