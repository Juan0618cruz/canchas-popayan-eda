# 📐 Modelo C4 — Plataforma de Gestión y Reserva de Canchas Popayán
### Proyecto de Tesis: Arquitectura Dirigida por Eventos (EDA) + CQRS + Patrón Saga + MVC

Este documento describe la arquitectura técnica de la plataforma bajo el estándar **Modelo C4** (Contexto, Contenedores, Componentes y Código), incorporando la refactorización arquitectónica **Modelo-Vista-Controlador (MVC)** implementada en el backend y el frontend.

---

## 🧭 Nivel 1: Diagrama de Contexto del Sistema (System Context)

El diagrama de contexto describe los actores que interactúan con la plataforma y los sistemas externos integrados.

```mermaid
flowchart TD
    subgraph Actores["Actores del Sistema"]
        Deportista["🏃 Deportista / Usuario Web<br/>(Reserva canchas, consulta disponibilidad y paga en línea)"]
        AdminEstablecimiento["🏢 Administrador de Complejo<br/>(Gestiona taquilla presencial, tarifas, canchas y reportes)"]
    end

    subgraph SistemaPrincipal["Límite del Sistema"]
        PlataformaCanchas["🏟️ Plataforma Canchas Popayán EDA<br/>(Gestión de canchas, agendamiento concurrente, pasarela y notificaciones)"]
    end

    subgraph SistemasExternos["Sistemas Externos"]
        PasarelaWompi["💳 Pasarela Wompi Colombia<br/>(Procesamiento financiero: Nequi, PSE, Bancolombia, Tarjetas)"]
        ServidorSMTP["📧 Servidor SMTP / Gmail<br/>(Despacho de correos electrónicos transaccionales)"]
    end

    Deportista -->|"Consulta catálogo, agenda citas y paga"| PlataformaCanchas
    AdminEstablecimiento -->|"Administra canchas, taquilla presencial y caja"| PlataformaCanchas
    PlataformaCanchas -->|"Prepara firmas y recibe webhooks de pago"| PasarelaWompi
    PlataformaCanchas -->|"Envía notificaciones HTML en tiempo real"| ServidorSMTP
```

---

## 📦 Nivel 2: Diagrama de Contenedores (Container Diagram)

Muestra los contenedores lógicos que conforman la solución, sus responsabilidades de alto nivel y protocolos de comunicación.

