from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    project_root: Path
    raw_data_dir: Path
    processed_data_dir: Path
    feature_data_dir: Path


def load_config() -> PipelineConfig:
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    return PipelineConfig(
        project_root=project_root,
        raw_data_dir=data_dir / "raw",
        processed_data_dir=data_dir / "processed",
        feature_data_dir=data_dir / "features",
    )

