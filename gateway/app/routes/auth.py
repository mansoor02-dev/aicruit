from fastapi import APIRouter, HTTPException,Depends
import boto3
from app.helper.auth_helper import get_secret_hash
from ..core.db import get_db_session
from ..models.user import UserModel
from ..models.company import CompanyModel
from ..models.recruiter import RecruiterModel
from ..models.candidate import CandidateModel
from ..models.secrets import SecretKeys
from ..models.auth_models import LoginRequest, ResendOTPRequest, SignupRequest, ConfirmSignupRequest, ForgotPasswordRequest, ResetPasswordRequest, RefreshTokenRequest
from passlib.context import CryptContext
from sqlalchemy.orm import Session

router = APIRouter()

secret_keys = SecretKeys()
COGNITO_CLIENT_ID = secret_keys.COGNITO_CLIENT_ID
COGNITO_CLIENT_SECRET = secret_keys.COGNITO_CLIENT_SECRET
REGION_NAME = secret_keys.REGION_NAME


cognito_client = boto3.client("cognito-idp", region_name=REGION_NAME)


@router.post("/auth/signup")
def signup_user(data: SignupRequest,db:Session = Depends(get_db_session)):
    
    if data.role not in ['RECRUITER', 'CANDIDATE']:
        raise HTTPException(status_code=400, detail="Invalid role. Must be RECRUITER or CANDIDATE")
    
    secret_hash = get_secret_hash(data.email,COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET)
    try:
        cognito_response = cognito_client.sign_up(
            ClientId=COGNITO_CLIENT_ID,
            Username=data.email,
            Password=data.password,
            SecretHash=secret_hash,
            UserAttributes=[
                {"Name": "email", "Value": data.email},
                {"Name": "name", "Value": data.name},
                {"Name": "custom:role", "Value": data.role},
            ],
        )
        cognito_sub = cognito_response.get("UserSub")
        
        if not cognito_sub:
            raise HTTPException(status_code=500, detail="Failed to retrieve user sub from Cognito response")
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_password = pwd_context.hash(data.password)

        new_user = UserModel(
            full_name=data.name,
            email=data.email,
            cognito_sub=cognito_sub,
            password_hash=hashed_password,
            role=data.role, # Store the role!
            email_verified=False
        )
        db.add(new_user)
        db.flush()
        
        # 5. Create Specific Profile (The Magic Part)
        if data.role == "RECRUITER":
            # For 40% submission: Create a new company for every recruiter automatically
            # or link to a default one. Here we create a new one.
            company_name = data.company_name if data.company_name else f"{data.name}'s Company"
            
            new_company = CompanyModel(
                name=company_name
            )
            db.add(new_company)
            db.flush() # Get company ID

            new_recruiter = RecruiterModel(
                id=new_user.id, # Link to User
                company_id=new_company.id, # Link to new Company
                is_admin=True # First user is always admin
            )
            db.add(new_recruiter)

        elif data.role == "CANDIDATE":
            new_candidate = CandidateModel(
                id=new_user.id, # Link to User
                phone=data.phone
            )
            db.add(new_candidate)

        # 6. Commit Everything
        db.commit()
        db.refresh(new_user)
        
        return {
            "message": "User registered successfully. Please verify email.",
            "user_sub": cognito_sub,
            "role": data.role
        }

    except Exception as e:
        db.rollback() # Important: Undo DB changes if Cognito fails or Profile creation fails
        raise HTTPException(status_code=500, detail=str(e))
    
    
@router.post("/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db_session)):
    secret_hash = get_secret_hash(
        data.email,
        COGNITO_CLIENT_ID,
        COGNITO_CLIENT_SECRET
    )

    try:
        cognito_response = cognito_client.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": data.email,
                "PASSWORD": data.password,
                "SECRET_HASH": secret_hash,
            }
        )

        user = db.query(UserModel).filter(UserModel.email == data.email).first()
    
        return {
            "access_token": cognito_response['AuthenticationResult']['AccessToken'],
            "id_token": cognito_response['AuthenticationResult']['IdToken'],
            "refresh_token": cognito_response['AuthenticationResult']['RefreshToken'],
            "user_profile": {
                "id": str(user.id),
                "name": user.full_name,
                "role": user.role,
                "company_id": str(user.recruiter.company_id) if user.role == 'RECRUITER' else None
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/confirm-signup")
def confirm_signup(data: ConfirmSignupRequest):
    secret_hash = get_secret_hash(data.email,COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET)
    try:
        cognito_response = cognito_client.confirm_sign_up(
            ClientId=COGNITO_CLIENT_ID,
            Username=data.email,
            SecretHash=secret_hash,
            ConfirmationCode=data.otp,
        )
        
        return {"message":"User confirmed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
@router.post("/auth/resend-otp")
def resend_otp(data: ResendOTPRequest):
    secret_hash = get_secret_hash(data.email,COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET)
    try:
        cognito_response = cognito_client.resend_confirmation_code(
            ClientId=COGNITO_CLIENT_ID,
            Username=data.email,
            SecretHash=secret_hash
        )
        
        return {"message":"OTP resent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/auth/forgot-password")
def forgot_password(data: ForgotPasswordRequest):
    secret_hash = get_secret_hash(data.email,COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET)
    try:
        cognito_response = cognito_client.forgot_password(
            ClientId=COGNITO_CLIENT_ID,
            Username=data.email,
            SecretHash=secret_hash
        )
        
        return {"message":"Password reset initiated. Check your email for the OTP."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/reset-password")
def reset_password(data: ResetPasswordRequest):
    secret_hash = get_secret_hash(data.email, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET)
    try:
        cognito_response = cognito_client.confirm_forgot_password(
            ClientId=COGNITO_CLIENT_ID,
            Username=data.email,
            ConfirmationCode=data.otp,
            Password=data.new_password,
            SecretHash=secret_hash
        )
        return {"message": "Password reset successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/refresh-token")
def refresh_token(data: RefreshTokenRequest):
    secret_hash = get_secret_hash(data.email,COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET)
    try:
        cognito_response = cognito_client.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={
                "REFRESH_TOKEN": data.refresh_token,
                "SECRET_HASH": secret_hash,
            }
        )
        return cognito_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    