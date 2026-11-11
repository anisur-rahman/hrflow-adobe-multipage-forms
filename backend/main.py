import os
from pathlib import Path
from datetime import date
from decimal import Decimal
from typing import Literal
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator, model_validator, ValidationError
app=FastAPI(title='HRFlow Adobe Forms')
class Onboarding(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True,extra='ignore')
    first_name:str=Field(min_length=1,max_length=100)
    last_name:str=Field(min_length=1,max_length=100)
    email:EmailStr
    phone:str=Field(min_length=1,max_length=30)
    address:str=''; city:str=''; state:str=''; zip_code:str=''
    department:Literal['IT','HR','Finance','Operations']
    job_title:str=Field(min_length=1,max_length=150)
    start_date:date
    employment_type:Literal['Full-time','Part-time','Contractor']
    annual_salary:Decimal=Field(gt=0,max_digits=12,decimal_places=2)
    remote_employee:bool
    remote_location:str=''
    health_plan:Literal['Individual','Family','Waive']
    dental:bool=False; vision:bool=False
    retirement_percent:Decimal=Field(ge=0,le=100,decimal_places=2)
    emergency_name:str=Field(min_length=1,max_length=200)
    emergency_relationship:Literal['Spouse','Parent','Sibling','Friend','Other']
    emergency_phone:str=Field(min_length=1,max_length=30)
    emergency_notes:str=''
    acknowledged:bool
    employee_name:str=Field(min_length=1,max_length=200)
    @field_validator('email')
    @classmethod
    def normalize_email(cls,v):
        # Store emails in lowercase so case variants count as the same address.
        return v.lower()
    @model_validator(mode='after')
    def rules(self):
        if self.remote_employee and not self.remote_location: raise ValueError('Remote location required')
        if not self.acknowledged: raise ValueError('Acknowledgment required')
        return self

def save(d):
    import psycopg
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO employees(first_name,last_name,email,phone,address,city,state,zip_code,acknowledged,employee_name) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',(d.first_name,d.last_name,d.email,d.phone,d.address,d.city,d.state,d.zip_code,d.acknowledged,d.employee_name))
            i=cur.fetchone()[0]
            cur.execute('INSERT INTO employment VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',(i,d.department,d.job_title,d.start_date,d.employment_type,d.annual_salary,d.remote_employee,d.remote_location))
            cur.execute('INSERT INTO benefits VALUES (%s,%s,%s,%s,%s)',(i,d.health_plan,d.dental,d.vision,d.retirement_percent))
            cur.execute('INSERT INTO emergency_contacts VALUES (%s,%s,%s,%s,%s)',(i,d.emergency_name,d.emergency_relationship,d.emergency_phone,d.emergency_notes))
    return i
FORM_HTML=Path(__file__).with_name('form.html')
@app.get('/',include_in_schema=False)
def root():return RedirectResponse('/form')
@app.get('/form',include_in_schema=False)
def web_form():return FileResponse(FORM_HTML,media_type='text/html')
@app.get('/health')
def health():return {'status':'ok'}
@app.post('/submit',status_code=201)
async def submit(request:Request):
    from starlette.concurrency import run_in_threadpool
    raw=dict(await request.form())
    for k in ('remote_employee','dental','vision','acknowledged'):
        if k in raw: raw[k]={'Yes':True,'No':False,'Off':False}.get(raw[k],raw[k])
    try: d=Onboarding.model_validate(raw)
    except ValidationError as e: raise HTTPException(422,detail=e.errors(include_input=False,include_context=False,include_url=False))
    try: i=await run_in_threadpool(save,d)
    except Exception as e:
        if getattr(e,'sqlstate',None)=='23505':raise HTTPException(409,'Employee email already exists')
        raise HTTPException(503,'Database unavailable or write failed')
    return {'status':'saved','employee_id':i}
