from typing import Optional
from fastapi import Header, HTTPException, status
from app.config import settings


async def verify_api_key(
    x_depoii_key: Optional[str] = Header(
        None,
        alias="X-Depoii-Key",
        description="Secret API key for Depoii internal calls"
    )
) -> str:
    """
    Enforces secret header authentication across internal service calls.
    Returns 401 Unauthorized if missing or incorrect.
    """
    if not x_depoii_key or x_depoii_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Depoii-Key header credentials",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_depoii_key
