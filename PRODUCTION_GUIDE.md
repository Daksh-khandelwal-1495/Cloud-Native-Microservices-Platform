# Production Deployment Guide - Step by Step

## 🚀 Making Your Project Production Ready

This guide walks through deploying your Cloud-Native Microservices Platform to production using Docker, Kubernetes, and GitOps with ArgoCD.

### Prerequisites
- Docker Desktop with Kubernetes enabled
- GitHub repository with your code
- Access to a production Kubernetes cluster (AKS, EKS, GKE, or on-premises)

## 📋 Step-by-Step Production Deployment

### 1. Container Registry Setup (GitHub Container Registry)

Create a GitHub Personal Access Token:
1. Go to GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
2. Generate new token with `write:packages` and `repo` permissions
3. Copy the token

Add the token as a repository secret:
1. Go to your GitHub repo > Settings > Secrets and variables > Actions
2. Create new secret named `CR_PAT` with your token value

### 2. Automated Image Building (CI/CD)

The GitHub Actions workflow (`.github/workflows/ci-cd.yml`) will automatically:
- Build Docker images for all services when you push to main/master
- Push images to `ghcr.io/daksh-khandelwal-1495/<service>:latest` and `ghcr.io/daksh-khandelwal-1495/<service>:<commit-sha>`

To trigger the build:
```bash
git add .
git commit -m "Production ready deployment"
git push origin master
```

Check the Actions tab in GitHub to see the build progress.

### 3. Kubernetes Cluster Setup

For production, you'll need a Kubernetes cluster. Options:
- **Azure Kubernetes Service (AKS)**: `az aks create --resource-group myResourceGroup --name myAKSCluster --node-count 3`
- **Google Kubernetes Engine (GKE)**: `gcloud container clusters create my-cluster --zone=us-central1-a`
- **Amazon EKS**: Use AWS Console or `eksctl create cluster`
- **Local testing**: Use Docker Desktop Kubernetes (already configured)

### 4. Create Kubernetes Secrets

Before deploying, create the required secrets in your cluster:

```bash
# PostgreSQL password
kubectl create secret generic postgres-secrets \
  --from-literal=password=YOUR_SECURE_PASSWORD \
  --namespace=default

# Container registry access (for private images)
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=Daksh-khandelwal-1495 \
  --docker-password=YOUR_GITHUB_TOKEN \
  --namespace=default

# Optional: Add imagePullSecrets to deployments if using private registry
```

### 5. Deploy to Kubernetes

Option A - Direct deployment:
```bash
# Deploy all services
kubectl apply -f catalog-service/k8s/
kubectl apply -f order-service/k8s/
kubectl apply -f user-service/k8s/
kubectl apply -f advanced-ml-service/k8s/

# Check deployment status
kubectl get pods
kubectl get services
kubectl get hpa
```

Option B - GitOps with ArgoCD (Recommended):
```bash
# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Access ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Deploy the application
kubectl apply -f argocd/microservices-app.yaml
```

### 6. Verify Deployment

Check that all services are running:
```bash
# Check pod status
kubectl get pods -o wide

# Check service endpoints
kubectl get services

# Check HPA status
kubectl get hpa

# View logs if needed
kubectl logs -l app=catalog-service
kubectl logs -l app=advanced-ml-service
```

Test the services:
```bash
# Port forward to test locally
kubectl port-forward svc/catalog-service 8080:5000 &
kubectl port-forward svc/advanced-ml-service 8083:5000 &

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8083/predict
```

### 7. Monitoring and Observability

If you have Prometheus/Grafana installed:
```bash
# Check metrics are being scraped
kubectl port-forward svc/prometheus 9090:9090 &
# Visit http://localhost:9090/targets to see scrape targets

# Check Grafana dashboards
kubectl port-forward svc/grafana 3000:3000 &
# Visit http://localhost:3000 (admin/admin)
```

### 8. Production Best Practices

**Resource Management:**
- All services have CPU/memory requests and limits set
- HPA configured for auto-scaling based on CPU usage
- Readiness and liveness probes configured

**Security:**
- Use Kubernetes secrets for sensitive data
- Images are pulled from trusted registries
- Network policies can be added for pod-to-pod communication control

**High Availability:**
- Minimum 2 replicas per service
- Rolling update strategy with zero downtime
- Health checks ensure traffic only goes to healthy pods

## 🔄 Rollback Procedures

### Rolling Back a Deployment
```bash
# Check deployment history
kubectl rollout history deployment/catalog-service

# Rollback to previous version
kubectl rollout undo deployment/catalog-service

# Rollback to specific revision
kubectl rollout undo deployment/catalog-service --to-revision=2

# Check rollback status
kubectl rollout status deployment/catalog-service
```

### ArgoCD Rollback
```bash
# Using ArgoCD CLI
argocd app rollback cloudproject-microservices

# Or via UI: Applications > cloudproject-microservices > History and Rollback
```

## 🛠️ Troubleshooting

### Common Issues

**Pods not starting:**
```bash
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

**Image pull errors:**
- Check if registry credentials are correct
- Verify image names and tags
- Ensure `imagePullSecrets` are configured if using private registry

**Service connectivity issues:**
```bash
# Test pod-to-pod connectivity
kubectl exec -it <pod-name> -- nslookup catalog-service
kubectl exec -it <pod-name> -- curl http://catalog-service:5000/health
```

**Resource issues:**
```bash
# Check node resources
kubectl top nodes
kubectl describe node <node-name>

# Check pod resources
kubectl top pods
```

### Health Check Endpoints
- All services expose `/health` endpoint for monitoring
- Prometheus metrics available at `/metrics`
- Services include proper readiness/liveness probes

## 📊 Scaling and Performance

### Manual Scaling
```bash
# Scale specific service
kubectl scale deployment catalog-service --replicas=5

# Check HPA status
kubectl get hpa
```

### Monitoring Performance
```bash
# Watch resource usage
kubectl top pods --watch

# Monitor HPA decisions
kubectl describe hpa catalog-service-hpa
```

## 🔒 Security Considerations

1. **Secrets Management**: Use Kubernetes secrets or external secret management (Azure Key Vault, AWS Secrets Manager)
2. **RBAC**: Implement role-based access control for production clusters  
3. **Network Policies**: Restrict pod-to-pod communication
4. **Image Scanning**: Scan images for vulnerabilities before deployment
5. **TLS**: Enable TLS for all service communications in production

Your platform is now production-ready with automated CI/CD, proper resource management, health checks, and monitoring! 🎉