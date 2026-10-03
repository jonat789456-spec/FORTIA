from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

EVENT_TYPES = ("player_eliminated", "opponent_eliminated", "victory_confirmed")
VERSION = "automatic-temporal-labeling-0.3.0"
REGIONS = {"top_center": (.15, 0, .85, .38), "center": (.10, .12, .90, .78), "top_full": (0, 0, 1, .42)}
TEXT_PATTERNS = {"player_eliminated": ("eliminado por", "eliminada por", "eliminated by", "eliminado po"), "opponent_eliminated": ("eliminación", "eliminacion", "elimination", "eliminado"), "victory_confirmed": ("victoria campal", "victoria camp", "victory royale", "victory", "ictoria campal", "ictoria")}
OCR_STATS = {"calls": 0, "cache_hits": 0, "cache_misses": 0, "seconds": 0.0, "preprocess_seconds": 0.0, "durations": []}
OCR_CACHE: dict[str, list[dict[str, object]]] = {}
OCR_CACHE_PATH: Path | None = None
OCR_CACHE_MODE = "use"

def reset_ocr_stats() -> None:
    OCR_STATS.update({"calls": 0, "cache_hits": 0, "cache_misses": 0, "seconds": 0.0, "preprocess_seconds": 0.0, "durations": []})

def ocr_stats() -> dict[str, object]:
    durations = sorted(OCR_STATS["durations"])
    p95 = durations[min(len(durations)-1, int(len(durations)*.95))] if durations else 0.0
    return {"tesseract_calls": OCR_STATS["calls"], "cache_hits": OCR_STATS["cache_hits"], "cache_misses": OCR_STATS["cache_misses"], "tesseract_seconds": OCR_STATS["seconds"], "preprocess_seconds": OCR_STATS["preprocess_seconds"], "tesseract_mean_sec": OCR_STATS["seconds"] / max(1, OCR_STATS["calls"]), "tesseract_p95_sec": p95}

def configure_ocr_cache(path: Path | None, mode: str = "use") -> None:
    global OCR_CACHE_PATH, OCR_CACHE_MODE, OCR_CACHE
    OCR_CACHE_PATH, OCR_CACHE_MODE, OCR_CACHE = path, mode, {}
    if path and mode == "use" and path.exists():
        try: OCR_CACHE = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): OCR_CACHE = {}

def flush_ocr_cache() -> None:
    if not OCR_CACHE_PATH or OCR_CACHE_MODE == "ignore": return
    OCR_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True); temporary = OCR_CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(OCR_CACHE, ensure_ascii=False), encoding="utf-8"); temporary.replace(OCR_CACHE_PATH)

def ocr_cache_key(frame: np.ndarray, frame_index: int, time_sec: float, regions: tuple[str, ...], exhaustive: bool, language: str = "eng+spa", tesseract_version: str = "") -> str:
    return hashlib.sha256(frame.tobytes()).hexdigest() + f"|{frame_index}|{time_sec:.6f}|{','.join(regions)}|{exhaustive}|{VERSION}|{tesseract_version}|{language}"

