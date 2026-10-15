import pandas as pd
from django.db import transaction
from supplyhub.models import OrdenCompra, LineaOC
from .seguimiento_oc_service import normalizar_planta

def importar_oracle_open_po(archivo_excel, usuario_responsable: str) -> dict:
    try:
        df = pd.read_excel(archivo_excel, sheet_name='Data')
    except Exception:
        df = pd.read_excel(archivo_excel)
    
    resumen = {"procesados": 0, "insertados_oc": 0, "insertados_linea": 0, "actualizados": 0, "errores": []}

    with transaction.atomic():
        for index, row in df.iterrows():
            try:
                with transaction.atomic():
                    po_val = row.get('Po Number')
                    if pd.isna(po_val):
                        continue
                
                    numero_oc = str(int(po_val) if isinstance(po_val, float) else po_val).strip()
                    if not numero_oc or numero_oc == 'nan':
                        continue

                    planta_orig = str(row.get('Ship To Org Name', '')).strip()
                    planta_norm = normalizar_planta(planta_orig)
                    proveedor = str(row.get('Supplier Name', '')).strip()
                    comprador = str(row.get('Buyer Full Name', '')).strip()
                    estatus_auth = str(row.get('Authorization Status', '')).strip()
                    moneda = str(row.get('C Currency', '')).strip()
                
                    fecha_creation = row.get('Rel Creation Date')
                    fecha_creacion_po = pd.to_datetime(fecha_creation).date() if pd.notnull(fecha_creation) else None

                    orden, oc_creada = OrdenCompra.objects.update_or_create(
                        numero_oc=numero_oc,
                        sistema_origen="ORACLE_QES",
                        defaults={
                            'proveedor': proveedor,
                            'planta_original': planta_orig,
                            'planta_normalizada': planta_norm,
                            'comprador': comprador if comprador != 'nan' else '',
                            'estatus_autorizacion': estatus_auth if estatus_auth != 'nan' else '',
                            'moneda': moneda if moneda != 'nan' else '',
                            'fecha_creacion_po': fecha_creacion_po,
                        }
                    )
                    if oc_creada:
                        resumen["insertados_oc"] += 1
                
                    rel_val = row.get('Release Number')
                    release = "" if pd.isna(rel_val) else str(int(rel_val) if isinstance(rel_val, float) else rel_val).strip()
                    num_linea = str(int(row.get('Line Number', 1))).strip()
                
                    cant_sol = pd.to_numeric(row.get('Quantity Ordered', 0), errors='coerce')
                    cant_due = pd.to_numeric(row.get('Quantity due', 0), errors='coerce')
                    cant_rec = pd.to_numeric(row.get('Quantity Received', 0), errors='coerce')
                    unit_price = pd.to_numeric(row.get('Unit Price', 0), errors='coerce')

                    fecha_need = row.get('Need By Date')
                    fecha_original = pd.to_datetime(fecha_need).date() if pd.notnull(fecha_need) else None

                    correo = str(row.get('Correo Proveedor', '')).strip()

                    linea, linea_creada = LineaOC.objects.update_or_create(
                        orden=orden,
                        release=release,
                        numero_linea=num_linea,
                        defaults={
                            'codigo_articulo': str(row.get('Item', '')).strip(),
                            'descripcion': str(row.get('Item Description', '')).strip(),
                            'unidad_medida': str(row.get('Unit Of Measure', '')).strip(),
                            'ubicacion_entrega': planta_orig,
                            'cantidad_solicitada': cant_sol if pd.notnull(cant_sol) else 0,
                            'cantidad_pendiente': cant_due if pd.notnull(cant_due) else 0,
                            'cantidad_recibida': cant_rec if pd.notnull(cant_rec) else 0,
                            'precio_unitario': unit_price if pd.notnull(unit_price) else 0,
                            'estatus_necesidad': str(row.get('Status need', '')).strip(),
                            'fecha_original': fecha_original,
                            'fecha_comprometida': fecha_original,
                        }
                    )
                
                    if correo and correo.lower() != 'nan':
                        linea.correo_proveedor = correo
                        linea.save(update_fields=['correo_proveedor'])

                    if linea_creada:
                        resumen["insertados_linea"] += 1
                    else:
                        resumen["actualizados"] += 1

                    resumen["procesados"] += 1
            except Exception as e:
                resumen["errores"].append(f"Fila {index + 2}: {str(e)}")

    return resumen