from __future__ import annotations

import tempfile
from pathlib import Path

import pikepdf


class PDFPasswordRequired(Exception):
    """Raised when an encrypted PDF needs a password."""


class PDFPasswordIncorrect(Exception):
    """Raised when the supplied password is wrong."""


def decrypt_pdf(pdf_path: Path, password: str | None = None) -> Path:
    try:
        with pikepdf.open(str(pdf_path)) as _:
            return pdf_path
    except pikepdf.PasswordError:
        pass

    if not password:
        raise PDFPasswordRequired(
            f"PDF '{pdf_path.name}' is password-protected. "
            "For HDFC: use your 9-digit Customer ID."
        )

    try:
        with pikepdf.open(str(pdf_path), password=password) as pdf:
            temp_dir = Path(tempfile.mkdtemp(prefix="finassist_"))
            decrypted = temp_dir / f"decrypted_{pdf_path.name}"
            pdf.save(str(decrypted))
            return decrypted
    except pikepdf.PasswordError as e:
        raise PDFPasswordIncorrect(f"Incorrect password for '{pdf_path.name}'.") from e
