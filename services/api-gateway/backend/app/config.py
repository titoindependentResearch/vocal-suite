from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    PROJECT_NAME: str = "VocalSuite API Gateway"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # URL del servicio de conversión a PDF (Gotenberg)
    GOTENBERG_URL: str = "http://localhost:3000"

    class Config:
        case_sensitive = True
        env_file = ".env"

# Instancia global exportada para toda la aplicación
settings = Settings()
