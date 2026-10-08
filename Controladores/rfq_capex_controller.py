from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from supplyhub.forms import RFQCapexForm, RFQDecisionForm, RFQEstadoForm
from supplyhub.models import RFQCapex
from supplyhub.services.permission_guard import supplyhub_route_required
from supplyhub.services.rfq_capex_service import (
    actor_from_request,
    change_decision,
    change_status,
    create_rfq,
    update_rfq,
)

RFQ_ROUTE = "/hub/rfq-capex/"


@supplyhub_route_required(RFQ_ROUTE)
def rfq_capex_index(request):
    qs = RFQCapex.objects.all()

    query = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip()
    planta = (request.GET.get("planta") or "").strip()
    decision = (request.GET.get("decision") or "").strip()

    if query:
        qs = qs.filter(
            Q(rfq__icontains=query)
            | Q(descripcion__icontains=query)
            | Q(solicitante__icontains=query)
            | Q(clave_capex__icontains=query)
        )
    if estado:
        qs = qs.filter(estado=estado)
    if planta:
        qs = qs.filter(planta=planta)
    if decision:
        qs = qs.filter(decision_seguimiento=decision)

    context = {
        "page_title": "RFQ / CAPEX",
        "rfqs": qs[:100],
        "query": query,
        "selected_estado": estado,
        "selected_planta": planta,
        "selected_decision": decision,
        "estado_choices": RFQCapex.Estado.choices,
        "planta_choices": RFQCapex.Planta.choices,
        "decision_choices": RFQCapex.Decision.choices,
        "stats": {
            "total": RFQCapex.objects.count(),
            "pendientes": RFQCapex.objects.filter(
                decision_seguimiento=RFQCapex.Decision.PENDIENTE
            ).count(),
            "cotizacion": RFQCapex.objects.filter(
                estado=RFQCapex.Estado.COTIZACION
            ).count(),
            "concluidas": RFQCapex.objects.filter(
                estado=RFQCapex.Estado.CONCLUIDA
            ).count(),
        },
    }
    return render(request, "rfq_capex/index.html", context)


@supplyhub_route_required(RFQ_ROUTE)
def rfq_capex_create(request):
    form = RFQCapexForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        rfq = create_rfq(
            cleaned_data=form.cleaned_data,
            actor=actor_from_request(request),
        )
        messages.success(request, f"RFQ {rfq.rfq} creado.")
        return redirect("supplyhub:rfq_capex_detail", pk=rfq.pk)

    return render(
        request,
        "rfq_capex/form.html",
        {"form": form, "page_title": "Nuevo RFQ / CAPEX", "editing": False},
    )


@supplyhub_route_required(RFQ_ROUTE)
def rfq_capex_edit(request, pk: int):
    rfq = get_object_or_404(RFQCapex, pk=pk)
    form = RFQCapexForm(request.POST or None, instance=rfq)
    if request.method == "POST" and form.is_valid():
        update_rfq(
            instance=rfq,
            cleaned_data=form.cleaned_data,
            actor=actor_from_request(request),
        )
        messages.success(request, f"RFQ {rfq.rfq} actualizado.")
        return redirect("supplyhub:rfq_capex_detail", pk=rfq.pk)

    return render(
        request,
        "rfq_capex/form.html",
        {
            "form": form,
            "page_title": f"Editar RFQ {rfq.rfq}",
            "editing": True,
            "rfq_obj": rfq,
        },
    )


@supplyhub_route_required(RFQ_ROUTE)
def rfq_capex_detail(request, pk: int):
    rfq = get_object_or_404(RFQCapex, pk=pk)
    return render(
        request,
        "rfq_capex/detail.html",
        {
            "rfq_obj": rfq,
            "estado_form": RFQEstadoForm(initial={"estado": rfq.estado}),
            "decision_form": RFQDecisionForm(
                initial={"decision": rfq.decision_seguimiento}
            ),
        },
    )


@supplyhub_route_required(RFQ_ROUTE)
def rfq_capex_status(request, pk: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    rfq = get_object_or_404(RFQCapex, pk=pk)
    form = RFQEstadoForm(request.POST)
    if form.is_valid():
        change_status(
            instance=rfq,
            new_status=form.cleaned_data["estado"],
            actor=actor_from_request(request),
            comment=form.cleaned_data.get("comentario", ""),
        )
        messages.success(request, "Estado actualizado.")
    else:
        messages.error(request, "No fue posible actualizar el estado.")
    return redirect("supplyhub:rfq_capex_detail", pk=pk)


@supplyhub_route_required(RFQ_ROUTE)
def rfq_capex_decision(request, pk: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    rfq = get_object_or_404(RFQCapex, pk=pk)
    form = RFQDecisionForm(request.POST)
    if form.is_valid():
        change_decision(
            instance=rfq,
            new_decision=form.cleaned_data["decision"],
            actor=actor_from_request(request),
            reason=form.cleaned_data.get("motivo", ""),
        )
        messages.success(request, "Decisión de seguimiento actualizada.")
    else:
        messages.error(request, "No fue posible actualizar la decisión.")
    return redirect("supplyhub:rfq_capex_detail", pk=pk)
