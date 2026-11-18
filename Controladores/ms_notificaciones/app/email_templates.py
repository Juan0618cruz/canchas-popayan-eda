"""
Corporate HTML + Plain-Text email templates for ms_notificaciones (Canchas Popayán).

Every template function accepts an enriched event ``data`` dict and returns
a 3-tuple: ``(subject, text_body, html_body)``.
"""

import html as _html
from typing import Iterable

METODO_DISPLAY: dict[str, str] = {
    "WOMPI": "Wompi",
    "BRE_B": "Bre-B",
    "EFECTIVO": "Efectivo",
    "WOMPI_NEQUI": "Wompi",
    "WOMPI_PSE": "Wompi",
    "WOMPI_BANCOLOMBIA": "Wompi",
    "WOMPI_CARD": "Wompi",
    "TARJETA": "Wompi",
    "TRANSFERENCIA": "Bre-B",
    "NEQUI": "Bre-B",
}

_HEADER = """\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       🏟️  CANCHAS POPAYÁN — Plataforma de Reservas
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

_FOOTER = """\

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Este es un mensaje automático. Por favor no responda.
¿Preguntas? Escríbanos a soporte@canchas-popayan.com
📍 Popayán, Cauca — Colombia
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def _wrap_text(content: str) -> str:
    return _HEADER + "\n" + content.strip() + "\n" + _FOOTER


def _format_cop(raw_monto: object) -> str:
    if raw_monto is None or raw_monto == "N/A" or raw_monto == "":
        return "N/A"
    try:
        num = int(round(float(str(raw_monto))))
        return f"$ {num:,} COP".replace(",", ".")
    except Exception:
        return f"$ {raw_monto} COP"


def _format_metodo(raw_metodo: object) -> str:
    key = str(raw_metodo or "N/A").strip().upper()
    return METODO_DISPLAY.get(key, key)


def _format_time(raw_time: object) -> str:
    s = str(raw_time or "N/A").strip()
    return s[:5] if len(s) >= 5 and ":" in s else s


