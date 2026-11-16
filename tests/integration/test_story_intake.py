from docx import Document
import pytest

from apps.story_intake.parser import parse_word_story
from apps.story_intake.main import main
from apps.story_intake.store import StoryRecordStore
from shared.errors.exceptions import ValidationError


def _write_story(path, omit_criteria=False):
    document = Document()
    document.add_paragraph("Source reference: SCRUM-6")
    document.add_paragraph("Title: Tour overview")
    document.add_paragraph("Description: Present a static tour itinerary.")
    document.add_paragraph("Actors: Traveler")
    document.add_paragraph("Goals: Review trip details")
    if not omit_criteria:
        document.add_paragraph("Acceptance criteria: Keep the brochure available.")
    document.add_paragraph("Assumptions: The page is static.")
    document.add_paragraph("Open questions: None")
    document.save(path)


def test_word_story_normalizes_and_persists_until_explicit_delete(tmp_path):
    document_path = tmp_path / "story.docx"
    database_path = tmp_path / "records.sqlite3"
    _write_story(document_path)

    story = parse_word_story(document_path)
    store = StoryRecordStore(database_path)
    store.add(story)

    reopened = StoryRecordStore(database_path)
    assert reopened.list_records()[0]["source_reference"] == "SCRUM-6"
    assert reopened.list_records()[0]["acceptance_criteria"] == ["Keep the brochure available."]
    assert reopened.delete(story.record_id) is True
    assert reopened.list_records() == []


def test_incomplete_story_is_rejected_without_record(tmp_path):
    document_path = tmp_path / "incomplete.docx"
    _write_story(document_path, omit_criteria=True)
    with pytest.raises(ValidationError, match="missing fields: acceptance_criteria"):
        parse_word_story(document_path)


def test_repeated_single_value_is_reported_as_ambiguous(tmp_path):
    document_path = tmp_path / "ambiguous.docx"
    _write_story(document_path)
    document = Document(document_path)
    document.add_paragraph("Title: A conflicting second title")
    document.save(document_path)

    with pytest.raises(ValidationError, match="ambiguous repeated fields: title"):
        parse_word_story(document_path)


def test_malformed_docx_is_a_validation_failure(tmp_path):
    document_path = tmp_path / "malformed.docx"
    document_path.write_text("not a Word document", encoding="utf-8")
    with pytest.raises(ValidationError, match="Unable to read a valid Word"):
        parse_word_story(document_path)


def test_unconfigured_external_source_fails_without_calling_remote_service(capsys):
    assert main(["jira", "SCRUM-6"]) == 2
    response = capsys.readouterr().out
    assert "integration_unavailable" in response
    assert "no external request was made" in response
