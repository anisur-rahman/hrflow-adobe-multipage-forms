"""HRFlow onboarding API.

Receives the onboarding form (from the Acrobat PDF or the web version at
/form), validates it, and saves it to PostgreSQL in a single transaction.
"""
import logging
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

logger = logging.getLogger("hrflow")

app = FastAPI(title="HRFlow Adobe Forms")

FORM_PAGE = Path(__file__).with_name("form.html")

# Acrobat submits checkboxes as "Yes"/"Off" and the remote dropdown as "Yes"/"No".
YES_NO_FIELDS = ("remote_employee", "dental", "vision", "acknowledged")
YES_NO_VALUES = {"Yes": True, "No": False, "Off": False}


class Onboarding(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    # Page 1: personal information
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=1, max_length=30)
    address: str = Field(default="", max_length=200)
    city: str = Field(default="", max_length=100)
    state: str = Field(default="", max_length=50)
    zip_code: str = Field(default="", max_length=20)

    # Page 2: employment
    department: Literal["IT", "HR", "Finance", "Operations"]
    job_title: str = Field(min_length=1, max_length=150)
    start_date: date
    employment_type: Literal["Full-time", "Part-time", "Contractor"]
    annual_salary: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    remote_employee: bool
    remote_location: str = Field(default="", max_length=200)

    # Page 3: benefits
    health_plan: Literal["Individual", "Family", "Waive"]
    dental: bool = False
    vision: bool = False
    retirement_percent: Decimal = Field(ge=0, le=100, decimal_places=2)

    # Page 4: emergency contact
    emergency_name: str = Field(min_length=1, max_length=200)
    emergency_relationship: Literal["Spouse", "Parent", "Sibling", "Friend", "Other"]
    emergency_phone: str = Field(min_length=1, max_length=30)
    emergency_notes: str = Field(default="", max_length=1000)

    # Page 5: acknowledgment
    acknowledged: bool
    employee_name: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value):
        # Store emails in lowercase so case variants count as the same address.
        return value.lower()

    @model_validator(mode="after")
    def check_cross_field_rules(self):
        if self.remote_employee and not self.remote_location:
            raise ValueError("Remote location required")
        if not self.remote_employee:
            self.remote_location = ""
        if not self.acknowledged:
            raise ValueError("Acknowledgment required")
        return self


def save(form: Onboarding) -> int:
    """Insert one employee across all four tables. Returns the new employee id.

    psycopg's connection context manager commits on success and rolls back
    if any insert fails, so a submission is never half-saved.
    """
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO employees
                (first_name, last_name, email, phone, address, city, state, zip_code,
                 acknowledged, employee_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (form.first_name, form.last_name, form.email, form.phone, form.address,
             form.city, form.state, form.zip_code, form.acknowledged, form.employee_name),
        )
        employee_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO employment
                (employee_id, department, job_title, start_date, employment_type,
                 annual_salary, remote_employee, remote_location)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (employee_id, form.department, form.job_title, form.start_date,
             form.employment_type, form.annual_salary, form.remote_employee,
             form.remote_location),
        )
        cur.execute(
            """
            INSERT INTO benefits (employee_id, health_plan, dental, vision, retirement_percent)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (employee_id, form.health_plan, form.dental, form.vision, form.retirement_percent),
        )
        cur.execute(
            """
            INSERT INTO emergency_contacts (employee_id, contact_name, relationship, phone, notes)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (employee_id, form.emergency_name, form.emergency_relationship,
             form.emergency_phone, form.emergency_notes),
        )
    return employee_id


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/form")


@app.get("/form", include_in_schema=False)
def web_form():
    return FileResponse(FORM_PAGE, media_type="text/html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/submit", status_code=201)
async def submit(request: Request):
    data = dict(await request.form())
    for name in YES_NO_FIELDS:
        if name in data:
            data[name] = YES_NO_VALUES.get(data[name], data[name])

    try:
        form = Onboarding.model_validate(data)
    except ValidationError as exc:
        errors = exc.errors(include_input=False, include_context=False, include_url=False)
        raise HTTPException(status_code=422, detail=errors)

    try:
        employee_id = await run_in_threadpool(save, form)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Employee email already exists")
    except psycopg.OperationalError:
        logger.exception("Database connection failed")
        raise HTTPException(status_code=503, detail="Database unavailable")
    except psycopg.Error:
        logger.exception("Database write failed")
        raise HTTPException(status_code=500, detail="Could not save the submission")

    return {"status": "saved", "employee_id": employee_id}
