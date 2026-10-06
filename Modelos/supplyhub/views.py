"""Fachada de funciones públicas Django.

La coordinación real vive en Controladores/, siguiendo el patrón MVC adaptado
usado por Sistema Data Analytics.
"""
from Controladores.hub_controller import hub_index

__all__ = ["hub_index"]
