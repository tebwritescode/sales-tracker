#!/bin/bash

echo "Sales Tracker Setup Script"
echo "=========================="

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  --dev           Run in development mode (with volume mounts)"
    echo "  --production    Run in production mode (with Docker volumes)"
    echo "  --persistent    Run with persistent local data (recommended for production)"
    echo "  --stop          Stop all running containers"
    echo "  --clean         Stop containers and remove volumes"
    echo "  --help          Show this help message"
    echo ""
    echo "Default: Development mode"
}

# Function to ensure directories exist
ensure_directories() {
    echo "Creating necessary directories..."
    mkdir -p data uploads
    chmod 755 data uploads
    
    # Create .gitkeep files if they don't exist
    [ ! -f data/.gitkeep ] && echo "# Keep this directory in git" > data/.gitkeep
    [ ! -f uploads/.gitkeep ] && echo "# Keep this directory in git" > uploads/.gitkeep
    
    echo "✓ Directories created"
}

# Function to build the image
build_image() {
    echo "Building Docker image..."
    if docker build -t sales-tracker . ; then
        echo "✓ Image built successfully"
    else
        echo "✗ Failed to build image"
        exit 1
    fi
}

# Function to run development mode
run_dev() {
    echo "Starting in development mode..."
    ensure_directories
    build_image
    
    # Set proper permissions for data directory
    docker run --rm -v $(pwd):/host -w /host alpine:latest sh -c "
        chown -R 1000:1000 data uploads 2>/dev/null || true
        chmod 755 data uploads
    "
    
    docker-compose up --build
}

# Function to run production mode
run_production() {
    echo "Starting in production mode..."
    ensure_directories
    build_image
    docker-compose --profile production up -d
    echo "✓ Production services started"
    echo "Access the application at: http://localhost"
}

# Function to run persistent mode
run_persistent() {
    echo "Starting with persistent data..."
    ensure_directories
    build_image
    
    # Fix permissions for the mounted volumes
    current_uid=$(id -u)
    current_gid=$(id -g)
    
    echo "Setting up permissions for user $current_uid:$current_gid..."
    chmod 755 data uploads
    
    # Use the persistent profile
    COMPOSE_PROFILES=persistent docker-compose up -d sales-tracker-persistent
    echo "✓ Persistent service started"
    echo "Access the application at: http://localhost:5001"
    echo "Data is stored in: $(pwd)/data/"
}

# Function to stop services
stop_services() {
    echo "Stopping all services..."
    docker-compose --profile production --profile persistent down
    echo "✓ All services stopped"
}

# Function to clean everything
clean_all() {
    echo "Cleaning up containers and volumes..."
    stop_services
    docker-compose down --volumes
    docker system prune -f
    echo "✓ Cleanup completed"
}

# Function to show status
show_status() {
    echo "Current status:"
    echo "=================="
    docker-compose ps
    echo ""
    echo "Docker volumes:"
    docker volume ls | grep sales
    echo ""
    echo "Local directories:"
    ls -la data/ uploads/ 2>/dev/null || echo "No local directories found"
}

# Parse command line arguments
case "${1}" in
    --dev|--development)
        run_dev
        ;;
    --production)
        run_production
        ;;
    --persistent)
        run_persistent
        ;;
    --stop)
        stop_services
        ;;
    --clean)
        clean_all
        ;;
    --status)
        show_status
        ;;
    --help)
        show_usage
        ;;
    "")
        echo "Starting in development mode (default)..."
        run_dev
        ;;
    *)
        echo "Unknown option: $1"
        show_usage
        exit 1
        ;;
esac