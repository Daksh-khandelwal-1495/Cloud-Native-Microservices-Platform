#!/bin/bash
# Demo Script: See All Microservices Working

echo "🚀 Cloud-Native Microservices Platform Demo"
echo "=============================================="
echo ""

# Check if services are running locally
echo "📊 Checking service health..."
echo ""

# Function to test service
test_service() {
    local service_name=$1
    local port=$2
    local endpoint=${3:-"/health"}
    
    echo "Testing $service_name (port $port)..."
    if command -v curl &> /dev/null; then
        response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port$endpoint 2>/dev/null)
        if [ "$response" = "200" ]; then
            echo "✅ $service_name: Running (HTTP $response)"
        else
            echo "❌ $service_name: Not responding (HTTP $response)"
        fi
    else
        echo "⚠️  curl not available, skipping HTTP test for $service_name"
    fi
}

# Test all services
test_service "User Service" 5001
test_service "Catalog Service" 5002  
test_service "Order Service" 5003
test_service "Advanced ML Service" 5004

echo ""
echo "🧪 Testing API Functionality..."
echo ""

# Test User Service
echo "👤 Testing User Service..."
if command -v curl &> /dev/null; then
    echo "Creating a test user..."
    curl -s -X POST http://localhost:5001/users \
         -H "Content-Type: application/json" \
         -d '{"name": "Demo User", "email": "demo@example.com"}' || echo "Service not running"
    
    echo ""
    echo "Getting users list..."
    curl -s http://localhost:5001/users || echo "Service not running"
fi

echo ""
echo ""

# Test Catalog Service  
echo "📚 Testing Catalog Service..."
if command -v curl &> /dev/null; then
    echo "Adding a test product..."
    curl -s -X POST http://localhost:5002/catalog \
         -H "Content-Type: application/json" \
         -d '{"name": "Demo Product", "price": 99.99, "category": "electronics", "inventory_count": 50}' || echo "Service not running"
    
    echo ""
    echo "Getting catalog..."
    curl -s http://localhost:5002/catalog || echo "Service not running"
fi

echo ""
echo ""

# Test Order Service
echo "📋 Testing Order Service..."  
if command -v curl &> /dev/null; then
    echo "Creating a test order..."
    curl -s -X POST http://localhost:5003/orders \
         -H "Content-Type: application/json" \
         -d '{"product_name": "Demo Product", "quantity": 2, "unit_price": 99.99, "customer_id": 1}' || echo "Service not running"
    
    echo ""
    echo "Getting orders..."
    curl -s http://localhost:5003/orders || echo "Service not running"
fi

echo ""
echo ""

# Test ML Service
echo "🧠 Testing Advanced ML Service..."
if command -v curl &> /dev/null; then
    echo "Getting ML predictions..."
    curl -s http://localhost:5004/predict || echo "Service not running"
    
    echo ""
    echo "Getting model performance..."
    curl -s http://localhost:5004/models/performance || echo "Service not running"
fi

echo ""
echo ""
echo "🎯 Demo completed!"
echo ""
echo "To run services locally:"
echo "1. Install dependencies: pip install -r requirements.txt (in each service folder)"
echo "2. Start PostgreSQL and Redis"
echo "3. Run each service: python app.py (in separate terminals)"
echo ""
echo "To see full functionality, use the Kubernetes deployment:"
echo "kubectl apply -f */k8s/"