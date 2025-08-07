#!/usr/bin/env python3

import os
import sys

if __name__ == '__main__':
    # Set environment variables for production
    os.environ.setdefault('FLASK_ENV', 'production')
    os.environ.setdefault('SECRET_KEY', 'your-production-secret-key-change-this')
    
    # Import and run the app
    from app import app, init_db
    
    # Initialize database if needed
    print("Initializing database...")
    init_db()
    
    # Run the app
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))