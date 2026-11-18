"""
app/seed.py - Seed the database with pilot complexes and their courts.

Ensures that the complex with ID "a1b2c3d4-e5f6-7890-abcd-ef1234567890" (Balón de Oro)
and its 4 synthetic soccer courts exist and are linked to Juan Pablo Admin.
Pre-generates BloqueHorario rows for the next 30 days (1-hour slots, LIBRE).
"""
import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BloqueHorario, Cancha, Complejo, EstadoBloque, TipoCancha

ADMIN_COMPLEJO_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
BERNABEU_COMPLEJO_ID = uuid.UUID("b2c3d4e5-f6a7-8901-bcde-fa2345678901")


def _generate_slots(
    cancha_id: uuid.UUID,
    fecha: date,
    hora_apertura: time,
    hora_cierre: time,
) -> list[BloqueHorario]:
    """Create BloqueHorario objects from hora_apertura to hora_cierre in 1-hour increments."""
    slots: list[BloqueHorario] = []
    current_hour = hora_apertura.hour
    close_hour = hora_cierre.hour

    while current_hour < close_hour:
        slots.append(
            BloqueHorario(
                id=uuid.uuid4(),
                cancha_id=cancha_id,
                fecha=fecha,
                hora_inicio=time(current_hour, 0),
                hora_fin=time(current_hour + 1, 0),
                estado=EstadoBloque.LIBRE,
                reserva_id=None,
                updated_at=datetime.utcnow(),
            )
        )
        current_hour += 1

    return slots


