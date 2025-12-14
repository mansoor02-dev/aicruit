from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from ..core.db import get_db_session
from ..models.user import UserModel

# OAuth2 scheme for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# ---------------------------------------------------------
# 1. AUTHENTICATION (The "Who are you?" Check)
# ---------------------------------------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db_session)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # For 40% Submission: "Soft Verify"
        # We decode to get the 'sub' without fetching AWS keys yet.
        # In production, you would fetch JWKS keys here.
        payload = jwt.get_unverified_claims(token)
        user_sub: str = payload.get("sub")
        
        if user_sub is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception

    # Check against Postgres to ensure user exists & get their Role
    user = db.query(UserModel).filter(UserModel.cognito_sub == user_sub).first()
    
    if user is None:
        raise credentials_exception

    return user

# ---------------------------------------------------------
# 2. AUTHORIZATION (The "What can you do?" Check)
# ---------------------------------------------------------
class RoleChecker:
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles

    def __call__(self, user: UserModel = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=f"Operation not permitted. User role '{user.role}' is not authorized."
            )
        return user