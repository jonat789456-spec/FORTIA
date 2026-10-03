from __future__ import annotations

import threading
from dataclasses import dataclass

from ..config import settings


@dataclass(frozen=True)
class WindowInfo:
    handle: int
    title: str
    left: int
    top: int
    width: int
    height: int
    minimized: bool = False


class CaptureStatus:
    def __init__(self) -> None:
        self.available = False
        self.reason = "Dependencias de captura no verificadas"


_capture_local = threading.local()


def enumerate_windows(title_filter: str | None = None, process_name: str | None = None, exact: bool | None = None) -> list[WindowInfo]:
    """Enumera ventanas de Fortnite si pywin32 está disponible.

    No se captura el dashboard y no se inventa una ventana si Fortnite no está
    abierto. La integración completa se activa en Windows con pywin32 y mss.
    """
    filter_text = (title_filter or settings.capture_window_title).strip().casefold()
    process_filter = (process_name if process_name is not None else settings.capture_process_name).strip().casefold()
    exact_match = settings.capture_window_title_exact if exact is None else exact
    try:
        import win32gui  # type: ignore
        import win32process  # type: ignore
        try:
            import psutil  # type: ignore
        except ImportError:
            psutil = None

        windows: list[WindowInfo] = []

        def callback(handle: int, _: object) -> None:
            if not win32gui.IsWindowVisible(handle):
                return
            title = win32gui.GetWindowText(handle)
            normalized_title = title.strip().casefold()
            title_matches = (
                normalized_title == filter_text
                if exact_match
                else bool(filter_text and filter_text in normalized_title)
            )
            if process_filter:
                _, pid = win32process.GetWindowThreadProcessId(handle)
                actual_process = psutil.Process(pid).name().casefold() if psutil is not None else ""
                if process_filter not in actual_process:
                    return
                # Fortnite en modo ventana sin bordes puede tener título vacío
                # o uno que no contiene "Fortnite". Una coincidencia del
                # proceso principal es suficiente en ese caso.
                if filter_text and not title_matches and normalized_title:
                    return
            elif filter_text and not title_matches:
                return
            left, top, right, bottom = win32gui.GetWindowRect(handle)
            if right <= left or bottom <= top:
                return
            windows.append(WindowInfo(handle, title, left, top, right - left, bottom - top, bool(win32gui.IsIconic(handle))))

        win32gui.EnumWindows(callback, None)
        return windows
    except (ImportError, OSError, RuntimeError):
        return []
    except Exception:
        # pywin32 puede estar instalado sin que sus DLL estén disponibles en
        # el proceso actual; la captura debe degradarse sin romper la API.
        return []


def capture_window(window: WindowInfo):
    """Captura una imagen de la ventana; devuelve None si mss no está disponible."""
    try:
        import mss  # type: ignore
        import numpy as np  # type: ignore

        if window.minimized or window.width <= 0 or window.height <= 0:
            return None
        screen = getattr(_capture_local, "screen", None)
        if screen is None:
            screen = mss.mss()
            _capture_local.screen = screen
        raw = screen.grab({"left": window.left, "top": window.top, "width": window.width, "height": window.height})
        # mss entrega BGRA/BGR; el resto del pipeline y Pillow trabajan en RGB.
        return np.asarray(raw)[:, :, :3][:, :, ::-1].copy()
    except (ImportError, OSError):
        screen = getattr(_capture_local, "screen", None)
        if screen is not None:
            try:
                screen.close()
            except Exception:
                pass
            _capture_local.screen = None
        return None


def capture_capability() -> dict[str, object]:
    windows = enumerate_windows()
    alternative = settings.capture_mode.casefold() == "alternative"
    return {"available": bool(windows), "mode": "alternative" if alternative else "fortnite", "label": "Modo de prueba de captura" if alternative else "Fortnite", "windows": [window.__dict__ for window in windows], "reason": None if windows else "Ventana no detectada o dependencias ausentes"}
