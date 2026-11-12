from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import timedelta
from pydantic import BaseModel, SecretStr
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Bound CPU bursts independently of the default network I/O thread pool.
password_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="password")

from app.database import get_db
from app.models import User
from app.limiter import limiter, authenticated_user_key
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user, credential_stamp, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()

class UserCreate(BaseModel):
    email: str
    password: str
    first_name: str = None
    last_name: str = None

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

@router.post("/register", response_model=UserResponse)
@limiter.limit("5/hour")
async def register(request: Request, user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Bu e-posta adresi zaten kayıtlı.")
        
    hashed_password = await asyncio.get_running_loop().run_in_executor(password_pool, get_password_hash, user.password)
    new_user = User(email=user.email, hashed_password=hashed_password, first_name=user.first_name, last_name=user.last_name)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
@limiter.limit("10/minute;100/hour")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not await asyncio.get_running_loop().run_in_executor(password_pool, verify_password, form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "credential_stamp": credential_stamp(user.hashed_password)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "email": user.email, "first_name": user.first_name, "last_name": user.last_name}

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
