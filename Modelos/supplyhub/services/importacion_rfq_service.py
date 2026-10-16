"""Importación RFQ con celdas vacías normalizadas y auditoría de estados."""
import pandas as pd
from django.db import transaction
from supplyhub.models import RFQCapex
from .rfq_capex_service import create_rfq, update_rfq, change_status, normalize_plant, _plain


def importar_rfq_capex_excel(archivo_excel, usuario_responsable):
    try:
        frame = pd.read_excel(archivo_excel, sheet_name=0)
    except Exception as exc:
        raise ValueError('No se pudo leer el archivo Excel.') from exc
    if len(frame) and any('RFQ' in str(v).upper() for v in frame.iloc[0] if pd.notna(v)) and 'RFQ' not in [str(c).strip().upper() for c in frame.columns]:
        frame.columns = [str(v).strip() for v in frame.iloc[0]]
        frame = frame.iloc[1:].reset_index(drop=True)
    summary = dict(procesados=0, insertados=0, actualizados=0, errores=[])
    def cell(row, *names):
        for name in names:
            value = row.get(name)
            if value is not None and pd.notna(value) and str(value).strip():
                return value
        return None
    def text(value):
        if value is None:
            return ''
        if isinstance(value,float) and value.is_integer():
            return str(int(value))
        return str(value).strip()
    def date_value(value):
        return pd.to_datetime(value,errors='raise').date() if value is not None else None
    if not any(c in frame.columns for c in ['RFQ','Request #','PEDIDO','numero_rfq','rfq']):
        raise ValueError('No se encontró una columna RFQ/Pedido.')
    for index,row in frame.iterrows():
        number = text(cell(row,'RFQ','Request #','PEDIDO','numero_rfq','rfq')).replace('#','').strip()
        if not number:
            continue
        try:
            with transaction.atomic():
                existing = RFQCapex.objects.select_for_update().filter(rfq=number)
                if existing.count() > 1:
                    raise ValueError('Hay RFQ duplicadas; se requiere revisión.')
                obj = existing.first()
                data = {'rfq':number}
                fields = {
                    'descripcion':['DESCRIPCION','Breve descripción de la solicitud de CapEx'],
                    'solicitante':['SOLICITANTE','Nombre del Solicitante'],
                    'correo_solicitante':['Dirección de correo electrónico'],
                    'clave_capex':['PROYECTO','Clave del proyecto o Numero de CapEx'],
                    'comparativa':['COMPARATIVA','Aprobación de Capex'],
                    'proveedor_seleccionado':['PROVEEDOR SELECCIONADO','Proveedores Sugeridos'],
                    'numero_oc':['#OC'], 'en_tiempo':['EN TIEMPO'],
                }
                for field,names in fields.items():
                    value = cell(row,*names)
                    if value is not None or obj is None:
                        data[field] = text(value)
                plant_raw = cell(row,'PLANTA','Selecciona Unidad de Negocio','Planta')
                if plant_raw is not None or obj is None:
                    plant = normalize_plant(text(plant_raw))
                    if plant is None:
                        raise ValueError('Planta no reconocida.')
                    data['planta'] = plant
                for field,names in {
                    'fecha_oc':['FECHA DE OC'],
                    'fecha_tentativa_entrega':['FECHA TENTATIVA DE ENTREGA'],
                    'fecha_entrega':['FECHA DE ENTREGA','Fecha de cierre real'],
                    'fecha_arranque':['FECHA DE ARRANQUE','Timestamp'],
                }.items():
                    value = cell(row,*names)
                    if value is not None:
                        data[field] = date_value(value)
                total = cell(row,'TIEMPO TOTAL','Días de respuesta')
                if total is not None:
                    numeric = pd.to_numeric(total, errors='raise')
                    if numeric < 0 or int(numeric) != numeric:
                        raise ValueError('El tiempo total debe ser un entero no negativo.')
                    data['tiempo_total'] = int(numeric)
                raw_status = cell(row,'ESTATUS','Overall Status','Estatus')
                status = None
                if raw_status is not None:
                    states = {_plain(label): value for value,label in RFQCapex.Estado.choices}
                    states.update({_plain(value):value for value,_ in RFQCapex.Estado.choices})
                    status = states.get(_plain(text(raw_status)))
                    if status is None:
                        raise ValueError('Estatus no reconocido.')
                created = obj is None
                if created:
                    obj = create_rfq(cleaned_data=data,actor=usuario_responsable)
                    obj.origen = RFQCapex.Origen.SHEET
                    obj.identificador_origen = number
                    obj.save(update_fields=['origen','identificador_origen'])
                else:
                    update_rfq(instance=obj,cleaned_data=data,actor=usuario_responsable)
                if status:
                    change_status(instance=obj,new_status=status,actor=usuario_responsable,comment='Importación Excel.')
            summary['procesados'] += 1
            summary['insertados' if created else 'actualizados'] += 1
        except Exception:
            summary['errores'].append(f'Fila {index + 2}: revisa formato, planta, estado y duplicados.')
    return summary
