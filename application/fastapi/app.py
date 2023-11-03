from fastapi import FastAPI, HTTPException, status, Body, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from db_utils import load_sql_db_config, get_sql_db_connection, close_sql_db_connection, execute_sql_query, query_piencone_vectors
from auth_utils import hash_password, create_jwt_token, decode_jwt_token
from openai_utils import embed_user_query, ask_openai
from pydantic import BaseModel
from dotenv import load_dotenv
import pathlib, os

env_path = pathlib.Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# Define the global variable
DB_CONFIG = load_sql_db_config()
SECRET_KEY = os.getenv("PRIVATE_KEY")

app = FastAPI()

class RegisterRequestModel(BaseModel):
    fullname: str
    email: str
    username: str
    password: str
    is_active: bool
    
class LoginRequestModel(BaseModel):
    username: str
    password: str
    
class ChatRequestModel(BaseModel):
    query: str
    file_name: list
    sec_no: list
    
security = HTTPBearer()

def get_current_user(authorization: HTTPAuthorizationCredentials = Depends(security)):
    token = authorization.credentials
    conn = get_sql_db_connection(DB_CONFIG)
    try:
        payload = decode_jwt_token(token)
        username = payload.get("username")
        sql_fetch_user = f"SELECT username, emailid, fullname, active FROM [{DB_CONFIG['schema']}].[application_user] WHERE username = %s"
        user = execute_sql_query(conn, sql_fetch_user, (username,), fetch="ONE")
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
    
@app.post("/login", status_code=status.HTTP_200_OK)
async def login(data: LoginRequestModel = Body(...)):
    conn = get_sql_db_connection(DB_CONFIG)
    sql_fetch_password = f"SELECT password FROM [{DB_CONFIG['schema']}].[application_user] WHERE username = %s"
    stored_password_hash = execute_sql_query(conn, sql_fetch_password, (data.username,), fetch="ONE")
    provided_password_hash = hash_password(data.password)
    if stored_password_hash is None or provided_password_hash != stored_password_hash[0]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    close_sql_db_connection(conn=conn)
    token, expiration= create_jwt_token({"username":data.username})
    return {
        "token" : token,
        "validity" : expiration
    }
    
@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(data: RegisterRequestModel = Body(...)):
    conn = get_sql_db_connection(DB_CONFIG)
    schema = DB_CONFIG['schema']
    sql_check_username = f"SELECT 1 FROM [{schema}].[application_user] WHERE username = %s"
    username_check_result = execute_sql_query(conn, sql_check_username, (data.username,), fetch="ONE")
    if username_check_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )
    hashed_password = hash_password(data.password)
    sql_insert = (
        f"INSERT INTO [{schema}].[application_user] "
        f"(username, password, emailid, active, Fullname) VALUES (%s, %s, %s, %s, %s)"
    )
    execute_sql_query(conn, sql_insert, (data.username, hashed_password, data.email, True, data.fullname))
    close_sql_db_connection(conn=conn)
    return {"success": True}

@app.post("/chat", status_code=status.HTTP_200_OK, dependencies=[Depends(get_current_user)])
async def answer_user_query(data: ChatRequestModel = Body(...)):
    user_query = data.query
    query_filter_conditions = {}
    if len(data.file_name) > 0:
        query_filter_conditions["File_Name"] = {"$in": data.file_name}
    if len(data.sec_no) > 0:
        query_filter_conditions["SEC_Number"] = {"$in": data.sec_no}
    user_query_embedding_vector = embed_user_query(user_query=user_query)
    simlarity_query_result = query_piencone_vectors(user_query_embedding_vector, 3, query_filter_conditions)
    ids = tuple(match['id'] for match in simlarity_query_result['matches'])
    conn = get_sql_db_connection(DB_CONFIG)
    schema = DB_CONFIG['schema']
    id_placeholders = ', '.join(['%s'] * len(ids))
    sql_get_pdf_chunks = f"SELECT Chunk_Content FROM [{schema}].[bigdataassignment3_chunkstorage] WHERE ID IN ({id_placeholders})"
    pdf_chunks = execute_sql_query(conn, sql_get_pdf_chunks, ids, fetch="ALL")
    print(pdf_chunks)
    open_ai_answer = ask_openai(pdf_chunks, user_query)
    return {
        "response" : open_ai_answer
    }
    
@app.get("/get_all_filter", status_code=status.HTTP_200_OK, dependencies=[Depends(get_current_user)])
async def get_all_filter():
    conn = get_sql_db_connection(DB_CONFIG)
    schema = DB_CONFIG['schema']
    sql_get_file_names = f"SELECT distinct File_Name FROM [{schema}].[bigdataassignment3_chunkstorage]"
    sql_get_sec_no = f"SELECT distinct SEC_Number FROM [{schema}].[bigdataassignment3_chunkstorage]"
    file_names = execute_sql_query(conn, sql_get_file_names, None, fetch="ALL")
    sec_no = execute_sql_query(conn, sql_get_sec_no, None, fetch="ALL")
    return{
        "file_names":file_names,
        "sec_no":sec_no
    }