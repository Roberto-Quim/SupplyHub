"""
dataanalytics_usuario_plantas_service.py — Plantas por usuario (Fase 1).

Responsabilidad:
    - Catálogo de plantas disponibles (SingleSignOnMcx.dbo.PlantasMcx).
    - Asignación manual de plantas por usuario en DataAnalytics.dbo.UsuarioSitios.

Reglas de negocio (confirmadas):
    - UsuarioSitios.ClavePlanta guarda SIEMPRE la clave normal de PlantasMcx
      (p. ej. BHK, FDM, QCT, MCM, TEN). Nunca ClavePlantaQues, nombres ni 'MCX'.
    - Fallback efectivo: 'MCM' / 'RAMOS ARIZPE'.
    - La vista SSO puede traer CLAVEPLANTA='MCX'; se normaliza por descripción
      (RAMOS→MCM, TENANGO→TEN, en duda→MCM). Esa normalización es para derivación
      (Fase 2); en la asignación manual una clave 'MCX' es inválida y se rechaza.
    - Jerarquía: TI puede asignar a cualquiera (incluido TI); Administrador puede a
      Administrador/Usuario y a sí mismo, NO a TI; Usuario normal no puede asignar.
    - Vía pública sin actor válido: falla cerrado. system=True es la única vía
      interna explícita (siembra/migración).

Seguridad:
    - Consultas parametrizadas (?), nunca concatenación de input.
    - Escrituras con commit() en éxito y rollback() en excepción; conexión cerrada.
    - Activación/desactivación lógica (Activo=0/1); no se borra físicamente.

NOTA: el catálogo vive en la base SingleSignOnMcx y la asignación en DataAnalytics;
se usa nombre de 3 partes (SingleSignOnMcx.dbo.PlantasMcx) sobre la misma conexión.
"""

import logging
import os

logger = logging.getLogger('supplyhub')

# Catálogo y asignación
_CATALOGO = 'SingleSignOnMcx.dbo.PlantasMcx'
_ASIGNACION = 'dbo.UsuarioSitios'

# Fallback efectivo confirmado (clave normal del catálogo)
FALLBACK_CLAVE = 'MCM'
FALLBACK_PLANTA = 'RAMOS ARIZPE'

# ──────────────────────────────────────────────────────────────
# ALLOWLIST (Fase 2): aunque PlantasMcx tenga 17 plantas, esta app SOLO usa estas
# 5, con su clave normal y su nombre oficial. El frontend solo las muestra y el
# backend solo las acepta. Cualquier otra clave (PBC, QAM, IOS, SUD, QUI, SCQ,
# MCX, RAMOS, QMR, ClavePlantaQues, nombres, etc.) se rechaza/ignora.
# ──────────────────────────────────────────────────────────────

# Allowlist de CLAVES permitidas (5). Es válido tener esta constante de claves.
# Los NOMBRES y demás datos visibles (Planta, PlantaQuestum, ClavePlantaQues,
# OrganizationCode, Domicilio, Telefono) NO se hardcodean: provienen de
# SingleSignOnMcx.dbo.PlantasMcx (ver list_plantas_disponibles / get_usuario_plantas).
PLANTAS_PERMITIDAS = {'BHK', 'FDM', 'MCM', 'QCT', 'TEN'}

# Cláusulas SQL reutilizables (solo claves del allowlist; sin nombres).
_ALLOWLIST_IN_SQL = "('BHK', 'FDM', 'MCM', 'QCT', 'TEN')"
_ORDEN_CASE_SQL = (
    "CASE LTRIM(RTRIM({col})) "
    "WHEN 'BHK' THEN 1 WHEN 'FDM' THEN 2 WHEN 'QCT' THEN 3 "
    "WHEN 'MCM' THEN 4 WHEN 'TEN' THEN 5 ELSE 99 END"
)
# Orden de claves (sin nombres) para ordenar en memoria cuando aplique.
_ORDEN_CLAVE = {'BHK': 1, 'FDM': 2, 'QCT': 3, 'MCM': 4, 'TEN': 5}


def _s(v) -> str:
    return str(v).strip() if v is not None else ''


