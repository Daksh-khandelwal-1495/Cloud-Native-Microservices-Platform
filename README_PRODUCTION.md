Production deployment guide — Cloud-Native Microservices Platform

This document walks through steps to make the project production-ready, build and push images, and deploy via ArgoCD (GitOps).

1) Pick a Container Registry
- Recommended: GitHub Container Registry (GHCR) or Docker Hub.
- For GHCR: create a Personal Access Token (PAT) with "write:packages" and store it as repository secret `CR_PAT`.

2) CI/CD (GitHub Actions)
- File: `.github/workflows/ci-cd.yml` (already added)
- What it does: builds Docker images for each service and pushes tags:
  - ghcr.io/<owner>/catalog-service:<sha>
  - ghcr.io/<owner>/catalog-service:latest (for main)
- Secrets required:
  - `CR_PAT` - registry token (for GHCR)
  - If you use Docker Hub instead, set `DOCKERHUB_USERNAME` and `DOCKERHUB_PASSWORD` and update the login step.

3) Kubernetes manifests and best practices
- Use immutable image tags in production (use the `${{ github.sha }}` image tag created by CI).
- Set `imagePullPolicy: IfNotPresent` for tagged images or `Always` for `:latest`.
- Ensure resource `requests` and `limits` are set for all containers (CPU & memory).
- Use `readinessProbe` and `livenessProbe` (already present in many manifests).
- Store secrets in Kubernetes using `kubectl create secret generic` or external secret managers (Azure KeyVault, AWS Secrets Manager, HashiCorp Vault).

4) GitOps with ArgoCD
- Install ArgoCD in your cluster (see https://argo-cd.readthedocs.io)
- Register your Git repository in ArgoCD or create an `Application` manifest (we added `argocd/microservices-app.yaml` as a template).
- Replace `repoURL` with your repository and commit. ArgoCD will sync the manifests automatically.
- Use `argocd app sync cloudproject-microservices` to manually trigger if needed.

5) Image updates & automated promotions
- Option A: Use image tags in manifests and let CI update manifests via commit (e.g. a second job in Actions that updates k8s image tags and creates a PR).
- Option B: Use automated image updater tools (Flux Image Update, ArgoCD Image Updater).

6) TLS, Ingress, and external access
- Provision an Ingress controller (nginx/Traefik) and configure TLS (cert-manager + Let's Encrypt) for production domains.

7) Monitoring & Logging
- Prometheus + Grafana (already instrumented in manifests via scrape annotations).
- Centralized logs: Fluentd/Fluent Bit -> Elasticsearch/Logz or cloud provider logging.

8) Rollbacks & Disaster Recovery
- Use ArgoCD rollback features or `kubectl rollout undo` for Deployments.
- Keep DB backups and test restore procedures.

9) Local testing (optional)
- Build locally: `docker build -t advanced-ml-service:local advanced-ml-service/`
- Run locally: `docker run -p 5000:5000 advanced-ml-service:local`

10) Next steps and optional improvements
- Add a `kustomize` overlay structure per environment (dev/staging/prod).
- Add a small job in the CI workflow to update k8s manifests with the new SHA tag and open a PR.
- Add a GitHub Action to automatically create an ArgoCD sync (via ArgoCD CLI) after merge to main if you want immediate deploy.


Quick commands (examples):

# Create secret for GHCR
kubectl create secret generic reg-secret --from-literal=token=<GHCR_PAT> -n default

# Apply manifests locally
kubectl apply -k ./ # or `kubectl apply -f k8s/` depending on layout

# ArgoCD sync (example)
argocd app sync cloudproject-microservices

Replace placeholders where necessary and follow your cloud provider's best practices for networking, node pools, and RBAC.
