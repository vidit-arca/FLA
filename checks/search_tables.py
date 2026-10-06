import json
data = json.load(open('/Users/apple/Desktop/FLA/old_fla.json'))
queries = ['No. of foreign direct investors', 'Month and Year of receiving FDI', 'Month and Year of ODI', 'Total Equity of DIE', 'Equity of DIE held by you']
for t_name, t_data in data.items():
    preview = t_data.get('preview', [])
    for row in preview:
        for k, v in row.items():
            val_str = str(v)
            for q in queries:
                if q.lower() in val_str.lower():
                    print(f"Found '{q}' in {t_name}")
                    print(f"Row: {row}")