def _is_enabled() -> bool:
    from django.conf import settings
    return settings.DATAANALYTICS_ENABLED


def _get_conn():
    from supplyhub.connectors.dataanalytics_connection import get_dataanalytics_conn
    return get_dataanalytics_conn()


def _safe_close(conn) -> None:
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def _safe_rollback(conn) -> None:
    if conn is not None:
        try:
            conn.rollback()
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────
# Migración a Stored Procedures (fase 5): SP-first con fallback seguro.
#
#   - LECTURAS: intentan EXEC dbo.<Nombre>DAsp y, si el SP/objeto aún no existe
#     en la BD (error 2812/208/42S02, ESPERADO durante la migración), caen a la
#     query directa equivalente en el MISMO cursor.
#   - ESCRITURAS: solo hacen fallback si el SP NO existe (2812) — el error ocurre
#     al enlazar el EXEC, antes de ejecutar nada, así que es seguro reintentar con
#     SQL directo. Cualquier otro error se propaga → rollback (no fallback).
# ──────────────────────────────────────────────────────────────

def _is_missing_database_object_error(exc: Exception) -> bool:
    """
    True si la excepción es "objeto de BD inexistente" en SQL Server, caso ESPERADO
    durante la migración a SPs (antes de ejecutar 017): NO es un bug.
      - Procedimiento inexistente: 'Could not find stored procedure' · error 2812
      - Tabla/objeto inexistente:  'Invalid object name' · error 208 · SQLSTATE 42S02
    """
    texto = str(exc).lower()
    if 'could not find stored procedure' in texto:
        return True
    if '2812' in texto:
        return True
    if 'invalid object name' in texto:
        return True
    if '42s02' in texto:
        return True
    if '208' in texto and 'object name' in texto:
        return True
    return False


def _is_missing_stored_procedure_error(exc: Exception) -> bool:
    """
    True SOLO si el SP no existe ('Could not find stored procedure' / error 2812).
    Para ESCRITURAS solo se hace fallback en este caso; otros errores se propagan.
    """
    texto = str(exc).lower()
    return ('could not find stored procedure' in texto) or ('2812' in texto)


def _sp_or_direct_execute(cur, sp_sql, sp_params, direct_sql, direct_params, sp_name):
    """
    Ejecuta el SP de lectura; si el SP/objeto aún no existe en la BD (2812/208/...),
    cae a la query directa equivalente en el MISMO cursor (fallback temporal). Otros
    errores se propagan al llamador. Deja el cursor listo para fetchone()/fetchall().
    Parámetros con ? (nunca concatenados).
    """
    try:
        if sp_params is None:
            cur.execute(sp_sql)
        else:
            cur.execute(sp_sql, sp_params)
    except Exception as exc:
        if _is_missing_database_object_error(exc):
            logger.warning('UsuarioPlantas: SP %s no existe todavía; usando query directa.', sp_name)
            if direct_params is None:
                cur.execute(direct_sql)
            else:
                cur.execute(direct_sql, direct_params)
        else:
            raise


def _row_planta(row) -> dict:
    return {
        'clave_planta':      str(row[0]).strip() if row[0] is not None else '',
        'planta':            str(row[1]).strip() if row[1] is not None else '',
        'planta_questum':    str(row[2]).strip() if row[2] is not None else '',
        'clave_planta_ques': str(row[3]).strip() if row[3] is not None else '',
    }


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def normalizar_clave_planta(clave, descripcion=None) -> str:
    """
    Normaliza una clave/descripción a una de las 5 claves permitidas
    ('BHK','FDM','QCT','MCM','TEN'). Nunca devuelve 'MCX', 'RAMOS', 'QMR' ni nombres.

    Reglas:
      - Si la clave ya es una de las 5 permitidas → se usa.
      - Si la clave es 'MCX' (vista SSO) o no es permitida, se decide por texto
        (clave + descripción/nombre):
          'BLACK HAWK'                                   → 'BHK'
          'FORJA' / 'FORJA DE MONTERREY'                 → 'FDM'
          'CENTRO TECNOL...' / 'MAQUINADOS SALTILLO'/QCT → 'QCT'
          'TENANGO'                                      → 'TEN'
          'RAMOS' / 'RAMOS ARIZPE'                       → 'MCM'
      - Si no hay match → fallback 'MCM'.
    """
    c = (clave or '').strip().upper()
    if c in PLANTAS_PERMITIDAS:
        return c

    texto = f'{c} {(descripcion or "").strip().upper()}'
    if 'BLACK HAWK' in texto:
        return 'BHK'
    if 'FORJA' in texto:
        return 'FDM'
    if 'CENTRO TECNOL' in texto or 'MAQUINADOS SALTILLO' in texto or 'QCT' in texto:
        return 'QCT'
    if 'TENANGO' in texto:
        return 'TEN'
    if 'RAMOS' in texto:
        return 'MCM'
    return FALLBACK_CLAVE


