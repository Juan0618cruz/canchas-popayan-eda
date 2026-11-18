"""
Configuración del microservicio ms_reservas cargada mediante Pydantic Settings.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db_reservas:5432/reservas_db"
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    MS_USUARIOS_URL: str = "http://ms_usuarios:8001"

    # Metadatos del microservicio
    SERVICE_NAME: str = "ms_reservas"
    SERVICE_VERSION: str = "1.0.0"

    # Intervalo de sondeo del despachador Outbox en segundos
    OUTBOX_POLL_INTERVAL: int = 2

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = Settings()
