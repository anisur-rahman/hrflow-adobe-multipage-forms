from pathlib import Path
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject, NumberObject, ArrayObject, DecodedStreamObject
ROOT=Path(__file__).resolve().parents[1]
PAGES=[('Personal information',[('first_name','First name','text'),('last_name','Last name','text'),('email','Email','text'),('phone','Phone','text'),('address','Street address','text'),('city','City','text'),('state','State','text'),('zip_code','ZIP code','text')]),('Employment information',[('department','Department',['Select','IT','HR','Finance','Operations']),('job_title','Job title','text'),('start_date','Start date (YYYY-MM-DD)','text'),('employment_type','Employment type',['Select','Full-time','Part-time','Contractor']),('annual_salary','Annual salary (USD)','text'),('monthly_salary','Monthly salary (calculated)','readonly'),('remote_employee','Remote employee?',['No','Yes']),('remote_location','Remote location (if Yes)','text')]),('Benefits enrollment',[('health_plan','Health plan',['Select','Individual','Family','Waive']),('dental','Dental coverage','check'),('vision','Vision coverage','check'),('retirement_percent','Retirement contribution (%)','text'),('retirement_monthly','Monthly retirement (calculated)','readonly')]),('Emergency contact',[('emergency_name','Contact name','text'),('emergency_relationship','Relationship',['Select','Spouse','Parent','Sibling','Friend','Other']),('emergency_phone','Contact phone','text'),('emergency_notes','Additional notes','text')]),('Review and submit',[('review_name','Employee name','readonly'),('review_email','Email','readonly'),('review_department','Department','readonly'),('review_salary','Annual salary','readonly'),('employee_name','Type your name to acknowledge','text'),('acknowledged','I certify the information is accurate','check')])]
REQUIRED=set('first_name last_name email phone department job_title start_date employment_type annual_salary remote_employee health_plan retirement_percent emergency_name emergency_relationship emergency_phone employee_name acknowledged'.split())
def action(js):return DictionaryObject({NameObject('/S'):NameObject('/JavaScript'),NameObject('/JS'):TextStringObject(js)})
def build():
 b=BytesIO(); c=canvas.Canvas(b,pagesize=(612,792)); c.setTitle('HRFlow | Employee onboarding'); buttons=[]
 for p,(title,fields) in enumerate(PAGES):
  c.setFillColor(HexColor('#17365d'));c.rect(0,690,612,102,fill=1,stroke=0);c.setFillColor(white);c.setFont('Helvetica-Bold',25);c.drawString(42,747,'HRFlow');c.setFont('Helvetica',12);c.drawString(42,721,'Employee onboarding  /  Training demonstration');c.setFillColor(HexColor('#17365d'));c.setFont('Helvetica-Bold',21);c.drawString(42,650,title);c.setFont('Helvetica',10);c.drawString(42,630,f'STEP {p+1} OF 5  |  * Required  |  Synthetic data only')
  for i,(n,label,kind) in enumerate(fields):
   y=586-i*60;c.setFillColor(HexColor('#17365d'));c.setFont('Helvetica-Bold',11);c.drawString(42,y+30,label+(' *' if n in REQUIRED else ''));kw=dict(name=n,tooltip=label,x=42,y=y,width=528,height=24,borderColor=HexColor('#8095aa'),fillColor=HexColor('#f3f7fb'),textColor=HexColor('#17365d'),fontSize=11,fieldFlags='required' if n in REQUIRED else '')
   if kind=='check':c.acroForm.checkbox(name=n,tooltip=label,x=42,y=y,size=19,checked=False,buttonStyle='check',borderColor=HexColor('#8095aa'),fillColor=white,fieldFlags='required' if n in REQUIRED else '')
   elif isinstance(kind,list):c.acroForm.choice(**kw,options=kind,value=kind[0])
   else:c.acroForm.textfield(**{**kw,'fieldFlags':'readOnly' if kind=='readonly' else kw['fieldFlags']},value='')
  bs=[]
  if p>0:bs.append(('previous_'+str(p+1),'Previous',42,f'this.pageNum={p-1};'))
  if p<4:bs.append(('next_'+str(p+1),'Next',442,f'nextPage(this,{p});'))
  else:bs.extend([('reset_button','Reset',220,'resetAll(this);'),('submit_button','Submit',442,'submitAll(this);')])
  for n,label,x,js in bs:
   c.setFillColor(HexColor('#17365d'));c.roundRect(x,54,128,32,5,fill=1,stroke=0);c.setFillColor(white);c.setFont('Helvetica-Bold',12);c.drawCentredString(x+64,65,label);buttons.append((p,n,label,x,js))
  c.setFillColor(HexColor('#526579'));c.setFont('Helvetica',9);c.drawString(42,28,'HR-002  |  v1.0  |  Local demo only');c.drawRightString(570,28,f'{p+1} / 5');c.showPage()
 c.save();b.seek(0);w=PdfWriter(clone_from=PdfReader(b));w.add_js((ROOT/'javascript/document.js').read_text());w._root_object[NameObject('/Lang')]=TextStringObject('en-US');form=w._root_object['/AcroForm'];fields=form['/Fields'];co=ArrayObject()
 for page in w.pages:
  page[NameObject('/Tabs')]=NameObject('/A')
  for ref in page.get('/Annots',[]):
   f=ref.get_object();n=str(f.get('/T',''))
   if n=='remote_location':f[NameObject('/F')]=NumberObject(2)
   if n=='remote_employee':f[NameObject('/AA')]=DictionaryObject({NameObject('/V'):action('remote(this,event.value);')});f[NameObject('/Ff')]=NumberObject(int(f['/Ff'])| (1<<26))
   if n in ('monthly_salary','retirement_monthly','review_name','review_email','review_department','review_salary'):
    expr={'monthly_salary':"var a=Number(val(this,'annual_salary'));event.value=a>0?(a/12).toFixed(2):'';",'retirement_monthly':"var a=Number(val(this,'annual_salary')),r=Number(val(this,'retirement_percent'));event.value=a>0&&r>=0&&r<=100?(a/12*r/100).toFixed(2):'';",'review_name':"event.value=val(this,'first_name')+' '+val(this,'last_name');",'review_email':"event.value=val(this,'email');",'review_department':"event.value=val(this,'department');",'review_salary':"event.value=val(this,'annual_salary');"}[n];f[NameObject('/AA')]=DictionaryObject({NameObject('/C'):action(expr)});co.append(ref)
 form[NameObject('/CO')]=co
 for p,n,label,x,js in buttons:
  page=w.pages[p];f=DictionaryObject({NameObject('/Type'):NameObject('/Annot'),NameObject('/Subtype'):NameObject('/Widget'),NameObject('/FT'):NameObject('/Btn'),NameObject('/Ff'):NumberObject(65536),NameObject('/F'):NumberObject(4),NameObject('/T'):TextStringObject(n),NameObject('/TU'):TextStringObject(label),NameObject('/Rect'):ArrayObject([NumberObject(x),NumberObject(54),NumberObject(x+128),NumberObject(86)]),NameObject('/P'):page.indirect_reference,NameObject('/A'):action(js),NameObject('/MK'):DictionaryObject({NameObject('/CA'):TextStringObject(label)})});ap=DecodedStreamObject();ap.set_data(('0.09 0.21 0.36 rg 0 0 128 32 re f 1 1 1 rg BT /Helv 12 Tf 12 11 Td ('+label+') Tj ET').encode());ap.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Form'),NameObject('/BBox'):ArrayObject([NumberObject(0),NumberObject(0),NumberObject(128),NumberObject(32)]),NameObject('/Resources'):DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/Helv'):DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})})})});f[NameObject('/AP')]=DictionaryObject({NameObject('/N'):w._add_object(ap)});ref=w._add_object(f);fields.append(ref);page['/Annots'].append(ref)
 out=ROOT/'forms/employee-onboarding.pdf';w.write(out);print(out)
if __name__=='__main__':build()