def derivar_clave_planta_inicial(no_nomina=None, correo=None, clave_planta=None,
                                 planta=None, descripcion=None) -> str:
    """
    Deriva la clave de planta inicial (siempre una de las 5 permitidas) a partir
    de los datos disponibles del usuario (clave/planta/descripción del conector de
    nómina o búsqueda). Si nada coincide, devuelve el fallback 'MCM'.
    No ejecuta consultas: trabaja con los datos que se le pasan.
    """
    texto_desc = ' '.join(x for x in (descripcion, planta) if x)
    clave = clave_planta or planta or ''
    resultado = normalizar_clave_planta(clave, texto_desc)
    # Garantía dura: nunca devolver algo fuera del allowlist.
    return resultado if resultado in PLANTAS_PERMITIDAS else FALLBACK_CLAVE


def _ensure_usuario_planta_inicial_directo(cur, id_usuario: int, clave: str) -> bool:
    """
    Fallback directo de EnsureUsuarioPlantaInicialDAsp (mismo comportamiento):
      - Si el usuario ya tiene plantas ACTIVAS → no toca nada y devuelve False.
      - Si no → reactiva la clave si existía (inactiva) o la inserta, y devuelve True.
    No hace commit (lo hace el llamador). Parámetros con ? (nunca concatenados).
    """
    cur.execute(
        f'SELECT COUNT(*) FROM {_ASIGNACION} WHERE IdUsuario = ? AND Activo = 1',
        (id_usuario,),
    )
    if (cur.fetchone() or [0])[0] > 0:
        return False

    cur.execute(
        f'SELECT IdUsuarioSitio FROM {_ASIGNACION} '
        f'WHERE IdUsuario = ? AND LTRIM(RTRIM(ClavePlanta)) = ?',
        (id_usuario, clave),
    )
    if cur.fetchone():
        cur.execute(
            f'UPDATE {_ASIGNACION} SET Activo = 1, FechaUpd = GETDATE() '
            f'WHERE IdUsuario = ? AND LTRIM(RTRIM(ClavePlanta)) = ?',
            (id_usuario, clave),
        )
    else:
        cur.execute(
            f'INSERT INTO {_ASIGNACION} (IdUsuario, ClavePlanta, Activo, FechaAdd, FechaUpd) '
            f'VALUES (?, ?, 1, GETDATE(), GETDATE())',
            (id_usuario, clave),
        )
    return True


