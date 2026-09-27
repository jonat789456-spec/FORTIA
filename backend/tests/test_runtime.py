import asyncio
from dataclasses import replace

import numpy as np

from app.capture import windows
from app.capture.windows import enumerate_windows
from app.config import settings
from app.runtime.pipeline import LatestFrameBuffer, PipelineState, RuntimePipeline


def test_latest_frame_buffer_descarta_el_anterior() -> None:
    async def scenario() -> None:
        buffer = LatestFrameBuffer()
        await buffer.put("old")
        await buffer.put("new")
        assert await buffer.get() == "new"
        assert buffer.dropped == 1
        assert await buffer.get() is None

    asyncio.run(scenario())


def test_captura_acepta_filtro_de_ventana_configurable() -> None:
    assert enumerate_windows("__ventana_fortnite_inexistente__") == []


def test_modo_alternativo_se_identifica_sin_presentarlo_como_fortnite(monkeypatch) -> None:
    monkeypatch.setattr(windows, "settings", replace(settings, capture_mode="alternative", capture_window_title="__prueba__"))
    result = windows.capture_capability()
    assert result["mode"] == "alternative"
    assert result["label"] == "Modo de prueba de captura"


def test_buffer_conserva_objetos_de_captura() -> None:
    async def scenario() -> None:
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        buffer = LatestFrameBuffer()
        await buffer.put(frame)
        recovered = await buffer.get()
        assert recovered.shape == (4, 4, 3)

    asyncio.run(scenario())


def test_pipeline_publica_fusion_y_estados_estructurados() -> None:
    async def scenario() -> None:
        events = []

        async def publish(session_id, event_type, data, status):
            events.append((event_type, data, status))

        pipeline = RuntimePipeline(publish)
        session_id = "test-runtime"
        pipeline.states[session_id] = PipelineState(status="capturing")
        pipeline.histories[session_id] = __import__("collections").deque([np.zeros((768, 1360, 3), dtype=np.uint8) for _ in range(6)], maxlen=6)
        pipeline.health_readers[session_id] = __import__("app.preprocessing.structured", fromlist=["HealthShieldReader"]).HealthShieldReader()
        pipeline.inventory_readers[session_id] = __import__("app.preprocessing.structured", fromlist=["InventoryReader"]).InventoryReader()
        pipeline.last_health_sample[session_id] = 0.0
        pipeline.states[session_id].health_frames_dropped = 0
        await pipeline._health_fast(session_id, np.zeros((768, 1360, 3), dtype=np.uint8), __import__("app.capture.windows", fromlist=["WindowInfo"]).WindowInfo(1, "test", 0, 0, 1360, 768), 1.0)
        await pipeline._infer_latest(session_id, __import__("app.capture.windows", fromlist=["WindowInfo"]).WindowInfo(1, "test", 0, 0, 1360, 768))
        event_types = {event[0] for event in events}
        assert "frame_sequence.updated" in event_types
        assert "main_prediction.updated" in event_types
        assert "health_shield.updated" in event_types
        assert "recommendation.updated" in event_types
        main = next(event[1] for event in events if event[0] == "main_prediction.updated")
        assert abs(main["eliminatedProbability"] + main["eliminationProbability"] + main["victoryProbability"] - 1.0) < 1e-5

    asyncio.run(scenario())