@lru_cache(maxsize=1)
def resolve_tesseract() -> tuple[str | None, Path | None, dict[str, object]]:
    config_path = Path(__file__).with_name("tesseract_config.json")
    candidates = [os.environ.get(v, "") for v in ("FORTIA_TESSERACT_CMD", "TESSERACT_CMD")]
    if config_path.exists():
        try: candidates.append(str(json.loads(config_path.read_text(encoding="utf-8")).get("cmd", "")))
        except (OSError, json.JSONDecodeError): pass
    candidates += [r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe", shutil.which("tesseract") or ""]
    command = next((c for c in candidates if c and Path(c).exists()), None); tessdata = Path(__file__).with_name("tessdata")
    if not tessdata.exists() and command:
        installed = Path(command).parent / "tessdata"; tessdata = installed if installed.exists() else None
    diagnostics: dict[str, object] = {"available": bool(command), "path": command, "tessdata": str(tessdata) if tessdata else None, "languages": [], "ocr_enabled": False}
    if command:
        try:
            diagnostics["version"] = subprocess.check_output([command, "--version"], text=True, stderr=subprocess.STDOUT).splitlines()[0]
            langs = subprocess.check_output([command, "--list-langs"], text=True, stderr=subprocess.STDOUT).splitlines(); detected = {x.strip() for x in langs if x.strip() and not x.startswith("List of")}
            if tessdata and tessdata.exists(): detected.update(p.stem for p in tessdata.glob("*.traineddata"))
            diagnostics["languages"] = sorted(detected); diagnostics["ocr_enabled"] = {"eng", "spa"}.issubset(detected)
        except (OSError, subprocess.CalledProcessError) as exc: diagnostics["error"] = str(exc)
    return command, tessdata, diagnostics

def utc_now() -> str: return datetime.now(timezone.utc).isoformat()
def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()
def normalize_text(text: str) -> str:
    for bad, good in (("ÃƒÂ³", "ó"), ("ÃƒÂ¡", "á"), ("ÃƒÂ©", "é"), ("ÃƒÂ­", "í"), ("ÃƒÂº", "ú")): text = text.replace(bad, good)
    return re.sub(r"[^a-z0-9áéíóúüñ ]+", " ", text.casefold()).strip()
def fuzzy_similarity(text: str, phrase: str) -> float:
    from difflib import SequenceMatcher
    text, phrase = normalize_text(text), normalize_text(phrase)
    if phrase in text: return 1.0
    words, target = text.split(), phrase.split(); score = SequenceMatcher(None, text, phrase).ratio()
    for size in range(max(1, len(target) - 1), min(len(words), len(target) + 2) + 1):
        for start in range(len(words) - size + 1): score = max(score, SequenceMatcher(None, " ".join(words[start:start + size]), phrase).ratio())
    return score
def match_event(text: str) -> tuple[str | None, float, str]:
    best: tuple[str | None, float, str] = (None, 0.0, "")
    for event_type, patterns in TEXT_PATTERNS.items():
        for phrase in patterns:
            score = fuzzy_similarity(text, phrase); minimum = .72 if len(phrase) >= 8 else .90
            if score >= minimum and score > best[1]: best = event_type, score, f"ocr:{phrase}"
    return best
def _crop(frame: np.ndarray, region: str):
    h, w = frame.shape[:2]; x1, y1, x2, y2 = REGIONS[region]; bounds = int(w*x1), int(h*y1), int(w*x2), int(h*y2)
    return frame[bounds[1]:bounds[3], bounds[0]:bounds[2]], bounds
def visual_signature(frame: np.ndarray, region: str = "center") -> tuple[float, str]:
    roi, _ = _crop(frame, region); hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    return min(1., .30*float(np.mean(hsv[:,:,1]))/255 + .30*float(np.mean(hsv[:,:,2]))/255 + .40*float(np.mean(cv2.Canny(roi,80,160)))/255), "visual_banner_geometry"

@dataclass
class OCRObservation:
    time_sec: float; frame: int; text_original: str; text_normalized: str; ocr_confidence: float; fuzzy_similarity: float; event_type: str; region: str; region_bbox_rel: tuple[float,float,float,float]; method: str; visual_score: float
    image_path: str = ""; region_path: str = ""; preprocessed_path: str = ""; mask_path: str = ""
def optional_ocr_observations(frame: np.ndarray, time_sec: float = 0., frame_index: int = 0, exhaustive: bool = True, region_names: tuple[str,...] | None = None) -> list[OCRObservation]:
    try: import pytesseract  # type: ignore
    except ImportError: return []
    command, tessdata, diagnostics = resolve_tesseract()
    if not command or not diagnostics.get("ocr_enabled"): return []
    cache_key = ocr_cache_key(frame, frame_index, time_sec, region_names or (), exhaustive, "eng+spa", str(diagnostics.get("version", "")))
    if OCR_CACHE_MODE != "rebuild" and cache_key in OCR_CACHE:
        OCR_STATS["cache_hits"] += 1
        return [OCRObservation(**item) for item in OCR_CACHE[cache_key]]
    OCR_STATS["cache_misses"] += 1
    pytesseract.pytesseract.tesseract_cmd = command
    if tessdata: os.environ["TESSDATA_PREFIX"] = str(tessdata)
    regions = region_names or (("top_center", "center", "top_full") if exhaustive else ("top_center", "center")); found = []
    for region in regions:
        preprocessing_started = time.perf_counter(); crop, _ = _crop(frame, region); gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY); scaled = cv2.resize(gray, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC); OCR_STATS["preprocess_seconds"] += time.perf_counter() - preprocessing_started
        variants = [scaled, cv2.threshold(scaled,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]] if exhaustive else [scaled]
        for vi, variant in enumerate(variants):
            for psm in ((6,7,11,12) if exhaustive else (6,)):
                started = time.perf_counter(); data = pytesseract.image_to_data(variant, lang="eng+spa", config=f"--psm {psm}", output_type=pytesseract.Output.DICT); elapsed = time.perf_counter() - started; OCR_STATS["calls"] += 1; OCR_STATS["seconds"] += elapsed; OCR_STATS["durations"].append(elapsed); raw = " ".join(str(v) for v in data.get("text",[]) if str(v).strip()); event, similarity, _ = match_event(raw)
                vals = [float(c) for c in data.get("conf",[]) if str(c).strip() not in {"", "-1"}]; confidence = max(0., min(1., sum(vals)/len(vals)/100)) if vals else 0.
                if event:
                    found.append(OCRObservation(time_sec, frame_index, raw, normalize_text(raw), confidence, similarity, event, region, REGIONS[region], f"ocr_eng_spa_{region}_psm{psm}_v{vi}", visual_signature(crop)[0]))
                    if not exhaustive and similarity >= .94: break
            if found and not exhaustive and max(x.fuzzy_similarity for x in found) >= .94: break
    unique = {}
    for item in found:
        key = (item.event_type, item.region)
        if key not in unique or (item.fuzzy_similarity,item.ocr_confidence) > (unique[key].fuzzy_similarity,unique[key].ocr_confidence): unique[key] = item
    result = list(unique.values())
    if OCR_CACHE_MODE != "ignore": OCR_CACHE[cache_key] = [item.__dict__ for item in result]
    return result
