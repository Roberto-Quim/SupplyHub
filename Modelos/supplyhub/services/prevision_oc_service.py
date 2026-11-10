"""
Servicio de previsualización para importación de Órdenes de Compra Oracle QES.
Analiza el archivo Excel antes de importar, clasificando registros como nuevos,
actualizaciones o duplicados, y validando posibles errores.
"""
import pandas as pd
from datetime import date, timedelta
from supplyhub.models import OrdenCompra, LineaOC
from .seguimiento_oc_service import normalizar_planta


def validar_linea_oc(datos: dict, linea_existente=None) -> list:
    """
    Valida una línea de OC según reglas de negocio.
    
    Retorna lista de advertencias/errores:
    - Tipo 'error': Bloquea importación
    - Tipo 'warning': Permite importación pero alerta
    
    Args:
        datos: dict con datos parseados de la línea
        linea_existente: instancia de LineaOC si existe, None si es nueva
    
    Returns:
        Lista de dicts: [{"tipo": "error|warning", "mensaje": "..."}]
    """
    validaciones = []
    
    # V1: Validar proveedor no vacío
    proveedor = datos.get('proveedor', '')
    if not proveedor or proveedor.lower() == 'nan':
        validaciones.append({"tipo": "error", "mensaje": "Falta nombre del proveedor"})
    
    # V2: Validar cantidades no negativas
    cant_sol = datos.get('cant_sol', 0)
    cant_due = datos.get('cant_due', 0)
    cant_rec = datos.get('cant_rec', 0)
    
    if cant_sol < 0:
        validaciones.append({"tipo": "error", "mensaje": f"Cantidad solicitada negativa: {cant_sol}"})
    if cant_due < 0:
        validaciones.append({"tipo": "error", "mensaje": f"Cantidad pendiente negativa: {cant_due}"})
    if cant_rec < 0:
        validaciones.append({"tipo": "error", "mensaje": f"Cantidad recibida negativa: {cant_rec}"})
    
    # V3: Cantidad pendiente no debe exceder cantidad solicitada
    if cant_due > cant_sol:
        validaciones.append({"tipo": "warning", "mensaje": f"Cantidad pendiente ({cant_due}) mayor que solicitada ({cant_sol})"})
    
    # V4: Cantidad recibida + pendiente debe ser ~igual a solicitada
    suma_cant = cant_rec + cant_due
    if abs(suma_cant - cant_sol) > 0.01:  # Tolerancia para decimales
        validaciones.append({"tipo": "warning", "mensaje": f"Suma de recibida ({cant_rec}) + pendiente ({cant_due}) = {suma_cant} ≠ solicitada ({cant_sol})"})
    
    # V5: Validar precio unitario
    precio = datos.get('precio', 0)
    if precio < 0:
        validaciones.append({"tipo": "error", "mensaje": f"Precio unitario negativo: {precio}"})
    if precio == 0 and cant_sol > 0:
        validaciones.append({"tipo": "warning", "mensaje": "Precio unitario en cero con cantidad solicitada"})
    
    # V6: Validar fecha Need By
    fecha_original = datos.get('fecha_original')
    if fecha_original:
        hoy = date.today()
        
        # Fecha muy antigua (más de 2 años en el pasado)
        if fecha_original < (hoy - timedelta(days=730)):
            validaciones.append({"tipo": "warning", "mensaje": f"Fecha Need By muy antigua: {fecha_original}"})
        
        # Si hay cantidad pendiente y fecha ya pasó, alertar
        if cant_due > 0 and fecha_original < hoy:
            dias_retraso = (hoy - fecha_original).days
            if dias_retraso > 7:
                validaciones.append({"tipo": "warning", "mensaje": f"Línea vencida: {dias_retraso} días de retraso"})
    
    # V7: Validar descripción y código de artículo
    descripcion = datos.get('descripcion', '')
    codigo_articulo = datos.get('codigo_articulo', '')
    
    if not descripcion and not codigo_articulo:
        validaciones.append({"tipo": "warning", "mensaje": "Falta descripción y código de artículo"})
    
    # V8: Alertas de cambios significativos (solo si es actualización)
    if linea_existente:
        # Cambio significativo en precio (>20%)
        precio_actual = float(linea_existente.precio_unitario) if linea_existente.precio_unitario else 0.0
        if precio_actual > 0 and precio > 0:
            cambio_precio_pct = abs((precio - precio_actual) / precio_actual) * 100
            if cambio_precio_pct > 20:
                validaciones.append({"tipo": "warning", "mensaje": f"Cambio significativo en precio: {cambio_precio_pct:.1f}% ({precio_actual} → {precio})"})
        
        # Cambio de fecha que alarga entrega
        if linea_existente.fecha_original and fecha_original:
            dias_cambio = (fecha_original - linea_existente.fecha_original).days
            if dias_cambio > 7:
                validaciones.append({"tipo": "warning", "mensaje": f"Fecha de entrega pospuesta: +{dias_cambio} días"})
        
        # Reducción significativa de cantidad pendiente (posible surtido parcial)
        cant_pendiente_actual = float(linea_existente.cantidad_pendiente) if linea_existente.cantidad_pendiente else 0.0
        if cant_pendiente_actual > 0 and cant_due < cant_pendiente_actual:
            reduccion = cant_pendiente_actual - cant_due
            validaciones.append({"tipo": "warning", "mensaje": f"Reducción cantidad pendiente: {cant_pendiente_actual} → {cant_due} (-{reduccion})"})
    
    return validaciones


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
            oc_existente = None
            linea_existente = None
            
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
            
            # === VALIDACIONES DE NEGOCIO ===
            datos_validacion = {
                'proveedor': proveedor,
                'cant_sol': float(cant_sol) if pd.notnull(cant_sol) else 0.0,
                'cant_due': float(cant_due) if pd.notnull(cant_due) else 0.0,
                'cant_rec': float(cant_rec) if pd.notnull(cant_rec) else 0.0,
                'precio': float(unit_price) if pd.notnull(unit_price) else 0.0,
                'fecha_original': fecha_original,
                'descripcion': descripcion,
                'codigo_articulo': codigo_articulo
            }
            
            # Buscar línea existente si hay OC existente
            linea_existente_validacion = None
            if oc_existente and linea_existente:
                linea_existente_validacion = linea_existente
            
            validaciones = validar_linea_oc(datos_validacion, linea_existente_validacion)
            
            # Si hay errores críticos, cambiar estado a "error"
            tiene_errores = any(v["tipo"] == "error" for v in validaciones)
            if tiene_errores and estado != "error":
                estado = "error"
                razon = "; ".join([v["mensaje"] for v in validaciones if v["tipo"] == "error"])
            
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
                "razon": razon,
                "validaciones": validaciones,
                "tiene_errores": tiene_errores,
                "tiene_warnings": any(v["tipo"] == "warning" for v in validaciones)
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
