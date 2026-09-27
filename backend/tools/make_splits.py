"""Crea y valida splits estratificados por video, sin fuga entre modalidades."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split


ROOT = Path(__file__).resolve().parents[2]
DF_ROOT = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF")
MANIFEST_ROOT = ROOT / "backend" / "data" / "manifests"
SPLIT_ROOT = ROOT / "backend" / "data" / "splits"
REPORT_ROOT = ROOT / "backend" / "reports" / "splits"
SEED = 42


def main() -> int:
    videos = pd.read_csv(DF_ROOT / "df_videos.csv", encoding="utf-8-sig")
    videos.insert(0, "id_video", range(1, len(videos) + 1))
    duplicate_groups = pd.read_csv(MANIFEST_ROOT / "duplicate_groups.csv", encoding="utf-8-sig")

    # Union-find: todos los videos conectados por un duplicado exacto deben
    # permanecer en el mismo conjunto, aunque aparezcan en grupos distintos.
    parent = {int(value): int(value) for value in videos["id_video"]}

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    duplicate_components = 0
    for row in duplicate_groups.itertuples(index=False):
        paths = json.loads(row.paths)
        ids = sorted({int(match.group(1)) for path in paths if (match := re.search(r"video[_-]?(\d+)", path, re.IGNORECASE))})
        if len(ids) > 1:
            duplicate_components += 1
            for identifier in ids[1:]:
                union(ids[0], identifier)

    videos["group_id"] = videos["id_video"].map(lambda value: find(int(value)))
    videos["ambiguous_abajo"] = videos["video"].str.casefold().str.contains("abajo", na=False)
    initial_ambiguous_ids = set(videos.loc[videos["ambiguous_abajo"], "id_video"].astype(int))
    ambiguous_roots = {find(identifier) for identifier in initial_ambiguous_ids}
    videos["supervised_eligible"] = ~videos["group_id"].isin(ambiguous_roots)
    videos["exclusion_reason"] = videos.apply(
        lambda row: "abajo_ambiguo_o_duplicado_con_abajo" if not row["supervised_eligible"] else "",
        axis=1,
    )
    eligible_videos = videos[videos["supervised_eligible"]].copy()
    groups = eligible_videos.groupby("group_id", as_index=False).agg(
        representative_class=("etiqueta", "first"),
        class_count=("etiqueta", "nunique"),
        videos=("id_video", "count"),
    )
    groups["stratify_label"] = groups["representative_class"].astype(str)
    train_groups, remaining_groups = train_test_split(groups["group_id"], test_size=0.30, random_state=SEED, stratify=groups["stratify_label"])
    remaining = groups[groups["group_id"].isin(remaining_groups)]
    val_groups, test_groups = train_test_split(remaining["group_id"], test_size=0.50, random_state=SEED, stratify=remaining["stratify_label"])
    split_by_group = {int(value): "train" for value in train_groups}
    split_by_group.update({int(value): "validation" for value in val_groups})
    split_by_group.update({int(value): "test" for value in test_groups})
    split_by_id = {int(row.id_video): split_by_group[int(row.group_id)] for row in eligible_videos.itertuples()}
    eligible_videos["split"] = eligible_videos["id_video"].map(split_by_id)
    videos["split"] = videos["id_video"].map(lambda value: split_by_id.get(int(value), "excluded_ambiguous"))
    train_ids = videos.loc[videos["split"] == "train", "id_video"]
    val_ids = videos.loc[videos["split"] == "validation", "id_video"]
    test_ids = videos.loc[videos["split"] == "test", "id_video"]

    SPLIT_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    videos.to_csv(SPLIT_ROOT / "video_split.csv", index=False, encoding="utf-8-sig")
    videos.loc[~videos["supervised_eligible"], ["id_video", "video", "clase", "ambiguous_abajo", "group_id", "exclusion_reason"]].to_csv(SPLIT_ROOT / "excluded_ambiguous.csv", index=False, encoding="utf-8-sig")

    overlap = {
        "train_validation": sorted(set(train_ids) & set(val_ids)),
        "train_test": sorted(set(train_ids) & set(test_ids)),
        "validation_test": sorted(set(val_ids) & set(test_ids)),
    }
    cross_split_duplicate_groups = []
    for row in duplicate_groups.itertuples(index=False):
        paths = json.loads(row.paths)
        ids = {int(match.group(1)) for path in paths if (match := re.search(r"video[_-]?(\d+)", path, re.IGNORECASE))}
        splits = sorted({videos.loc[videos["id_video"] == identifier, "split"].iloc[0] for identifier in ids if identifier in split_by_id})
        if len(splits) > 1:
            cross_split_duplicate_groups.append({"sha256": row.sha256, "ids": sorted(ids), "splits": splits})

    class_by_split = videos.groupby(["split", "clase", "etiqueta"], dropna=False).size().reset_index(name="videos")
    class_by_split.to_csv(REPORT_ROOT / "class_distribution_by_split.csv", index=False, encoding="utf-8-sig")
    summary = {
        "seed": SEED,
        "requested_ratios": {"train": 0.70, "validation": 0.15, "test": 0.15},
        "actual_counts": videos["split"].value_counts().to_dict(),
        "supervised_counts": eligible_videos["split"].value_counts().to_dict(),
        "actual_ratios": eligible_videos["split"].value_counts(normalize=True).round(6).to_dict(),
        "class_distribution": class_by_split.to_dict(orient="records"),
        "duplicate_group_count": int(len(groups)),
        "duplicate_groups_with_multiple_ids": int(duplicate_components),
        "mixed_label_groups": int((groups["class_count"] > 1).sum()),
        "initial_abajo_excluded": int(len(initial_ambiguous_ids)),
        "total_excluded_from_supervision": int((~videos["supervised_eligible"]).sum()),
        "overlap": overlap,
        "cross_split_duplicate_groups": cross_split_duplicate_groups,
        "augmentation_applied": False,
        "scaler_fit_split": "train_only",
        "test_used_for_selection": False,
        "valid": bool(not any(overlap.values()) and not cross_split_duplicate_groups and videos.loc[videos["supervised_eligible"], "split"].notna().all() and initial_ambiguous_ids.issubset(set(videos.loc[~videos["supervised_eligible"], "id_video"]))),
    }
    (REPORT_ROOT / "split_validation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [
        "# Validación del split por video",
        "",
        f"Semilla: `{SEED}`",
        "",
        class_by_split.to_markdown(index=False),
        "",
        f"- Solapamientos de IDs: `{overlap}`",
        f"- Grupos duplicados que cruzan splits: **{len(cross_split_duplicate_groups)}**",
        f"- Casos `Abajo` excluidos inicialmente: **{len(initial_ambiguous_ids)}**",
        f"- Videos excluidos por componentes duplicados conectados: **{int((~videos['supervised_eligible']).sum())}**",
        "- Aumentación aplicada: **no**",
        "- Ajuste de scaler: **solo train**",
        "- Prueba utilizada para seleccionar modelos: **no**",
        f"- Estado automático: **{'válido' if summary['valid'] else 'requiere revisión'}**",
    ]
    (REPORT_ROOT / "SPLIT_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"split": str(SPLIT_ROOT / "video_split.csv"), "report": str(REPORT_ROOT / "split_validation.json"), "valid": summary["valid"]}, ensure_ascii=False))
    return 0 if summary["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