```mermaid
flowchart TB
    Deportista["🏃 Deportista"]
    Admin["🏢 Administrador"]

    subgraph FronteraFrontend["Frontend Web (Nginx + React SPA :3000)"]
        FrontendApp["💻 Single Page Application (SPA)<br/>React 18 + TypeScript + Tailwind CSS<br/>(Vistas normalizadas MVC)"]
    end

    subgraph FronteraBackend["Plataforma Backend (FastAPI Microservices)"]
        ApiGateway["🚪 api_gateway (:8000)<br/>FastAPI + GatewayController<br/>Reverse Proxy, CORS, JWT Ingestion"]
        
        MsUsuarios["👤 ms_usuarios (:8001)<br/>Controladores: AuthController, UsuariosController<br/>Gestión de usuarios y credenciales"]
        MsCanchas["⚽ ms_canchas (:8002)<br/>Controladores: CanchasController, AdminCanchasController<br/>Catálogo, disponibilidad y slots"]
        MsReservas["📅 ms_reservas (:8003)<br/>Controladores: ReservasController, AdminReservasController<br/>Saga Orchestrator + Transactional Outbox"]
        MsPagos["💵 ms_pagos (:8004)<br/>Controladores: PagosController<br/>Transacciones Wompi y Caja Presencial"]
        MsNotif["🔔 ms_notificaciones (:8005)<br/>Controladores: NotificacionesController<br/>Consumidor EDA y Servicio SMTP"]
    end

    subgraph FronteraBroker["Event Broker (AMQP 0-9-1)"]
        RabbitMQ["🐇 RabbitMQ (Topic Exchange :5672)<br/>Exchange: canchas_events"]
    end

    subgraph FronteraPersistencia["Bases de Datos"]
        DbUsuarios[("🐘 PostgreSQL :5432<br/>db_usuarios")]
        DbCanchas[("🐘 PostgreSQL :5432<br/>db_canchas")]
        DbReservas[("🐘 PostgreSQL :5432<br/>db_reservas")]
        DbPagos[("🐘 PostgreSQL :5432<br/>db_pagos")]
        DbNotif[("💾 SQLite 3<br/>notificaciones.db")]
    end

    Deportista -->|"HTTPS / HTTP :3000"| FrontendApp
    Admin -->|"HTTPS / HTTP :3000"| FrontendApp

    FrontendApp -->|"REST / JSON :8000"| ApiGateway

    ApiGateway -->|"HTTP Proxy :8001"| MsUsuarios
    ApiGateway -->|"HTTP Proxy :8002"| MsCanchas
    ApiGateway -->|"HTTP Proxy :8003"| MsReservas
    ApiGateway -->|"HTTP Proxy :8004"| MsPagos
    ApiGateway -->|"HTTP Proxy :8005"| MsNotif

    MsUsuarios -->|"SQL / AsyncPG"| DbUsuarios
    MsCanchas -->|"SQL / AsyncPG"| DbCanchas
    MsReservas -->|"SQL / AsyncPG"| DbReservas
    MsPagos -->|"SQL / AsyncPG"| DbPagos
    MsNotif -->|"SQLite Driver"| DbNotif

    MsUsuarios -.->|"Eventos: Registro, Clave"| RabbitMQ
    MsCanchas <-.->|"Eventos: Bloqueos, Mantenimiento"| RabbitMQ
    MsReservas <-.->|"Eventos: Saga Reservas (Outbox)"| RabbitMQ
    MsPagos <-.->|"Eventos: PagoAprobado, PagoRechazado"| RabbitMQ
    RabbitMQ -.->|"Eventos consumidos"| MsNotif
```

---

## 🧩 Nivel 3: Diagrama de Componentes (Component Diagram)

Detalla la organización interna bajo el patrón **Modelo-Vista-Controlador (MVC)** tanto en el frontend como en los microservicios del backend.

### 3.1. Componentes del Frontend (Vistas y Controladores)

```mermaid
flowchart TD
    subgraph Vistas["Capa de Vistas (frontend/src/Vista/)"]
        VistaLanding["VistaLanding.tsx<br/>(Página principal pública)"]
        VistaCancha["VistaCancha.tsx<br/>(Catálogo y disponibilidad)"]
        VistaReserva["VistaReserva.tsx<br/>(Agenda y reservas del usuario)"]
        VistaPerfil["VistaPerfil.tsx / VistaUsuario.tsx<br/>(Gestión de cuenta)"]
        VistaReportes["VistaReportes.tsx / VistaAdmin.tsx<br/>(Métricas y bitácora EDA)"]
        subgraph VistasAdmin["Vistas Administrativas (Vista/admin/)"]
            VistaAdminLayout["VistaAdminLayout.tsx"]
            VistaAdminCanchas["VistaAdminCanchas.tsx"]
            VistaAdminTaquilla["VistaAdminTaquilla.tsx"]
            VistaAdminPagos["VistaAdminPagos.tsx"]
            VistaAdminApariencia["VistaAdminApariencia.tsx"]
        end
    end

    subgraph ControladoresFrontend["Capa Controladores / Hooks (frontend/src/hooks/)"]
        HookCatalogo["useCatalogoController.ts<br/>(Controlador de Catálogo y Slots)"]
        HookReservas["useMisReservasController.ts<br/>(Controlador de Cancelación y Reagendamiento)"]
        HookPerfil["usePerfilController.ts<br/>(Controlador de Datos de Usuario)"]
    end

    subgraph ModelosYServicios["Capa Modelo y Clientes API (frontend/src/lib/)"]
        ApiClient["api.ts (canchasApi, authApi, reservasApi, pagosApi)"]
        Tipos["types.ts (Interfaces DTO y Entidades)"]
    end

    VistaLanding --> HookCatalogo
    VistaCancha --> HookCatalogo
    VistaReserva --> HookReservas
    VistaPerfil --> HookPerfil
    VistasAdmin --> ApiClient

    HookCatalogo --> ApiClient
    HookReservas --> ApiClient
    HookPerfil --> ApiClient
    ApiClient --> Tipos
```

