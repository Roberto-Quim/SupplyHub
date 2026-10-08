from __future__ import annotations

import re
import unicodedata

from django.db import transaction

from supplyhub.models import HistorialDecisionRFQ, HistorialEstadoRFQ, RFQCapex


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().strip()
    return re.sub(r"\s+", " ", value)


def normalize_plant(raw: str) -> str | None:
    """Normaliza aliases conocidos sin destruir el texto de origen."""
    value = _plain(raw)
    if not value:
        return None
    if "tenango" in value:
        return RFQCapex.Planta.MACIMEX_TENANGO
    if (
        "maq ra" in value
        or "maquinados ramos" in value
        or "ramos arizpe" in value
        or value == "maqra"
    ):
        return RFQCapex.Planta.MAQ_RA
    return None


def actor_from_request(request) -> str:
    """La identidad de negocio es la nómina cuando está disponible."""
    corporate = str(request.session.get("sh_usuario", "") or "").strip()
    if corporate:
        return corporate
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return str(user.get_username() or "").strip()
    return ""


@transaction.atomic
def create_rfq(*, cleaned_data: dict, actor: str) -> RFQCapex:
    planta = cleaned_data["planta"]
    planta_display = dict(RFQCapex.Planta.choices).get(planta, planta)
    rfq = RFQCapex.objects.create(
        rfq=cleaned_data["rfq"],
        descripcion=cleaned_data["descripcion"],
        fecha_arranque=cleaned_data.get("fecha_arranque"),
        solicitante=cleaned_data["solicitante"],
        correo_solicitante=cleaned_data.get("correo_solicitante", ""),
        planta=planta,
        planta_origen=planta_display,
        clave_capex=cleaned_data.get("clave_capex", ""),
        tipo_capex=cleaned_data.get("tipo_capex", ""),
        origen=RFQCapex.Origen.MANUAL,
        creado_por=actor,
        actualizado_por=actor,
    )
    HistorialEstadoRFQ.objects.create(
        rfq=rfq,
        estado_anterior="",
        estado_nuevo=rfq.estado,
        comentario="Registro creado en SupplyHub.",
        usuario=actor,
    )
    HistorialDecisionRFQ.objects.create(
        rfq=rfq,
        decision_anterior="",
        decision_nueva=rfq.decision_seguimiento,
        motivo="Pendiente de confirmación de seguimiento.",
        usuario=actor,
    )
    return rfq


@transaction.atomic
def update_rfq(*, instance: RFQCapex, cleaned_data: dict, actor: str) -> RFQCapex:
    for field in (
        "rfq",
        "descripcion",
        "fecha_arranque",
        "solicitante",
        "correo_solicitante",
        "planta",
        "clave_capex",
        "tipo_capex",
    ):
        setattr(instance, field, cleaned_data.get(field))
    instance.planta_origen = dict(RFQCapex.Planta.choices).get(
        instance.planta, instance.planta
    )
    instance.actualizado_por = actor
    instance.save()
    return instance


@transaction.atomic
def change_status(
    *,
    instance: RFQCapex,
    new_status: str,
    actor: str,
    comment: str = "",
) -> RFQCapex:
    valid = {value for value, _ in RFQCapex.Estado.choices}
    if new_status not in valid:
        raise ValueError("Estado RFQ no válido.")
    previous = instance.estado
    if previous == new_status:
        return instance

    instance.estado = new_status
    instance.actualizado_por = actor
    instance.save(update_fields=("estado", "actualizado_por", "actualizado_en"))
    HistorialEstadoRFQ.objects.create(
        rfq=instance,
        estado_anterior=previous,
        estado_nuevo=new_status,
        comentario=(comment or "").strip(),
        usuario=actor,
    )
    return instance


@transaction.atomic
def change_decision(
    *,
    instance: RFQCapex,
    new_decision: str,
    actor: str,
    reason: str = "",
) -> RFQCapex:
    valid = {value for value, _ in RFQCapex.Decision.choices}
    if new_decision not in valid:
        raise ValueError("Decisión RFQ no válida.")
    previous = instance.decision_seguimiento
    if previous == new_decision:
        return instance

    instance.decision_seguimiento = new_decision
    instance.actualizado_por = actor
    instance.save(
        update_fields=("decision_seguimiento", "actualizado_por", "actualizado_en")
    )
    HistorialDecisionRFQ.objects.create(
        rfq=instance,
        decision_anterior=previous,
        decision_nueva=new_decision,
        motivo=(reason or "").strip(),
        usuario=actor,
    )
    return instance
