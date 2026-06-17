import os
import sqlite3

def get_db_connection():
    database_url = os.getenv('DATABASE_URL')
    if database_url and database_url.startswith('mysql://'):
        try:
            import re
            import mysql.connector
            from mysql.connector import Error
        except ImportError as e:
            print(f"MySQL connector not installed: {e}")
            return None, True

        # Parse DATABASE_URL for MySQL
        # Assuming format: mysql://user:password@host:port/database or mysql://user:password@host/database
        match = re.match(r'mysql://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/(.+)', database_url)
        if match:
            user, password, host, port, database = match.groups()
            port = int(port) if port else 3306  # Default MySQL port
            try:
                conn = mysql.connector.connect(
                    host=host,
                    user=user,
                    password=password,
                    database=database,
                    port=port
                )
                return conn, True
            except Error as e:
                print(f"Error connecting to MySQL: {e}")
                return None, True
        else:
            print("Invalid DATABASE_URL format")
            return None, True
    else:
        # Fallback to SQLite
        conn = sqlite3.connect('expenses.db')
        conn.row_factory = sqlite3.Row
        return conn, False