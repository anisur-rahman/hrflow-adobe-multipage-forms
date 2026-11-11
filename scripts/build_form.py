"""Build forms/employee-onboarding.pdf.

ReportLab draws the five pages and creates the basic form fields. pypdf then
adds the parts ReportLab can't: document-level JavaScript, push buttons with
JavaScript actions, calculation scripts and the calculation order.

Run from the project root:  python scripts/build_form.py
"""
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "forms" / "employee-onboarding.pdf"
DOCUMENT_JS = ROOT / "javascript" / "document.js"

# Layout (PDF points, origin bottom-left, US Letter)
PAGE_SIZE = (612, 792)
LEFT = 42
FIELD_WIDTH = 528
FIELD_HEIGHT = 24
CHECKBOX_SIZE = 19
FIRST_ROW_Y = 586
ROW_SPACING = 60
BUTTON_Y = 54
BUTTON_WIDTH = 128
BUTTON_HEIGHT = 32

NAVY = HexColor("#17365d")
BORDER = HexColor("#8095aa")
FIELD_FILL = HexColor("#f3f7fb")
FOOTER_GREY = HexColor("#526579")

# Field kinds. A list instead of a kind means a dropdown with those options.
TEXT = "text"
READONLY = "readonly"
CHECKBOX = "checkbox"

PAGES = [
    ("Personal information", [
        ("first_name", "First name", TEXT),
        ("last_name", "Last name", TEXT),
        ("email", "Email", TEXT),
        ("phone", "Phone", TEXT),
        ("address", "Street address", TEXT),
        ("city", "City", TEXT),
        ("state", "State", TEXT),
        ("zip_code", "ZIP code", TEXT),
    ]),
    ("Employment information", [
        ("department", "Department", ["Select", "IT", "HR", "Finance", "Operations"]),
        ("job_title", "Job title", TEXT),
        ("start_date", "Start date (YYYY-MM-DD)", TEXT),
        ("employment_type", "Employment type", ["Select", "Full-time", "Part-time", "Contractor"]),
        ("annual_salary", "Annual salary (USD)", TEXT),
        ("monthly_salary", "Monthly salary (calculated)", READONLY),
        ("remote_employee", "Remote employee?", ["No", "Yes"]),
        ("remote_location", "Remote location (if Yes)", TEXT),
    ]),
    ("Benefits enrollment", [
        ("health_plan", "Health plan", ["Select", "Individual", "Family", "Waive"]),
        ("dental", "Dental coverage", CHECKBOX),
        ("vision", "Vision coverage", CHECKBOX),
        ("retirement_percent", "Retirement contribution (%)", TEXT),
        ("retirement_monthly", "Monthly retirement (calculated)", READONLY),
    ]),
    ("Emergency contact", [
        ("emergency_name", "Contact name", TEXT),
        ("emergency_relationship", "Relationship", ["Select", "Spouse", "Parent", "Sibling", "Friend", "Other"]),
        ("emergency_phone", "Contact phone", TEXT),
        ("emergency_notes", "Additional notes", TEXT),
    ]),
    ("Review and submit", [
        ("review_name", "Employee name", READONLY),
        ("review_email", "Email", READONLY),
        ("review_department", "Department", READONLY),
        ("review_salary", "Annual salary", READONLY),
        ("employee_name", "Type your name to acknowledge", TEXT),
        ("acknowledged", "I certify the information is accurate", CHECKBOX),
    ]),
]

REQUIRED = {
    "first_name", "last_name", "email", "phone",
    "department", "job_title", "start_date", "employment_type", "annual_salary", "remote_employee",
    "health_plan", "retirement_percent",
    "emergency_name", "emergency_relationship", "emergency_phone",
    "employee_name", "acknowledged",
}

# Calculate scripts for read-only fields. They call functions in document.js
# so the formulas live in one place.
CALCULATIONS = {
    "monthly_salary": "event.value = monthlySalary(this);",
    "retirement_monthly": "event.value = monthlyRetirement(this);",
    "review_name": "event.value = reviewName(this);",
    "review_email": "event.value = fieldValue(this, 'email');",
    "review_department": "event.value = fieldValue(this, 'department');",
    "review_salary": "event.value = fieldValue(this, 'annual_salary');",
}

