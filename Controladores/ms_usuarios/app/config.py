"""
Configuración del microservicio ms_usuarios cargada desde variables de entorno.
Utiliza pydantic-settings para validación de tipos y carga desde archivo .env.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración central para ms_usuarios."""

    # Base de datos PostgreSQL
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/canchas_usuarios"
    )

    # Conexión a RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # Seguridad JWT
    JWT_SECRET: str = "super-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # Metadatos del microservicio
    APP_NAME: str = "ms_usuarios"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
