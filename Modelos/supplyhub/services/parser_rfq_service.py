import re

def parsear_texto_correo_rfq(texto: str) -> dict:
    """
    Parsea el texto pegado de un correo de Form Approvals para autocompletar el formulario de RFQ.
    """
    datos = {}

    # Extract PEDIDO / RFQ
    rfq_match = re.search(r'PEDIDO\s*#?(\d+)', texto, re.IGNORECASE)
    if rfq_match:
        datos['rfq'] = rfq_match.group(1).strip()

    # Extract Solicitante Name
    solic_match = re.search(r'Nombre del Solicitante:\s*([^\r\n]+)', texto, re.IGNORECASE)
    if solic_match:
        datos['solicitante'] = solic_match.group(1).strip()

    # Extract Email
    email_match = re.search(r'Dirección de correo electrónico:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', texto, re.IGNORECASE)
    if email_match:
        datos['correo_solicitante'] = email_match.group(1).strip()

    # Extract Clave de Proyecto / CAPEX
    proyecto_match = re.search(r'Clave del proyecto o Numero de CapEx:\s*([^\r\n]+)', texto, re.IGNORECASE)
    if proyecto_match:
        datos['clave_capex'] = proyecto_match.group(1).strip()

    # Extract Tipo de CAPEX
    tipo_match = re.search(r'Tipo de CapEx:\s*([^\r\n]+)', texto, re.IGNORECASE)
    if tipo_match:
        datos['tipo_capex'] = tipo_match.group(1).strip()

    # Extract Unidad de Negocio / Planta
    planta_match = re.search(r'Selecciona Unidad de Negocio:\s*([^\r\n]+)', texto, re.IGNORECASE)
    if planta_match:
        planta_str = planta_match.group(1).strip().upper()
        if 'TENANGO' in planta_str:
            datos['planta'] = 'MACIMEX_TENANGO'
        else:
            datos['planta'] = 'MAQ_RA'

    # Extract Descripción
    desc_match = re.search(r'Breve descripción de la solicitud de CapEx:\s*(.*?)(?=Marca:|Modelo:|Cantidad|Proveedores|Provedores|$)', texto, re.IGNORECASE | re.DOTALL)
    if desc_match:
        datos['descripcion'] = desc_match.group(1).strip()

    return datos