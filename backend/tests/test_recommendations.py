import asyncio

from app.recommendations import HealthAlertGate, evaluate, evaluate_prediction
from app.runtime.events import EventHub


def test_recomendaciones_usan_datos_estructurados() -> None:
    recommendations = evaluate("session-test", health=25, shield=10, has_healing=None)
    assert {item["code"] for item in recommendations} == {"LOW_HEALTH", "LOW_SHIELD"}
    assert all(item["sessionId"] == "session-test" and item["validUntil"] for item in recommendations)


def test_recomendacion_degradacion_y_riesgo() -> None:
    codes = {item["code"] for item in evaluate_prediction("session-test", 0.8, ["audio"])}
    assert codes == {"HIGH_ELIMINATION_RISK", "MISSING_MODALITY"}


def test_alerta_de_vida_requiere_persistencia_y_respetahisteresis() -> None:
    gate = HealthAlertGate()
    assert gate.update(48, 60, 0.95, "available") == set()
    assert gate.update(35, 60, 0.95, "available") == set()
    assert gate.update(35, 60, 0.95, "available") == set()
    assert gate.update(35, 60, 0.95, "available") == {"LOW_HEALTH"}
    assert gate.update(35, 60, 0.60, "low_confidence") == set()
    gate.update(46, 60, 0.95, "available")
    assert gate.health_active is False


def test_event_history_conserva_eventos() -> None:
    async def scenario() -> None:
        hub = EventHub()
        await hub.publish("session-test", "test.event", {"value": 1})
        assert hub.history("session-test")[0]["type"] == "test.event"

    asyncio.run(scenario())


def test_event_hub_reemplaza_frames_binarios_pendientes() -> None:
    class FakeWebSocket:
        def __init__(self) -> None:
            self.sent = []
            self.release = asyncio.Event()

        async def send_json(self, payload) -> None:
            self.sent.append(("json", payload))

        async def send_bytes(self, payload) -> None:
            self.sent.append(("binary", payload))
            await self.release.wait()

    async def scenario() -> None:
        hub = EventHub()
        websocket = FakeWebSocket()
        await hub.add("session-test", websocket, role="visual")
        await hub.publish_binary("session-test", "stream.updated", {"frameId": 1}, b"one")
        await asyncio.sleep(0)
        await hub.publish_binary("session-test", "stream.updated", {"frameId": 2}, b"two")
        await hub.publish_binary("session-test", "stream.updated", {"frameId": 3}, b"three")
        assert hub.metrics("session-test")["websocketVisualDropped"] >= 1
        websocket.release.set()
        await hub.remove("session-test", websocket)

    asyncio.run(scenario())
