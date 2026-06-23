import sqlite3
conn = sqlite3.connect('/Users/apple/Desktop/FLA/fla_automation_engine/test.db')
cursor = conn.cursor()
cursor.execute("SELECT logs FROM extraction_tasks ORDER BY rowid DESC LIMIT 1")
row = cursor.fetchone()
if row:
    print(row[0])
