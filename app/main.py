from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import usuarios, auth, camiones, choferes, auditoria, viajes, multas, combustible

app = FastAPI(title="AIBAR SRL - API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(usuarios.router)
app.include_router(auth.router)
app.include_router(camiones.router)
app.include_router(choferes.router)
app.include_router(auditoria.router)
app.include_router(viajes.router)
app.include_router(multas.router)
app.include_router(combustible.router)


@app.get("/")
def health_check():
    return {"status": "ok", "mensaje": "AIBAR API funcionando"}