async def seed_database(session: AsyncSession) -> None:
    """
    Seed database with pilot data for Popayán.
    Ensures that Complejo Balón de Oro (id=a1b2c3d4-e5f6-7890-abcd-ef1234567890)
    exists with at least 4 synthetic soccer courts.
    """
    today = date.today()
    next_30_days: list[date] = [today + timedelta(days=d) for d in range(30)]

    # 1. Verificar si existe el complejo del administrador
    res_c1 = await session.execute(select(Complejo).where(Complejo.id == ADMIN_COMPLEJO_ID))
    complejo1 = res_c1.scalar_one_or_none()

    if not complejo1:
        complejo1 = Complejo(
            id=ADMIN_COMPLEJO_ID,
            nombre="Complejo Deportivo Balón de Oro",
            direccion="Carrera 15 # 12-45, Barrio San José",
            barrio="San José",
            ciudad="Popayán",
            descripcion=(
                "Complejo deportivo con canchas sintéticas de alta calidad en Popayán. "
                "Contamos con camerinos, iluminación nocturna LED y parqueadero vigilado."
            ),
            activo=True,
        )
        session.add(complejo1)
        await session.flush()

    # 2. Asegurar que Complejo 1 tenga sus 4 canchas
    res_canchas1 = await session.execute(
        select(Cancha).where(Cancha.complejo_id == ADMIN_COMPLEJO_ID)
    )
    canchas_existentes1 = res_canchas1.scalars().all()

    canchas_nuevas: list[Cancha] = []

    if len(canchas_existentes1) < 4:
        # Definición de las 4 canchas principales de Balón de Oro
        canchas_def = [
            {
                "id": uuid.UUID("11111111-2222-3333-4444-555555555501"),
                "nombre": "Cancha 1 - Fútbol 5 (Grama Sintética)",
                "tipo": TipoCancha.FUTBOL_5,
                "tarifa_por_hora": 70000.0,
                "descripcion": "Cancha de fútbol 5 con grama sintética monofilamento de última generación.",
            },
            {
                "id": uuid.UUID("11111111-2222-3333-4444-555555555502"),
                "nombre": "Cancha 2 - Fútbol 7 (Techada Iluminada)",
                "tipo": TipoCancha.FUTBOL_7,
                "tarifa_por_hora": 90000.0,
                "descripcion": "Cancha de fútbol 7 techada con arcos reglamentarios e iluminación LED.",
            },
            {
                "id": uuid.UUID("11111111-2222-3333-4444-555555555503"),
                "nombre": "Cancha 3 - Fútbol 8 (Profesional)",
                "tipo": TipoCancha.FUTBOL_8,
                "tarifa_por_hora": 120000.0,
                "descripcion": "Cancha de fútbol 8 de tamaño oficial, ideal para torneos y ligas locales.",
            },
            {
                "id": uuid.UUID("11111111-2222-3333-4444-555555555504"),
                "nombre": "Cancha 4 - Fútbol 5 (Nocturna San José)",
                "tipo": TipoCancha.FUTBOL_5,
                "tarifa_por_hora": 75000.0,
                "descripcion": "Cancha rápida de fútbol 5 para partidos nocturnos con excelente visibilidad.",
            },
        ]

        nombres_existentes = {c.nombre for c in canchas_existentes1}
        for cdef in canchas_def:
            if cdef["nombre"] not in nombres_existentes:
                nueva_cancha = Cancha(
                    id=cdef["id"],
                    complejo_id=ADMIN_COMPLEJO_ID,
                    nombre=cdef["nombre"],
                    tipo=cdef["tipo"],
                    tarifa_por_hora=cdef["tarifa_por_hora"],
                    descripcion=cdef["descripcion"],
                    activo=True,
                    hora_apertura=time(8, 0),
                    hora_cierre=time(22, 0),
                )
                session.add(nueva_cancha)
                canchas_nuevas.append(nueva_cancha)

        await session.flush()

    # 3. Complejo 2: Complejo Sintético Bernabéu (Julumito)
    res_c2 = await session.execute(select(Complejo).where(Complejo.id == BERNABEU_COMPLEJO_ID))
    complejo2 = res_c2.scalar_one_or_none()

    if not complejo2:
        complejo2 = Complejo(
            id=BERNABEU_COMPLEJO_ID,
            nombre="Complejo Sintético Bernabéu",
            direccion="Vía Julumito Km 2",
            barrio="Julumito",
            ciudad="Popayán",
            descripcion=(
                "Moderno complejo deportivo en Julumito, Popayán. Canchas certificadas "
                "con vista a la montaña y zona de comidas."
            ),
            activo=True,
        )
        session.add(complejo2)
        await session.flush()

        cancha2_1 = Cancha(
            id=uuid.UUID("22222222-3333-4444-5555-666666666601"),
            complejo_id=BERNABEU_COMPLEJO_ID,
            nombre="Cancha Bernabéu A - Fútbol 5",
            tipo=TipoCancha.FUTBOL_5,
            tarifa_por_hora=65000.0,
            descripcion="Cancha compacta para fútbol 5 en Julumito.",
            activo=True,
            hora_apertura=time(8, 0),
            hora_cierre=time(22, 0),
        )
        cancha2_2 = Cancha(
            id=uuid.UUID("22222222-3333-4444-5555-666666666602"),
            complejo_id=BERNABEU_COMPLEJO_ID,
            nombre="Cancha Bernabéu B - Fútbol 7",
            tipo=TipoCancha.FUTBOL_7,
            tarifa_por_hora=85000.0,
            descripcion="Cancha de fútbol 7 en césped sintético.",
            activo=True,
            hora_apertura=time(8, 0),
            hora_cierre=time(22, 0),
        )
        session.add_all([cancha2_1, cancha2_2])
        canchas_nuevas.extend([cancha2_1, cancha2_2])
        await session.flush()

    # 4. Generar bloques horarios para las canchas nuevas si no tienen
    if canchas_nuevas:
        bloques: list[BloqueHorario] = []
        for cancha in canchas_nuevas:
            for dia in next_30_days:
                bloques.extend(
                    _generate_slots(
                        cancha_id=cancha.id,
                        fecha=dia,
                        hora_apertura=cancha.hora_apertura,
                        hora_cierre=cancha.hora_cierre,
                    )
                )

        BATCH_SIZE = 500
        for i in range(0, len(bloques), BATCH_SIZE):
            session.add_all(bloques[i : i + BATCH_SIZE])
            await session.flush()

    await session.commit()
    print("[seed] ✅ Seed completado con éxito: Complejo Balón de Oro y canchas operativas.")
