import os
import sys
import tempfile
import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinter import *
import threading
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
        pdf = self.pdf_path.get()
        out_name = self.output_name.get().strip()

        if not os.path.isfile(pdf):
            messagebox.showerror("Error", "Please choose a valid PDF file.")
            return

        if not out_name.lower().endswith(".pdf"):
            out_name += ".pdf"

        self.user_context = self.context_box.get("1.0", "end-1c")

        # Disable the Start button while running
        for w in (self.progress_bar, self.status_label):
            try:
                # Only apply state to widgets that accept it
                w.configure(state="disabled")
            except ValueError as exc:
                # Not all widgets support `state`; ignore the error
                if "state" not in str(exc):
                    raise     # re‑raise unexpected errors

        threading.Thread(
            target=self._run_pipeline_thread,
            args=(pdf, out_name),
            daemon=True   # so it exits if you close the window
        ).start()

    # ------------------------------------------------------------------
    def run_pipeline(self, pdf_path: str, output_pdf: str) -> None:
        """All the heavy lifting – orchestrates the four steps."""
        # 1️⃣ PDF → temporary HTML
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_in:
            temp_html = tmp_in.name
        self.set_progress(0.15)
        pdf_to_html(pdf_path, temp_html)

        # 2️⃣ Read original HTML
        with open(temp_html, encoding="utf-8") as f:
            original_html = f.read()
        self.set_progress(0.30)

        # 3️⃣ Build prompt (fixed + user supplied)
        fixed_context = (
            "Below is an instruction that describes a task. "
            "Write a response that appropriately completes the request and only output the answer and nothing extra."
        )
        full_prompt = (
            f"{fixed_context}\n\n"
            f"User context:\n{self.user_context}\n\n"
            f"Original HTML:\n{original_html}"
        )

        # 4️⃣ Send to LM – this may take a while
        self.set_progress(0.45)
        edited_html = self.lm.ask(full_prompt)

        # 5️⃣ Write the edited HTML temporarily
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_out:
            temp_edited = tmp_out.name
            tmp_out.write(edited_html.encode("utf-8"))

        # 6️⃣ Convert edited HTML → final PDF
        self.set_progress(0.75)
        html_to_pdf(temp_edited, output_pdf)

        # Clean up temporaries
        os.remove(temp_html)
        os.remove(temp_edited)

        # Final progress tick
        self.set_progress(1.0)


    def _run_pipeline_thread(self, pdf_path: str, output_pdf: str) -> None:
        try:
            self.set_status("Converting PDF → HTML…")
            self.set_progress(0.1)
            self.run_pipeline(pdf_path, output_pdf)
            self.set_status("Done!")
            self.set_progress(1.0)
            messagebox.showinfo(
                "Success",
                f"Modified PDF written to:\n{os.path.abspath(output_pdf)}"
            )
        except Exception as exc:
            # Show error – this is run in the main thread via after
            def _show_error():
                messagebox.showerror("Processing error", str(exc))
            self.after(0, _show_error)
        finally:
            # Re‑enable widgets no matter what
            for w in (self.progress_bar, self.status_label):
                try:
                    # Only apply state to widgets that accept it
                    w.configure(state="disabled")
                except ValueError as exc:
                    # Not all widgets support `state`; ignore the error
                    if "state" not in str(exc):
                        raise     # re‑raise unexpected errors

# ----------------------------------------------------------------------
if __name__ == "__main__":
    app = PDFEditorApp()
    app.mainloop()
