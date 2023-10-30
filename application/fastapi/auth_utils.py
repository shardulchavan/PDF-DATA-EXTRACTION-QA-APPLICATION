from datetime import datetime, timedelta
from dotenv import load_dotenv
import os, hmac, hashlib, pathlib, jwt

env_path = pathlib.Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# Define the global variable
SECRET_KEY = os.getenv("PRIVATE_KEY")

def hash_password(password: str) -> str:
    secret_key=os.getenv('PRIVATE_KEY').encode()
    hash_object = hmac.new(secret_key, msg=password.encode(), digestmod=hashlib.sha256)
    hash_hex = hash_object.hexdigest()
    return hash_hex


def create_jwt_token(data: dict):
    expiration = datetime.utcnow() + timedelta(minutes=1)
    token_payload = {"exp": expiration, **data}
    token = jwt.encode(token_payload, SECRET_KEY, algorithm="HS256")
    return token, expiration

def decode_jwt_token(token: str):
    decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return decoded_token