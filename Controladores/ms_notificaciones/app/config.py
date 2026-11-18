"""
Configuración del microservicio ms_notificaciones cargada mediante Pydantic Settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parámetros de conexión a RabbitMQ, servidor SMTP y almacenamiento SQLite."""

    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"

    # Configuración de servidor SMTP (ej. contraseña de aplicación Gmail)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "Canchas Popayan"
    SMTP_FROM_EMAIL: str = ""

    # Resiliencia de envío SMTP y simulación local
    SMTP_DEV_MODE: str = "auto"
    SMTP_TIMEOUT: int = 5
    SMTP_MAX_RETRIES: int = 2
    SMTP_RETRY_BACKOFF_SECONDS: float = 1.0

    # Ruta de persistencia de base de datos SQLite
    NOTIF_DB_PATH: str = "/app/data/notificaciones.db"

    # URLs de microservicios internos para enriquecimiento de datos
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
