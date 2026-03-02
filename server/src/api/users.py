from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_postgres_session
from src.repositories.users import UserRepository
from src.schemas.users import (
    UserResponse, UserRegisterRequest, UserLoginRequest, TokenResponse,
    CreateUserRequest, CreateUserResponse,
    DeleteUserRequest, DeleteUserResponse,
    SessionConfig, SessionConfigUpdate,
)
from src.core.auth import (
    get_password_hash, verify_password, create_token_for_user, get_current_user, get_current_superuser
)
from src.models.postgres.users import UserModel


router = APIRouter(prefix="/api/users", tags=["users"])


def get_user_repository(
    postgres_session: AsyncSession = Depends(get_postgres_session)
) -> UserRepository:
    return UserRepository(postgres_session)


@router.post("/", response_model=TokenResponse)
async def create_user(
    user_repo: UserRepository = Depends(get_user_repository)
):
    try:
        user = await user_repo.create_user()
        token = create_token_for_user(user)
        
        return TokenResponse(
            access_token=token,
            user=UserResponse.model_validate(user)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register", response_model=TokenResponse)
async def register_user(
    request: UserRegisterRequest,
    current_user: UserModel = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository)
):
    try:
        password_hash = get_password_hash(request.password)
        
        registered_user = await user_repo.register_user(
            current_user.id, 
            request.email, 
            password_hash
        )
        
        token = create_token_for_user(registered_user)
        
        return TokenResponse(
            access_token=token,
            user=UserResponse.model_validate(registered_user)
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login_user(
    request: UserLoginRequest,
    user_repo: UserRepository = Depends(get_user_repository)
):
    try:
        user = await user_repo.get_user_by_email(request.email)
        
        if not user or not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        token = create_token_for_user(user)
        
        return TokenResponse(
            access_token=token,
            user=UserResponse.model_validate(user)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserModel = Depends(get_current_user)
):
    return UserResponse.model_validate(current_user)


@router.get("/me/session-config", response_model=SessionConfig)
async def get_session_config(
    current_user: UserModel = Depends(get_current_user),
):
    if current_user.session_config:
        return SessionConfig(**current_user.session_config)
    return SessionConfig()


@router.patch("/me/session-config", response_model=SessionConfig)
async def update_session_config(
    body: SessionConfigUpdate,
    current_user: UserModel = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository),
):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        existing = current_user.session_config or {}
        return SessionConfig(**existing)
    user = await user_repo.update_session_config(current_user.id, updates)
    return SessionConfig(**user.session_config)


@router.post("/create-user", response_model=CreateUserResponse)
async def create_user_by_superuser(
    request: CreateUserRequest,
    current_superuser: UserModel = Depends(get_current_superuser),
    user_repo: UserRepository = Depends(get_user_repository)
):
    try:
        if len(request.password) < 6:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 6 characters long"
            )
        
        password_hash = get_password_hash(request.password)
        
        created_user = await user_repo.create_registered_user(
            request.email,
            password_hash
        )
        
        return CreateUserResponse(
            success=True,
            message=f"Successfully created user {created_user.email}",
            user=UserResponse.model_validate(created_user)
        )
        
    except ValueError as e:
        return CreateUserResponse(
            success=False,
            message=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete-user", response_model=DeleteUserResponse)
async def delete_user_by_superuser(
    request: DeleteUserRequest,
    current_superuser: UserModel = Depends(get_current_superuser),
    user_repo: UserRepository = Depends(get_user_repository)
):
    try:
        deleted_user = await user_repo.delete_user(
            request.user_identifier,
            current_superuser.id
        )
        
        return DeleteUserResponse(
            success=True,
            message=f"Successfully deleted user {deleted_user.email or deleted_user.id}"
        )
        
    except ValueError as e:
        return DeleteUserResponse(
            success=False,
            message=str(e)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 