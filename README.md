# 🏟️ Plataforma de Gestión y Reserva de Canchas Deportivas – Popayán
### Proyecto de Tesis – Arquitectura de Microservicios EDA + CQRS + Saga Pattern

---

## 🏗️ Arquitectura General

```
Internet
   │
   ▼
[api_gateway :8000]  ◄── frontend_net ──► [frontend_app]
   │
   └── backend_net ──────────────────────────────────────────────────────────┐
        │                                                                     │
        ├── [ms_usuarios :8001] ──► [db_usuarios :5432]                      │
        ├── [ms_canchas  :8002] ──► [db_canchas  :5432]                      │
        ├── [ms_reservas :8003] ──► [db_reservas :5432]                      │
        ├── [ms_pagos    :8004] ──► [db_pagos    :5432]                      │
        ├── [ms_notificaciones :8005]                                         │
        └── [rabbitmq    :5672 / 15672] ◄────────────────────────────────────┘
```

## 🚀 Levantar el Sistema

```bash
docker-compose up --build
```

### Verificar servicios:
| Servicio | URL |
|---|---|
| API Gateway | http://localhost:8000 |
| API Gateway Docs | http://localhost:8000/docs |
| RabbitMQ Management | http://localhost:15672 (admin/admin) |

## 📋 Historias de Usuario Implementadas

| HU | Servicio | Descripción |
|---|---|---|
| HU-01 | ms_usuarios | Registro de deportista |
| HU-02 | ms_usuarios | Solicitud recuperación de contraseña |
| HU-03 | ms_usuarios | Login deportista (JWT) |
| HU-04 | ms_usuarios | Ver/editar perfil propio |
| HU-05 | ms_canchas | Consultar catálogo y disponibilidad |
| HU-06 | ms_reservas | Solicitar reserva web |
| HU-07 | ms_reservas | Historial de reservas propias |
| HU-08 | ms_reservas | Cancelar reserva propia |
| HU-09 | ms_reservas | Reprogramar reserva |
| HU-10 | ms_pagos | Procesar pago en línea (Mock) |
| HU-11 | ms_usuarios | Registro administrador |
| HU-12 | ms_usuarios | Login administrador (JWT) |
| HU-13 | ms_usuarios | Recuperación contraseña admin |
| HU-14 | ms_canchas | Consultar canchas propias (Admin) |
| HU-15 | ms_canchas | Editar canchas propias (Admin) |
| HU-16 | ms_reservas | Registrar reserva presencial (Admin) |
| HU-17 | ms_reservas | Cancelar reserva como admin |
| HU-18 | ms_reservas | Reprogramar reserva como admin |
| HU-19 | ms_pagos | Consultar pagos por complejo (Admin) |
| HU-20 | ms_pagos | Registrar pago presencial (Admin) |

## 🔄 Flujo Saga: Reserva Online con Pago

```
Usuario → POST /reservas
    ms_reservas: estado=PENDIENTE_PAGO
    outbox → RabbitMQ: "ReservaSolicitada"
        └─► ms_canchas: bloque → BLOQUEADO_TEMPORAL
        └─► ms_notificaciones: email "Reserva Recibida"

Usuario → POST /pagos/procesar (simular_resultado="APROBADO")
    ms_pagos: Pago guardado, estado=APROBADO
    RabbitMQ: "PagoAprobado"
        └─► ms_reservas (saga): estado → CONFIRMADA
        └─► ms_canchas: bloque → OCUPADO
        └─► ms_notificaciones: email "¡Pago Confirmado!"

# ROLLBACK si pago es rechazado:
    ms_pagos → "PagoRechazado"
        └─► ms_reservas (saga): estado → CANCELADA → "ReservaCancelada"
        └─► ms_canchas: bloque → LIBRE (compensación)
        └─► ms_notificaciones: email "Pago No Procesado"
```

## 🔑 Autenticación JWT

Todos los endpoints protegidos requieren:
```
Authorization: Bearer <token>
```

El API Gateway valida el token y agrega headers internos:
- `X-User-Id`: UUID del usuario
- `X-User-Rol`: `USUARIO` o `ADMIN_ESTABLECIMIENTO`
- `X-Establecimiento-Id`: UUID del complejo (solo admins)

## 📨 Exchange RabbitMQ

- **Exchange**: `canchas_events` (topic)
- **Routing Keys**:
  - `reserva.solicitada`
  - `reserva.cancelada`
  - `reserva.reprogramada`
  - `pago.aprobado`
  - `pago.rechazado`
  - `pago.presencial.validado`
  - `clave.restablecimiento.solicitada`
  - `cancha.actualizada`

### Esquema de sobre (envelope):
```json
{
  "eventId": "uuid-v4",
  "eventType": "ReservaSolicitada",
  "aggregateId": "uuid-de-la-reserva",
  "timestamp": "2026-11-06T14:30:00-05:00",
  "version": "1.0",
  "data": { "...campos específicos del evento..." }
}
```

## 🧪 Prueba del Saga Rollback (en vivo)

