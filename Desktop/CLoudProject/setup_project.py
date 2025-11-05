import os

# Define services
services = ["user-service", "catalog-service", "order-service"]

# Define common files
base_files = ["app.py", "requirements.txt", "Dockerfile"]
k8s_files = ["deployment.yaml", "service.yaml", "hpa.yaml"]

for service in services:
    # Create service root folder
    os.makedirs(f"{service}/k8s", exist_ok=True)

    # Create base files
    for f in base_files:
        open(f"{service}/{f}", "w").close()

    # Create k8s files
    for f in k8s_files:
        open(f"{service}/k8s/{f}", "w").close()

print("✅ Project structure created!")
