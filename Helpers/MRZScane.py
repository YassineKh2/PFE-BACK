from fastmrz import FastMRZ
import json
import os


def GetMRZData(ImagePath: str):
    base_dir = os.path.dirname(os.path.abspath(__file__)) 
    project_root = os.path.dirname(base_dir)

    image_full_path = os.path.join(project_root, "Files", ImagePath)

    print(image_full_path)
    fast_mrz = FastMRZ(tesseract_path=r'C:\Program Files\Tesseract-OCR\tesseract.exe')
    passport_mrz = fast_mrz.get_details(image_full_path, include_checkdigit=False)

    return json.dumps(passport_mrz)