---

### 3.2. Componentes del Backend (Estructura MVC de Microservicios)

Cada microservicio desacopla estrictamente los enrutadores HTTP, los controladores de lógica de negocio, los modelos de base de datos y la mensajería asíncrona:

```mermaid
flowchart LR
    subgraph Enrutadores["Capa Routers (HTTP Adapters)"]
        R_Auth["routers/auth.py"]
        R_User["routers/usuarios.py"]
        R_Cancha["routers/canchas.py"]
        R_AdmCancha["routers/admin.py"]
        R_Res["routers/reservas.py"]
        R_AdmRes["routers/admin_reservas.py"]
        R_Pagos["routers/pagos.py"]
        R_Notif["routers/notificaciones.py"]
    end

    subgraph Controladores["Capa Controladores (Lógica de Negocio)"]
        C_Gateway["GatewayController"]
        C_Auth["AuthController"]
        C_User["UsuariosController"]
        C_Cancha["CanchasController"]
        C_AdmCancha["AdminCanchasController"]
        C_Res["ReservasController"]
        C_AdmRes["AdminReservasController"]
        C_Pagos["PagosController"]
        C_Notif["NotificacionesController"]
    end

    subgraph Modelos["Capa Modelos (Entities / DB)"]
        M_User["Usuario, TokenRecuperacion"]
        M_Cancha["Complejo, Cancha, BloqueHorario"]
        M_Res["Reserva, OutboxEvent, Contador"]
        M_Pagos["Pago, Transaccion"]
        M_Notif["EmailLog (SQLite)"]
    end

    subgraph Eventos["Capa Eventos (RabbitMQ Broker)"]
        OutboxPub["OutboxPublisher (ms_reservas)"]
        Consumidores["RabbitMQ Consumers (EDA Saga)"]
    end

    R_Auth --> C_Auth
    R_User --> C_User
    R_Cancha --> C_Cancha
    R_AdmCancha --> C_AdmCancha
    R_Res --> C_Res
    R_AdmRes --> C_AdmRes
    R_Pagos --> C_Pagos
    R_Notif --> C_Notif

    C_Auth --> M_User
    C_User --> M_User
    C_Cancha --> M_Cancha
    C_AdmCancha --> M_Cancha
    C_Res --> M_Res
    C_AdmRes --> M_Res
    C_Pagos --> M_Pagos
    C_Notif --> M_Notif

    C_Res --> OutboxPub
    OutboxPub --> Eventos
    C_Pagos --> Eventos
    Eventos --> Consumidores
```

---

## 🔍 Nivel 4: Diagrama de Código (Class & Code Level)

### Mapeo de Controladores Backend y Responsabilidades

| Microservicio | Controlador | Archivo | Responsabilidad Principal |
|---|---|---|---|
| **api_gateway** | `GatewayController` | `Controladores/api_gateway/app/gateway_controller.py` | Reverse proxy asíncrono, clasificación de rutas públicas/admin, decodificación JWT e inyección de encabezados de contexto. |
| **ms_usuarios** | `AuthController` | `Controladores/ms_usuarios/app/auth_controller.py` | Registro de usuarios/administradores, emisión de JWT, recuperación y cambio de contraseñas. |
| **ms_usuarios** | `UsuariosController` | `Controladores/ms_usuarios/app/usuarios_controller.py` | Consulta de perfil propio, actualización de datos personales y auditoría. |
| **ms_canchas** | `CanchasController` | `Controladores/ms_canchas/app/canchas_controller.py` | Consulta pública de complejos, cálculo dinámico de bloques horarios y disponibilidad. |
| **ms_canchas** | `AdminCanchasController` | `Controladores/ms_canchas/app/admin_controller.py` | Administración de complejos, creación/edición de canchas, bloqueos por mantenimiento y carga de banners. |
| **ms_reservas** | `ReservasController` | `Controladores/ms_reservas/app/reservas_controller.py` | Solicitud de reservas con bloqueo pesimista en PostgreSQL, cancelación, reprogramación y escritura en tabla Outbox. |
| **ms_reservas** | `AdminReservasController` | `Controladores/ms_reservas/app/admin_reservas_controller.py` | Taquilla presencial, gestión de agenda integral por complejo y confirmación en sitio. |
| **ms_pagos** | `PagosController` | `Controladores/ms_pagos/app/pagos_controller.py` | Integración Wompi Colombia (firma de integridad HMAC SHA-256), recepción de webhooks, pago presencial y eventos Saga. |
| **ms_notificaciones** | `NotificacionesController` | `Controladores/ms_notificaciones/app/notificaciones_controller.py` | Consulta de bitácora de correos despachados, filtrado por eventType y estadísticas de despacho. |

