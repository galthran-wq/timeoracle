import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.prompts import DEFAULT_CATEGORIES
from src.core.auth import get_current_user
from src.core.database import get_postgres_session
from src.models.postgres.users import UserModel
from src.repositories.agent_memories import AgentMemoryRepository
from src.schemas.agent_memories import (
    AgentMemoryCreate,
    AgentMemoryListResponse,
    AgentMemoryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/memories", response_model=AgentMemoryListResponse)
async def list_memories(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_postgres_session),
):
    repo = AgentMemoryRepository(session)
    memories = await repo.get_active_for_user(current_user.id, limit=limit)
    total = await repo.count_for_user(current_user.id)
    return AgentMemoryListResponse(
        memories=[AgentMemoryResponse.model_validate(m) for m in memories],
        total_count=total,
    )


@router.post("/memories", response_model=AgentMemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    body: AgentMemoryCreate,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_postgres_session),
):
    repo = AgentMemoryRepository(session)
    try:
        memory = await repo.create(
            user_id=current_user.id,
            content=body.content,
            source="manual",
        )
        return AgentMemoryResponse.model_validate(memory)
    except Exception:
        logger.exception("Failed to create memory for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: UUID,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_postgres_session),
):
    repo = AgentMemoryRepository(session)
    deleted = await repo.delete(memory_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")


@router.get("/default-categories")
async def get_default_categories(
    current_user: UserModel = Depends(get_current_user),
):
    return DEFAULT_CATEGORIES
