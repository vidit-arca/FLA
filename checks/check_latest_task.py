import sqlite3, json

conn = sqlite3.connect("/Users/apple/Desktop/FLA/automation_engine/fla_tasks.db")
c = conn.cursor()
c.execute("PRAGMA table_info(extraction_tasks)")
cols = [r[1] for r in c.fetchall()]
print("Columns:", cols)

c.execute("SELECT id, status, output_excel, extracted_data FROM extraction_tasks ORDER BY rowid DESC LIMIT 3")
rows = c.fetchall()
for r in rows:
    print(f"\nID: {r[0]} | status: {r[1]}")
    print(f"  output_excel: {r[2]}")
    data = json.loads(r[3]) if r[3] else {}
    print(f"  extracted_data keys (first 15): {list(data.keys())[:15]}")
    docs = data.get("docs", {})
    print(f"  docs in extracted_data: {docs}")
    print(f"  paid_up_capital: {data.get('paid_up_capital')}")
    print(f"  turnover: {data.get('turnover')}")
    print(f"  full_text snippet: {str(data.get('full_text', ''))[:100]}")
