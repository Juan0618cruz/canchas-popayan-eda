"""
Módulo de configuración del API Gateway.
Carga variables de entorno mediante Pydantic Settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración centralizada cargada desde variables de entorno.
    Las URLs de microservicios y el secreto JWT son configurables en tiempo de ejecución.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Configuración de JWT
    jwt_secret: str = "super-secret-jwt-key-change-in-production"
    jwt_algorithm: str = "HS256"

    # Direcciones URL de microservicios downstream
    ms_usuarios_url: str = "http://ms_usuarios:8001"
    ms_canchas_url: str = "http://ms_canchas:8002"
    ms_reservas_url: str = "http://ms_reservas:8003"
    ms_pagos_url: str = "http://ms_pagos:8004"
    ms_notificaciones_url: str = "http://ms_notificaciones:8005"

    # Parámetros del cliente HTTP
    http_timeout: float = 30.0
    http_max_connections: int = 100
    http_max_keepalive_connections: int = 20


# Instancia única de configuración
settings = Settings()
