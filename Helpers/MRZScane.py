from fastmrz import FastMRZ
import json
import numpy as np

fast_mrz = FastMRZ(tesseract_path=r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe')
passport_mrz = fast_mrz.get_details(r"C:\Users\binitns\Desktop\passport.jpg", include_checkdigit=False)
print("JSON:")
print(json.dumps(passport_mrz, indent=4))
