from fastapi import HTTPException
from app.database import supabase
from app.core.security import verify_password, create_acces_token

def autenticar_usuario(nombre_usuario:str, password:str)-> dict:
    resultado = supabase.table('usuarios').select('*').eq('nombre_usuario',nombre_usuario).execute()

    if not resultado.data:
        raise HTTPException(status_code=401, detail='Usuario o contraseña incorrectos')

    usuario = resultado.data[0]

    if not usuario['activo']:
        raise HTTPException(status_code=403, detail='Usuario inactivo')

    if not verify_password(password, usuario['password_hash']):
        raise HTTPException(status_code=401, detail='Usuario o contraseña incorrectos')

    acces_token = create_acces_token({
        'sub': usuario['id'],
        'rol': usuario['rol'],
    })

    return {'access_token': acces_token, 'token_type': 'bearer'}
