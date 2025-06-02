from fastmrz import FastMRZ
import json


def GetMRZData(ImagePath: str):
    fast_mrz = FastMRZ(tesseract_path=r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe')
    passport_mrz = fast_mrz.get_details(ImagePath, include_checkdigit=False)
    return json.dumps(passport_mrz)
