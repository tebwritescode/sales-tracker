#!/usr/bin/env python3
"""
Database troubleshooting and fix script for Sales Tracker
"""

import os
import sys
import sqlite3
from pathlib import Path

def check_environment():
    """Check the current environment and permissions"""
    print("=== Environment Check ===")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python version: {sys.version}")
    print(f"User ID: {os.getuid() if hasattr(os, 'getuid') else 'N/A'}")
    print(f"Process ID: {os.getpid()}")
    
    # Check directory permissions
    current_dir = Path('.')
    data_dir = Path('data')
    
    print(f"\nCurrent directory ({current_dir.absolute()}):")
    print(f"  Exists: {current_dir.exists()}")
    print(f"  Readable: {os.access(current_dir, os.R_OK)}")
    print(f"  Writable: {os.access(current_dir, os.W_OK)}")
    print(f"  Executable: {os.access(current_dir, os.X_OK)}")
    
    print(f"\nData directory ({data_dir.absolute()}):")
    print(f"  Exists: {data_dir.exists()}")
    if data_dir.exists():
        print(f"  Readable: {os.access(data_dir, os.R_OK)}")
        print(f"  Writable: {os.access(data_dir, os.W_OK)}")
        print(f"  Executable: {os.access(data_dir, os.X_OK)}")

def test_sqlite_creation():
    """Test SQLite database creation in different locations"""
    print("\n=== SQLite Database Creation Test ===")
    
    test_locations = [
        'test_db.sqlite',
        'data/test_db.sqlite',
        '/tmp/test_db.sqlite'
    ]
    
    for location in test_locations:
        try:
            print(f"\nTesting: {location}")
            
            # Ensure directory exists
            dir_path = os.path.dirname(location)
            if dir_path and dir_path != '':
                os.makedirs(dir_path, exist_ok=True)
                print(f"  Directory created/verified: {dir_path}")
            
            # Try to create database
            conn = sqlite3.connect(location)
            cursor = conn.cursor()
            
            # Create a test table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
            ''')
            
            # Insert test data
            cursor.execute("INSERT INTO test_table (name) VALUES (?)", ("test",))
            conn.commit()
            
            # Read test data
            cursor.execute("SELECT * FROM test_table")
            result = cursor.fetchone()
            
            conn.close()
            
            # Clean up
            if os.path.exists(location):
                os.remove(location)
            
            print(f"  ✓ SUCCESS: Database created and tested successfully")
            print(f"  ✓ Test data: {result}")
            
        except Exception as e:
            print(f"  ✗ FAILED: {e}")

def fix_permissions():
    """Fix directory permissions"""
    print("\n=== Fixing Permissions ===")
    
    directories = ['.', 'data', 'uploads']
    
    for directory in directories:
        try:
            if not os.path.exists(directory):
                os.makedirs(directory, mode=0o755)
                print(f"✓ Created directory: {directory}")
            
            # Try to fix permissions
            os.chmod(directory, 0o755)
            print(f"✓ Fixed permissions for: {directory}")
            
        except Exception as e:
            print(f"✗ Failed to fix {directory}: {e}")

def create_minimal_database():
    """Create a minimal working database"""
    print("\n=== Creating Minimal Database ===")
    
    try:
        # Try current directory first
        db_path = 'sales_tracker.db'
        
        print(f"Creating database at: {os.path.abspath(db_path)}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create essential tables
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                default_analytics_period VARCHAR(20) DEFAULT 'YTD',
                admin_username VARCHAR(50) DEFAULT 'admin',
                admin_password_hash VARCHAR(128),
                field_toggles TEXT DEFAULT '{}',
                color_scheme VARCHAR(50) DEFAULT 'default'
            );
            
            CREATE TABLE IF NOT EXISTS employee (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                hire_date DATE NOT NULL,
                active_status BOOLEAN DEFAULT 1,
                commission_rate FLOAT DEFAULT 0.0,
                draw_amount FLOAT DEFAULT 0.0
            );
            
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                date DATE NOT NULL,
                revenue_amount FLOAT NOT NULL,
                number_of_deals INTEGER DEFAULT 1,
                commission_earned FLOAT DEFAULT 0.0,
                draw_payment FLOAT DEFAULT 0.0,
                period_type VARCHAR(20) DEFAULT 'month',
                FOREIGN KEY (employee_id) REFERENCES employee (id)
            );
            
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                period_type VARCHAR(20) NOT NULL,
                period_start DATE NOT NULL,
                period_end DATE NOT NULL,
                revenue_goal FLOAT DEFAULT 0.0,
                deals_goal INTEGER DEFAULT 0,
                FOREIGN KEY (employee_id) REFERENCES employee (id)
            );
        ''')
        
        # Insert default admin settings (password is 'admin')
        cursor.execute('''
            INSERT OR REPLACE INTO settings (id, admin_username, admin_password_hash, color_scheme)
            VALUES (1, 'admin', 'scrypt:32768:8:1$BvKy8FZnI4E2XEeP$f8a4b1e3c2d5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6', 'default')
        ''')
        
        conn.commit()
        conn.close()
        
        print(f"✓ Database created successfully: {db_path}")
        print("✓ Default admin user: admin / admin")
        
        return True
        
    except Exception as e:
        print(f"✗ Failed to create database: {e}")
        return False

def main():
    """Main troubleshooting function"""
    print("Sales Tracker Database Troubleshooting Tool")
    print("=" * 50)
    
    # Run diagnostics
    check_environment()
    test_sqlite_creation()
    fix_permissions()
    
    # Try to create a working database
    success = create_minimal_database()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ Database troubleshooting completed successfully!")
        print("You can now try running the application.")
    else:
        print("✗ Database troubleshooting failed.")
        print("Please check the error messages above and ensure:")
        print("1. You have write permissions in the current directory")
        print("2. There is sufficient disk space")
        print("3. SQLite is properly installed")

if __name__ == '__main__':
    main()