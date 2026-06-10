import requests
task_id = "01777054-0e59-48c1-b07e-50ab6bdd5f02"
res = requests.get(f"http://localhost:8000/api/tasks/{task_id}")
data = res.json()
print("STATUS:", data.get('status'))
print("LOGS:", data.get('logs'))
if data.get('extracted_data'):
    print("EXTRACTED:", len(data.get('extracted_data')), "fields")