def optional_ocr(frame: np.ndarray, exhaustive: bool=True):
    found=optional_ocr_observations(frame,exhaustive=exhaustive)
    if not found: return "",0.,"ocr_unavailable_or_no_event_match"
    item=max(found,key=lambda x:x.fuzzy_similarity*x.ocr_confidence); return item.text_normalized,item.ocr_confidence,item.method

@dataclass
class Detection:
    id_video: str; video_name: str; video_path: str; event_type: str; event_time_sec: float; event_frame: int; confirmation_start_sec: float; confirmation_end_sec: float; duration_sec: float; fps: float; ocr_text_original: str; ocr_text_normalized: str; ocr_confidence: float; fuzzy_similarity: float; region: str; region_bbox_rel: str; consecutive_frames: int; persistence_duration_sec: float; visual_evidence: str; auditory_evidence: str; signals_available: str; signals_used: str; missing_signals: str; contradictory_signals: str; confidence_score: float; confidence_level: str; confidence_reason: str; acceptance_rule: str; applied_threshold: str; exclusion_reason: str; timestamp_uncertainty_sec: float; evidence_visual_path: str; evidence_region_path: str; evidence_preprocessed_path: str; evidence_mask_path: str; event_sequence_number: int; candidate_time_sec: float; first_possible_time_sec: float; first_confirmed_time_sec: float; first_stable_signal_sec: float; confirmation_end_sec_refined: float; ocr_confirmation_time_sec: float; visual_onset_time_sec: float; onset_method: str; ocr_calls_used: int; visual_frames_used: int; pre_event_signal_time_sec: float | None; pre_event_signal_type: str; pre_event_signal_confidence: float; frame_pts: float | None; frame_time_base: str; native_frame_observed: bool; native_evidence_type: str; source_fps: float; decoded_fps: float; visual_analysis_fps: float; ocr_analysis_fps: float; timestamp_source: str; native_fps: float; refinement_fps: float; refinement_rule: str; evidence_manifest_path: str; detector_version: str; processed_at: str