def _build_corporate_html(
    badge_text: str,
    badge_color: str,
    title: str,
    greeting: str,
    intro: str,
    rows: Iterable[tuple[str, str]],
    footer_note: str,
) -> str:
    esc = _html.escape
    row_html = "\n".join(
        f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;color:#4b5563;font-size:13px;font-weight:600;width:42%;">{esc(k)}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;color:#111827;font-size:13px;font-weight:700;">{esc(v)}</td>
        </tr>
        """
        for k, v in rows
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8" /></head>
<body style="margin:0;padding:0;background-color:#f3f4f6;font-family:'Segoe UI',Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:24px 12px;background-color:#f3f4f6;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e5e7eb;box-shadow:0 4px 16px rgba(0,0,0,0.06);">
          <tr>
            <td style="background:linear-gradient(135deg,#047857,#10b981);padding:24px 28px;text-align:left;">
              <div style="color:#ecfdf5;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">⚽ Canchas Popayán</div>
              <h1 style="margin:6px 0 0;color:#ffffff;font-size:22px;font-weight:800;">{esc(title)}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 28px;">
              <span style="display:inline-block;padding:5px 12px;border-radius:999px;background:{badge_color};color:#ffffff;font-size:11px;font-weight:700;letter-spacing:0.5px;margin-bottom:14px;">{esc(badge_text)}</span>
              <p style="margin:0 0 8px;color:#111827;font-size:15px;font-weight:600;">{esc(greeting)}</p>
              <p style="margin:0 0 20px;color:#4b5563;font-size:14px;line-height:1.55;">{esc(intro)}</p>

              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;background:#f9fafb;border-radius:12px;overflow:hidden;margin-bottom:20px;border:1px solid #e5e7eb;">
                {row_html}
              </table>

              <div style="background:#ecfdf5;border-left:4px solid #10b981;padding:12px 16px;border-radius:6px;margin-bottom:16px;">
                <p style="margin:0;color:#065f46;font-size:12px;line-height:1.5;font-weight:500;">{esc(footer_note)}</p>
              </div>
            </td>
          </tr>
          <tr>
            <td style="background:#f9fafb;padding:16px 28px;border-top:1px solid #e5e7eb;text-align:center;">
              <p style="margin:0;color:#9ca3af;font-size:11px;line-height:1.5;">
                Mensaje automático de <strong>Canchas Popayán</strong> · Popayán, Cauca — Colombia<br/>
                Soporte: <a href="mailto:soporte@canchas-popayan.com" style="color:#059669;text-decoration:none;">soporte@canchas-popayan.com</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def template_reserva_solicitada(data: dict) -> tuple[str, str, str]:
    """Email sent when a court reservation has been created/requested."""
    codigo_uid = str(data.get("codigo_uid") or data.get("reserva_id") or "N/A")
    nombre_usuario = str(data.get("nombre_usuario") or "Deportista")
    nombre_complejo = str(data.get("nombre_complejo") or "Complejo Deportivo Popayán")
    nombre_cancha = str(data.get("nombre_cancha") or "Cancha Sintética")
    fecha = str(data.get("fecha") or "N/A")
    hora = f"{_format_time(data.get('hora_inicio'))} – {_format_time(data.get('hora_fin'))}"
    monto_str = _format_cop(data.get("precio_total") or data.get("monto"))
    metodo = _format_metodo(data.get("metodo_pago") or data.get("metodo") or "Wompi (Pendiente)")
    estado = str(data.get("estado") or "PENDIENTE DE PAGO")

    subject = f"Reserva Recibida - {codigo_uid}"
    rows = [
        ("Código de reserva", codigo_uid),
        ("Complejo Deportivo", nombre_complejo),
        ("Cancha", nombre_cancha),
        ("Fecha", fecha),
        ("Hora", hora),
        ("Monto", monto_str),
        ("Método", metodo),
        ("Estado", estado),
    ]

    text_body = _wrap_text(
        f"Hola, {nombre_usuario}:\n\n"
        f"Hemos recibido tu solicitud de reserva ({codigo_uid}):\n\n"
        + "\n".join(f"  {k}: {v}" for k, v in rows)
        + "\n\nPor favor completa tu pago mediante Wompi Colombia o en taquilla para confirmar tu turno."
    )
    html_body = _build_corporate_html(
        badge_text=f"ESTADO: {estado}",
        badge_color="#d97706",
        title="Solicitud de Reserva Recibida",
        greeting=f"Hola, {nombre_usuario}:",
        intro="Hemos registrado tu reserva temporalmente. Completa el pago para asegurar tu horario.",
        rows=rows,
        footer_note="Tienes 15 minutos para completar el pago antes de que la franja horaria sea liberada automáticamente.",
    )
    return subject, text_body, html_body


def template_pago_aprobado(data: dict) -> tuple[str, str, str]:
    """Email sent when payment (Wompi / online / taquilla) for a reservation has been approved."""
    codigo_uid = str(data.get("codigo_uid") or data.get("reserva_id") or "N/A")
    nombre_usuario = str(data.get("nombre_usuario") or "Deportista")
    nombre_complejo = str(data.get("nombre_complejo") or "Complejo Deportivo Popayán")
    nombre_cancha = str(data.get("nombre_cancha") or "Cancha Sintética")
    fecha = str(data.get("fecha") or "N/A")
    hora = f"{_format_time(data.get('hora_inicio'))} – {_format_time(data.get('hora_fin'))}"
    monto_str = _format_cop(data.get("precio_total") or data.get("monto"))
    metodo = _format_metodo(data.get("metodo_pago") or data.get("metodo"))
    ref_pago = str(data.get("referencia_wompi") or data.get("pago_id") or "N/A")

    subject = f"Pago Aprobado y Reserva Confirmada - {codigo_uid}"
    rows = [
        ("Código de reserva", codigo_uid),
        ("Complejo Deportivo", nombre_complejo),
        ("Cancha", nombre_cancha),
        ("Fecha", fecha),
        ("Hora", hora),
        ("Monto Pagado", monto_str),
        ("Método de Pago", metodo),
        ("Referencia de Pago", ref_pago),
        ("Estado", "CONFIRMADA"),
    ]

    text_body = _wrap_text(
        f"¡Hola, {nombre_usuario}!\n\n"
        f"Tu pago para la reserva {codigo_uid} ha sido APROBADO:\n\n"
        + "\n".join(f"  {k}: {v}" for k, v in rows)
        + f"\n\nTu turno está asegurado. Llega 10 minutos antes y presenta tu código {codigo_uid} en recepción."
    )
    html_body = _build_corporate_html(
        badge_text="RESERVA CONFIRMADA",
        badge_color="#059669",
        title="¡Tu Reserva está Confirmada!",
        greeting=f"Hola, {nombre_usuario}:",
        intro="Tu pago fue aprobado exitosamente y tu cancha ya quedó reservada para el horario seleccionado.",
        rows=rows,
        footer_note=f"Llega 10 minutos antes de tu turno y presenta el código {codigo_uid} en la recepción del complejo.",
    )
    return subject, text_body, html_body


def template_pago_rechazado(data: dict) -> tuple[str, str, str]:
    """Email sent when payment has been rejected."""
    codigo_uid = str(data.get("codigo_uid") or data.get("reserva_id") or "N/A")
    nombre_usuario = str(data.get("nombre_usuario") or "Deportista")
    nombre_complejo = str(data.get("nombre_complejo") or "Complejo Deportivo Popayán")
    nombre_cancha = str(data.get("nombre_cancha") or "Cancha Sintética")
    monto_str = _format_cop(data.get("precio_total") or data.get("monto"))
    metodo = _format_metodo(data.get("metodo_pago") or data.get("metodo"))
    motivo = str(data.get("motivo_rechazo") or data.get("razon") or "Transacción rechazada por el banco emisor")

    subject = f"Pago No Aprobado - Reserva {codigo_uid}"
    rows = [
        ("Código de reserva", codigo_uid),
        ("Complejo Deportivo", nombre_complejo),
        ("Cancha", nombre_cancha),
        ("Monto", monto_str),
        ("Método de Pago", metodo),
        ("Motivo", motivo),
        ("Estado", "PAGO_RECHAZADO"),
    ]

    text_body = _wrap_text(
        f"Hola, {nombre_usuario}:\n\n"
        f"Tu intento de pago para la reserva {codigo_uid} no pudo ser procesado:\n\n"
        + "\n".join(f"  {k}: {v}" for k, v in rows)
        + "\n\nPuedes intentar nuevamente con otro método de pago en https://canchaspopayan.com."
    )
    html_body = _build_corporate_html(
        badge_text="PAGO NO APROBADO",
        badge_color="#dc2626",
        title="Pago No Aprobado",
        greeting=f"Hola, {nombre_usuario}:",
        intro="Lamentamos informarte que la transacción fue rechazada por la entidad financiera.",
        rows=rows,
        footer_note="Puedes reintentar el pago ingresando a 'Mis Reservas' o elegir un método diferente (Wompi o Bre-B).",
    )
    return subject, text_body, html_body


def template_reserva_cancelada(data: dict) -> tuple[str, str, str]:
    """Email sent when a reservation is cancelled."""
    codigo_uid = str(data.get("codigo_uid") or data.get("reserva_id") or "N/A")
    nombre_usuario = str(data.get("nombre_usuario") or "Deportista")
    nombre_complejo = str(data.get("nombre_complejo") or "Complejo Deportivo Popayán")
    nombre_cancha = str(data.get("nombre_cancha") or "Cancha Sintética")
    fecha = str(data.get("fecha") or "N/A")
    hora = f"{_format_time(data.get('hora_inicio'))} – {_format_time(data.get('hora_fin'))}"
    monto_str = _format_cop(data.get("precio_total") or data.get("monto"))
    motivo = str(data.get("motivo") or data.get("razon") or "Cancelación de reserva")

    subject = f"Reserva Cancelada - {codigo_uid}"
    rows = [
        ("Código de reserva", codigo_uid),
        ("Complejo Deportivo", nombre_complejo),
        ("Cancha", nombre_cancha),
        ("Fecha", fecha),
        ("Hora", hora),
        ("Monto", monto_str),
        ("Estado", "CANCELADA"),
        ("Motivo", motivo),
    ]

    text_body = _wrap_text(
        f"Hola, {nombre_usuario}:\n\nTu reserva {codigo_uid} ha sido cancelada:\n\n"
        + "\n".join(f"  {k}: {v}" for k, v in rows)
    )
    html_body = _build_corporate_html(
        badge_text="RESERVA CANCELADA",
        badge_color="#dc2626",
        title="Cancelación de Reserva",
        greeting=f"Hola, {nombre_usuario}:",
        intro="Te confirmamos que tu reserva ha sido cancelada y el horario quedó libre nuevamente.",
        rows=rows,
        footer_note="Si necesitas ayuda adicional o deseas agendar un nuevo horario, contáctanos en soporte@canchas-popayan.com.",
    )
    return subject, text_body, html_body


def template_reserva_reprogramada(data: dict) -> tuple[str, str, str]:
    """Email sent when a reservation has been rescheduled."""
    codigo_uid = str(data.get("codigo_uid") or data.get("reserva_id") or "N/A")
    nombre_usuario = str(data.get("nombre_usuario") or "Deportista")
    nombre_complejo = str(data.get("nombre_complejo") or "Complejo Deportivo Popayán")
    nombre_cancha = str(data.get("nombre_cancha") or "Cancha Sintética")
    fecha_ant = str(data.get("fecha_anterior") or data.get("old_fecha") or "N/A")
    hora_ant = f"{_format_time(data.get('hora_inicio_anterior'))} – {_format_time(data.get('hora_fin_anterior'))}"
    fecha_new = str(data.get("nueva_fecha") or data.get("fecha_nuevo") or data.get("fecha_nueva") or "N/A")
    hora_new = f"{_format_time(data.get('nueva_hora_inicio') or data.get('hora_inicio_nuevo'))} – {_format_time(data.get('nueva_hora_fin') or data.get('hora_fin_nuevo'))}"
    monto_str = _format_cop(data.get("precio_total") or data.get("monto"))
    estado = str(data.get("estado") or "REPROGRAMADA")

    subject = f"Reserva Reprogramada - {codigo_uid}"
    rows = [
        ("Código de reserva", codigo_uid),
        ("Complejo Deportivo", nombre_complejo),
        ("Cancha", nombre_cancha),
        ("Horario Anterior", f"{fecha_ant} ({hora_ant})"),
        ("Nuevo Horario", f"{fecha_new} ({hora_new})"),
        ("Monto", monto_str),
        ("Estado", estado),
    ]

    text_body = _wrap_text(
        f"Hola, {nombre_usuario}:\n\nTu reserva {codigo_uid} ha sido reprogramada:\n\n"
        + "\n".join(f"  {k}: {v}" for k, v in rows)
    )
    html_body = _build_corporate_html(
        badge_text="HORARIO REPROGRAMADO",
        badge_color="#7c3aed",
        title="Reserva Reprogramada Exitosamente",
        greeting=f"Hola, {nombre_usuario}:",
        intro="El cambio de horario se aplicó correctamente y tu franja anterior fue liberada automáticamente.",
        rows=rows,
        footer_note="Recuerda llegar 10 minutos antes de tu nuevo horario reservado.",
    )
    return subject, text_body, html_body


def template_clave_restablecimiento(data: dict) -> tuple[str, str, str]:
    """Email sent when a password reset is requested."""
    nombre = str(data.get("nombre") or "Usuario")
    email = str(data.get("email") or "")
    token = str(data.get("token") or data.get("reset_token") or "000000")
    expira_en = str(data.get("expira_en") or "15 minutos")

    subject = f"Código de Recuperación: {token} - Canchas Popayán"
    rows = [
        ("Cuenta", email or "N/A"),
        ("Código de 6 Dígitos", token),
        ("Vigencia", "15 minutos"),
    ]

    text_body = _wrap_text(
        f"Hola, {nombre}:\n\n"
        "Recibimos una solicitud para restablecer tu contraseña en la plataforma de Canchas Popayán.\n\n"
        f"Tu código numérico de verificación es:\n\n"
        f"       👉  {token}  👈\n\n"
        "Ingresa este código de 6 dígitos en la pantalla de recuperación junto con tu nueva contraseña.\n"
        "Este código es de un solo uso y expirará en 15 minutos.\n\n"
        "Si no solicitaste este cambio, puedes ignorar este correo con tranquilidad."
    )
    html_body = _build_corporate_html(
        badge_text="SEGURIDAD Y ACCESO",
        badge_color="#ea580c",
        title="Código de Recuperación de Contraseña",
        greeting=f"Hola, {nombre}:",
        intro="Usa el siguiente código de 6 dígitos en la plataforma para definir tu nueva contraseña:",
        rows=rows,
        footer_note="Este código es de un solo uso y expirará en 15 minutos. Si no solicitaste restablecer tu clave, ignora este mensaje.",
    )
    return subject, text_body, html_body


def template_usuario_registrado(data: dict) -> tuple[str, str, str]:
    """Email sent when a user successfully registers as Deportista."""
    nombre = str(data.get("nombre") or "Deportista")
    email = str(data.get("email") or "N/A")
    telefono = str(data.get("telefono") or "No registrado")

    subject = "¡Bienvenido a Canchas Popayán! Registro Exitoso"
    rows = [
        ("Nombre", nombre),
        ("Correo electrónico", email),
        ("Teléfono", telefono),
        ("Perfil", "Deportista"),
        ("Estado de cuenta", "ACTIVO"),
    ]

    text_body = _wrap_text(
        f"¡Hola, {nombre}!\n\n"
        "Te damos una cordial bienvenida a Canchas Popayán, la plataforma oficial de reservas de canchas sintéticas.\n\n"
        + "\n".join(f"  {k}: {v}" for k, v in rows)
        + "\n\nYa puedes ingresar a la plataforma, consultar la disponibilidad de canchas y agendar tus partidos."
    )
    html_body = _build_corporate_html(
        badge_text="REGISTRO EXITOSO",
        badge_color="#059669",
        title="¡Bienvenido a Canchas Popayán!",
        greeting=f"¡Hola, {nombre}!",
        intro="Tu cuenta como Deportista ha sido creada exitosamente. Ya puedes consultar disponibilidad en tiempo real y reservar tus partidos en Popayán.",
        rows=rows,
        footer_note="Inicia sesión con tu correo y contraseña en https://canchaspopayan.com o en tu app local.",
    )
    return subject, text_body, html_body


def template_admin_registrado(data: dict) -> tuple[str, str, str]:
    """Email sent when an administrator registers with a sports complex."""
    nombre = str(data.get("nombre") or "Administrador")
    email = str(data.get("email") or "N/A")
    telefono = str(data.get("telefono") or "No registrado")
    establecimiento_nombre = str(data.get("establecimiento_nombre") or "Complejo Deportivo")
    establecimiento_direccion = str(data.get("establecimiento_direccion") or "Popayán")

    subject = f"¡Bienvenido Administrador! Complejo {establecimiento_nombre} - Canchas Popayán"
    rows = [
        ("Administrador", nombre),
        ("Correo electrónico", email),
        ("Teléfono", telefono),
        ("Complejo Deportivo", establecimiento_nombre),
        ("Dirección", establecimiento_direccion),
        ("Rol", "ADMIN_ESTABLECIMIENTO"),
    ]

    text_body = _wrap_text(
        f"¡Hola, {nombre}!\n\n"
        f"Tu registro como Administrador del complejo {establecimiento_nombre} se completó con éxito:\n\n"
        + "\n".join(f"  {k}: {v}" for k, v in rows)
        + "\n\nYa puedes acceder al panel de administración para gestionar canchas, horarios, reservas y taquilla."
    )
    html_body = _build_corporate_html(
        badge_text="SEDE REGISTRADA",
        badge_color="#2563eb",
        title="Registro de Administrador de Sede",
        greeting=f"¡Hola, {nombre}!",
        intro=f"Te damos la bienvenida como administrador del complejo '{establecimiento_nombre}'. Tu sede está lista para operar en Canchas Popayán.",
        rows=rows,
        footer_note="Accede al panel de administración en la sección Taquilla y Agenda para comenzar a recibir reservas.",
    )
    return subject, text_body, html_body
