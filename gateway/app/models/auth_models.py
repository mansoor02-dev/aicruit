from pydantic import BaseModel
from typing import Optional

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str  # 'RECRUITER' or 'CANDIDATE'
    
    # Optional fields depending on role
    phone: Optional[str] = None
    company_name: Optional[str] = None  # Only for Recruiter

class LoginRequest(BaseModel):
    email: str
    password: str
    
class ResendOTPRequest(BaseModel):
    email: str
    
class ConfirmSignupRequest(BaseModel):
    email: str
    otp: str
    
    
class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str
    email:str