import fitz  # PyMuPDF
import base64
import os

DPI = int(os.getenv("PDF_DPI", 220))


def pdf_to_base64_pages(file_bytes: bytes) -> list[str]:
    """Convert each PDF page to a base64 PNG at high DPI for best OCR accuracy."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page in doc:
        mat = fitz.Matrix(DPI / 72, DPI / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        img_bytes = pix.tobytes("png")
        pages.append(base64.b64encode(img_bytes).decode("utf-8"))
    doc.close()
    return pages


def image_to_base64(file_bytes: bytes) -> list[str]:
    """Wrap a raw image into a single-item list to match the pages interface."""
    return [base64.b64encode(file_bytes).decode("utf-8")]
