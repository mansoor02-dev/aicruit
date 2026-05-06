import hmac
import hashlib
import base64

def get_secret_hash(username:str, client_id:str, client_secret:str) -> str:
    message = username + client_id
    dig = hmac.new(
        str(client_secret).encode("utf-8"),
        msg=message.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(dig).decode()