"""Tests for the generated PDF and the submission API.

The database is replaced with a fake save() so these run without PostgreSQL.
Real database writes are covered by the manual smoke test in the README.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend import main

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "forms" / "employee-onboarding.pdf"

VALID_FORM = {
    "first_name": "John",
    "last_name": "Smith",
    "email": "john@example.com",
    "phone": "202-555-0100",
    "department": "IT",
    "job_title": "Engineer",
    "start_date": "2026-12-01",
    "employment_type": "Full-time",
    "annual_salary": "120000",
    "remote_employee": "Yes",
    "remote_location": "Princeton NJ",
    "health_plan": "Individual",
    "dental": "Yes",
    "vision": "Off",
    "retirement_percent": "5",
    "emergency_name": "Jane Smith",
    "emergency_relationship": "Spouse",
    "emergency_phone": "202-555-0101",
    "acknowledged": "Yes",
    "employee_name": "John Smith",
}


@pytest.fixture
def saved(monkeypatch):
    """Replace the database write and collect what would have been saved."""
    submissions = []

    def fake_save(form):
        submissions.append(form)
        return 42

    monkeypatch.setattr(main, "save", fake_save)
    return submissions


@pytest.fixture
def client():
    return TestClient(main.app)


# --- PDF ---------------------------------------------------------------------

def test_pdf_has_five_pages_and_all_fields():
    reader = PdfReader(PDF_PATH)
    fields = reader.get_fields()

    assert len(reader.pages) == 5
    assert set(VALID_FORM) <= set(fields)
    assert len(fields) == 41  # 31 data fields + 10 navigation buttons


def test_pdf_has_javascript_and_calculation_order():
    root = PdfReader(PDF_PATH).trailer["/Root"]

    assert "/JavaScript" in root["/Names"]
    assert len(root["/AcroForm"]["/CO"]) == 6


def test_every_widget_has_a_tooltip_and_buttons_run_javascript():
    for page in PdfReader(PDF_PATH).pages:
        for annotation in page["/Annots"]:
            widget = annotation.get_object()
            assert widget.get("/TU"), f"{widget.get('/T')} has no tooltip"
            if widget.get("/Ff", 0) & (1 << 16):  # push button
                assert widget["/A"]["/S"] == "/JavaScript"


# --- API ---------------------------------------------------------------------

def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_valid_submission_is_saved(client, saved):
    response = client.post("/submit", data=VALID_FORM)

    assert response.status_code == 201
    assert response.json() == {"status": "saved", "employee_id": 42}
    assert saved[0].dental is True
    assert saved[0].vision is False


@pytest.mark.parametrize("changes", [
    {"email": "bad"},
    {"remote_location": ""},
    {"acknowledged": "Off"},
    {"annual_salary": "-1"},
    {"start_date": "2026-02-30"},
    {"retirement_percent": "101"},
    {"department": "Marketing"},
])
def test_invalid_submission_is_rejected(client, saved, changes):
    response = client.post("/submit", data={**VALID_FORM, **changes})

    assert response.status_code == 422
    assert saved == []


def test_email_is_lowercased(client, saved):
    client.post("/submit", data={**VALID_FORM, "email": "John@Example.COM"})

    assert saved[0].email == "john@example.com"


def test_remote_location_is_cleared_for_office_staff(client, saved):
    client.post("/submit", data={**VALID_FORM, "remote_employee": "No", "remote_location": "NJ"})

    assert saved[0].remote_location == ""


def test_duplicate_email_returns_409(client, monkeypatch):
    def duplicate(form):
        raise main.psycopg.errors.UniqueViolation()

    monkeypatch.setattr(main, "save", duplicate)

    assert client.post("/submit", data=VALID_FORM).status_code == 409


def test_database_down_returns_503(client, monkeypatch):
    def offline(form):
        raise main.psycopg.OperationalError()

    monkeypatch.setattr(main, "save", offline)

    assert client.post("/submit", data=VALID_FORM).status_code == 503


def test_web_form_has_every_field(client):
    response = client.get("/form")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    for name in VALID_FORM:
        assert f'name="{name}"' in response.text
