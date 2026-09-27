import numpy as np

from app.capture.windows import WindowInfo, capture_window
from app.preprocessing.structured import HealthShieldReader, InventoryReader


def test_health_shield_lee_barras_y_limita_rango() -> None:
    image = np.zeros((216, 489, 3), dtype=np.uint8)
    image[128:143, 47:292] = [10, 120, 220]
    image[147:174, 47:292] = [10, 220, 10]
    result = HealthShieldReader().read(image)
    assert result["status"] == "available"
    assert 0 <= result["healthValue"] <= 100
    assert 0 <= result["shieldValue"] <= 100
    assert result["healthValue"] >= 95
    assert result["shieldValue"] >= 95
    assert result["confidence"] >= 0.75


def test_health_shield_no_inventa_cero_y_expira_ultimo_valor() -> None:
    reader = HealthShieldReader(ttl_seconds=8.0)
    image = np.zeros((216, 489, 3), dtype=np.uint8)
    image[128:143, 47:292] = [10, 120, 220]
    image[147:174, 47:292] = [10, 220, 10]
    first = reader.read(image, timestamp=10.0)
    assert first["healthValue"] is not None
    estimated = reader.read(np.zeros_like(image), timestamp=12.0)
    assert estimated["healthValue"] is not None
    assert estimated["healthReading"]["status"] == "estimated"
    stale = reader.read(np.zeros_like(image), timestamp=14.0)
    assert stale["healthReading"]["status"] == "last_stable"
    expired = reader.read(np.zeros_like(image), timestamp=19.0)
    assert expired["status"] == "not_detected"
    assert expired["healthValue"] is None


def test_health_shield_conserva_cada_variable_de_forma_independiente() -> None:
    image = np.zeros((216, 489, 3), dtype=np.uint8)
    image[128:143, 47:292] = [10, 120, 220]
    image[147:174, 47:180] = [10, 220, 10]
    reader = HealthShieldReader()
    first = reader.read(image, timestamp=1.0)
    assert first["healthValue"] is not None and first["shieldValue"] is not None
    blank_health = image.copy()
    blank_health[147:174, 47:180] = 0
    second = reader.read(blank_health, timestamp=1.5)
    assert second["healthValue"] is not None
    assert second["healthReading"]["status"] == "estimated"
    assert second["shieldValue"] is not None


def test_health_shield_evidencia_100_54() -> None:
    image = np.zeros((216, 489, 3), dtype=np.uint8)
    image[128:143, 47:47 + 136] = [10, 120, 220]
    image[147:174, 47:292] = [10, 220, 10]
    result = HealthShieldReader().read(image, timestamp=1.0)
    assert result["healthValue"] >= 95
    assert 48 <= result["shieldValue"] <= 60
    assert result["healthReading"]["status"] == "current"
    assert result["shieldReading"]["status"] == "current"


def test_inventory_devuelve_cinco_espacios_sin_nombres_inventados() -> None:
    image = np.zeros((40, 250, 3), dtype=np.uint8)
    image[:, :50] = [30, 100, 220]
    image[:, 100:150] = [220, 30, 30]
    result = InventoryReader().read(image)
    assert len(result["slots"]) == 5
    assert result["slots"][0]["occupied"] is True
    assert result["slots"][1]["occupied"] is False
    assert result["slots"][0]["name"] is None


def test_capture_window_no_captura_ventana_minimizada() -> None:
    window = WindowInfo(1, "test", 0, 0, 100, 100, minimized=True)
    assert capture_window(window) is None


def test_health_shield_separa_100_50_y_rechaza_pico_aislado() -> None:
    def frame(shield_width: int) -> np.ndarray:
        image = np.zeros((216, 489, 3), dtype=np.uint8)
        image[128:143, 47:47 + shield_width] = [10, 120, 220]
        image[147:174, 47:292] = [10, 220, 10]
        return image

    reader = HealthShieldReader()
    first = reader.read(frame(245), timestamp=1.0)
    second = reader.read(frame(122), timestamp=2.0)
    assert first["healthValue"] >= 95
    assert 45 <= second["shieldValue"] <= 60
    assert second["healthValue"] >= 95
    for index in range(3, 6):
        stable = reader.read(frame(245), timestamp=float(index))
    assert stable["healthValue"] >= 95
    assert stable["shieldValue"] >= 95


def test_diagnostico_visual_esta_desactivado_por_defecto_y_es_bajo_demanda() -> None:
    image = np.zeros((216, 489, 3), dtype=np.uint8)
    image[128:143, 47:292] = [10, 120, 220]
    image[147:174, 47:292] = [10, 220, 10]
    reader = HealthShieldReader()
    assert reader.diagnostics_enabled is False
    debug = reader.read_debug(image)
    assert set(debug["regions"]) == {"health", "shield"}
    assert reader.diagnostics_enabled is False


def test_rechaza_icono_azul_aislado_y_no_lo_confunde_con_barra() -> None:
    image = np.zeros((216, 489, 3), dtype=np.uint8)
    image[147:174, 47:292] = [10, 220, 10]
    image[128:143, 420:441] = [10, 120, 220]
    result = HealthShieldReader().read_debug(image, timestamp=1.0)
    assert result["reading"]["healthCurrent"] >= 95
    assert result["reading"]["shieldCurrent"] is None
    assert result["reading"]["shield"]["status"] == "no_reading"
    assert result["reading"]["overshield"]["status"] == "not_applicable"
    assert result["regions"]["shield"]["rejected"]


def test_descenso_real_de_escudo_tiene_prioridad_sobre_historial() -> None:
    def frame(shield_width: int) -> np.ndarray:
        image = np.zeros((216, 489, 3), dtype=np.uint8)
        image[128:143, 47:47 + shield_width] = [10, 120, 220]
        image[147:174, 47:292] = [10, 220, 10]
        return image

    reader = HealthShieldReader()
    reader.read(frame(245), timestamp=1.0)
    reader.read(frame(245), timestamp=1.1)
    result = reader.read(frame(122), timestamp=1.2)
    assert 45 <= result["shieldCurrent"] <= 60
    assert result["shield"]["current"] == result["shieldCurrent"]
    assert result["shield"]["status"] == "current"


def test_valor_conservado_no_se_marca_actual_y_expira_en_cuatro_segundos() -> None:
    image = np.zeros((216, 489, 3), dtype=np.uint8)
    image[128:143, 47:292] = [10, 120, 220]
    image[147:174, 47:292] = [10, 220, 10]
    reader = HealthShieldReader()
    reader.read(image, timestamp=10.0)
    estimated = reader.read(np.zeros_like(image), timestamp=10.5)
    stable = reader.read(np.zeros_like(image), timestamp=13.0)
    stale = reader.read(np.zeros_like(image), timestamp=14.1)
    assert estimated["shield"]["status"] == "estimated"
    assert stable["shield"]["status"] == "last_stable"
    assert stale["shieldCurrent"] is None
    assert stale["shield"]["status"] == "stale"
