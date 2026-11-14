"""Autenticación con el JWT de Supabase y acceso de administrador."""
import hmac
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .supabase import anon_client

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    email: str | None
    token: str


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token")
    try:
        res = anon_client().auth.get_user(creds.credentials)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o caducado")
    if not res or not res.user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o caducado")
    return CurrentUser(id=res.user.id, email=res.user.email, token=creds.credentials)


def require_admin(
    x_admin_key: str | None = Header(default=None),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    s = get_settings()
    if x_admin_key and s.admin_api_key and hmac.compare_digest(x_admin_key, s.admin_api_key):
        return "admin-key"
    if creds is not None and s.admin_email_set:
        user = get_current_user(creds)
        if (user.email or "").lower() in s.admin_email_set:
            return user.email or user.id
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo administradores")