def ensure_usuario_planta_inicial(id_usuario: int, no_nomina=None, correo=None,
                                  clave_planta=None, planta=None, descripcion=None,
                                  system: bool = False, actor_id_perfil=None,
                                  actor_id_usuario=None) -> tuple[bool, str]:
    """
    Asignación AUTOMÁTICA de planta inicial al dar de alta/actualizar un usuario.

      - Si el usuario YA tiene al menos una planta ACTIVA → no hace nada.
      - Si no tiene → deriva una clave permitida y la inserta (Activo=1).
      - No borra físicamente; reactiva si existiera inactiva esa misma clave.
      - Transaccional (commit/rollback). Pensada como paso interno del alta; no
        re-valida jerarquía (el alta ya la validó). Sus fallos NO deben romper el alta.

    Returns (True, clave) si asignó; (False, motivo) si no asignó.
    """
    if not _is_enabled() or not id_usuario:
        return False, 'no aplica'

    clave = derivar_clave_planta_inicial(no_nomina, correo, clave_planta, planta, descripcion)
    if clave not in PLANTAS_PERMITIDAS:
        clave = FALLBACK_CLAVE

    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        # Escritura vía SP (fallback temporal: COUNT/exists/UPSERT directos, misma lógica).
        try:
            cur.execute('EXEC dbo.EnsureUsuarioPlantaInicialDAsp ?, ?',
                        (int(id_usuario), clave))
            row = cur.fetchone()
            asignada = bool(row[0]) if (row and row[0] is not None) else False
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('UsuarioPlantas: SP EnsureUsuarioPlantaInicialDAsp no existe todavía; usando SQL directo.')
                asignada = _ensure_usuario_planta_inicial_directo(cur, int(id_usuario), clave)
            else:
                raise

        if not asignada:
            return False, 'el usuario ya tiene plantas activas'

        conn.commit()
        logger.info('UsuarioPlantas: planta inicial asignada (IdUsuario=%s, clave=%s).',
                    id_usuario, clave)
        return True, clave

    except Exception as exc:
        _safe_rollback(conn)
        logger.exception('UsuarioPlantas: error al asignar planta inicial (IdUsuario=%s) — rollback.', id_usuario)
        return False, 'No se pudo guardar la asignación de plantas.'
    finally:
        _safe_close(conn)


# ──────────────────────────────────────────────────────────────
# Lectura
# ──────────────────────────────────────────────────────────────

def list_plantas_disponibles() -> list[dict]:
    """
    Catálogo de plantas disponibles para asignar: las 5 permitidas, leídas desde
    la FUENTE OFICIAL `SingleSignOnMcx.dbo.PlantasMcx` filtradas por el allowlist
    de claves y ordenadas BHK, FDM, QCT, MCM, TEN. Los nombres/datos visibles
    vienen de PlantasMcx (no de constantes). Defensa extra: ignora cualquier
    clave fuera del allowlist.
    """
    if not _is_enabled():
        return []
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetPlantasDisponiblesDAsp', None,
            'SELECT ClavePlanta, ClaveCompania, Planta, PlantaQuestum, ClavePlantaQues, '
            'OrganizationCode, Domicilio, Telefono '
            f'FROM {_CATALOGO} '
            f'WHERE LTRIM(RTRIM(ClavePlanta)) IN {_ALLOWLIST_IN_SQL} '
            f'ORDER BY {_ORDEN_CASE_SQL.format(col="ClavePlanta")}',
            None,
            'GetPlantasDisponiblesDAsp',
        )
        out = []
        for r in cur.fetchall():
            clave = _s(r[0]).upper()
            if clave not in PLANTAS_PERMITIDAS:        # defensa extra en memoria
                continue
            out.append({
                'clave_planta':      clave,
                'clave_compania':    _s(r[1]),
                'planta':            _s(r[2]),
                'planta_questum':    _s(r[3]),
                'clave_planta_ques': _s(r[4]),
                'organization_code': _s(r[5]),
                'domicilio':         _s(r[6]),
                'telefono':          _s(r[7]),
            })
        return out
    except Exception:
        logger.exception('UsuarioPlantas: error al listar el catálogo de plantas (PlantasMcx).')
        raise RuntimeError('No se pudo consultar DataAnalytics.') from None
    finally:
        _safe_close(conn)


def plant_identity_map() -> dict:
    """
    {ClavePlanta → ClaveIdentidadQues} desde PlantasMcx, SOLO para presentación visual
    (identidad de planta en dashboards). NO cambia claves de seguridad ni filtros.

    Defensivo (no rompe si algo falta): devuelve {} si DataAnalytics está deshabilitado,
    si la columna ClaveIdentidadQues aún no existe en el ambiente, o si falla la conexión.
    Query directa de solo lectura (no SP). Solo devuelve identidades no vacías.
    """
    if not _is_enabled():
        return {}
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            'SELECT LTRIM(RTRIM(ClavePlanta)) AS ClavePlanta, ClaveIdentidadQues '
            f'FROM {_CATALOGO} '
            f'WHERE LTRIM(RTRIM(ClavePlanta)) IN {_ALLOWLIST_IN_SQL}'
        )
        out = {}
        for r in cur.fetchall():
            clave = _s(r[0]).upper()
            ident = _s(r[1])
            if clave and ident:
                out[clave] = ident
        return out
    except Exception:
        # Ambiente sin la columna / sin acceso → fallback a alias de presentación.
        logger.warning('UsuarioPlantas: ClaveIdentidadQues no disponible; usando alias de presentación.')
        return {}
    finally:
        _safe_close(conn)


