from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url:str
    supabase_service_key:str

    jwt_secret:str
    jwt_algorithm:str ='HS256'
    jwt_expire_minutes:int = 480

    class Config:
        env_file = ".env"

settings = Settings()