---

### Mapeo de Vistas Frontend Normalizadas

| Vista Normalizada | Ruta URL | Archivo | Propósito en la Experiencia de Usuario |
|---|---|---|---|
| `VistaLanding` | `/` | `Vista/src/VistaLanding.tsx` | Pantalla de inicio pública, presentación de complejos y acceso rápido. |
| `VistaCancha` | `/catalogo` | `Vista/src/VistaCancha.tsx` | Catálogo de complejos, selección de fecha/hora y grilla interactiva de canchas sintéticas. |
| `VistaReserva` | `/mis-reservas` | `Vista/src/VistaReserva.tsx` | Historial de reservas del usuario con opciones de reprogramación o cancelación. |
| `VistaPerfil` | `/perfil` | `Vista/src/VistaPerfil.tsx` | Consulta y actualización de datos de perfil y cambio de credenciales de acceso. |
| `VistaReportes` | `/reportes`, `/monitor` | `Vista/src/VistaReportes.tsx` | Consola en tiempo real de eventos EDA y auditoría técnica de notificaciones. |
| `VistaLogin` | `/login` | `Vista/src/VistaLogin.tsx` | Formulario de autenticación con split-screen responsivo y persistencia de sesión JWT. |
| `VistaRegistro` | `/registro` | `Vista/src/VistaRegistro.tsx` | Creación de cuenta con pestañas independientes para deportistas y administradores. |
| `VistaRecuperarPassword` | `/recuperar-password` | `Vista/src/VistaRecuperarPassword.tsx` | Solicitud de enlace de restablecimiento e ingreso de nueva contraseña mediante token. |
| `VistaAdminLayout` | `/admin` | `Vista/src/admin/VistaAdminLayout.tsx` | Contenedor principal con barra de navegación lateral para el portal del administrador. |
| `VistaAdminCanchas` | `/admin/canchas` | `Vista/src/admin/VistaAdminCanchas.tsx` | Panel de gestión de canchas, tarifas por hora y bloqueos por mantenimiento. |
| `VistaAdminTaquilla` | `/admin/taquilla` | `Vista/src/admin/VistaAdminTaquilla.tsx` | Taquilla presencial, búsqueda de reservas por cliente y agenda diaria del complejo. |
| `VistaAdminPagos` | `/admin/pagos` | `Vista/src/admin/VistaAdminPagos.tsx` | Conciliación de ingresos, registro de pagos en efectivo/transferencia y reportes. |
| `VistaAdminApariencia` | `/admin/apariencia` | `Vista/src/admin/VistaAdminApariencia.tsx` | Personalización visual, fondos de pantalla y banners de los complejos deportivos. |

---

## 🛡️ Principios Arquitectónicos Garantizados

1. **Separación de Responsabilidades (SoC):** Cada capa (Router -> Controlador -> Modelo -> Broker) posee una única razón de cambio.
2. **Arquitectura Dirigida por Eventos (EDA):** Comunicación asíncrona mediante RabbitMQ Topic Exchange evitando acoplamiento temporal entre microservicios.
3. **Patrón Saga Coreografiado:** Orquestación de reserva y pago con compensación automática (rollback) si el pago es rechazado o cancelado.
4. **Patrón Transactional Outbox:** Garantía de entrega a nivel de persistencia de base de datos antes de despachar eventos al broker.
5. **Control de Concurrencia Estricto:** Bloqueos advisory/pessimistic en PostgreSQL para evitar sobre-venta de franjas horarias en partidos simultáneos.
