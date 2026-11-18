# 🏛️ Capa de Modelos (Model Layer) — Canchas Popayán EDA

Esta carpeta física en la raíz del proyecto consolida y documenta todos los **Modelos de Datos y Entidades de Dominio** bajo el patrón arquitectónico **Modelo Vista Controlador (MVC)**:

## 📂 Organización por Microservicio

| Microservicio | Entidades de Dominio / Modelos ORM | Archivo Fuente |
|---|---|---|
| **ms_usuarios** | `Usuario`, `RolUsuario`, `TokenRecuperacion` | [`ms_usuarios/`](./ms_usuarios/) |
| **ms_canchas** | `Complejo`, `Cancha`, `TipoCancha`, `BloqueHorario`, `BloqueoMantenimiento` | [`ms_canchas/`](./ms_canchas/) |
| **ms_reservas** | `Reserva`, `EstadoReserva`, `OutboxEvent`, `ContadorReservas` | [`ms_reservas/`](./ms_reservas/) |
| **ms_pagos** | `Pago`, `EstadoPago`, `MetodoPago`, `Transaccion` | [`ms_pagos/`](./ms_pagos/) |
| **ms_notificaciones** | `EmailLog` (persistencia SQLite) | [`ms_notificaciones/`](./ms_notificaciones/) |