def confidence_level(score: float) -> str: return "high_confidence" if score>=.85 else "medium_confidence" if score>=.60 else "low_confidence" if score>=.35 else "ambiguous"
def _decision(group):
    best=max(group,key=lambda x:(x.fuzzy_similarity,x.ocr_confidence)); count=len(group); exact=best.fuzzy_similarity>=.94; partial=best.event_type=="victory_confirmed" and best.region=="top_center" and best.fuzzy_similarity>=.90 and (len(best.text_normalized)>=6 or count>=2)
    if best.event_type=="player_eliminated": rule="strong_ocr_player_eliminated" if exact and best.region in {"top_center","top_full"} else "moderate_ocr_player_eliminated"
    elif best.event_type=="opponent_eliminated": rule="strong_ocr_opponent_eliminated" if exact and best.region in {"top_center","top_full"} else "moderate_ocr_opponent_eliminated"
    else: rule="persistent_partial_victory_banner" if partial and count>=2 else "strong_ocr_victory_confirmed" if exact and best.region in {"top_center", "top_full"} else "moderate_ocr_victory_confirmed"
    threshold="text>=0.90, region=top_center, frames>=2" if rule=="persistent_partial_victory_banner" else "text>=0.94, expected_region, no_contradiction" if rule.startswith("strong") else "text>=0.72, persistence_or_consensus"; score=min(1.,.72*(.65*best.fuzzy_similarity+.35*best.ocr_confidence)+.28*min(1.,count/2)); accepted=(rule.startswith("strong") or rule=="persistent_partial_victory_banner") and best.fuzzy_similarity>=.90
    if accepted: score=max(score,.86)
    return score,rule,threshold,"OCR inequívoco en región esperada; audio ausente no penaliza" if accepted else "requiere persistencia, consenso o similitud adicional","ocr,visual_geometry","audio","ocr,fuzzy_similarity,region,persistence,visual_geometry"

@dataclass(frozen=True)
class FrameTiming:
    frame_index: int; time_sec: float; pts: float | None; time_base: str; timestamp_source: str
def _timing(cap,index,fps):
    ms=float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.)
    return FrameTiming(index,ms/1000.,ms/1000.,"1/1000","opencv_pos_msec") if math.isfinite(ms) and ms>0 else FrameTiming(index,index/fps if fps else 0.,None,"1/fps","frame_index_over_source_fps")
def _save_evidence(item,frame,output,prefix):
    output.mkdir(parents=True,exist_ok=True); crop,_=_crop(frame,item.region); gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY); scaled=cv2.resize(gray,None,fx=2.2,fy=2.2,interpolation=cv2.INTER_CUBIC); mask=cv2.threshold(scaled,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]; item.image_path=str(output/f"{prefix}_full.jpg"); item.region_path=str(output/f"{prefix}_{item.region}.jpg"); item.preprocessed_path=str(output/f"{prefix}_preprocessed.jpg"); item.mask_path=str(output/f"{prefix}_mask.png"); cv2.imwrite(item.image_path,frame); cv2.imwrite(item.region_path,crop); cv2.imwrite(item.preprocessed_path,scaled); cv2.imwrite(item.mask_path,mask)

