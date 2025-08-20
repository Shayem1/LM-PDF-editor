# utils/conversion.py
import fitz  # PyMuPDF
import subprocess
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar, LTTextLine




def pdf_to_html(pdf_path: str, out_html: str) -> None:
    """Convert PDF to HTML preserving common document formatting."""
    doc = fitz.open(pdf_path)

    html_parts = [
        "<html><head><style>",
        """
        body { line-height: 1.4; margin:0; padding:0; font-family: Arial, sans-serif; }
        p { margin:0; }
        .sup { vertical-align: super; font-size: smaller; }
        .sub { vertical-align: sub; font-size: smaller; }
        """,
        "</style></head><body>"
    ]

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] == 0:  # text block
                for line in block["lines"]:
                    line_html = ""
                    for span in line["spans"]:
                        text = span["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        font = span["font"]
                        size = span["size"]
                        color_int = span.get("color", 0)
                        color_hex = f"#{color_int:06X}"
                        flags = span.get("flags", 0)

                        # Bold / Italic / Underline / Strikeout
                        if "bold" in font.lower():
                            text = f"<b>{text}</b>"
                        if "italic" in font.lower() or "oblique" in font.lower():
                            text = f"<i>{text}</i>"
                        if flags & 1:  # underline
                            text = f"<u>{text}</u>"
                        if flags & 2:  # strikeout
                            text = f"<s>{text}</s>"

                        # Superscript / Subscript heuristic
                        if span.get("origin", (0, 0))[1] < 0:  # slightly above baseline
                            text = f'<span class="sup">{text}</span>'
                        elif span.get("origin", (0, 0))[1] > 0:  # slightly below baseline
                            text = f'<span class="sub">{text}</span>'

                        # Alignment detection (approximate)
                        align = span.get("align", "left")  # PyMuPDF may not provide; could default
                        line_html += f'<span style="font-family:{font}; font-size:{size}pt; color:{color_hex}">{text}</span>'

                    html_parts.append(f"<p>{line_html}</p>")

    html_parts.append("</body></html>")

    with open(out_html, "w", encoding="utf-8") as f:
        f.write("".join(html_parts))


def html_to_pdf(html_file: str, out_pdf: str) -> None:
    """Convert HTML back to PDF using wkhtmltopdf while preserving formatting and UTF-8."""
    cmd = [
        "wkhtmltopdf",
        "--enable-local-file-access",  # allow access to local files (CSS/fonts)
        "--disable-smart-shrinking",   # preserve original layout
        "--encoding", "UTF-8",         # ensure UTF-8 characters render correctly
        html_file,
        out_pdf
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"wkhtmltopdf failed:\n{result.stderr}")
