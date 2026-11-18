"""
Módulo de configuración para ms_pagos.
Carga variables de entorno mediante Pydantic Settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parámetros de conexión, pasarela Wompi y servicios downstream."""

    # Conexión asíncrona a PostgreSQL (driver asyncpg)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ms_pagos"

    # URL de conexión a RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"

    # Configuración de la Pasarela Wompi Colombia
    WOMPI_PUBLIC_KEY: str = ""
    WOMPI_EVENTS_SECRET: str = ""
    WOMPI_INTEGRITY_SECRET: str = ""
    WOMPI_SANDBOX: bool = True

    # Direcciones de microservicios internos en la red Docker
    MS_USUARIOS_URL: str = "http://ms_usuarios:8001"
    MS_RESERVAS_URL: str = "http://ms_reservas:8003"
    MS_CANCHAS_URL: str = "http://ms_canchas:8002"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
