import re
import os

def parse_file(filepath, ext):
    """Extract raw text from uploaded file."""
    try:
        if ext == "pdf":
            return _parse_pdf(filepath)
        elif ext == "docx":
            return _parse_docx(filepath)
        else:
            return _parse_txt(filepath)
    except Exception as e:
        raise ValueError(f"Failed to parse file: {str(e)}")


def _parse_pdf(filepath):
    import fitz  # pymupdf
    doc = fitz.open(filepath)
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text)
    doc.close()
    return "\n".join(pages)


def _parse_docx(filepath):
    from docx import Document
    doc = Document(filepath)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _parse_txt(filepath):
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def clean_text(text):
    """Clean and normalise extracted text."""
    # Remove page numbers (standalone digits on a line)
    text = re.sub(r'^\s*\d{1,3}\s*$', '', text, flags=re.MULTILINE)
    # Collapse multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Collapse multiple spaces
    text = re.sub(r'[ \t]+', ' ', text)
    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    return text.strip()


def word_count(text):
    return len(text.split())


def allowed_extension(filename, allowed={"pdf", "txt", "docx"}):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def get_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ""