# PDF field flag and annotation flag values (PDF 1.7 spec, tables 221/226 and 165)
FLAG_PUSHBUTTON = 1 << 16
FLAG_COMMIT_ON_SEL_CHANGE = 1 << 26
ANNOT_HIDDEN = 2
ANNOT_PRINT = 4


# ---------------------------------------------------------------------------
# Step 1: draw pages and fields with ReportLab
# ---------------------------------------------------------------------------

def draw_header(c, page_number, title):
    c.setFillColor(NAVY)
    c.rect(0, 690, PAGE_SIZE[0], 102, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 25)
    c.drawString(LEFT, 747, "HRFlow")
    c.setFont("Helvetica", 12)
    c.drawString(LEFT, 721, "Employee onboarding  /  Training demonstration")

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 21)
    c.drawString(LEFT, 650, title)
    c.setFont("Helvetica", 10)
    c.drawString(LEFT, 630, f"STEP {page_number} OF {len(PAGES)}  |  * Required  |  Synthetic data only")


def draw_footer(c, page_number):
    c.setFillColor(FOOTER_GREY)
    c.setFont("Helvetica", 9)
    c.drawString(LEFT, 28, "HR-002  |  v1.0  |  Local demo only")
    c.drawRightString(PAGE_SIZE[0] - LEFT, 28, f"{page_number} / {len(PAGES)}")


def add_field(c, name, label, kind, y):
    required = name in REQUIRED
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(LEFT, y + 30, label + (" *" if required else ""))

    flags = "required" if required else ""
    if kind == CHECKBOX:
        c.acroForm.checkbox(
            name=name, tooltip=label, x=LEFT, y=y, size=CHECKBOX_SIZE,
            checked=False, buttonStyle="check",
            borderColor=BORDER, fillColor=white, fieldFlags=flags,
        )
        return

    common = dict(
        name=name, tooltip=label, x=LEFT, y=y, width=FIELD_WIDTH, height=FIELD_HEIGHT,
        borderColor=BORDER, fillColor=FIELD_FILL, textColor=NAVY, fontSize=11,
    )
    if isinstance(kind, list):
        c.acroForm.choice(**common, options=kind, value=kind[0], fieldFlags=flags)
    elif kind == READONLY:
        c.acroForm.textfield(**common, value="", fieldFlags="readOnly")
    else:
        c.acroForm.textfield(**common, value="", fieldFlags=flags)


def page_buttons(page_index):
    """Return (name, label, x, javascript) for each button on a page."""
    page_number = page_index + 1
    buttons = []
    if page_index > 0:
        buttons.append((f"previous_{page_number}", "Previous", LEFT, f"this.pageNum = {page_index - 1};"))
    if page_index < len(PAGES) - 1:
        buttons.append((f"next_{page_number}", "Next", 442, f"nextPage(this, {page_index});"))
    else:
        buttons.append(("reset_button", "Reset", 220, "resetAll(this);"))
        buttons.append(("submit_button", "Submit", 442, "submitAll(this);"))
    return buttons


