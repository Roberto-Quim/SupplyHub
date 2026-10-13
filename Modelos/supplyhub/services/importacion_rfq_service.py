import pandas as pd
from django.db import transaction
from supplyhub.models import RFQCapex

def importar_rfq_capex_excel(archivo_excel, usuario_responsable: str) -> dict:
    try:
        df = pd.read_excel(archivo_excel, sheet_name=0)
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo Excel: {str(e)}")

    resumen = {"procesados": 0, "insertados": 0, "actualizados": 0, "errores": []}

    # Si la fila 0 contiene las cabeceras reales (caso tabla de seguimiento de Edith)
    if df.shape[0] > 0 and any('RFQ' in str(x).upper() for x in df.iloc[0].values if pd.notna(x)):
        if 'RFQ' not in [str(c).strip().upper() for c in df.columns]:
            df.columns = [str(x).strip() for x in df.iloc[0].values]
            df = df.iloc[1:].reset_index(drop=True)

    with transaction.atomic():
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

                desc = str(row.get('DESCRIPCION') or row.get('Breve descripción de la solicitud de CapEx') or '').strip()
                solicitante = str(row.get('SOLICITANTE') or row.get('Nombre del Solicitante') or '').strip()
                planta_str = str(row.get('PLANTA') or row.get('Selecciona Unidad de Negocio') or row.get('Planta') or '').strip()
                
                # Normalizar Planta a Choice
                planta_enum = RFQCapex.Planta.MAQ_RA
                if 'TENANGO' in planta_str.upper():
                    planta_enum = RFQCapex.Planta.MACIMEX_TENANGO

                proyecto = str(row.get('PROYECTO') or row.get('Clave del proyecto o Numero de CapEx') or '').strip()
                estatus = str(row.get('ESTATUS') or row.get('Overall Status') or row.get('Estatus') or 'Solicitada').strip()

                comparativa = str(row.get('COMPARATIVA') or row.get('Aprobación de Capex') or '').strip()
                proveedor_sel = str(row.get('PROVEEDOR SELECCIONADO') or row.get('Proveedores Sugeridos') or '').strip()
                num_oc = str(row.get('#OC') or '').strip().replace('#', '')

                fecha_oc_val = row.get('FECHA DE OC')
                fecha_oc = pd.to_datetime(fecha_oc_val).date() if pd.notnull(fecha_oc_val) else None

                fecha_tent_val = row.get('FECHA TENTATIVA DE ENTREGA')
                fecha_tentativa = pd.to_datetime(fecha_tent_val).date() if pd.notnull(fecha_tent_val) else None

                fecha_ent_val = row.get('FECHA DE ENTREGA') or row.get('Fecha de cierre real')
                fecha_entrega = pd.to_datetime(fecha_ent_val).date() if pd.notnull(fecha_ent_val) else None

                en_tiempo = str(row.get('EN TIEMPO') or '').strip()
                
                tiempo_tot_val = row.get('TIEMPO TOTAL') or row.get('Días de respuesta')
                tiempo_tot = int(pd.to_numeric(tiempo_tot_val, errors='coerce')) if pd.notnull(tiempo_tot_val) and not pd.isna(tiempo_tot_val) else None

                rfq_obj, creado = RFQCapex.objects.update_or_create(
                    rfq=num_rfq,
                    defaults={
                        'descripcion': desc,
                        'solicitante': solicitante,
                        'planta': planta_enum,
                        'clave_capex': proyecto,
                        'comparativa': comparativa if comparativa.lower() != 'nan' else '',
                        'proveedor_seleccionado': proveedor_sel if proveedor_sel.lower() != 'nan' else '',
                        'numero_oc': num_oc if num_oc.lower() != 'nan' else '',
                        'fecha_oc': fecha_oc,
                        'fecha_tentativa_entrega': fecha_tentativa,
                        'fecha_entrega': fecha_entrega,
                        'en_tiempo': en_tiempo if en_tiempo.lower() != 'nan' else '',
                        'tiempo_total': tiempo_tot,
                        'creado_por': usuario_responsable,
                        'actualizado_por': usuario_responsable,
                    }
                )

                if creado:
                    resumen["insertados"] += 1
                else:
                    resumen["actualizados"] += 1

                resumen["procesados"] += 1

            except Exception as e:
                resumen["errores"].append(f"Fila {index + 2}: {str(e)}")

    return resumen