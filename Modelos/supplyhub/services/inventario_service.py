"""Cruce MIN–MAX por artículo y planta. Suma existencias, no multiplica mínimos por ubicación."""
from decimal import Decimal
import pandas as pd
from django.db import transaction
from supplyhub.models import LineaOC
from .seguimiento_oc_service import normalizar_planta


def importar_min_max(file):
    try:
        frame = pd.read_excel(file, sheet_name='Data')
    except Exception as exc:
        raise ValueError('No se pudo leer la hoja Data.') from exc
    if not {'Planta', 'Item', 'On Hand', 'Minimo', 'Maximo'}.issubset(frame.columns):
        raise ValueError('El reporte requiere Planta, Item, On Hand, Minimo y Maximo.')
    groups = {}
    for _, row in frame.iterrows():
        if pd.isna(row['Item']) or pd.isna(row['Planta']):
            continue
        plant = normalizar_planta(str(row['Planta']))
        if plant != 'MAQ_RA':
            continue
        item = str(int(row['Item']) if isinstance(row['Item'], float) and row['Item'].is_integer() else row['Item']).strip()
        key = (plant, item)
        stock, minima, maxima = groups.setdefault(key, [Decimal('0'), set(), set()])
        amount = pd.to_numeric(row['On Hand'], errors='coerce')
        if pd.notna(amount):
            groups[key][0] += Decimal(str(amount))
        for column, values in [('Minimo', minima), ('Maximo', maxima)]:
            value = pd.to_numeric(row[column], errors='coerce')
            if pd.notna(value):
                values.add(Decimal(str(value)))
    updated, errors = 0, []
    with transaction.atomic():
        for (plant, item), (stock, minima, maxima) in groups.items():
            if len(minima) > 1 or len(maxima) > 1:
                errors.append(f'Artículo {item}: mínimos/máximos distintos; requiere revisión.')
                continue
            low = next(iter(minima), Decimal('0'))
            high = next(iter(maxima), Decimal('0'))
            if low < 0 or high < low:
                errors.append(f'Artículo {item}: rango MIN–MAX inválido.')
                continue
            updated += LineaOC.objects.filter(orden__planta_normalizada=plant, codigo_articulo=item).update(stock=stock, min_max=f'{low.normalize():f} / {high.normalize():f}')
    return {'actualizados': updated, 'errores': errors}
