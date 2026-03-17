import fitz  # PyMuPDF
import base64
import io
import os
from PIL import Image, ImageEnhance, ImageFilter

Image.MAX_IMAGE_PIXELS = None  # PDFs are trusted input; suppress decompression bomb check

DPI = int(os.getenv("PDF_DPI", 200))
MAX_DIM = int(os.getenv("OCR_MAX_DIMENSION", 2048))  # gemma3:4b clips anything larger anyway


def _enhance(img_bytes: bytes) -> bytes:
    """Resize to model-friendly dimensions, sharpen, and boost contrast."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    # Cap dimensions — vision models downsample internally past their max resolution,
    # but doing it here with high-quality resampling produces much better OCR results.
    if img.width > MAX_DIM or img.height > MAX_DIM:
        img.thumbnail((MAX_DIM, MAX_DIM), Image.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.4)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def pdf_to_base64_pages(file_bytes: bytes) -> list[str]:
    """Convert each PDF page to a base64 PNG at high DPI for best OCR accuracy."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page in doc:
        mat = fitz.Matrix(DPI / 72, DPI / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        img_bytes = _enhance(pix.tobytes("png"))
        pages.append(base64.b64encode(img_bytes).decode("utf-8"))
    doc.close()
    return pages


def image_to_base64(file_bytes: bytes) -> list[str]:
    """Wrap a raw image into a single-item list to match the pages interface."""
    return [base64.b64encode(_enhance(file_bytes)).decode("utf-8")]
