"""Servicio de previsualización de importación RFQ/CAPEX antes de confirmar."""

import pandas as pd
from datetime import date, timedelta
from supplyhub.models import RFQCapex


def validar_registro_rfq(registro: dict, rfq_existente=None) -> list:
    """
    Valida un registro RFQ según reglas de negocio.
    
    Retorna lista de advertencias/errores:
    - Tipo 'error': Bloquea importación
    - Tipo 'warning': Permite importación pero alerta
    
    Args:
        registro: dict con datos parseados
        rfq_existente: instancia de RFQCapex si existe, None si es nuevo
    
    Returns:
        Lista de dicts: [{"tipo": "error|warning", "mensaje": "..."}]
    """
    validaciones = []
    
    # V1: Validar campos obligatorios
    if not registro.get('rfq'):
        validaciones.append({"tipo": "error", "mensaje": "Falta número de RFQ"})
    
    if not registro.get('descripcion_completa'):
        validaciones.append({"tipo": "error", "mensaje": "Falta descripción"})
    
    if not registro.get('solicitante'):
        validaciones.append({"tipo": "error", "mensaje": "Falta nombre del solicitante"})
    
    # V2: Validar longitud de campos de texto
    desc = registro.get('descripcion_completa', '')
    if len(desc) > 500:
        validaciones.append({"tipo": "warning", "mensaje": f"Descripción muy larga ({len(desc)} caracteres, máximo recomendado: 500)"})
    
    solicitante = registro.get('solicitante', '')
    if len(solicitante) > 200:
        validaciones.append({"tipo": "warning", "mensaje": f"Nombre del solicitante muy largo ({len(solicitante)} caracteres)"})
    
    # V3: Validar formato de número RFQ (debe ser numérico)
    rfq_num = registro.get('rfq', '')
    if rfq_num and not rfq_num.isdigit():
        validaciones.append({"tipo": "error", "mensaje": f"Número de RFQ inválido: '{rfq_num}' (debe ser numérico)"})
    
    # V4: Validar fecha de OC si existe
    fecha_oc_str = registro.get('fecha_oc', '')
    if fecha_oc_str:
        try:
            fecha_oc = pd.to_datetime(fecha_oc_str).date() if isinstance(fecha_oc_str, str) else fecha_oc_str
            hoy = date.today()
            
            # Fecha de OC no debe ser muy antigua (más de 2 años)
            if fecha_oc < (hoy - timedelta(days=730)):
                validaciones.append({"tipo": "warning", "mensaje": f"Fecha de OC muy antigua: {fecha_oc}"})
            
            # Fecha de OC no debe ser futura (más de 1 mes)
            if fecha_oc > (hoy + timedelta(days=30)):
                validaciones.append({"tipo": "warning", "mensaje": f"Fecha de OC futura: {fecha_oc}"})
        except:
            validaciones.append({"tipo": "error", "mensaje": f"Fecha de OC inválida: {fecha_oc_str}"})
    
    # V5: Validar que si hay OC, debe haber proveedor seleccionado
    num_oc = registro.get('numero_oc', '')
    proveedor = registro.get('proveedor_seleccionado', '')
    if num_oc and not proveedor:
        validaciones.append({"tipo": "warning", "mensaje": "Tiene # de OC pero falta proveedor seleccionado"})
    
    # V6: Si hay OC pero no hay fecha, advertir
    if num_oc and not fecha_oc_str:
        validaciones.append({"tipo": "warning", "mensaje": "Tiene # de OC pero falta fecha de OC"})
    
    # V7: Alertas de cambios significativos (solo si es actualización)
    if rfq_existente:
        # Cambio de planta
        if registro.get('planta_codigo') != rfq_existente.planta:
            validaciones.append({"tipo": "warning", "mensaje": f"Cambio de planta: {rfq_existente.get_planta_display()} → {registro.get('planta')}"})
        
        # Cambio de solicitante
        if registro.get('solicitante') != (rfq_existente.solicitante or ''):
            validaciones.append({"tipo": "warning", "mensaje": f"Cambio de solicitante: '{rfq_existente.solicitante}' → '{registro.get('solicitante')}'"})
    
    return validaciones


