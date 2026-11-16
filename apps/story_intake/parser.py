from __future__ import annotations

from pathlib import Path
import re
import zipfile

from docx import Document

from shared.contracts.story import NormalizedStory
from shared.errors.exceptions import ValidationError


MAX_DOCX_BYTES = 5 * 1024 * 1024
MAX_DOCX_EXPANDED_BYTES = 25 * 1024 * 1024
MAX_DOCX_MEMBERS = 1000

_FIELD_NAMES = {
    "source reference": "source_reference",
    "source_reference": "source_reference",
    "reference": "source_reference",
    "title": "title",
    "description": "description",
    "actors": "actors",
    "actor": "actors",
    "goals": "goals",
    "goal": "goals",
    "acceptance criteria": "acceptance_criteria",
    "acceptance_criteria": "acceptance_criteria",
    "assumptions": "assumptions",
    "open questions": "open_questions",
    "open_questions": "open_questions",
}
_SINGLE_FIELDS = {"source_reference", "title", "description"}
_FIELD_RE = re.compile(r"^\s*([^:]{1,60}):\s*(.*?)\s*$")


def _docx_text(path: Path) -> list[str]:
    if path.suffix.lower() != ".docx":
        raise ValidationError("Story intake accepts a .docx file")
    try:
        size = path.stat().st_size
        if size > MAX_DOCX_BYTES:
            raise ValidationError("Word document exceeds the 5 MiB input limit")
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > MAX_DOCX_MEMBERS or sum(item.file_size for item in members) > MAX_DOCX_EXPANDED_BYTES:
                raise ValidationError("Word document exceeds safe archive limits")
            if any(item.flag_bits & 0x1 for item in members):
                raise ValidationError("Encrypted Word documents are not supported")
        document = Document(path)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("Unable to read a valid Word .docx document") from exc

    text = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if len(cells) >= 2 and cells[0]:
                text.append(f"{cells[0].rstrip(':')}: {' '.join(cells[1:]).strip()}")
            else:
                text.extend(cell for cell in cells if cell)
    return text


def parse_word_story(path: str | Path) -> NormalizedStory:
    """Extract only explicitly labeled fields; never infer or fill missing requirements."""
    source = Path(path)
    fields: dict[str, list[str]] = {name: [] for name in set(_FIELD_NAMES.values())}
    current_field: str | None = None
    duplicates: list[str] = []
    for line in _docx_text(source):
        match = _FIELD_RE.match(line)
        if match:
            field_name = _FIELD_NAMES.get(match.group(1).strip().lower())
            if field_name is None:
                current_field = None
                continue
            value = match.group(2).strip()
            current_field = field_name
            if value:
                fields[field_name].append(value)
            continue
        if current_field and line.strip():
            fields[current_field].append(line.strip())

    for name in _SINGLE_FIELDS:
        if len(fields[name]) > 1:
            duplicates.append(name)
    required = ("source_reference", "title", "description", "actors", "goals", "acceptance_criteria")
    missing = [name for name in required if not fields[name]]
    if missing or duplicates:
        problems = []
        if missing:
            problems.append("missing fields: " + ", ".join(sorted(missing)))
        if duplicates:
            problems.append("ambiguous repeated fields: " + ", ".join(sorted(duplicates)))
        raise ValidationError("Story intake requires clarification (" + "; ".join(problems) + ")")

    normalized_lists = {
        name: tuple(value.strip().lstrip("-*• ").strip() for value in values if value.strip().lstrip("-*• ").strip())
        for name, values in fields.items()
        if name not in _SINGLE_FIELDS
    }
    return NormalizedStory.create(
        source_reference=fields["source_reference"][0],
        title=fields["title"][0],
        description=fields["description"][0],
        actors=normalized_lists["actors"],
        goals=normalized_lists["goals"],
        acceptance_criteria=normalized_lists["acceptance_criteria"],
        assumptions=normalized_lists["assumptions"],
        open_questions=normalized_lists["open_questions"],
    )
