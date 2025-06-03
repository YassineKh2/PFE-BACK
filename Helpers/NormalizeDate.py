from datetime import datetime

def normalize_date(date_str: str):
    if '(' in date_str:
        date_str = date_str[:date_str.index('(')].strip()

    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d",
        "%a %b %d %Y %H:%M:%S GMT%z", 
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None
