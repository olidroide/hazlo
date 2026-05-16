from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from hazlo.infrastructure.db.session import get_session


def get_db(session: AsyncSession = Depends(get_session)) -> AsyncSession:
    return session
