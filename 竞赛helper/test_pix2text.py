from pix2text import Pix2Text
import os

PDF_FILE = r"C:\竞赛helper\sample_5_pages.pdf"
OUTPUT_DIR = r"C:\竞赛helper\out_pix2text"

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Loading Pix2Text...")
p2t = Pix2Text.from_config(disable_table=True)

print(f"Processing: {PDF_FILE}")
doc = p2t.recognize_pdf(PDF_FILE)

md_file = os.path.join(OUTPUT_DIR, "result.md")
print(f"Saving to: {md_file}")
doc.to_markdown(md_file)
print("Done!")
