# Quick Docker Desktop + Local K8s Test
# Run this to test the services locally before pushing to production

echo "🚀 Testing Cloud Platform with Docker Desktop Kubernetes"
echo "=================================================="

# Check if Docker Desktop is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker Desktop is not running. Please start Docker Desktop first."
    exit 1
fi

# Check if Kubernetes is enabled in Docker Desktop
if ! kubectl cluster-info > /dev/null 2>&1; then
    echo "❌ Kubernetes is not enabled in Docker Desktop."
    echo "Enable it in Docker Desktop Settings > Kubernetes > Enable Kubernetes"
    exit 1
fi

echo "✅ Docker Desktop and Kubernetes are running"

# Build images locally for testing
echo "🔨 Building Docker images locally..."
cd "c:/Users/Daksh/Desktop/CLoudProject"

docker build -t catalog-service:local catalog-service/
docker build -t order-service:local order-service/
docker build -t user-service:local user-service/
docker build -t advanced-ml-service:local advanced-ml-service/

echo "✅ All images built successfully"

# Create namespace and secrets (for local testing)
echo "🔑 Creating secrets for local testing..."
kubectl create secret generic postgres-secrets \
  --from-literal=password=testpassword123 \
  --dry-run=client -o yaml | kubectl apply -f -

# Apply manifests with local images (create temporary manifests)
echo "📦 Deploying services to local Kubernetes..."

# Create temporary manifests with local images
sed 's|ghcr.io/daksh-khandelwal-1495/catalog-service:latest|catalog-service:local|g' catalog-service/k8s/deployment.yaml > /tmp/catalog-local.yaml
sed 's|ghcr.io/daksh-khandelwal-1495/order-service:latest|order-service:local|g' order-service/k8s/deployment.yaml > /tmp/order-local.yaml
sed 's|ghcr.io/daksh-khandelwal-1495/user-service:latest|user-service:local|g' user-service/k8s/deployment.yaml > /tmp/user-local.yaml
sed 's|ghcr.io/daksh-khandelwal-1495/advanced-ml-service:latest|advanced-ml-service:local|g' advanced-ml-service/k8s/deployment.yaml > /tmp/ml-local.yaml

# Also change imagePullPolicy to Never for local images
sed -i 's|imagePullPolicy: IfNotPresent|imagePullPolicy: Never|g' /tmp/catalog-local.yaml
sed -i 's|imagePullPolicy: IfNotPresent|imagePullPolicy: Never|g' /tmp/order-local.yaml  
sed -i 's|imagePullPolicy: IfNotPresent|imagePullPolicy: Never|g' /tmp/user-local.yaml
sed -i 's|imagePullPolicy: IfNotPresent|imagePullPolicy: Never|g' /tmp/ml-local.yaml

kubectl apply -f /tmp/catalog-local.yaml
kubectl apply -f /tmp/order-local.yaml
kubectl apply -f /tmp/user-local.yaml
kubectl apply -f /tmp/ml-local.yaml

# Apply HPA
kubectl apply -f catalog-service/k8s/hpa.yaml
kubectl apply -f order-service/k8s/hpa.yaml
kubectl apply -f user-service/k8s/hpa.yaml
kubectl apply -f advanced-ml-service/k8s/hpa.yaml

echo "⏳ Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app=catalog-service --timeout=120s
kubectl wait --for=condition=ready pod -l app=order-service --timeout=120s
kubectl wait --for=condition=ready pod -l app=user-service --timeout=120s
kubectl wait --for=condition=ready pod -l app=advanced-ml-service --timeout=120s

echo "✅ All services are running!"

# Port forward for testing
echo "🌐 Setting up port forwarding..."
kubectl port-forward svc/catalog-service 8080:5000 &
kubectl port-forward svc/order-service 8081:5000 &
kubectl port-forward svc/user-service 8082:5000 &
kubectl port-forward svc/advanced-ml-service 8083:5000 &

echo "=================================================="
echo "🎉 Local deployment complete!"
echo "Services are available at:"
echo "  📚 Catalog Service: http://localhost:8080"
echo "  📋 Order Service: http://localhost:8081"
echo "  👤 User Service: http://localhost:8082"
echo "  🧠 ML Service: http://localhost:8083"
echo ""
echo "Test endpoints:"
echo "  curl http://localhost:8080/health"
echo "  curl http://localhost:8083/predict"
echo ""
echo "To stop: Ctrl+C, then run: kubectl delete -f /tmp/*-local.yaml"
echo "=================================================="

# Keep port forwards running
wait