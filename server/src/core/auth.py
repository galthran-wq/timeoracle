from datetime import datetime, timedelta
from typing import Optional, Union, Tuple
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from uuid import UUID
from jose import JWTError, jwt

from src.core.database import get_postgres_session
from src.models.postgres import UserModel
from src.repositories.users import UserRepository
from src.core.config import settings

security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def create_token_for_user(user: UserModel) -> str:
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "is_verified": user.is_verified,
        "is_superuser": user.is_superuser
    }
    return create_access_token(token_data)


def decode_jwt_token(token: str) -> Tuple[bool, Optional[UUID], Optional[str]]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id_str: str = payload.get("sub")
        
        if user_id_str is None:
            return False, None, "Could not validate credentials"
        
        user_id = UUID(user_id_str)
        return True, user_id, None
        
    except JWTError:
        return False, None, "Could not validate credentials"
    except ValueError:
        return False, None, "Could not validate credentials"


async def validate_user_from_token(token: str, postgres_session: AsyncSession) -> Tuple[bool, Optional[UserModel], Optional[str]]:
    success, user_id, error = decode_jwt_token(token)
    if not success:
        return False, None, error
    
    user_repo = UserRepository(postgres_session)
    user = await user_repo.get_user(user_id)
    
    if user is None:
        return False, None, "Could not validate credentials"
    
    return True, user, None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    postgres_session: AsyncSession = Depends(get_postgres_session)
) -> UserModel:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    success, user, error = await validate_user_from_token(credentials.credentials, postgres_session)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_id(
    user: UserModel = Depends(get_current_user)
) -> UUID:
    return user.id


async def get_current_superuser(
    current_user: UserModel = Depends(get_current_user)
) -> UserModel:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Superuser access required."
        )
    return current_user 