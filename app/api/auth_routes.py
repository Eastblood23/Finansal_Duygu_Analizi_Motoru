from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from datetime import timedelta
from pydantic import BaseModel, SecretStr, EmailStr, Field
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Bound CPU bursts independently of the default network I/O thread pool.
password_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="password")

from app.database import get_db
from app.models import User
from app.limiter import limiter, authenticated_user_key
from app.services.registration_service import begin_registration, consume_registration, require_sender
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user, credential_stamp, ACCESS_TOKEN_EXPIRE_MINUTES

class PrivateValidationRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError as error:
                # Pydantic errors can include submitted passwords in their input field.
                return JSONResponse(status_code=422, content={"detail": [
                    {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
                    for item in error.errors()]})
        return safe_handler


router = APIRouter(route_class=PrivateValidationRoute)

class UserCreate(BaseModel):
    email: EmailStr
    password: SecretStr
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)

class RegistrationChallenge(BaseModel):
    challenge_id: str
    expires_in: int

class EmailVerification(BaseModel):
    challenge_id: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    code: str = Field(pattern=r"^[0-9]{6}$")

class Token(BaseModel):
    access_token: str
    token_type: str
    email: str
    first_name: str = None
    last_name: str = None

class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str = None
    last_name: str = None

class PasswordChange(BaseModel):
    current_password: SecretStr
    new_password: SecretStr

@router.post("/register", response_model=RegistrationChallenge, status_code=202)
@limiter.limit("5/hour;2/minute")
async def register(request: Request, user: UserCreate, db: AsyncSession = Depends(get_db)):
    require_sender()
    password = user.password.get_secret_value()
    if not 15 <= len(password) <= 128:
        raise HTTPException(400, "Şifre 15–128 karakter olmalı.")
    email = str(user.email).lower()
    result = await db.execute(select(User).where(func.lower(User.email) == email).limit(1))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Bu e-posta adresi zaten kayıtlı.")
        
    hashed_password = await asyncio.get_running_loop().run_in_executor(password_pool, get_password_hash, password)
    return await begin_registration(dict(email=email, hashed_password=hashed_password,
                                         first_name=user.first_name, last_name=user.last_name))


@router.post("/verify-email", response_model=Token)
@limiter.limit("10/minute;50/hour")
async def verify_email(request: Request, verification: EmailVerification, db: AsyncSession = Depends(get_db)):
    pending = await consume_registration(verification.challenge_id, verification.code)
    new_user = User(**pending)
    db.add(new_user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Bu e-posta zaten kayıtlı. Giriş yapabilirsiniz.") from None
    await db.refresh(new_user)
    return token_for(new_user)


def token_for(user):
    access_token = create_access_token(
        data={"sub": user.email, "credential_stamp": credential_stamp(user.hashed_password)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": access_token, "token_type": "bearer", "email": user.email,
            "first_name": user.first_name, "last_name": user.last_name}

@router.post("/login", response_model=Token)
@limiter.limit("10/minute;100/hour")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(func.lower(User.email) == form_data.username.strip().lower()).limit(1))
    user = result.scalar_one_or_none()
    
    if not user or not await asyncio.get_running_loop().run_in_executor(password_pool, verify_password, form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return token_for(user)

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password", status_code=204)
@limiter.limit("5/minute;20/hour", key_func=authenticated_user_key)
async def change_password(
    request: Request,
    passwords: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    old_hash = current_user.hashed_password
    current_password = passwords.current_password.get_secret_value()
    new_password = passwords.new_password.get_secret_value()
    if not 1 <= len(current_password) <= 1024 or not 15 <= len(new_password) <= 128:
        raise HTTPException(status_code=400, detail="Yeni şifre 15–128 karakter olmalı.")
    loop = asyncio.get_running_loop()
    if not await loop.run_in_executor(password_pool, verify_password, current_password, old_hash):
        raise HTTPException(status_code=400, detail="Mevcut şifre hatalı.")
    if current_password == new_password:
        raise HTTPException(status_code=400, detail="Yeni şifre mevcut şifreden farklı olmalı.")
    new_hash = await loop.run_in_executor(password_pool, get_password_hash, new_password)
    # Compare-and-swap prevents concurrent requests from overwriting a newer password.
    result = await db.execute(
        update(User).where(User.id == current_user.id, User.hashed_password == old_hash)
        .values(hashed_password=new_hash).execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Hesap bilgileri değişti. Yeniden giriş yapın.")
    await db.commit()
    return Response(status_code=204)