def get_usuario_plantas(id_usuario: int) -> list[dict]:
    """
    Plantas ACTIVAS asignadas al usuario en UsuarioSitios, limitadas al allowlist
    de 5. El nombre se resuelve desde `PlantasMcx` (no de constantes).
    """
    if not _is_enabled() or not id_usuario:
        return []
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetUsuarioPlantasDAsp ?', (int(id_usuario),),
            'SELECT LTRIM(RTRIM(us.ClavePlanta)) AS ClavePlanta, pm.Planta, '
            'pm.PlantaQuestum, pm.ClavePlantaQues '
            f'FROM {_ASIGNACION} us '
            f'LEFT JOIN {_CATALOGO} pm '
            '       ON LTRIM(RTRIM(pm.ClavePlanta)) = LTRIM(RTRIM(us.ClavePlanta)) '
            'WHERE us.IdUsuario = ? AND us.Activo = 1 '
            f'  AND LTRIM(RTRIM(us.ClavePlanta)) IN {_ALLOWLIST_IN_SQL}',
            (int(id_usuario),),
            'GetUsuarioPlantasDAsp',
        )
        out = []
        for r in cur.fetchall():
            clave = _s(r[0]).upper()
            if clave not in PLANTAS_PERMITIDAS:
                continue
            out.append({
                'clave_planta':      clave,
                'planta':            _s(r[1]),
                'planta_questum':    _s(r[2]),
                'clave_planta_ques': _s(r[3]),
            })
        out.sort(key=lambda d: _ORDEN_CLAVE.get(d['clave_planta'], 99))
        return out
    except Exception:
        logger.exception('UsuarioPlantas: error al leer plantas del usuario (IdUsuario=%s).', id_usuario)
        raise RuntimeError('No se pudo consultar DataAnalytics.') from None
    finally:
        _safe_close(conn)


def get_plantas_por_usuario_map(id_usuarios=None) -> dict:
    """
    {IdUsuario: set(ClavePlanta activas)} en UNA sola consulta (para la lista de
    usuarios). Útil para precargar los checkboxes sin N consultas.
    El parámetro id_usuarios se acepta por compatibilidad; con pocos usuarios se
    lee toda la tabla activa.
    """
    if not _is_enabled():
        return {}
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        _sp_or_direct_execute(
            cur,
            'EXEC dbo.GetUsuariosPlantasMapDAsp', None,
            f'SELECT IdUsuario, LTRIM(RTRIM(ClavePlanta)) AS ClavePlanta '
            f'FROM {_ASIGNACION} WHERE Activo = 1',
            None,
            'GetUsuariosPlantasMapDAsp',
        )
        m: dict = {}
        for r in cur.fetchall():
            if r[0] is None:
                continue
            clave = str(r[1]).strip().upper() if r[1] is not None else ''
            if clave:
                m.setdefault(int(r[0]), set()).add(clave)
        return m
    except Exception:
        logger.exception('UsuarioPlantas: error al leer el mapa de plantas por usuario.')
        return {}
    finally:
        _safe_close(conn)


def get_usuario_plantas_efectivas(id_usuario: int, id_perfil) -> dict:
    """
    Plantas EFECTIVAS para los dashboards (no escribe en BD):
      - Perfil TI       → todas las disponibles + puede_ver_todas=True.
      - No TI con asignaciones activas → esas plantas.
      - No TI sin asignaciones         → fallback 'MCM' / 'RAMOS ARIZPE'.
    Retorna: {'plantas': list[dict], 'puede_ver_todas': bool, 'es_fallback': bool}.
    """
    from supplyhub.services.da_admin.dataanalytics_user_admin_service import is_ti_profile

    if is_ti_profile(id_perfil):
        return {'plantas': list_plantas_disponibles(), 'puede_ver_todas': True, 'es_fallback': False}

    asignadas = get_usuario_plantas(id_usuario)
    if asignadas:
        return {'plantas': asignadas, 'puede_ver_todas': False, 'es_fallback': False}

    # Fallback MCM: la info VISIBLE (nombre, etc.) proviene de PlantasMcx.
    catalogo = list_plantas_disponibles()
    mcm = next((p for p in catalogo if p.get('clave_planta') == FALLBACK_CLAVE),
               {'clave_planta': FALLBACK_CLAVE, 'planta': ''})
    return {'plantas': [mcm], 'puede_ver_todas': False, 'es_fallback': True}


