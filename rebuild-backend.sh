#!/bin/bash

echo "========================================"
echo "Rebuilding Backend Container"
echo "========================================"

echo ""
echo "Stopping backend container..."
docker-compose stop backend

echo ""
echo "Rebuilding backend image..."
docker-compose build backend

echo ""
echo "Starting backend container..."
docker-compose up -d backend

echo ""
echo "Waiting for backend to be ready..."
sleep 5

echo ""
echo "Checking backend health..."
docker-compose logs --tail=50 backend

echo ""
echo "========================================"
echo "Backend rebuilt and restarted!"
echo "========================================"
echo ""
echo "You can now test the PDF generation again."
echo ""
