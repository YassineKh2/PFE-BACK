import os
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.data.read_api import read_local_images

def extract_markdown(input_path: str) -> str:

    
    base_dir = os.path.dirname(os.path.abspath(__file__)) 
    project_root = os.path.dirname(base_dir)

    input_path = os.path.join(project_root, "Files", input_path)


    # Define temporary directories for processing
    local_image_dir = "output/images"
    os.makedirs(local_image_dir, exist_ok=True)
    image_writer = FileBasedDataWriter(local_image_dir)


    # Determine the file extension
    _, ext = os.path.splitext(input_path)
    ext = ext.lower()

    if ext == ".pdf":
        # Process PDF file
        reader = FileBasedDataReader("")
        pdf_bytes = reader.read(input_path)
        ds = PymuDocDataset(pdf_bytes)

        # Determine if OCR is needed
        if ds.classify() == SupportedPdfParseMethod.OCR:
            infer_result = ds.apply(doc_analyze, ocr=True)
            pipe_result = infer_result.pipe_ocr_mode(image_writer)
        else:
            infer_result = ds.apply(doc_analyze, ocr=False)
            pipe_result = infer_result.pipe_txt_mode(image_writer)

        # Extract Markdown content
        md_content = pipe_result.get_markdown(os.path.basename(local_image_dir))
        return md_content

    elif ext in [".jpg", ".jpeg", ".png"]:
        # Process image file
        ds = read_local_images(input_path)[0]
        infer_result = ds.apply(doc_analyze, ocr=True)
        pipe_result = infer_result.pipe_ocr_mode(image_writer)

        # Extract Markdown content
        md_content = pipe_result.get_markdown(os.path.basename(local_image_dir))
        return md_content

    else:
        raise ValueError("Unsupported file type. Please provide a PDF or image file.")



