from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url:str
    supabase_service_key:str

    jwt_secret:str
    jwt_algorithm:str ='HS256'
    jwt_expire_minutes:int = 480

    gc_base_url: str = "https://apigc.tcsa.com.ar"
    gc_client_id: str = ""
    gc_client_secret: str = ""

    class Config:
        env_file = ".env"

settings = Settings()

