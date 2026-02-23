#!/bin/bash
# Falcon Agency VPS Deployment Script

echo "🚀 Starting Deployment..."

cd /opt/falcon-agency || { echo "Directory /opt/falcon-agency not found!"; exit 1; }

echo "📥 Pulling latest code..."
git pull

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "🔍 Running Health Check..."
python3 scripts/health_check.py

if [ $? -eq 0 ]; then
    echo "✅ Health Check Passed! Restarting service..."
    systemctl restart falcon_agency
    echo "🏁 Deployment Complete."
else
    echo "❌ Health Check Failed! Deployment aborted."
    exit 1
fi
