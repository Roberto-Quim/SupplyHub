"""
Servicio de previsualización para importación de Órdenes de Compra Oracle QES.
Analiza el archivo Excel antes de importar, clasificando registros como nuevos,
actualizaciones o duplicados, y validando posibles errores.
"""
import pandas as pd
from supplyhub.models import OrdenCompra, LineaOC
from .seguimiento_oc_service import normalizar_planta


def previsualizar_oracle_open_po(archivo_excel) -> dict:
    """
    Previsualiza importación de archivo Excel QES Open Purchase Order Report.
    
    Clasifica cada línea como:
    - nuevo: OC nueva o línea nueva que se insertará
    - actualizar: línea existente con datos modificados
    - duplicado: línea ya existente con datos idénticos
    - error: fila con problemas de validación
    
    Args:
        archivo_excel: archivo Excel cargado (Django UploadedFile)
    
    Returns:
        dict con keys:
            - registros: lista de dicts con info de cada registro
            - resumen: dict con contadores (nuevos, actualizar, duplicados, errores)
            - errores: lista de mensajes de error
    """
    try:
        df = pd.read_excel(archivo_excel, sheet_name='Data')
    except Exception:
        try:
            df = pd.read_excel(archivo_excel)
        except Exception as e:
            return {
                "registros": [],
                "resumen": {"nuevos": 0, "actualizar": 0, "duplicados": 0, "errores": 1},
                "errores": [f"No se pudo leer el archivo Excel: {str(e)}"]
            }
    
    registros = []
    resumen = {"nuevos": 0, "actualizar": 0, "duplicados": 0, "errores": 0}
    errores_globales = []

    for index, row in df.iterrows():
        fila_num = index + 2  # +2 porque Excel empieza en 1 y hay fila de encabezados
        
        try:
            # === VALIDACIÓN DE CAMPOS OBLIGATORIOS ===
            po_val = row.get('Po Number')
            if pd.isna(po_val):
                registros.append({
                    "fila": fila_num,
                    "numero_oc": "N/A",
                    "release": "",
                    "numero_linea": "",
                    "descripcion": "",
                    "proveedor": "",
                    "planta": "",
                    "estado": "error",
                    "razon": "Falta número de OC (Po Number)"
                })
                resumen["errores"] += 1
                continue
            
            numero_oc = str(int(po_val) if isinstance(po_val, float) else po_val).strip()
            if not numero_oc or numero_oc == 'nan':
                registros.append({
                    "fila": fila_num,
                    "numero_oc": "N/A",
                    "release": "",
                    "numero_linea": "",
                    "descripcion": "",
                    "proveedor": "",
                    "planta": "",
                    "estado": "error",
                    "razon": "Número de OC vacío o inválido"
                })
                resumen["errores"] += 1
                continue

            # === EXTRACCIÓN DE CAMPOS ===
            rel_val = row.get('Release Number')
            release = "" if pd.isna(rel_val) else str(int(rel_val) if isinstance(rel_val, float) else rel_val).strip()
            num_linea = str(int(row.get('Line Number', 1))).strip()
            
            def extraer_texto(campo, default=''):
                """Extrae texto del row, normalizando valores vacíos/nulos"""
                val = row.get(campo, default)
                if pd.isna(val) or val == '' or str(val).strip().lower() == 'nan':
                    return ""
                return str(val).strip()
            
            planta_orig = extraer_texto('Ship To Org Name')
            planta_norm = normalizar_planta(planta_orig)
            proveedor = extraer_texto('Supplier Name')
            descripcion = extraer_texto('Item Description')
            codigo_articulo = extraer_texto('Item')
            comprador = extraer_texto('Buyer Full Name')
            estatus_auth = extraer_texto('Authorization Status')
            moneda = extraer_texto('C Currency')
            unidad_medida = extraer_texto('Unit Of Measure')
            estatus_necesidad = extraer_texto('Status need')
            correo = extraer_texto('Correo Proveedor')
            
            cant_sol = pd.to_numeric(row.get('Quantity Ordered', 0), errors='coerce')
            cant_due = pd.to_numeric(row.get('Quantity due', 0), errors='coerce')
            cant_rec = pd.to_numeric(row.get('Quantity Received', 0), errors='coerce')
            unit_price = pd.to_numeric(row.get('Unit Price', 0), errors='coerce')

            fecha_creation = row.get('Rel Creation Date')
            fecha_creacion_po = pd.to_datetime(fecha_creation).date() if pd.notnull(fecha_creation) else None

            fecha_need = row.get('Need By Date')
            fecha_original = pd.to_datetime(fecha_need).date() if pd.notnull(fecha_need) else None

            # === CLASIFICACIÓN: NUEVO, ACTUALIZAR o DUPLICADO ===
            estado = "nuevo"
            razon = ""
            
            try:
                # Buscar OC existente
                oc_existente = OrdenCompra.objects.filter(
                    numero_oc=numero_oc,
                    sistema_origen="ORACLE_QES"
                ).first()
                
                if oc_existente:
                    # La OC existe, verificar si la línea existe
                    linea_existente = LineaOC.objects.filter(
                        orden=oc_existente,
                        release=release,
                        numero_linea=num_linea
                    ).first()
                    
                    if linea_existente:
                        # Comparar campos relevantes para detectar cambios
                        # Normalizar valores vacíos: None, "", "nan" se consideran iguales
                        def normalizar(val):
                            if val is None or val == "" or (isinstance(val, str) and val.lower() == "nan"):
                                return ""
                            return str(val).strip()
                        
                        campos_cambiados = []
                        
                        # Comparar campos de texto
                        if normalizar(linea_existente.codigo_articulo) != normalizar(codigo_articulo):
                            campos_cambiados.append("codigo_articulo")
                        if normalizar(linea_existente.descripcion) != normalizar(descripcion):
                            campos_cambiados.append("descripcion")
                        if normalizar(linea_existente.unidad_medida) != normalizar(unidad_medida):
                            campos_cambiados.append("unidad_medida")
                        if normalizar(linea_existente.estatus_necesidad) != normalizar(estatus_necesidad):
                            campos_cambiados.append("estatus_necesidad")
                        if normalizar(linea_existente.correo_proveedor) != normalizar(correo):
                            campos_cambiados.append("correo_proveedor")
                        
                        # Comparar cantidades (convertir todo a float para evitar problemas Decimal vs int)
                        cant_sol_actual = float(linea_existente.cantidad_solicitada) if linea_existente.cantidad_solicitada else 0.0
                        cant_due_actual = float(linea_existente.cantidad_pendiente) if linea_existente.cantidad_pendiente else 0.0
                        cant_rec_actual = float(linea_existente.cantidad_recibida) if linea_existente.cantidad_recibida else 0.0
                        precio_actual = float(linea_existente.precio_unitario) if linea_existente.precio_unitario else 0.0
                        
                        cant_sol_nueva = float(cant_sol) if pd.notnull(cant_sol) else 0.0
                        cant_due_nueva = float(cant_due) if pd.notnull(cant_due) else 0.0
                        cant_rec_nueva = float(cant_rec) if pd.notnull(cant_rec) else 0.0
                        precio_nuevo = float(unit_price) if pd.notnull(unit_price) else 0.0
                        
                        if cant_sol_actual != cant_sol_nueva:
                            campos_cambiados.append("cantidad_solicitada")
                        if cant_due_actual != cant_due_nueva:
                            campos_cambiados.append("cantidad_pendiente")
                        if cant_rec_actual != cant_rec_nueva:
                            campos_cambiados.append("cantidad_recibida")
                        if precio_actual != precio_nuevo:
                            campos_cambiados.append("precio_unitario")
                        
                        # Comparar fechas
                        if linea_existente.fecha_original != fecha_original:
                            campos_cambiados.append("fecha_original")
                        
                        if campos_cambiados:
                            estado = "actualizar"
                            razon = f"Campos modificados: {', '.join(campos_cambiados)}"
                        else:
                            estado = "duplicado"
                            razon = "Registro idéntico ya existe"
                    else:
                        estado = "nuevo"
                        razon = f"Línea nueva para OC existente #{numero_oc}"
                else:
                    estado = "nuevo"
                    razon = f"OC nueva #{numero_oc}"
                    
            except Exception as e:
                estado = "error"
                razon = f"Error al verificar registro: {str(e)}"
            
            # Construir registro de previsualización
            registros.append({
                "fila": fila_num,
                "numero_oc": numero_oc,
                "release": release,
                "numero_linea": num_linea,
                "descripcion": descripcion[:60] + "..." if len(descripcion) > 60 else descripcion,
                "proveedor": proveedor[:40] + "..." if len(proveedor) > 40 else proveedor,
                "planta": planta_orig[:30] + "..." if len(planta_orig) > 30 else planta_orig,
                "estado": estado,
                "razon": razon
            })
            
            # Actualizar contadores
            if estado == "nuevo":
                resumen["nuevos"] += 1
            elif estado == "actualizar":
                resumen["actualizar"] += 1
            elif estado == "duplicado":
                resumen["duplicados"] += 1
            elif estado == "error":
                resumen["errores"] += 1
                
        except Exception as e:
            # Error inesperado procesando la fila
            registros.append({
                "fila": fila_num,
                "numero_oc": "N/A",
                "release": "",
                "numero_linea": "",
                "descripcion": "",
                "proveedor": "",
                "planta": "",
                "estado": "error",
                "razon": f"Error al procesar fila: {str(e)}"
            })
            resumen["errores"] += 1
            errores_globales.append(f"Fila {fila_num}: {str(e)}")
    
    return {
        "registros": registros,
        "resumen": resumen,
        "errores": errores_globales
    }
