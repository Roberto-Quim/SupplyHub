from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from supplyhub.models import OrdenCompra, LineaOC
from supplyhub.services.importacion_oc_service import importar_oracle_open_po
from supplyhub.services.seguimiento_oc_service import evaluar_estado_linea, registrar_interaccion_linea
from supplyhub.services.rfq_capex_service import actor_from_request
from supplyhub.forms.seguimiento_oc import ImportarOCForm
from supplyhub.forms.seguimiento_linea import RegistrarSeguimientoForm
from supplyhub.services.permission_guard import supplyhub_route_required

SEGUIMIENTO_ROUTE = "/hub/seguimiento-oc/"


@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def seguimiento_oc_index(request):
    """Controlador con soporte para filtrado múltiple de plantas limpio"""
    plantas_raw = request.GET.getlist('planta')
    
    # Limpiar la lista para ignorar valores vacíos o 'TODAS'
    plantas_seleccionadas = [p for p in plantas_raw if p and p != 'TODAS']
    
    ordenes = OrdenCompra.objects.all().order_by('-fecha_creacion')
    
    # Si hay plantas específicas seleccionadas, filtramos
    if plantas_seleccionadas:
        ordenes = ordenes.filter(planta_normalizada__in=plantas_seleccionadas)
    else:
        # Si la lista quedó vacía (o venía 'TODAS'), mostramos todas las plantas
        plantas_seleccionadas = ['TODAS']

    opciones_plantas = OrdenCompra.PlantaNormalizada.choices

    return render(request, "seguimiento_oc/index.html", {
        "page_title": "Seguimiento de Órdenes de Compra",
        "ordenes": ordenes,
        "plantas_seleccionadas": plantas_seleccionadas,
        "opciones_plantas": opciones_plantas,
    })

@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def seguimiento_oc_detalle(request, pk):
    orden = get_object_or_404(OrdenCompra, pk=pk)
    
    if request.method == "POST":
        linea_id = request.POST.get("linea_id")
        linea = get_object_or_404(LineaOC, pk=linea_id, orden=orden)
        form = RegistrarSeguimientoForm(request.POST)
        
        if form.is_valid():
            usuario = actor_from_request(request)
            respuesta = form.cleaned_data["respuesta_proveedor"]
            nueva_fecha = form.cleaned_data["fecha_revisada_propuesta"]
            
            registrar_interaccion_linea(linea, respuesta, usuario, nueva_fecha)
            messages.success(request, f"Interacción registrada correctamente para la línea {linea.numero_linea}.")
            return redirect("supplyhub:seguimiento_oc_detalle", pk=orden.pk)
        else:
            messages.error(request, "Error al guardar el seguimiento. Verifica los datos.")
    
    lineas = orden.lineas.all().order_by('numero_linea')
    lineas_evaluadas = []
    
    for linea in lineas:
        evaluacion = evaluar_estado_linea(linea)
        lineas_evaluadas.append({
            "objeto": linea,
            "evaluacion": evaluacion,
            "historial": linea.historial.all()
        })

    form = RegistrarSeguimientoForm()

    return render(request, "seguimiento_oc/detalle.html", {
        "page_title": f"Detalle de OC #{orden.numero_oc}",
        "orden": orden,
        "lineas_evaluadas": lineas_evaluadas,
        "form": form
    })

@supplyhub_route_required(SEGUIMIENTO_ROUTE)
def importar_oc_view(request):
    """Controlador para manejar la subida del Excel de Oracle"""
    if request.method == "POST":
        form = ImportarOCForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES["archivo_excel"]
            usuario = actor_from_request(request)
            
            try:
                resumen = importar_oracle_open_po(archivo, usuario)
                messages.success(
                    request, 
                    f"Importación completada. OC nuevas: {resumen['insertados_oc']} | "
                    f"Líneas nuevas: {resumen['insertados_linea']} | "
                    f"Líneas actualizadas: {resumen['actualizados']}."
                )
                if resumen["errores"]:
                    messages.warning(request, f"Se omitieron {len(resumen['errores'])} filas con errores.")
                    
            except Exception as e:
                messages.error(request, f"Error crítico al importar el archivo: {str(e)}")
                
            return redirect("supplyhub:seguimiento_oc")
    else:
        form = ImportarOCForm()

    return render(request, "seguimiento_oc/importar.html", {
        "form": form,
        "page_title": "Importar Reporte Oracle"
    })