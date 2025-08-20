# utils/conversion.py
import subprocess
import os


def pdf_to_html(pdf_path: str, out_html: str) -> None:
    """Use pdf2htmlEX to convert a PDF into an HTML file."""
    cmd = [
        "pdf2htmlEX",
        "--embed-javascript", "no",
        "--process-outline", "yes",
        "--zoom", "1.3",
        pdf_path,
        out_html,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pdf2htmlEX failed:\n{result.stderr}")


def html_to_pdf(html_file: str, out_pdf: str) -> None:
    """Use wkhtmltopdf to convert an HTML file into a PDF."""
    cmd = ["wkhtmltopdf", "--enable-local-file-access", html_file, out_pdf]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"wkhtmltopdf failed:\n{result.stderr}")
