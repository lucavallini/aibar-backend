from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.models.token import Token
from app.services.auth_service import autenticar_usuario

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Token)


def login(form_data: OAuth2PasswordRequestForm = Depends()):
    return autenticar_usuario(form_data.username, form_data.password)