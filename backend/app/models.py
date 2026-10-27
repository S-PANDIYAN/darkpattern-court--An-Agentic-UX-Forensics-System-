from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Finding:
    pattern: str                    # taxonomy key
    description: str                # human-readable explanation
    confidence: float               # 0..1 how sure the detector is
    severity: float                 # 0..1 harm to the user
    evidence: list[str] = field(default_factory=list)   # quotes / measurements
    source: str = "dom"             # dom | ocr | vlm | temporal | path
    node_id: Optional[str] = None   # ToT node (= page state) where it was observed
    step: Optional[int] = None
    url: Optional[str] = None
    bbox: Optional[dict] = None     # {x,y,w,h} in page coordinates
    exhibit: Optional[str] = None   # relative path of annotated crop

    def to_dict(self):
        return asdict(self)