def get_auditorias_plant_scope(id_usuario, id_perfil) -> dict:
    """
    Alcance de plantas para el dashboard de Auditorías. Como las vistas de
    Auditorías filtran por NOMBRE (`Planta`), expone `nombres_permitidos`.

    Retorna:
      {
        'puede_ver_todas': bool,          # solo TI
        'plantas': [{'clave_planta','planta',...}, ...],
        'nombres_permitidos': ['RAMOS ARIZPE', ...],   # para WHERE Planta IN (...)
        'claves_permitidas': ['MCM', ...],
        'es_fallback': bool,
      }

    - TI → las 5 plantas del catálogo (nombres desde PlantasMcx) + puede_ver_todas.
    - No TI → solo sus plantas asignadas; sin asignaciones → fallback RAMOS ARIZPE.
    Red de seguridad: un no-TI nunca queda con alcance vacío (cae a RAMOS ARIZPE).
    """
    ef = get_usuario_plantas_efectivas(id_usuario, id_perfil)
    plantas = ef.get('plantas') or []
    nombres = [p['planta'] for p in plantas if p.get('planta')]
    claves = [p['clave_planta'] for p in plantas if p.get('clave_planta')]

    if not ef.get('puede_ver_todas') and not nombres:
        # Red de seguridad: nunca dejar a un no-TI sin alcance.
        nombres = [FALLBACK_PLANTA]
        if not claves:
            claves = [FALLBACK_CLAVE]

    return {
        'puede_ver_todas':    bool(ef.get('puede_ver_todas')),
        'plantas':            plantas,
        'nombres_permitidos': nombres,
        'claves_permitidas':  claves,
        'es_fallback':        bool(ef.get('es_fallback')),
    }


def get_tpt_plant_scope(id_usuario, id_perfil) -> dict:
    """
    Alcance de plantas para el dashboard de TPT. A diferencia de Auditorías (que
    filtra por NOMBRE), TPT filtra por CLAVE: la planta del lote se resuelve con
    COALESCE(EmbarcadoTpt.ClavePlanta, TransporteTpt.ClavePlanta), por lo que el
    consumidor usa `claves_permitidas`. La forma del dict es la misma que en
    Auditorías (TI → 5 + puede_ver_todas; no-TI → asignadas/fallback MCM).
    """
    return get_auditorias_plant_scope(id_usuario, id_perfil)


# ──────────────────────────────────────────────────────────────
# Escritura transaccional
# ──────────────────────────────────────────────────────────────

def _set_usuario_plantas_directo(cur, id_usuario: int, claves) -> None:
    """
    Fallback directo de SetUsuarioPlantasDAsp (misma lógica de upsert lógico):
      - Desactiva las que ya no estén seleccionadas (o todas si la lista es vacía).
      - Reactiva las existentes seleccionadas e inserta las nuevas.
    No hace commit (lo hace el llamador). Parámetros con ? (nunca concatenados).
    """
    if claves:
        placeholders = ','.join(['?'] * len(claves))
        cur.execute(
            f'UPDATE {_ASIGNACION} SET Activo = 0, FechaUpd = GETDATE() '
            f'WHERE IdUsuario = ? AND LTRIM(RTRIM(ClavePlanta)) NOT IN ({placeholders})',
            [id_usuario] + claves,
        )
    else:
        cur.execute(
            f'UPDATE {_ASIGNACION} SET Activo = 0, FechaUpd = GETDATE() '
            f'WHERE IdUsuario = ?',
            (id_usuario,),
        )

    for clave in claves:
        cur.execute(
            f'SELECT IdUsuarioSitio FROM {_ASIGNACION} '
            f'WHERE IdUsuario = ? AND LTRIM(RTRIM(ClavePlanta)) = ?',
            (id_usuario, clave),
        )
        if cur.fetchone():
            cur.execute(
                f'UPDATE {_ASIGNACION} SET Activo = 1, FechaUpd = GETDATE() '
                f'WHERE IdUsuario = ? AND LTRIM(RTRIM(ClavePlanta)) = ?',
                (id_usuario, clave),
            )
        else:
            cur.execute(
                f'INSERT INTO {_ASIGNACION} (IdUsuario, ClavePlanta, Activo, FechaAdd, FechaUpd) '
                f'VALUES (?, ?, 1, GETDATE(), GETDATE())',
                (id_usuario, clave),
            )


