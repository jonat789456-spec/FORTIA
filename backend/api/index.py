"""Adaptador ASGI para las rutas HTTP de Vercel.

Vercel Functions no ofrece un proceso persistente ni WebSocket estable; este
adaptador se usa únicamente para comprobar las rutas HTTP y el health check.
La captura/inferencia en tiempo real requiere un servicio ASGI persistente.
"""

from app.main import app

__all__ = ["app"]
