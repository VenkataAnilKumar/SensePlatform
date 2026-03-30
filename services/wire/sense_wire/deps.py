"""
Sense Wire — FastAPI Dependencies
JWT auth reuses Sense Gate's token format.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status
from jose import JWTError
from jose import jwt

from sense_wire.config import get_settings
from sense_wire.database import get_db

settings = get_settings()


def _decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """Validate a Sense Gate JWT from the Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT required")
    token = authorization.removeprefix("Bearer ").strip()
    return _decode_jwt(token)


async def get_ws_user(token: str = Query(..., description="Sense Gate JWT")) -> dict:
    """Validate a Sense Gate JWT passed as a query param for WebSocket connections."""
    return _decode_jwt(token)


UserDep = Annotated[dict, Depends(get_current_user)]
DBDep = Annotated[object, Depends(get_db)]
