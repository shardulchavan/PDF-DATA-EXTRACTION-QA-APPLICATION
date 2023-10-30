import os
import pymssql
from fastapi import HTTPException, status


def load_db_config():
    return {
        "server": os.getenv('DATABASE_SERVER'),
        "name": os.getenv('DATABASE_NAME'),
        "username": os.getenv('DATABASE_USERNAME'),
        "password": os.getenv('DATABASE_PASSWORD'),
        "schema": os.getenv('DATABASE_SCHEMA')
    }

def get_db_connection(config):
    try:
        conn = pymssql.connect(server=config['server'], user=config['username'], password=config['password'], database=config['name'])
        return conn
    except pymssql.InterfaceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failed: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
def close_db_connection(conn):
    try:
        if conn:
            conn.close()
    except Exception as e:  
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close database connection: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
def execute_query(conn, query, params, fetch=False):
    cursor = conn.cursor()
    result = None
    try:
        cursor.execute(query, params)
        if fetch:
            result = cursor.fetchone()
        else:
            conn.commit()
    except pymssql.DatabaseError as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return result
