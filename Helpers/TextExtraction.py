import easyocr
import re
import cv2
import numpy as np
import argparse


def preprocess_image(image_path):
    img = cv2.imread(image_path)
    # h, w = img.shape[:2]
    # # Define top-right quarter: x from w/2→w, y from 0→h/2
    # x1, y1 = w // 2, 0
    # x2, y2 = w, h // 2
    # roi = img[y1:y2, x1:x2]
    return img

def extract_passport_id(image_path, languages=['en'], gpu=False):

    # Preprocess image
    preprocessed = preprocess_image(image_path)
    
    # Initialize the EasyOCR reader
    reader = easyocr.Reader(languages, gpu=gpu)
    
    # Perform OCR; detail=0 returns only text
    ocr_texts = reader.readtext(preprocessed, detail=0)

    return ocr_texts
    pattern = re.compile(r'^[A-Z][A-Z0-9]{6,8}$')

    results = []
    for raw in ocr_texts:
        # 1) Uppercase everything
        candidate = raw.upper()
        # 2) Remove any chars that aren't A–Z or 0–9
        candidate = re.sub(r'[^A-Z0-9]', '', candidate)
        # 3) Test against the regex
        if pattern.match(candidate):
            results.append(candidate)

    return results

    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract passport/ID number from an image"
    )
    parser.add_argument("image_path", help="Path to the image file")
    parser.add_argument(
        "--langs", nargs="+", default=["en"],
        help="Languages for OCR (e.g., en, fr)"
    )
    parser.add_argument(
        "--gpu", action="store_true",
        help="Enable GPU acceleration if available"
    )
    args = parser.parse_args()

    result = extract_passport_id(args.image_path, args.langs, args.gpu)
    if result:
        print(f"Detected ID: {result}")
    else:
        print("No valid ID found in the image.")
