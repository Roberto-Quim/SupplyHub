#!/usr/bin/env python
"""Django command-line utility para SupplyHub.

Ejecutar desde la raíz:
    python Otros/manage.py check
    python Otros/manage.py migrate
    python Otros/manage.py runserver
"""
import os
import sys
from pathlib import Path


def main():
    base = Path(__file__).resolve().parent.parent
    for path in (str(base), str(base / "Modelos"), str(base / "Otros")):
        if path not in sys.path:
            sys.path.insert(0, path)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
