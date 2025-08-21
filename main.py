import os
import sys
import tempfile
import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinter import *
import threading
import subprocess
import tkinterdnd2
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:   # drag‑and‑drop optional
    DND_FILES = None

# local helpers
from utils.conversion import pdf_to_html, html_to_pdf
from utils.lm_client import LMClient


class PDFEditorApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PDF Editor – LLM Studio")
        self.geometry("520x400")

        # ----------  VARIABLES ----------
        self.pdf_path = ctk.StringVar()
        self.output_name = ctk.StringVar(value="output.pdf")
        self.user_context = ""

        # ---- Progress UI -------------------------------------------------
        self.progress_bar = ctk.CTkProgressBar(self, width=200)
        self.progress_bar.set(0)               # start at 0 %
        self.progress_bar.pack(pady=(5, 10))

        self.status_label = ctk.CTkLabel(self, text="Ready")
        self.status_label.pack()

        # ----------  FILE SELECTION ----------
        file_frame = ctk.CTkFrame(self)
        file_frame.pack(padx=10, pady=(10, 0), fill="x")

        self.file_entry = ctk.CTkEntry(
            file_frame,
            textvariable=self.pdf_path,
            width=300
        )
        self.file_entry.pack(side="left", expand=True, fill="x")

        select_btn = ctk.CTkButton(
            file_frame,
            text="Select File",
            command=self.select_file
        )
        select_btn.pack(side="right")

        # ----------  OUTPUT FILE ----------
        out_frame = ctk.CTkFrame(self)
        out_frame.pack(padx=10, pady=(5, 0), fill="x")
        ctk.CTkLabel(out_frame, text="Output file name:").pack(side="left")
        self.output_entry = ctk.CTkEntry(
            out_frame,
            textvariable=self.output_name,
            width=200
        )
        self.output_entry.pack(side="right")

        # ----------  CONTEXT ----------
        ctx_frame = ctk.CTkFrame(self)
        ctx_frame.pack(padx=10, pady=(5, 0), fill="both", expand=True)

        ctk.CTkLabel(ctx_frame, text="Context (prompt):").pack(anchor="w")
        self.context_box = ctk.CTkTextbox(ctx_frame, height=80)
        self.context_box.pack(fill="both", expand=True)

        # ----------  START ----------
        start_btn = ctk.CTkButton(
            self,
            text="Start",
            command=self.start_process
        )
        start_btn.pack(pady=(5, 10))

        # ----------  OPTIONAL DRAG‑AND‑DROP ----------
        if DND_FILES:
            try:
                self.tk.call("package", "require", "TkinterDnD")
                self.dnd = TkinterDnD.Tk()
                self.file_entry.drop_target_register(DND_FILES)
                self.file_entry.dnd_bind("<<Drop>>", self.on_drop)
            except Exception as exc:   # pragma: no cover
                print(f"Drag‑and‑drop unavailable: {exc}")

        # LM client (assumes local API on port 8000)
        self.lm = LMClient()



    # ----------  Utility helpers that schedule updates  ----------
    def set_progress(self, fraction: float) -> None:
        """Set progress bar value (0‑1).  Runs in the GUI thread."""
        self.after(0, lambda: self.progress_bar.set(fraction))

    def set_status(self, text: str) -> None:
        """Update the status label."""
        self.after(0, lambda: self.status_label.configure(text=text))



    # ------------------------------------------------------------------
    def on_drop(self, event):
        """Accept a file dropped onto the entry widget."""
        files = self.tk.splitlist(event.data)          # may contain many paths
        if files:
            self.pdf_path.set(files[0])                # first file only

    def select_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a PDF",
            filetypes=[("PDF files", "*.pdf")]
        )
        if path:
            self.pdf_path.set(path)

    # ------------------------------------------------------------------
    def start_process(self) -> None:
        """Start the processing thread, using a selected PDF or creating a new one."""
        pdf = self.pdf_path.get().strip() or None  # Use selected file or None
        out_name = self.output_name.get().strip()
        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        # Update user_context from the text box
        self.user_context = self.context_box.get("1.0", "end-1c")

        # Disable progress/status widgets
        for w in (self.progress_bar, self.status_label):
            try:
                w.configure(state="disabled")
            except ValueError as exc:
                if "state" not in str(exc):
                    raise

        # Start pipeline thread
        threading.Thread(
            target=self._run_pipeline_thread,
            args=(pdf, out_name),
            daemon=True
        ).start()

    # ------------------------------------------------------------------
    def run_pipeline(self, pdf_path: str | None, output_pdf: str) -> None:
        """All the heavy lifting – orchestrates the steps."""
        # 1️⃣ PDF → temporary HTML (or create blank HTML if no input PDF)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tmp_in:
            temp_html_path = tmp_in.name
            if pdf_path:
                self.set_progress(0.15)
                pdf_to_html(pdf_path, temp_html_path)
            else:
                # Create a basic blank HTML template
                tmp_in.write("<html><body></body></html>")
                self.set_progress(0.10)

        # 2️⃣ Read original HTML
        with open(temp_html_path, encoding="utf-8") as f:
            original_html = f.read()
        self.set_progress(0.30)

        # 3️⃣ Build prompt (fixed + user supplied)
        fixed_context = (
            """You are an assistant that edits and extends an existing HTML document.  
            Rules:  
            1. Always return the **entire HTML document** with all original formatting, text, colors, fonts, font size, and layout fully preserved.  
            2. Never change, remove, or restyle existing content unless explicitly instructed.  
            3. If questions are present in the document, do not alter their formatting or styles.  
            4. When adding answers beneath questions, use the following format only:  
            <div style="margin-top:5px; font-family:Arial; font-size:12pt; color:#000000;">Answer: ...</div>  
            (Use this exact style for all answers, unless the user requests a different style.)  
            5. Always keep font size, colors, and styles consistent for answers — do not copy styles from the question.  
            6. If the user asks for a specific formatting style (different font, size, or color), apply that style **only to the new answer text**.  
            7. If only a portion of the document is affected, still include the **unchanged rest of the document** exactly as given.  
            8. Do not output anything other than the modified full HTML document.
            9. Always return complete HTML wrapped in <html><body> … </body></html>.
            10. Use inline CSS styles only (no external CSS, no JavaScript).
            11. Ensure the HTML converts cleanly into a PDF with wkhtmltopdf or similar tools.
            12. Use safe fonts (Arial, Times New Roman, Verdana, Courier New) and specify font sizes.
            13. Keep formatting simple but polished: headings, paragraphs, tables, borders, spacing, and alignment.
            14. Do not include explanations, comments, or extra text outside the HTML."""  

        )
        full_prompt = (
            f"{fixed_context}\n\n"
            f"User context:\n{self.user_context}\n\n"
            f"Original HTML:\n{original_html}"
        )

        # 4️⃣ Send to LM – this may take a while
        self.set_progress(0.45)
        edited_html = self.lm.ask(full_prompt)

        # 5️⃣ Write the edited HTML temporarily (close immediately so wkhtmltopdf can access it)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tmp_out:
            tmp_out.write(edited_html)
            temp_edited_path = tmp_out.name

        # 6️⃣ Convert HTML → PDF using wkhtmltopdf
        self.set_progress(0.75)
        try:
            import subprocess  # ensure subprocess is defined
            cmd = [
                "wkhtmltopdf",
                "--enable-local-file-access",
                "--disable-smart-shrinking",
                "--encoding", "UTF-8",
                temp_edited_path,
                output_pdf
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"wkhtmltopdf failed:\n{result.stderr}")
        finally:
            # Clean up temp files
            for path in (temp_html_path, temp_edited_path):
                if os.path.exists(path):
                    os.remove(path)

        # Final progress tick
        self.set_progress(1.0)


    def _run_pipeline_thread(self, pdf_path: str | None, output_pdf: str) -> None:
        """Threaded pipeline runner."""
        try:
            if pdf_path:
                self.set_status("Converting PDF → HTML…")
                self.set_progress(0)
            else:
                self.set_status("Creating new PDF…")
                self.set_progress(0.05)

            self.run_pipeline(pdf_path, output_pdf)

            self.set_status("Done!")
            self.set_progress(1.0)
            messagebox.showinfo(
                "Success",
                f"Modified PDF written to:\n{os.path.abspath(output_pdf)}"
            )
        except Exception as exc:
            def _show_error(exc):
                messagebox.showerror("Processing error", str(exc))
            self.after(0, _show_error, exc)
        finally:
            for w in (self.progress_bar, self.status_label):
                try:
                    w.configure(state="normal")
                except ValueError as exc:
                    if "state" not in str(exc):
                        raise
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app = PDFEditorApp()
    app.mainloop()
