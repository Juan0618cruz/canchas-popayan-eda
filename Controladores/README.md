# 🎮 Capa de Controladores (Controller Layer) — Canchas Popayán EDA

Esta carpeta física en la raíz del proyecto consolida y aloja todos los **Microservicios y Controladores** del backend bajo el patrón arquitectónico **Modelo Vista Controlador (MVC)**:

## 📂 Organización de Microservicios y Controladores

| Microservicio | Controlador Principal | Ubicación Interna | Responsabilidad |
|---|---|---|---|
| **api_gateway** | `GatewayController` | [`api_gateway/app/gateway_controller.py`](./api_gateway/app/gateway_controller.py) | Reverse proxy asíncrono, clasificación de rutas públicas/admin, decodificación JWT. |
| **ms_usuarios** | `AuthController`, `UsuariosController` | [`ms_usuarios/app/auth_controller.py`](./ms_usuarios/app/auth_controller.py) | Autenticación, registro de usuarios/administradores, emisión de JWT y perfil. |
| **ms_canchas** | `CanchasController`, `AdminCanchasController` | [`ms_canchas/app/canchas_controller.py`](./ms_canchas/app/canchas_controller.py) | Disponibilidad, cálculo de franjas horarias y administración de canchas. |
| **ms_reservas** | `ReservasController`, `AdminReservasController` | [`ms_reservas/app/reservas_controller.py`](./ms_reservas/app/reservas_controller.py) | Reserva pesimista, cancelación, taquilla presencial y Transactional Outbox. |
| **ms_pagos** | `PagosController` | [`ms_pagos/app/pagos_controller.py`](./ms_pagos/app/pagos_controller.py) | Integración Wompi Colombia (firma HMAC SHA-256), webhooks y eventos Saga. |
| **ms_notificaciones** | `NotificacionesController` | [`ms_notificaciones/app/notificaciones_controller.py`](./ms_notificaciones/app/notificaciones_controller.py) | Bitácora de correos despachados y estadísticas de despacho SMTP. |
