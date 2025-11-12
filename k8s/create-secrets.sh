# Create Kubernetes secrets for the microservices platform

# PostgreSQL secret
kubectl create secret generic postgres-secrets \
  --from-literal=password=your-secure-postgres-password \
  --namespace=default

# Redis secret (if needed for auth)
kubectl create secret generic redis-secrets \
  --from-literal=password=your-redis-password \
  --namespace=default

# Container registry secret for pulling images from GHCR
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=Daksh-khandelwal-1495 \
  --docker-password=YOUR_GITHUB_TOKEN \
  --namespace=default

# Example ConfigMap for shared configuration
kubectl create configmap app-config \
  --from-literal=log-level=info \
  --from-literal=environment=production \
  --namespace=default

echo "Secrets and ConfigMaps created successfully!"
echo "Note: Replace placeholder values with actual credentials before running."