from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import uuid


@dataclass(frozen=True)
class NormalizedStory:
    record_id: str
    source_reference: str
    title: str
    description: str
    actors: tuple[str, ...]
    goals: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    assumptions: tuple[str, ...]
    open_questions: tuple[str, ...]
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        source_reference: str,
        title: str,
        description: str,
        actors: tuple[str, ...],
        goals: tuple[str, ...],
        acceptance_criteria: tuple[str, ...],
        assumptions: tuple[str, ...],
        open_questions: tuple[str, ...],
    ) -> NormalizedStory:
        return cls(
            record_id=str(uuid.uuid4()),
            source_reference=source_reference,
            title=title,
            description=description,
            actors=actors,
            goals=goals,
            acceptance_criteria=acceptance_criteria,
            assumptions=assumptions,
            open_questions=open_questions,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
