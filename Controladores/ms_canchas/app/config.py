"""
Configuración del microservicio ms_canchas cargada mediante Pydantic Settings.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Parámetros de conexión y metadatos para ms_canchas."""

    DATABASE_URL: str = "postgresql+asyncpg://canchas_user:canchas_pass@localhost:5432/canchas_db"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # Nombre del Topic Exchange compartido entre todos los microservicios
    EXCHANGE_NAME: str = "canchas_events"

    # Metadatos del microservicio
    SERVICE_NAME: str = "ms_canchas"
    SERVICE_VERSION: str = "1.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
