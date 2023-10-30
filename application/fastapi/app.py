from fastapi import FastAPI, HTTPException, status, Body, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from db_utils import load_db_config, get_db_connection, close_db_connection, execute_query
from auth_utils import hash_password, create_jwt_token, decode_jwt_token
from openai_utils import embed_user_query
from pydantic import BaseModel
from dotenv import load_dotenv
import pathlib, os

env_path = pathlib.Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# Define the global variable
DB_CONFIG = load_db_config()
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
    
class EmbedRequestModel(BaseModel):
    query: str
    
security = HTTPBearer()

def get_current_user(authorization: HTTPAuthorizationCredentials = Depends(security)):
    token = authorization.credentials
    conn = get_db_connection(DB_CONFIG)
    try:
        payload = decode_jwt_token(token)
        username = payload.get("username")
        sql_fetch_user = f"SELECT username, emailid, fullname, active FROM [{DB_CONFIG['schema']}].[application_user] WHERE username = %s"
        user = execute_query(conn, sql_fetch_user, (username,), fetch=True)
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

@app.get("/secure-data", dependencies=[Depends(get_current_user)])
async def get_secure_data():
    return {"message": "This is protected data"}

@app.post("/embed")
async def test(data: EmbedRequestModel = Body(...)):
    return {"result" : embed_user_query(data.query)}
    
@app.post("/login", status_code=status.HTTP_200_OK)
async def login(data: LoginRequestModel = Body(...)):
    conn = get_db_connection(DB_CONFIG)
    sql_fetch_password = f"SELECT password FROM [{DB_CONFIG['schema']}].[application_user] WHERE username = %s"
    stored_password_hash = execute_query(conn, sql_fetch_password, (data.username,), fetch=True)
    provided_password_hash = hash_password(data.password)
    if stored_password_hash is None or provided_password_hash != stored_password_hash[0]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expiration= create_jwt_token({"username":data.username})
    return {
        "token" : token,
        "validity" : expiration
    }
    


@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(data: RegisterRequestModel = Body(...)):
    conn = get_db_connection(DB_CONFIG)
    schema = DB_CONFIG['schema']
    sql_check_username = f"SELECT 1 FROM [{schema}].[application_user] WHERE username = %s"
    username_check_result = execute_query(conn, sql_check_username, (data.username,), fetch=True)
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
    execute_query(conn, sql_insert, (data.username, hashed_password, data.email, True, data.fullname))
    close_db_connection(conn)
    return {"success": True}
