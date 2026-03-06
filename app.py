import os
import re
import zipfile
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image as RLImage,
    PageBreak,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
ANSWER_PATTERN = re.compile(r"(?:[_\-\s])([A-Ea-e])(?=\.[^.]+$)")


class WorksheetBuilderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Worksheet PDF Builder")
        self.root.geometry("760x560")

        self.zip_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.problems_per_page = tk.IntVar(value=5)
        self.include_answer_key = tk.BooleanVar(value=True)
        self.add_work_space = tk.BooleanVar(value=True)
        self.status_text = tk.StringVar(value="Choose a ZIP file to begin.")

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 12, "pady": 8}

        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)

        title = ttk.Label(
            main,
            text="Worksheet PDF Builder",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(anchor="w", padx=12, pady=(14, 6))

        subtitle = ttk.Label(
            main,
            text=(
                "Build a worksheet PDF from a ZIP of problem screenshots. "
                "Use filenames like problem_12_D.png so the final letter becomes the answer key."
            ),
            wraplength=720,
            justify="left",
        )
        subtitle.pack(anchor="w", padx=12, pady=(0, 10))

        file_frame = ttk.LabelFrame(main, text="Files")
        file_frame.pack(fill="x", **pad)

        ttk.Label(file_frame, text="Input ZIP:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        ttk.Entry(file_frame, textvariable=self.zip_path, width=70).grid(row=0, column=1, sticky="ew", padx=10, pady=10)
        ttk.Button(file_frame, text="Browse", command=self.choose_zip).grid(row=0, column=2, padx=10, pady=10)

        ttk.Label(file_frame, text="Output PDF:").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        ttk.Entry(file_frame, textvariable=self.output_path, width=70).grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        ttk.Button(file_frame, text="Save As", command=self.choose_output).grid(row=1, column=2, padx=10, pady=10)

        file_frame.columnconfigure(1, weight=1)

        options_frame = ttk.LabelFrame(main, text="Options")
        options_frame.pack(fill="x", **pad)

        ttk.Label(options_frame, text="Problems per page:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        ttk.Spinbox(
            options_frame,
            from_=1,
            to=10,
            textvariable=self.problems_per_page,
            width=6,
        ).grid(row=0, column=1, sticky="w", padx=10, pady=10)

        ttk.Checkbutton(
            options_frame,
            text="Include answer key page",
            variable=self.include_answer_key,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=6)

        ttk.Checkbutton(
            options_frame,
            text="Leave extra space for student work",
            variable=self.add_work_space,
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=6)

        help_frame = ttk.LabelFrame(main, text="Answer-key filename format")
        help_frame.pack(fill="x", **pad)

        help_text = (
            "Recommended format: make the final letter before the extension the answer choice.\n\n"
            "Examples:\n"
            "  algebra_01_A.png\n"
            "  geo-problem-12-C.jpg\n"
            "  q7 b.jpeg\n\n"
            "Accepted answer letters: A through E."
        )
        ttk.Label(help_frame, text=help_text, justify="left").pack(anchor="w", padx=10, pady=10)

        action_frame = ttk.Frame(main)
        action_frame.pack(fill="x", **pad)

        ttk.Button(action_frame, text="Build PDF", command=self.build_pdf).pack(side="left")
        ttk.Label(action_frame, textvariable=self.status_text).pack(side="left", padx=14)

    def choose_zip(self):
        path = filedialog.askopenfilename(
            title="Choose ZIP of problem images",
            filetypes=[("ZIP files", "*.zip")],
        )
        if path:
            self.zip_path.set(path)
            if not self.output_path.get():
                self.output_path.set(str(Path(path).with_suffix(".pdf")))

    def choose_output(self):
        path = filedialog.asksaveasfilename(
            title="Save worksheet PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if path:
            self.output_path.set(path)

    def build_pdf(self):
        zip_path = self.zip_path.get().strip()
        output_path = self.output_path.get().strip()

        if not zip_path:
            messagebox.showerror("Missing ZIP", "Please choose an input ZIP file.")
            return

        if not os.path.isfile(zip_path):
            messagebox.showerror("ZIP not found", "The selected ZIP file could not be found.")
            return

        if not output_path:
            messagebox.showerror("Missing output", "Please choose where to save the PDF.")
            return

        try:
            self.status_text.set("Extracting images...")
            self.root.update_idletasks()

            with tempfile.TemporaryDirectory() as temp_dir:
                extract_dir = Path(temp_dir) / "extracted"
                extract_dir.mkdir(parents=True, exist_ok=True)

                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(extract_dir)

                images = self._collect_images(extract_dir)
                if not images:
                    raise ValueError("No supported image files were found inside the ZIP.")

                self.status_text.set("Preparing pages...")
                self.root.update_idletasks()

                self._generate_pdf(images, output_path)

            self.status_text.set("Done.")
            messagebox.showinfo("Success", f"Worksheet saved to:\n{output_path}")

        except Exception as exc:
            self.status_text.set("Build failed.")
            messagebox.showerror("Error", str(exc))

    def _collect_images(self, extract_dir: Path):
        images = []
        for path in extract_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                answer = self._extract_answer_from_filename(path.name)
                images.append({"path": path, "answer": answer})
        return images

    @staticmethod
    def _extract_answer_from_filename(filename: str):
        match = ANSWER_PATTERN.search(filename)
        return match.group(1).upper() if match else None

    def _prepare_image_for_pdf(self, image_path: Path, temp_dir: Path, index: int):
        out_path = temp_dir / f"prepared_{index:04d}.png"
        with Image.open(image_path) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")
            if im.mode == "RGBA":
                bg = Image.new("RGB", im.size, "white")
                bg.paste(im, mask=im.split()[-1])
                im = bg
            im.save(out_path, format="PNG")
        return out_path

    def _generate_pdf(self, images, output_path: str):
        styles = getSampleStyleSheet()
        normal = styles["Normal"]
        heading = styles["Heading2"]

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=0.6 * inch,
            rightMargin=0.6 * inch,
            topMargin=0.6 * inch,
            bottomMargin=0.6 * inch,
        )

        elements = []
        problems_per_page = max(1, int(self.problems_per_page.get()))
        page_width, _ = letter
        usable_width = page_width - doc.leftMargin - doc.rightMargin

        with tempfile.TemporaryDirectory() as prep_dir_str:
            prep_dir = Path(prep_dir_str)
            for idx, item in enumerate(images, start=1):
                if idx > 1 and (idx - 1) % problems_per_page == 0:
                    elements.append(PageBreak())

                prepared_path = self._prepare_image_for_pdf(item["path"], prep_dir, idx)
                with Image.open(prepared_path) as im:
                    width_px, height_px = im.size

                max_image_width = usable_width
                max_image_height = 1.05 * inch if problems_per_page >= 5 else 1.5 * inch
                scale = min(max_image_width / width_px, max_image_height / height_px)

                elements.append(Paragraph(f"<b>Problem {idx}</b>", normal))
                elements.append(
                    RLImage(
                        str(prepared_path),
                        width=width_px * scale,
                        height=height_px * scale,
                    )
                )

                spacer_height = 0.32 * inch if self.add_work_space.get() else 0.14 * inch
                elements.append(Spacer(1, spacer_height))

            if self.include_answer_key.get():
                answer_items = [
                    (i, item["answer"])
                    for i, item in enumerate(images, start=1)
                    if item["answer"] is not None
                ]

                if answer_items:
                    elements.append(PageBreak())
                    elements.append(Paragraph("Answer Key", heading))
                    elements.append(Spacer(1, 0.15 * inch))
                    for number, answer in answer_items:
                        elements.append(Paragraph(f"{number}. {answer}", normal))
                        elements.append(Spacer(1, 0.06 * inch))

        doc.build(elements)


def main():
    root = tk.Tk()
    app = WorksheetBuilderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()