import asyncio
from mfdetect.mmdet_pipeline import MMDetPipeline
from mineru.parallel.task import Task
from mineru.pipeline.pipeline import Pipeline
import os
import fitz

PDF_FILE = "C:/竞赛helper/sample_5_pages.pdf"
OUTPUT_DIR = "C:/竞赛helper/out_mineru/sample"

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Starting MinerU Pipeline directly...")

# Use the Pipeline class to process the PDF
# mineru.cli.client uses this internally
from mineru.pipeline.pipeline import Pipeline

# Create a pipeline instance with OCR mode and Chinese language
pipeline = Pipeline(
    input_path=PDF_FILE,
    output_dir=OUTPUT_DIR,
    config={
        "pipeline_params": {
            "ocr_config": {"lang_list": ["ch", "en"]},
            "formula_enable": True,
            "table_enable": False,  # Disabled for now to avoid model issues
        }
    },
)

# Run the pipeline
print("Processing...")
pipeline.run()
print("Done!")
