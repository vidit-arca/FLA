import requests

task_id = "dc3c9635-b1ea-4456-92c6-297a2f9de5d7"
res = requests.get(f"http://localhost:8000/api/tasks/{task_id}")
data = res.json()
extracted_data = data.get('extracted_data')
extracted_data['domestic_sales_fy'] = 9999999.0

res = requests.post(f"http://localhost:8000/api/export/{task_id}", json=extracted_data)
print(res.json())
