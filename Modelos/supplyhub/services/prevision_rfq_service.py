"""Servicio de previsualización de importación RFQ/CAPEX antes de confirmar."""

import pandas as pd
from supplyhub.models import RFQCapex


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

            # Parsear datos
            desc = str(row.get('DESCRIPCION') or row.get('Breve descripción de la solicitud de CapEx') or '').strip()
            solicitante = str(row.get('SOLICITANTE') or row.get('Nombre del Solicitante') or '').strip()
            planta_str = str(row.get('PLANTA') or row.get('Selecciona Unidad de Negocio') or row.get('Planta') or '').strip()
            
            # Normalizar Planta a Choice
            planta_enum = RFQCapex.Planta.MAQ_RA
            if 'TENANGO' in planta_str.upper():
                planta_enum = RFQCapex.Planta.MACIMEX_TENANGO
            planta_display = dict(RFQCapex.Planta.choices).get(planta_enum, planta_enum)

            proyecto = str(row.get('PROYECTO') or row.get('Clave del proyecto o Numero de CapEx') or '').strip()
            comparativa = str(row.get('COMPARATIVA') or row.get('Aprobación de Capex') or '').strip()
            proveedor_sel = str(row.get('PROVEEDOR SELECCIONADO') or row.get('Proveedores Sugeridos') or '').strip()
            num_oc = str(row.get('#OC') or '').strip().replace('#', '')

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

            registros.append(registro)
            resumen["total"] += 1
            
            # Incrementar contador según estado
            if estado == "nuevo":
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