def draw_pages():
    """Draw every page and return the PDF bytes."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=PAGE_SIZE)
    c.setTitle("HRFlow | Employee onboarding")

    for page_index, (title, fields) in enumerate(PAGES):
        page_number = page_index + 1
        draw_header(c, page_number, title)
        for row, (name, label, kind) in enumerate(fields):
            add_field(c, name, label, kind, FIRST_ROW_Y - row * ROW_SPACING)
        draw_footer(c, page_number)
        c.showPage()

    c.save()
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Step 2: add JavaScript, buttons and calculations with pypdf
# ---------------------------------------------------------------------------

def javascript_action(code):
    return DictionaryObject({
        NameObject("/S"): NameObject("/JavaScript"),
        NameObject("/JS"): TextStringObject(code),
    })


def button_appearance(label):
    """Appearance stream for a navy button with a centred white label."""
    font_size = 12
    text_x = (BUTTON_WIDTH - stringWidth(label, "Helvetica-Bold", font_size)) / 2
    content = (
        f"0.09 0.21 0.36 rg 0 0 {BUTTON_WIDTH} {BUTTON_HEIGHT} re f "
        f"1 1 1 rg BT /HelvB {font_size} Tf {text_x:.2f} 11 Td ({label}) Tj ET"
    )
    stream = DecodedStreamObject()
    stream.set_data(content.encode())
    stream.update({
        NameObject("/Type"): NameObject("/XObject"),
        NameObject("/Subtype"): NameObject("/Form"),
        NameObject("/BBox"): ArrayObject([NumberObject(0), NumberObject(0),
                                          NumberObject(BUTTON_WIDTH), NumberObject(BUTTON_HEIGHT)]),
        NameObject("/Resources"): DictionaryObject({
            NameObject("/Font"): DictionaryObject({
                NameObject("/HelvB"): DictionaryObject({
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica-Bold"),
                }),
            }),
        }),
    })
    return stream


def add_button(writer, page, name, label, x, code):
    widget = DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Widget"),
        NameObject("/FT"): NameObject("/Btn"),
        NameObject("/Ff"): NumberObject(FLAG_PUSHBUTTON),
        NameObject("/F"): NumberObject(ANNOT_PRINT),
        NameObject("/T"): TextStringObject(name),
        NameObject("/TU"): TextStringObject(label),
        NameObject("/Rect"): ArrayObject([NumberObject(x), NumberObject(BUTTON_Y),
                                          NumberObject(x + BUTTON_WIDTH), NumberObject(BUTTON_Y + BUTTON_HEIGHT)]),
        NameObject("/P"): page.indirect_reference,
        NameObject("/A"): javascript_action(code),
        NameObject("/MK"): DictionaryObject({NameObject("/CA"): TextStringObject(label)}),
        NameObject("/AP"): DictionaryObject({NameObject("/N"): writer._add_object(button_appearance(label))}),
    })
    # pypdf has no public API for adding a new widget object, hence _add_object.
    ref = writer._add_object(widget)
    writer.root_object["/AcroForm"]["/Fields"].append(ref)
    page["/Annots"].append(ref)


def add_field_behaviour(writer):
    """Attach the conditional field logic and calculation scripts."""
    calculation_order = ArrayObject()
    for page in writer.pages:
        page[NameObject("/Tabs")] = NameObject("/A")  # tab through fields in annotation order
        for ref in page.get("/Annots", []):
            field = ref.get_object()
            name = str(field.get("/T", ""))

            if name == "remote_location":
                field[NameObject("/F")] = NumberObject(ANNOT_HIDDEN)  # shown when remote = Yes
            elif name == "remote_employee":
                field[NameObject("/AA")] = DictionaryObject({
                    NameObject("/V"): javascript_action("toggleRemoteLocation(this, event.value);"),
                })
                field[NameObject("/Ff")] = NumberObject(int(field["/Ff"]) | FLAG_COMMIT_ON_SEL_CHANGE)
            elif name in CALCULATIONS:
                field[NameObject("/AA")] = DictionaryObject({
                    NameObject("/C"): javascript_action(CALCULATIONS[name]),
                })
                calculation_order.append(ref)

    writer.root_object["/AcroForm"][NameObject("/CO")] = calculation_order


def build():
    writer = PdfWriter(clone_from=PdfReader(BytesIO(draw_pages())))
    writer.add_js(DOCUMENT_JS.read_text())
    writer.root_object[NameObject("/Lang")] = TextStringObject("en-US")

    add_field_behaviour(writer)
    for page_index in range(len(PAGES)):
        page = writer.pages[page_index]
        for name, label, x, code in page_buttons(page_index):
            add_button(writer, page, name, label, x, code)

    writer.write(OUTPUT)
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
