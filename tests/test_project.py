from pathlib import Path
from pypdf import PdfReader
from fastapi.testclient import TestClient
from backend import main
ROOT=Path(__file__).resolve().parents[1]
SAMPLE=dict(first_name='John',last_name='Smith',email='john@example.com',phone='202-555-0100',department='IT',job_title='Engineer',start_date='2026-12-01',employment_type='Full-time',annual_salary='120000',remote_employee='Yes',remote_location='Princeton NJ',health_plan='Individual',dental='Yes',vision='Off',retirement_percent='5',emergency_name='Jane Smith',emergency_relationship='Spouse',emergency_phone='202-555-0101',acknowledged='Yes',employee_name='John Smith')
def test_pdf():
 r=PdfReader(ROOT/'forms/employee-onboarding.pdf');assert len(r.pages)==5
 f=r.get_fields();assert set(SAMPLE)<=set(f);assert len(f)==41
 assert '/JavaScript' in r.trailer['/Root']['/Names'];assert len(r.trailer['/Root']['/AcroForm']['/CO'])==6
 for p in r.pages:
  for a in p['/Annots']:
   w=a.get_object();assert w.get('/TU');
   if w.get('/Ff',0)&65536:assert w['/A']['/S']=='/JavaScript'
def test_api(monkeypatch):
 monkeypatch.setattr(main,'save',lambda d:42);c=TestClient(main.app)
 assert c.get('/health').status_code==200
 assert c.post('/submit',data=SAMPLE).json()=={'status':'saved','employee_id':42}
 for changes in [{'email':'bad'},{'remote_location':''},{'acknowledged':'Off'},{'annual_salary':'-1'},{'start_date':'2026-02-30'},{'retirement_percent':'101'}]:
  assert c.post('/submit',data={**SAMPLE,**changes}).status_code==422

def test_email_lowercased(monkeypatch):
 saved=[];monkeypatch.setattr(main,'save',lambda d:saved.append(d) or 42);c=TestClient(main.app)
 assert c.post('/submit',data={**SAMPLE,'email':'John@Example.COM'}).status_code==201
 assert saved[0].email=='john@example.com'

def test_web_form():
 c=TestClient(main.app);r=c.get('/form');assert r.status_code==200 and 'text/html' in r.headers['content-type']
 for name in SAMPLE:assert f'name="{name}"' in r.text