def _refine_group_legacy(video_path,group,fps,duration,refinement_fps):
    candidate=min(group,key=lambda x:x.time_sec); start=max(0.,candidate.time_sec-2.); end=min(duration,max(x.time_sec for x in group)+(8. if candidate.event_type=="victory_confirmed" else 3.)); cap=cv2.VideoCapture(str(video_path)); observations=[]; frames_seen=0; ocr_frames=0; last_visual=None; last_ocr=-1e9
    if not cap.isOpened(): return candidate,None,{"candidate_time_sec":candidate.time_sec,"first_possible_time_sec":candidate.time_sec,"first_confirmed_time_sec":candidate.time_sec,"native_frame_observed":False,"decoded_fps":0.,"visual_analysis_fps":0.,"ocr_analysis_fps":0.,"refinement_rule":"refinement_unavailable","evidence_frames":[]}
    safe=max(0,int(max(0.,start-2.)*fps)); cap.set(cv2.CAP_PROP_POS_FRAMES,safe); index=safe
    while True:
        ok,frame=cap.read()
        if not ok: break
        t=_timing(cap,index,fps); index+=1
        if t.time_sec<start: continue
        if t.time_sec>end: break
        frames_seen+=1; score,_=visual_signature(frame,"top_full"); changed=last_visual is None or abs(score-last_visual)>=.025; near=abs(t.time_sec-candidate.time_sec)<=1.; due=t.time_sec-last_ocr>=1./max(12.,refinement_fps); last_visual=score
        if changed or near or due:
            last_ocr=t.time_sec; ocr_frames+=1; found=optional_ocr_observations(frame,t.time_sec,t.frame_index,exhaustive=False); compatible=[x for x in found if x.event_type==candidate.event_type]
            if compatible: observations.append((max(compatible,key=lambda x:(x.fuzzy_similarity,x.ocr_confidence)),frame,t))
    cap.release(); elapsed=max(end-start,1e-9); base={"candidate_time_sec":candidate.time_sec,"native_frame_observed":frames_seen>0,"decoded_fps":frames_seen/elapsed,"visual_analysis_fps":frames_seen/elapsed,"ocr_analysis_fps":ocr_frames/elapsed,"frame_time_base":"1/1000_or_1/fps","timestamp_source":"opencv_pos_msec_or_frame_index_fallback","evidence_frames":[]}
    if not observations: return candidate,None,{**base,"first_possible_time_sec":candidate.time_sec,"first_confirmed_time_sec":candidate.time_sec,"refinement_rule":"native_frames_without_event_specific_evidence"}
    first=observations[0][2]; confirmed=next((i-1 for i in range(1,len(observations)) if observations[i][2].time_sec-observations[i-1][2].time_sec<=max(3./fps,1./max(12.,refinement_fps))),None); selected=observations[confirmed if confirmed is not None else 0]; end_confirmation=observations[confirmed+1][2] if confirmed is not None else selected[2]; evidence=[{"role":"first_possible","frame":first.frame_index,"pts":first.pts,"timestamp_sec":first.time_sec},{"role":"first_confirmed","frame":selected[2].frame_index,"pts":selected[2].pts,"timestamp_sec":selected[2].time_sec},{"role":"confirmation_end","frame":end_confirmation.frame_index,"pts":end_confirmation.pts,"timestamp_sec":end_confirmation.time_sec}]
    return selected[0],selected[1],{**base,"first_possible_time_sec":first.time_sec,"first_confirmed_time_sec":selected[2].time_sec,"first_stable_signal_sec":selected[2].time_sec,"confirmation_end_sec":end_confirmation.time_sec,"frame_pts":selected[2].pts,"frame_time_base":selected[2].time_base,"timestamp_source":selected[2].timestamp_source,"evidence_frames":evidence,"refinement_rule":"first_two_compatible_sequential_native_frames" if confirmed is not None else "single_inequivocal_native_reading"}

