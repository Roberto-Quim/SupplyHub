# Paso 1 — Fundación creada

Archivos incluidos:

- `.gitignore`
- `.env.example`
- `requirements*.txt`
- `README.md`
- `Controladores/hub_controller.py`
- `Modelos/supplyhub/` con app Django, fachada de vistas, seguridad Fernet y context processor
- `Otros/manage.py`
- `Otros/config/` con settings/urls/WSGI/ASGI
- `Otros/docs/ARQUITECTURA_SUPPLYHUB.md`
- `Vistas/base.html`
- `Vistas/hub/index.html`
- `tests/test_foundation.py`

Validación recomendada después de copiar al repo:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python Otros/manage.py check
python Otros/manage.py migrate
python Otros/manage.py test tests
```
