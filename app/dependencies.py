from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from app.database import supabase
from app.core.security import decode_access_token
from app.models.usuario import UsuarioOut

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)) -> UsuarioOut:
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token no válido o expirado")

    usuario_id = payload.get("sub")
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Token no válido")

    resultado = supabase.table('usuarios').select('*').eq('id', usuario_id).execute()

    if not resultado.data:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    usuario = resultado.data[0]

    if not usuario['activo']:
        raise HTTPException(status_code=403, detail="Usuario deshabilitado")

    return UsuarioOut(**usuario)


def require_rol(*roles_permitidos:str):
    def verificar_rol(usuario: UsuarioOut = Depends(get_current_user)):
        if usuario.rol not in roles_permitidos:
            raise HTTPException(status_code=403, detail="No tienes permiso para acceder a este recurso")
        return usuario
    return verificar_rol