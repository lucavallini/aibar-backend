from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from app.models.token import Token
from app.services.auth_service import autenticar_usuario
from app.core.rate_limit import verificar_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    clave = request.client.host if request.client else "desconocido"
    verificar_rate_limit(clave)
    return autenticar_usuario(form_data.username, form_data.password)
