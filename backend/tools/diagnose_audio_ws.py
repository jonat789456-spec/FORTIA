"""Comprueba que el evento de audio real llegue por WebSocket."""
from __future__ import annotations

import sys
import time
import threading
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--tone", action="store_true")
args = parser.parse_args()


with TestClient(app) as client:
    session = client.post("/api/v1/sessions").json()["sessionId"]
    if args.tone:
        import winsound
        threading.Thread(target=lambda: winsound.Beep(880, 7000), daemon=True).start()
    client.post(f"/api/v1/sessions/{session}/start")
    with client.websocket_connect(f"/api/v1/ws/sessions/{session}") as websocket:
        deadline = time.monotonic() + 8
        seen = 0
        while time.monotonic() < deadline:
            payload = websocket.receive_json()
            if payload.get("type") == "audio_prediction.updated":
                print(payload)
                seen += 1
                if seen >= 3:
                    break
    client.post(f"/api/v1/sessions/{session}/reset")
