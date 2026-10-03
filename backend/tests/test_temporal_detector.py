import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "temporal_labeling"))

import numpy as np

from detector import OCRObservation, _decision, confidence_level, fuzzy_similarity, match_event, _timing, ocr_cache_key  # noqa: E402


def observation(text: str, event: str, frame: int, time: float, region: str = "top_center") -> OCRObservation:
    return OCRObservation(time, frame, text, text.casefold(), 0.80, fuzzy_similarity(text, "eliminado por" if event == "player_eliminated" else "ictoria"), event, region, (0.15, 0, 0.85, 0.38), "test", 0.7)


def test_exact_player_ocr_is_accepted_without_audio() -> None:
    score, rule, _, _, available, missing, _ = _decision([observation("ELIMINADO POR", "player_eliminated", 10, 1.0)])
    assert score >= 0.85
    assert rule == "strong_ocr_player_eliminated"
    assert "ocr" in available and missing == "audio"


def test_persistent_partial_victory_is_accepted() -> None:
    group = [observation("ictoria", "victory_confirmed", n, 1.0 + n / 8) for n in (1, 2)]
    score, rule, *_ = _decision(group)
    assert score >= 0.85
    assert rule == "persistent_partial_victory_banner"


def test_isolated_out_of_region_is_not_strong() -> None:
    item = observation("ictoria", "victory_confirmed", 1, 1.0, "center")
    score, rule, *_ = _decision([item])
    assert score < 0.85
    assert rule != "persistent_partial_victory_banner"


def test_generic_words_do_not_match() -> None:
    assert match_event("por") [0] is None
    assert match_event("campal") [0] is None


def test_confidence_categories_are_stable() -> None:
    assert confidence_level(.90) == "high_confidence"
    assert confidence_level(.70) == "medium_confidence"
    assert confidence_level(.40) == "low_confidence"
    assert confidence_level(.20) == "ambiguous"


def test_pts_is_converted_to_seconds_when_decoder_exposes_it() -> None:
    class Capture:
        def get(self, prop: int) -> float:
            return 1250.0

    timing = _timing(Capture(), 30, 24.0)
    assert timing.time_sec == 1.25
    assert timing.pts == 1.25
    assert timing.timestamp_source == "opencv_pos_msec"


def test_frame_index_fallback_is_explicit_for_missing_pts() -> None:
    class Capture:
        def get(self, prop: int) -> float:
            return 0.0

    timing = _timing(Capture(), 30, 24.0)
    assert timing.time_sec == 1.25
    assert timing.pts is None
    assert timing.timestamp_source == "frame_index_over_source_fps"


def test_ocr_cache_key_changes_with_pts_and_configuration() -> None:
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    first = ocr_cache_key(frame, 10, 1.0, ("top_center",), False, "eng+spa", "tesseract")
    different_time = ocr_cache_key(frame, 10, 1.1, ("top_center",), False, "eng+spa", "tesseract")
    different_config = ocr_cache_key(frame, 10, 1.0, ("center",), False, "eng+spa", "tesseract")
    assert first != different_time
    assert first != different_config