def _refine_group(video_path, group, fps, duration, refinement_fps):
    """Cascada: todos los frames pasan por visión; OCR solo confirma propuestas."""
    candidate = min(group, key=lambda x: x.time_sec); start = max(0., candidate.time_sec - 2.); end = min(duration, max(x.time_sec for x in group) + (8. if candidate.event_type == "victory_confirmed" else 3.))
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened(): return candidate, None, {"candidate_time_sec": candidate.time_sec, "first_possible_time_sec": candidate.time_sec, "first_confirmed_time_sec": candidate.time_sec, "native_frame_observed": False, "refinement_rule": "refinement_unavailable", "evidence_frames": []}
    safe = max(0, int(max(0., start - 2.) * fps)); cap.set(cv2.CAP_PROP_POS_FRAMES, safe); index = safe; frames = []; proposals = []; previous = None
    while True:
        ok, frame = cap.read()
        if not ok: break
        timing = _timing(cap, index, fps); index += 1
        if timing.time_sec < start: continue
        if timing.time_sec > end: break
        visual, _ = visual_signature(frame, "top_full"); changed = previous is None or abs(visual - previous) >= .018
        frames.append((timing, cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA), visual));
        if changed and (visual >= .25 or abs(timing.time_sec - candidate.time_sec) <= 1.): proposals.append(len(frames) - 1)
        previous = visual
    cap.release(); elapsed = max(end - start, 1e-9); base = {"candidate_time_sec": candidate.time_sec, "native_frame_observed": bool(frames), "decoded_fps": len(frames)/elapsed, "visual_analysis_fps": len(frames)/elapsed, "ocr_analysis_fps": 0., "frame_time_base": "1/1000_or_1/fps", "timestamp_source": "opencv_pos_msec_or_frame_index_fallback", "visual_frames_used": len(frames), "ocr_calls_used": 0, "evidence_frames": []}
    if not frames: return candidate, None, {**base, "first_possible_time_sec": candidate.time_sec, "first_confirmed_time_sec": candidate.time_sec, "refinement_rule": "refinement_unavailable"}
    # Representantes: comienzo, mejor calidad visual, cercanía al candidato y centro; se deduplican por frames.
    ranked = sorted(set(proposals), key=lambda i: (abs(frames[i][0].time_sec-candidate.time_sec), -frames[i][2]))
    ranked += [max(range(len(frames)), key=lambda i: frames[i][2]), min(range(len(frames)), key=lambda i: abs(frames[i][0].time_sec-candidate.time_sec)), len(frames)//2]
    chosen = []
    for i in ranked:
        if all(abs(frames[i][0].frame_index - frames[j][0].frame_index) > max(1, int(fps*.08)) for j in chosen): chosen.append(i)
        if len(chosen) >= 4: break
    # Recupera solo los representantes completos; el resto permanece en thumbnails.
    selected_frames = {}; full_cap = cv2.VideoCapture(str(video_path)); full_cap.set(cv2.CAP_PROP_POS_FRAMES, safe); full_index = safe
    while selected_frames.keys() != set(chosen):
        ok, full_frame = full_cap.read()
        if not ok: break
        if full_index in chosen: selected_frames[full_index] = full_frame.copy()
        if full_index > max(chosen): break
        full_index += 1
    full_cap.release()
    observations = []
    for i in sorted(chosen):
        timing, _, _ = frames[i]; frame = selected_frames.get(i)
        if frame is None: continue
        regions = (candidate.region,) if candidate.region in REGIONS else None; exhaustive_confirmation = candidate.region == "top_full" and not observations; found = optional_ocr_observations(frame, timing.time_sec, timing.frame_index, exhaustive=exhaustive_confirmation, region_names=regions); compatible = [x for x in found if x.event_type == candidate.event_type]
        if compatible: observations.append((max(compatible, key=lambda x:(x.fuzzy_similarity,x.ocr_confidence)), frame, timing, i))
    base["ocr_calls_used"] = int(ocr_stats()["tesseract_calls"]); base["ocr_analysis_fps"] = len(chosen)/elapsed
    if not observations: return candidate, None, {**base, "first_possible_time_sec": candidate.time_sec, "first_confirmed_time_sec": candidate.time_sec, "refinement_rule": "native_frames_without_event_specific_evidence"}
    selected = max(observations, key=lambda x:(x[0].fuzzy_similarity, x[0].ocr_confidence)); selected_i = selected[3]; selected_thumb = frames[selected_i][1]; onset_i = selected_i
    # Seguimiento visual hacia atrás: no hay OCR y se exige continuidad visual con el banner confirmado.
    stable = 0
    for i in range(selected_i, -1, -1):
        small_a = cv2.resize(frames[i][1], (64, 36)); small_b = cv2.resize(selected_thumb, (64, 36)); difference = float(np.mean(cv2.absdiff(small_a, small_b))) / 255.
        if difference <= .20: onset_i = i; stable += 1
        elif stable >= 2: break
        else: stable = 0
    onset = frames[onset_i][0]; confirmed = selected[2]; evidence = [{"role":"visual_onset","frame":onset.frame_index,"pts":onset.pts,"timestamp_sec":onset.time_sec},{"role":"ocr_confirmation","frame":confirmed.frame_index,"pts":confirmed.pts,"timestamp_sec":confirmed.time_sec}]
    return selected[0], selected[1], {**base, "first_possible_time_sec": onset.time_sec, "first_stable_signal_sec": onset.time_sec, "first_confirmed_time_sec": confirmed.time_sec, "confirmation_end_sec": confirmed.time_sec, "ocr_confirmation_time_sec": confirmed.time_sec, "visual_onset_time_sec": onset.time_sec, "onset_method": "visual_tracking_after_ocr", "frame_pts": onset.pts, "frame_time_base": onset.time_base, "timestamp_source": onset.timestamp_source, "evidence_frames": evidence, "refinement_rule": "ocr_identity_visual_onset"}

def detect_video(video_path: Path,id_video: str,sample_fps: float=8.,refine_fps: float=12.,evidence_dir: Path|None=None, cache_path: Path|None=None, cache_mode: str="use"):
    configure_ocr_cache(cache_path, cache_mode); reset_ocr_stats(); started_video = time.perf_counter()
    cap=cv2.VideoCapture(str(video_path))
    if not cap.isOpened(): return [],{"status":"failed","error":"video_open_failed"}
    fps=float(cap.get(cv2.CAP_PROP_FPS) or 0.); count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0); duration=count/fps if fps else 0.; stride=max(1,int(round(fps/sample_fps))) if fps else 1; observations=[]; frames={}; index=0; decoded=0; last_visual=None
    while True:
        ok,frame=cap.read()
        if not ok: break
        if index%stride==0:
            t=_timing(cap,index,fps); banner_score,_=visual_signature(frame,"top_full"); changed=last_visual is None or abs(banner_score-last_visual)>=.018; last_visual=banner_score
            # El barrido grueso usa señal visual ligera; OCR solo se activa
            # ante un banner/cambio o como muestreo de seguridad de 1 Hz.
            visual_gate=(changed and banner_score>=.34) or (fps>0 and index%max(1,int(round(fps)))==0)
            found=optional_ocr_observations(frame,t.time_sec,index,exhaustive=False,region_names=("top_center","center","top_full") if (banner_score>=.34 or index%max(1,int(round(fps)))==0) else None) if visual_gate else []
            observations.extend(found)
            if found: frames[index]=frame.copy()
        index+=1; decoded+=1
    cap.release(); observations.sort(key=lambda x:x.time_sec)
    # Fallback de cobertura para banners estilizados: solo se activa si la
    # cascada ligera no produjo candidatos y restringe OCR a frames visualmente compatibles.
    if not observations:
        cap = cv2.VideoCapture(str(video_path)); index = 0; fallback_step = max(1, int(round(fps))); fallback_frames = []
        while True:
            ok, frame = cap.read()
            if not ok: break
            if index % fallback_step == 0:
                timing = _timing(cap, index, fps); banner_score, _ = visual_signature(frame, "top_full")
                if banner_score >= .25:
                    fallback_frames.append((timing, frame.copy(), banner_score)); found = optional_ocr_observations(frame, timing.time_sec, index, exhaustive=False, region_names=("top_full",)); observations.extend(found); frames[index] = frame.copy()
                    if len(observations) >= 3: break
            index += 1
        cap.release()
        if not observations:
            representatives = sorted(fallback_frames, key=lambda x: (-x[2], abs(x[0].time_sec-duration*.8)))[:6]
            for timing, frame, _ in representatives:
                found = optional_ocr_observations(frame, timing.time_sec, timing.frame_index, exhaustive=True, region_names=("top_full",)); observations.extend(found)
                if len(observations) >= 3: break
        observations.sort(key=lambda x:x.time_sec)
    groups=[]
    for item in observations:
        if not groups or item.time_sec-groups[-1][-1].time_sec>2.5 or item.event_type!=groups[-1][-1].event_type: groups.append([item])
        else: groups[-1].append(item)
    detections=[]
    for sequence,group in enumerate(groups,1):
        best=max(group,key=lambda x:(x.fuzzy_similarity,x.ocr_confidence)); score,rule,threshold,reason,available,missing,used=_decision(group); original_level=confidence_level(score); refined,refined_frame,info=_refine_group(video_path,group,fps,duration,refine_fps); native=bool(info.get("native_frame_observed")); event_time=float(info["first_confirmed_time_sec"]); level=original_level if native and info.get("refinement_rule")!="native_frames_without_event_specific_evidence" else "ambiguous"; accepted=level=="high_confidence"; manifest=""
        if refined_frame is None and best.frame in frames: refined,refined_frame=best,frames[best.frame]
        if evidence_dir and refined_frame is not None:
            _save_evidence(refined,refined_frame,evidence_dir,f"{id_video}_{sequence}_{int(event_time*1000)}"); manifest=str(evidence_dir/f"{id_video}_{sequence}_manifest.json"); Path(manifest).write_text(json.dumps({"event_type":best.event_type,"rule":rule,"frames":info.get("evidence_frames",[]),"ocr_text":refined.text_original,"visual_signal":"compatible_banner_geometry","native_frame_observed":native},ensure_ascii=False,indent=2),encoding="utf-8")
        uncertainty=max(1/max(fps,1.),abs(event_time-float(info["first_possible_time_sec"]))); first,last=group[0],group[-1]; exclusion="" if accepted else ("no_reproducible_confirmed_native_evidence" if not native or not info.get("evidence_frames") else "insufficient_event_specific_evidence")
        detections.append(Detection(str(id_video),video_path.name,str(video_path),best.event_type,event_time,refined.frame,first.time_sec,float(info.get("confirmation_end_sec",last.time_sec)),max(0,last.time_sec-first.time_sec),fps,refined.text_original,refined.text_normalized,refined.ocr_confidence,refined.fuzzy_similarity,refined.region,json.dumps(refined.region_bbox_rel),len(group),max(0,last.time_sec-first.time_sec),"compatible_banner_geometry","unavailable",available,used,missing,"none_detected",score,level,reason,rule,threshold,exclusion,uncertainty,refined.image_path,refined.region_path,refined.preprocessed_path,refined.mask_path,sequence,float(info["candidate_time_sec"]),float(info["first_possible_time_sec"]),event_time,float(info.get("first_stable_signal_sec",event_time)),float(info.get("confirmation_end_sec",event_time)),float(info.get("ocr_confirmation_time_sec",event_time)),float(info.get("visual_onset_time_sec",info["first_possible_time_sec"])),str(info.get("onset_method","")),int(info.get("ocr_calls_used",0)),int(info.get("visual_frames_used",0)),None,"",0.,info.get("frame_pts"),str(info.get("frame_time_base","")),native,"ocr+visual_sequential_frame",fps,float(info.get("decoded_fps",0.)),float(info.get("visual_analysis_fps",0.)),float(info.get("ocr_analysis_fps",0.)),str(info.get("timestamp_source","")),fps,refine_fps,str(info.get("refinement_rule","")),manifest,VERSION,utc_now()))
    flush_ocr_cache(); result={"status":"processed","fps":fps,"source_fps":fps,"frame_count":count,"duration_sec":duration,"sample_fps":sample_fps,"refine_fps":refine_fps,"decoded_fps":decoded/max(duration,1e-9),"candidate_count":len(observations),"detection_count":len(detections),"accepted_count":sum(x.confidence_level=="high_confidence" for x in detections),"fps_mode":"constant_assumed_by_container_metadata","video_seconds":time.perf_counter()-started_video,"ocr":ocr_stats()}; return detections,result
def executable_versions():
    command,_,diagnostics=resolve_tesseract(); return {"python":subprocess.check_output(["python","--version"],text=True,stderr=subprocess.STDOUT).strip(),"opencv":cv2.__version__,"tesseract":command,"ffprobe":shutil.which("ffprobe"),"tesseract_diagnostics":diagnostics}
