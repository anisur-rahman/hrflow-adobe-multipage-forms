function val(d,n){return String(d.getField(n).valueAsString).replace(/^\s+|\s+$/g,'');}
var requiredPages=[['first_name','last_name','email','phone'],['department','job_title','start_date','employment_type','annual_salary','remote_employee'],['health_plan','retirement_percent'],['emergency_name','emergency_relationship','emergency_phone'],['employee_name']];
function errorField(d,n,msg){app.alert(msg);d.getField(n).setFocus();return false;}
function validatePage(d,p){var a=requiredPages[p];for(var i=0;i<a.length;i++){if(!val(d,a[i])||val(d,a[i])==='Select')return errorField(d,a[i],'Complete '+a[i]);}
if(p===0&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val(d,'email')))return errorField(d,'email','Enter a valid email.');
if(p===1){var s=Number(val(d,'annual_salary'));if(!isFinite(s)||s<=0||s>9999999999.99)return errorField(d,'annual_salary','Enter a positive salary within 10 digits.');var t=val(d,'start_date');var m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(t);var dt=m?new Date(Number(m[1]),Number(m[2])-1,Number(m[3])):null;if(!dt||dt.getFullYear()!==Number(m[1])||dt.getMonth()!==Number(m[2])-1||dt.getDate()!==Number(m[3]))return errorField(d,'start_date','Use a valid YYYY-MM-DD date.');if(val(d,'remote_employee')==='Yes'&&!val(d,'remote_location'))return errorField(d,'remote_location','Enter remote location.');}
if(p===2){var r=Number(val(d,'retirement_percent'));if(!isFinite(r)||r<0||r>100)return errorField(d,'retirement_percent','Enter 0 to 100.');}
if(p===4&&val(d,'acknowledged')!=='Yes')return errorField(d,'acknowledged','Confirm acknowledgment.');return true;}
function remote(d,v){var f=d.getField('remote_location');f.display=v==='Yes'?display.visible:display.hidden;f.required=v==='Yes';if(v!=='Yes')f.value='';}
function calc(d){var a=Number(val(d,'annual_salary')),r=Number(val(d,'retirement_percent'));d.getField('monthly_salary').value=a>0?(a/12).toFixed(2):'';d.getField('retirement_monthly').value=a>0&&r>=0&&r<=100?(a/12*r/100).toFixed(2):'';d.getField('review_name').value=val(d,'first_name')+' '+val(d,'last_name');d.getField('review_email').value=val(d,'email');d.getField('review_department').value=val(d,'department');d.getField('review_salary').value=val(d,'annual_salary');}
function nextPage(d,p){if(validatePage(d,p)){calc(d);d.pageNum=p+1;}}
function submitAll(d){for(var p=0;p<5;p++){d.pageNum=p;if(!validatePage(d,p))return;}calc(d);d.submitForm({cURL:'http://127.0.0.1:8000/submit',cSubmitAs:'HTML',bEmpty:true});}
function resetAll(d){d.resetForm();remote(d,'No');calc(d);d.pageNum=0;}
