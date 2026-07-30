from app.database import supabase
from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.core.security import verify_password, create_access_token

def autenticar_usuario(nombre_usuario:str, password:str)-> dict:
    resultado = supabase.table('usuarios').select('*').eq('nombre_usuario',nombre_usuario).execute()

    if not resultado.data:
        raise UnauthorizedError('Usuario o contraseña incorrectos')

    usuario = resultado.data[0]

    if not usuario['activo']:
        raise ForbiddenError('Usuario inactivo')

    if not verify_password(password, usuario['password_hash']):
        raise UnauthorizedError('Usuario o contraseña incorrectos')

    access_token = create_access_token({
        'sub': usuario['id'],
        'rol': usuario['rol'],
    })

    return {'access_token': access_token, 'token_type': 'bearer'}
