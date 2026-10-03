"""Genera ventanas causales a partir de eventos anotados, sin mirar después.

Entrada: CSV con ``session_id``, ``timestamp_sec`` y ``event_time_sec``.
El script no lee ni escribe el split ``test`` y falla si detecta una ventana
posterior al evento.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


WINDOWS = ((10.0, 7.0), (7.0, 5.0), (5.0, 3.0), (3.0, 1.0), (1.0, 0.0))


def build_windows(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"session_id", "timestamp_sec", "event_time_sec", "outcome"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Faltan columnas: {sorted(missing)}")
    output: list[dict[str, object]] = []
    for session_id, group in frame.groupby("session_id", sort=False):
        event = float(group["event_time_sec"].iloc[0])
        for row in group.sort_values("timestamp_sec").itertuples(index=False):
            seconds = event - float(row.timestamp_sec)
            if seconds < -1e-6:
                raise ValueError(f"Muestra posterior al evento en {session_id}: {seconds:.3f}s")
            if 0.0 <= seconds <= 10.0:
                bucket = "evento_confirmado" if seconds <= 0 else next((f"{high:g}_{low:g}s" for high, low in WINDOWS if low < seconds <= high), "evento_confirmado")
                outcome_name = str(row.outcome).casefold()
                main_label = 0 if outcome_name in {"eliminado", "0", "death"} else 2 if outcome_name in {"victoria", "2", "victory"} else 1
                output.append({**row._asdict(), "main_label": main_label, "seconds_to_event": seconds, "window": bucket, "risk_3s": int(0 < seconds <= 3), "risk_5s": int(0 < seconds <= 5), "risk_10s": int(0 < seconds <= 10)})
        # Negativos explícitos: sobreviven y no se reutilizan como positivos.
        if str(group["outcome"].iloc[0]).casefold() in {"survived", "victoria", "eliminacion"}:
            for row in group.sort_values("timestamp_sec").itertuples(index=False):
                outcome_name = str(row.outcome).casefold()
                main_label = 2 if outcome_name in {"victoria", "2", "victory"} else 1
                output.append({**row._asdict(), "main_label": main_label, "seconds_to_event": None, "window": "negative_survival", "risk_3s": 0, "risk_5s": 0, "risk_10s": 0})
    return pd.DataFrame(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build_windows(pd.read_csv(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")
    print({"windows": len(result), "output": str(args.output), "test_used": False})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
