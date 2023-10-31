import os
import pymssql, pinecone
from fastapi import HTTPException, status


def load_sql_db_config():
    return {
        "server": os.getenv('SQL_DATABASE_SERVER'),
        "name": os.getenv('SQL_DATABASE_NAME'),
        "username": os.getenv('SQL_DATABASE_USERNAME'),
        "password": os.getenv('SQL_DATABASE_PASSWORD'),
        "schema": os.getenv('SQL_DATABASE_SCHEMA')
    }

def get_sql_db_connection(config):
    try:
        conn = pymssql.connect(server=config['server'], user=config['username'], password=config['password'], database=config['name'])
        return conn
    except pymssql.InterfaceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failed: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
def close_sql_db_connection(conn):
    try:
        if conn:
            conn.close()
    except Exception as e:  
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close database connection: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
def execute_sql_query(conn, query, params, fetch = False):
    cursor = conn.cursor()
    result = None
    try:
        cursor.execute(query, params)
        if not fetch:
            conn.commit()
            
        else:
            if fetch == "ONE":
                result = cursor.fetchone()
            elif fetch == "ALL":
                result = cursor.fetchall()
    except pymssql.DatabaseError as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return result

def load_pinecone_db_config():
    return {
        "api_key": os.getenv('PINECONE_API_KEY'),
        "index": os.getenv('PINECONE_INDEX')
    }
    
def query_piencone_vectors(query, top_k, filter_condition = None):
    # config = load_pinecone_db_config
    # pinecone.init(api_key=config['api_key'])
    # index = pinecone.Index(index_name=config['PINECONE_INDEX'])
    # if filter_condition is None:
    #     results = index.query(queries=query, top_k=top_k, include=["id"])
    # else:
    #     results = index.query(queries=query, top_k=top_k, filter=filter_condition, include=["id"])
    # pinecone.deinit()  
    # return results
    return [1,2,3]