def previsualizar_rfq_excel(archivo_excel) -> dict:
    """
    Analiza un archivo Excel de RFQ/CAPEX sin modificar la base de datos.
    
    Retorna un diccionario con:
    - registros: lista de diccionarios con datos parseados y estado (nuevo/actualizar/duplicado/error)
    - resumen: contadores por categoría
    - errores: lista de mensajes de error
    """
    try:
        df = pd.read_excel(archivo_excel, sheet_name=0)
    except Exception as e:
        return {
            "registros": [],
            "resumen": {"total": 0, "nuevos": 0, "actualizar": 0, "duplicados": 0, "errores": 0},
            "errores": [f"Error al leer archivo Excel: {str(e)}"],
        }

    # Si la fila 0 contiene las cabeceras reales (caso tabla de seguimiento de Edith)
    if df.shape[0] > 0 and any('RFQ' in str(x).upper() for x in df.iloc[0].values if pd.notna(x)):
        if 'RFQ' not in [str(c).strip().upper() for c in df.columns]:
            df.columns = [str(x).strip() for x in df.iloc[0].values]
            df = df.iloc[1:].reset_index(drop=True)

    registros = []
    resumen = {"total": 0, "nuevos": 0, "actualizar": 0, "duplicados": 0, "errores": 0}
    errores = []

    # Obtener todos los RFQ existentes de una sola vez para comparación
    rfqs_existentes = {rfq.rfq: rfq for rfq in RFQCapex.objects.all()}

    for index, row in df.iterrows():
        try:
            # Buscar el número de RFQ en diferentes variantes de columna
            rfq_raw = None
            for col_name in ['RFQ', 'Request #', 'PEDIDO', 'numero_rfq', 'rfq']:
                if col_name in row and pd.notna(row[col_name]):
                    rfq_raw = row[col_name]
                    break

            if pd.isna(rfq_raw) or rfq_raw is None:
                continue

            # Limpiar el valor eliminando '#' y decimales
            num_rfq = str(int(rfq_raw) if isinstance(rfq_raw, float) else rfq_raw).strip().replace('#', '')
            if not num_rfq or num_rfq.lower() == 'nan':
                continue

            # Parsear datos (normalizar 'nan' como cadena vacía)
            def extraer_texto(valor):
                if pd.isna(valor) or valor is None:
                    return ''
                texto = str(valor).strip()
                return '' if texto.lower() == 'nan' else texto
            
            desc = extraer_texto(row.get('DESCRIPCION') or row.get('Breve descripción de la solicitud de CapEx'))
            solicitante = extraer_texto(row.get('SOLICITANTE') or row.get('Nombre del Solicitante'))
            planta_str = extraer_texto(row.get('PLANTA') or row.get('Selecciona Unidad de Negocio') or row.get('Planta'))
            
            # Normalizar Planta a Choice
            planta_enum = RFQCapex.Planta.MAQ_RA
            if 'TENANGO' in planta_str.upper():
                planta_enum = RFQCapex.Planta.MACIMEX_TENANGO
            planta_display = dict(RFQCapex.Planta.choices).get(planta_enum, planta_enum)

            proyecto = extraer_texto(row.get('PROYECTO') or row.get('Clave del proyecto o Numero de CapEx'))
            comparativa = extraer_texto(row.get('COMPARATIVA') or row.get('Aprobación de Capex'))
            proveedor_sel = extraer_texto(row.get('PROVEEDOR SELECCIONADO') or row.get('Proveedores Sugeridos'))
            num_oc = extraer_texto(row.get('#OC'))

            fecha_oc_val = row.get('FECHA DE OC')
            fecha_oc = pd.to_datetime(fecha_oc_val).date() if pd.notnull(fecha_oc_val) else None

            # Determinar estado: nuevo, actualizar o duplicado
            rfq_existente = rfqs_existentes.get(num_rfq)
            if rfq_existente:
                # Normalizar valores para comparación (tratar '' como igual que ausencia de dato)
                desc_actual = rfq_existente.descripcion or ''
                solic_actual = rfq_existente.solicitante or ''
                capex_actual = rfq_existente.clave_capex or ''
                
                desc_nuevo = desc or ''
                solic_nuevo = solicitante or ''
                capex_nuevo = proyecto or ''
                
                # Comparar si hay cambios reales
                tiene_cambios = (
                    desc_actual != desc_nuevo or
                    solic_actual != solic_nuevo or
                    rfq_existente.planta != planta_enum or
                    capex_actual != capex_nuevo
                )
                estado = "actualizar" if tiene_cambios else "duplicado"
            else:
                estado = "nuevo"

            registro = {
                "fila": index + 2,  # +2 porque Excel empieza en 1 y puede haber fila de cabecera
                "rfq": num_rfq,
                "descripcion": desc[:60] + "..." if len(desc) > 60 else desc,
                "descripcion_completa": desc,
                "solicitante": solicitante,
                "planta": planta_display,
                "planta_codigo": planta_enum,
                "clave_capex": proyecto,
                "comparativa": comparativa if comparativa.lower() != 'nan' else '',
                "proveedor_seleccionado": proveedor_sel if proveedor_sel.lower() != 'nan' else '',
                "numero_oc": num_oc if num_oc.lower() != 'nan' else '',
                "fecha_oc": fecha_oc.isoformat() if fecha_oc else '',
                "estado": estado,
            }
            
            # Ejecutar validaciones de negocio
            validaciones = validar_registro_rfq(registro, rfq_existente)
            
            # Si hay errores críticos, cambiar estado a "error"
            tiene_errores = any(v["tipo"] == "error" for v in validaciones)
            if tiene_errores:
                estado = "error"
                registro["estado"] = "error"
            
            # Agregar validaciones al registro
            registro["validaciones"] = validaciones
            registro["tiene_errores"] = tiene_errores
            registro["tiene_warnings"] = any(v["tipo"] == "warning" for v in validaciones)

            registros.append(registro)
            resumen["total"] += 1
            
            # Incrementar contador según estado final
            if estado == "error":
                resumen["errores"] += 1
            elif estado == "nuevo":
                resumen["nuevos"] += 1
            elif estado == "actualizar":
                resumen["actualizar"] += 1
            elif estado == "duplicado":
                resumen["duplicados"] += 1

        except Exception as e:
            error_msg = f"Fila {index + 2}: {str(e)}"
            errores.append(error_msg)
            registros.append({
                "fila": index + 2,
                "rfq": "ERROR",
                "descripcion": str(e),
                "estado": "error",
            })
            resumen["errores"] += 1

    return {
        "registros": registros,
        "resumen": resumen,
        "errores": errores,
    }
