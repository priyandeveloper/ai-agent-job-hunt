"""Read a resume file into plain text. No model call."""

from pathlib import Path


def load_resume(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"Resume not found: {path}")

    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        pages = PdfReader(str(path)).pages
        text = "\n".join((page.extract_text() or "") for page in pages)
    else:
        text = path.read_text(encoding="utf-8")

    text = text.strip()
    if len(text) < 40:
        raise SystemExit(f"Could not read enough text from {path.name}.")
    return text
