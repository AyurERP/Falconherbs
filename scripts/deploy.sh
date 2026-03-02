#!/bin/bash
# Falcon Agency VPS Deployment Script

echo "Starting Deployment..."

cd /opt/falcon-agency || { echo "Directory /opt/falcon-agency not found!"; exit 1; }

echo "Cleaning __pycache__..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

echo "Pulling latest code..."
git pull

echo "Installing dependencies..."
venv/bin/pip install -r requirements.txt --quiet

echo "Running Health Check..."
venv/bin/python main.py --check

if [ $? -eq 0 ]; then
    echo "✅ Health Check Passed! Restarting service..."
    systemctl restart falcon_agency
    echo "🏁 Deployment Complete."
else
    echo "❌ Health Check Failed! Deployment aborted."
    exit 1
fi
