from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routers import usuarios, auth, camiones, choferes, auditoria, viajes, multas, combustible, empresas, acoplados, observaciones, telemetria
from app.core.exceptions import NotFoundError, BadRequestError, ConflictError, ForbiddenError, UnauthorizedError, InternalError, TooManyRequestsError
from app.core.logging import configurar_logging, logger

configurar_logging()

app = FastAPI(title="AIBAR SRL - API")

@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": exc.detail})

@app.exception_handler(BadRequestError)
async def bad_request_handler(request: Request, exc: BadRequestError):
    return JSONResponse(status_code=400, content={"detail": exc.detail})

@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError):
    return JSONResponse(status_code=409, content={"detail": exc.detail})

@app.exception_handler(ForbiddenError)
async def forbidden_handler(request: Request, exc: ForbiddenError):
    return JSONResponse(status_code=403, content={"detail": exc.detail})

@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(request: Request, exc: UnauthorizedError):
    return JSONResponse(status_code=401, content={"detail": exc.detail})

@app.exception_handler(TooManyRequestsError)
async def too_many_requests_handler(request: Request, exc: TooManyRequestsError):
    return JSONResponse(status_code=429, content={"detail": exc.detail})

@app.exception_handler(InternalError)
async def internal_handler(request: Request, exc: InternalError):
    logger.error("Error interno en %s %s: %s", request.method, request.url.path, exc.detail, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": exc.detail})

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Excepción no controlada en %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200",
                   "https://aibarsrl.netlify.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(usuarios.router)
app.include_router(auth.router)
app.include_router(camiones.router)
app.include_router(choferes.router)
app.include_router(auditoria.router)
app.include_router(viajes.router)
app.include_router(multas.router)
app.include_router(combustible.router)
app.include_router(empresas.router)
app.include_router(acoplados.router)
app.include_router(observaciones.router)
app.include_router(telemetria.router)


@app.get("/")
def health_check():
    return {"status": "ok", "mensaje": "AIBAR API funcionando"}