def set_usuario_plantas(id_usuario: int, claves_plantas, actor_id_perfil=None,
                        actor_id_usuario=None, system: bool = False) -> tuple[bool, str]:
    """
    Asigna el conjunto de plantas (claves normales) a un usuario en UsuarioSitios.

    - Jerarquía (FAIL-CLOSED en la vía pública): el actor debe poder modificar al
      usuario objetivo (Administrador no puede tocar TI; Usuario normal no puede
      asignar). system=True es la única vía interna que omite la jerarquía.
    - Deduplica y normaliza (mayúsculas/sin espacios) las claves.
    - Valida que cada clave exista en el catálogo (rechaza 'MCX', 'RAMOS', nombres
      o ClavePlantaQues, que no existen como ClavePlanta).
    - Upsert lógico: reactiva las seleccionadas, inserta nuevas, desactiva las que
      ya no estén seleccionadas. No borra físicamente.

    Returns (True, '') en éxito; (False, mensaje) en error/denegación.
    """
    if not _is_enabled():
        return False, 'DataAnalytics no está habilitado.'
    if not id_usuario:
        return False, 'Usuario inválido.'

    # Jerarquía (fail-closed sin actor válido en la vía pública).
    if not system:
        from supplyhub.services.da_admin.dataanalytics_user_admin_service import can_actor_modify_user
        if not can_actor_modify_user(actor_id_perfil, id_usuario):
            return False, 'No tienes permiso para asignar plantas a este usuario.'

    # Normalizar + deduplicar preservando orden.
    claves = list(dict.fromkeys(
        (str(c).strip().upper() for c in (claves_plantas or []) if str(c).strip())
    ))

    # Validar contra el ALLOWLIST de 5 (no contra el catálogo SSO de 17). Rechaza
    # PBC/QAM/IOS/SUD/QUI/SCQ/MCX/RAMOS/QMR/nombres/ClavePlantaQues, etc.
    invalidas = [c for c in claves if c not in PLANTAS_PERMITIDAS]
    if invalidas:
        return False, f'Una o más claves de planta no son válidas: {", ".join(invalidas)}.'

    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        # Escritura vía SP (fallback temporal: UPDATE/INSERT directos, misma lógica).
        # Las claves ya están normalizadas y validadas contra el allowlist arriba;
        # viajan como CSV en un parámetro (?), nunca concatenadas al SQL.
        try:
            csv = ','.join(claves) if claves else None
            cur.execute('EXEC dbo.SetUsuarioPlantasDAsp ?, ?', (int(id_usuario), csv))
        except Exception as exc:
            if _is_missing_stored_procedure_error(exc):
                logger.warning('UsuarioPlantas: SP SetUsuarioPlantasDAsp no existe todavía; usando SQL directo.')
                _set_usuario_plantas_directo(cur, int(id_usuario), claves)
            else:
                raise

        conn.commit()
        logger.info('UsuarioPlantas: plantas actualizadas (IdUsuario=%s, total=%s).',
                    id_usuario, len(claves))
        return True, ''

    except Exception as exc:
        _safe_rollback(conn)
        logger.exception('UsuarioPlantas: error al asignar plantas (IdUsuario=%s) — rollback.', id_usuario)
        return False, 'No se pudo guardar. Revisa los datos y la conexión con DataAnalytics.'
    finally:
        _safe_close(conn)
