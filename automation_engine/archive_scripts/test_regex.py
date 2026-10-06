import re

md_content = """
a) Movement in the Equity Share Capital during the year

| Particulars                                       | As at March 3 | 1, 2025  | As at Murch   | 31, 2024 |
|---------------------------------------------------|---------------|----------|---------------|----------|
|                                                   | No. of Shares | Rs.      | No. of Shares | Rs.      |
| Shares outstanding at the beginning of the period | 1,31,000      | 1.310.00 | 1.31.000      | 1.310.00 |
| Issued during the year                            |               |          | 1,51,500      | 1,510,00 |
| Shares outstanding at the end of the period       | 1,31,000      | 1,310.00 | 1,31,000      | 1,310.00 |

b Movement in Complusory Convertible Preference Share capital during the year
| Particulars                                                               | Particulars As at March 31, 2025 |              | As at<br>March 31, 2024 |              |
|---------------------------------------------------------------------------|----------------------------------|--------------|-------------------------|--------------|
|                                                                           | No. of Shares                    | Rs. In Lakhs | No. of Shares           | Rs. In Lakhs |
| Shares outstanding at the beginning of the year<br>Issued during the year | 5,030                            | 0.50         | 5,030                   | 0.50         |
| Shares outstanding at the end of the year                                 | 5,030                            | 0.50         | 5,030                   | 0.50         |
"""

eq_match = re.search(r'Movement in.*?Equity Share [Cc]apital[\s\S]*?Shares outstanding at the end of the (?:year|period)\s*\|\s*([\d,.]+)\s*\|\s*[\d,.]+\s*\|\s*([\d,.]+)', md_content, re.IGNORECASE)
if eq_match:
    print("EQ FY:", eq_match.group(1))
    print("EQ PY:", eq_match.group(2))
else:
    print("EQ NOT FOUND")

ccps_match = re.search(r'Movement in.*?(?:Preference|Convertible Preference) Share [Cc]apital[\s\S]*?Shares outstanding at the end of the (?:year|period)\s*\|\s*([\d,.]+)\s*\|\s*[\d,.]+\s*\|\s*([\d,.]+)', md_content, re.IGNORECASE)
if ccps_match:
    print("CCPS FY:", ccps_match.group(1))
    print("CCPS PY:", ccps_match.group(2))
else:
    print("CCPS NOT FOUND")