```bash
# 1. Registrar usuario
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Juan Pérez","email":"juan@test.com","password":"123456","telefono":"3001234567"}'

# 2. Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"juan@test.com","password":"123456"}'
# Guardar el token

# 3. Ver canchas disponibles
curl http://localhost:8000/canchas/complejos

# 4. Crear reserva
curl -X POST http://localhost:8000/reservas \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"cancha_id":"<uuid>","complejo_id":"<uuid>","fecha":"2026-11-20","hora_inicio":"10:00","hora_fin":"11:00","monto":70000}'

# 5a. Pago APROBADO (flujo feliz)
curl -X POST http://localhost:8000/pagos/procesar \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"reserva_id":"<uuid>","usuario_id":"<uuid>","complejo_id":"<uuid>","monto":70000,"metodo":"TARJETA","simular_resultado":"APROBADO"}'

# 5b. Pago RECHAZADO (prueba Saga Rollback)
# -d '{ ..., "simular_resultado":"RECHAZADO"}'

# 6. Ver logs de notificaciones (para sustentación)
curl http://localhost:8000/notificaciones/logs
```

## 🏟️ Datos Piloto (Seed Data)

Al arrancar `ms_canchas`, se crean automáticamente si la BD está vacía:

| Complejo | Cancha | Tipo | Tarifa/hora |
|---|---|---|---|
| Balón de Oro (Barrio San José) | Cancha 1 | Fútbol 5 | $70.000 COP |
| Balón de Oro (Barrio San José) | Cancha 2 | Fútbol 7 | $90.000 COP |
| Balón de Oro (Barrio San José) | Cancha 3 | Fútbol 8 | $120.000 COP |
| Bernabéu (Julumito) | Cancha A | Fútbol 5 | $65.000 COP |
| Bernabéu (Julumito) | Cancha B | Fútbol 7 | $85.000 COP |
| Bernabéu (Julumito) | Cancha C | Fútbol 8 | $110.000 COP |

## 📁 Estructura del Proyecto (Arquitectura MVC + Microservicios EDA)

La solución desacopla estrictamente **Modelos**, **Vistas** y **Controladores** bajo los estándares de ingeniería de software requeridos para la sustentación:

```
canchas-popayan-eda/
├── docker-compose.yml
├── README.md
├── docs/
│   └── MODELO_C4.md                   # Especificación técnica y diagramas C4 (Nivel 1 al 4)
├── Controladores/                     # 🎮 Capa de Controladores unificada en la raíz (MVC)
│   ├── api_gateway/ (gateway_controller.py)
│   ├── ms_usuarios/ (auth_controller.py, usuarios_controller.py)
│   ├── ms_canchas/ (canchas_controller.py, admin_controller.py)
│   ├── ms_reservas/ (reservas_controller.py, admin_reservas_controller.py)
│   ├── ms_pagos/ (pagos_controller.py)
│   └── ms_notificaciones/ (notificaciones_controller.py)
├── Modelos/                           # 🏛️ Capa de Modelos y Entidades de Dominio en la raíz (MVC)
│   ├── ms_usuarios/ (Usuario, TokenRecuperacion)
│   ├── ms_canchas/ (Complejo, Cancha, BloqueHorario, BloqueoMantenimiento)
│   ├── ms_reservas/ (Reserva, OutboxEvent, ContadorReservas)
│   ├── ms_pagos/ (Pago, Transaccion)
│   └── ms_notificaciones/ (EmailLog)
├── Vista/                             # 🖥️ Capa de Vistas del Frontend en la raíz (MVC)
│   ├── Dockerfile, nginx.conf, package.json
│   └── src/                           # Componentes, vistas y lógica cliente
│       ├── VistaLanding.tsx           # Portal de bienvenida y catálogo público
│       ├── VistaCancha.tsx            # Catálogo, disponibilidad y selección de horarios
│       ├── VistaReserva.tsx           # Gestión de reservas del usuario y reprogramación
│       ├── VistaPerfil.tsx            # Perfil y credenciales de usuario
│       ├── VistaReportes.tsx          # Monitor de eventos EDA en tiempo real
│       ├── VistaLogin.tsx             # Inicio de sesión con autenticación JWT
│       ├── VistaRegistro.tsx          # Registro de deportistas y administradores
│       ├── VistaRecuperarPassword.tsx # Recuperación y restablecimiento de contraseña
│       ├── admin/                     # Vistas del portal administrativo de establecimientos
│       │   ├── VistaAdminLayout.tsx
│       │   ├── VistaAdminCanchas.tsx
│       │   ├── VistaAdminTaquilla.tsx
│       │   ├── VistaAdminPagos.tsx
│       │   └── VistaAdminApariencia.tsx
│       ├── components/                # Componentes reutilizables de UI (Átomos/Moléculas)
│       ├── hooks/                     # Controladores de estado React
│       ├── lib/                       # Capa de API y tipos de datos
│       └── App.tsx                    # Enrutador principal de la aplicación SPA
└── tests/                             # Suite de pruebas unitarias y de integración (Pytest)
```

## 📐 Especificación y Modelo C4

La documentación formal de arquitectura en formato C4 (Diagramas de Contexto, Contenedores, Componentes y Código) se encuentra detallada en:
👉 [`docs/MODELO_C4.md`](docs/MODELO_C4.md)

