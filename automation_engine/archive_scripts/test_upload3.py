import requests
import time

url = "http://localhost:8000/api/upload?company_name=ExcelTest"
files = [
    ('files', open('/Users/apple/Desktop/FLA/data/Karomi/ocr/Financials.md', 'rb')),
    ('files', open('/Users/apple/Desktop/FLA/data/Karomi/ocr/odi_audit.md', 'rb'))
]
res = requests.post(url, files=files)
task_id = res.json().get('task_id')

if task_id:
    print(requests.post(f"http://localhost:8000/api/process/{task_id}").json())
    time.sleep(2)
    print(requests.get(f"http://localhost:8000/api/tasks/{task_id}").json().get('status'))
