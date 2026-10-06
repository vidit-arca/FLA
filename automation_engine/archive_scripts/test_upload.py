import requests

url = "http://localhost:8000/api/upload?company_name=TestCompany2"
files = [
    ('files', open('/Users/apple/Desktop/FLA/data/Karomi/ocr/Financials.md', 'rb')),
    ('files', open('/Users/apple/Desktop/FLA/data/Karomi/ocr/odi_audit.md', 'rb')),
    ('files', open('/Users/apple/Desktop/FLA/data/Karomi/FLA details from company 1.xlsx', 'rb'))
]
res = requests.post(url, files=files)
print(res.json())
task_id = res.json().get('task_id')

if task_id:
    print(requests.post(f"http://localhost:8000/api/process/{task_id}").json())
    
import time
time.sleep(2)
res = requests.get(f"http://localhost:8000/api/tasks/{task_id}")
data = res.json()
print("STATUS:", data.get('status'))
if data.get('extracted_data'):
    print("EXTRACTED:", len(data.get('extracted_data')), "fields")
