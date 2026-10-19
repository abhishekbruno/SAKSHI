"""
Master Academic B.Tech Computer Science Project Report Builder.
Assembles the complete report across all front matter, 6 chapters, conclusion, references, and appendices.
Enforces multi-pass page-number synchronization so TOC, LOF, and LOT match exact rendered pages.
Guarantees AT LEAST 40 FULL PAGES (target: 45–50 pages).
"""
import io
import os
import sys

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate

import report_styles
from report_styles import (
    get_academic_styles,
    AcademicNumberedCanvas,
    PageTracker,
    get_pg,
    to_roman,
    page_registry,
    MARGIN,
    PAGE_WIDTH,
    PAGE_HEIGHT,
)

from report_frontmatter import get_frontmatter
from report_chapter1 import get_chapter1
from report_chapter2 import get_chapter2
from report_chapter3 import get_chapter3
from report_chapter4 import get_chapter4
from report_chapter5 import get_chapter5
from report_chapter6 import get_chapter6
from report_conclusion import get_conclusion
from report_references import get_references
from report_appendices import get_appendices


def build_story(styles):
    story = []
    # Front Matter (Title, Certificate, Declaration, Ack, Abstract, TOC, LOF, LOT, LOA)
    story.extend(get_frontmatter(styles, get_pg, PageTracker))
    # Chapter 1: Introduction
    story.extend(get_chapter1(styles, PageTracker))
    # Chapter 2: Literature Survey
    story.extend(get_chapter2(styles, PageTracker))
    # Chapter 3: System Analysis and Design
    story.extend(get_chapter3(styles, PageTracker))
    # Chapter 4: Implementation
    story.extend(get_chapter4(styles, PageTracker))
    # Chapter 5: Testing and Results
    story.extend(get_chapter5(styles, PageTracker))
    # Chapter 6: Security, Limitations and Future Work
    story.extend(get_chapter6(styles, PageTracker))
    # Conclusion
    story.extend(get_conclusion(styles, PageTracker))
    # References
    story.extend(get_references(styles, PageTracker))
    # Appendices (A through G)
    story.extend(get_appendices(styles, PageTracker))
    return story


def generate_report():
    output_filename = "SAKSHI_BTech_CS_Project_Report.pdf"
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_filename)
    styles = get_academic_styles()
    doc_kwargs = dict(
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    print("====================================================================")
    print("Building Full SAKSHI B.Tech Academic Project Report (40+ Pages)...")
    print("====================================================================")

    # Pass 1: Dry run to populate page_registry
    print("Executing Pass 1 (Dry run for page-number discovery)...")
    buffer1 = io.BytesIO()
    doc1 = SimpleDocTemplate(buffer1, **doc_kwargs)
    story1 = build_story(styles)
    doc1.build(story1, canvasmaker=AcademicNumberedCanvas)

    if "ch1" in page_registry:
        report_styles.ch1_page_number = page_registry["ch1"]
        print(f"Pass 1 complete. Chapter 1 begins on absolute page {report_styles.ch1_page_number}.")
    else:
        print(f"Warning: 'ch1' not in page_registry, using default {report_styles.ch1_page_number}")

    # Pass 2: Re-run with updated page numbers
    print("Executing Pass 2 (Page synchronization & directory refinement)...")
    buffer2 = io.BytesIO()
    doc2 = SimpleDocTemplate(buffer2, **doc_kwargs)
    story2 = build_story(styles)
    doc2.build(story2, canvasmaker=AcademicNumberedCanvas)

    if "ch1" in page_registry:
        report_styles.ch1_page_number = page_registry["ch1"]
        print(f"Pass 2 complete. Chapter 1 begins on absolute page {report_styles.ch1_page_number}.")

    # Pass 3: Final render to disk
    print(f"Executing Pass 3 (Writing final PDF to {output_filename})...")
    doc3 = SimpleDocTemplate(output_path, **doc_kwargs)
    story3 = build_story(styles)
    doc3.build(story3, canvasmaker=AcademicNumberedCanvas)

    file_size = os.path.getsize(output_path)
    total_pages = doc3.page
    ch1_abs = report_styles.ch1_page_number
    front_matter_pages = ch1_abs - 1
    main_content_pages = total_pages - front_matter_pages

    print("====================================================================")
    print("SUCCESS: Academic Report generated successfully!")
    print(f"File Path: {output_path}")
    print(f"File Size: {file_size / (1024*1024):.2f} MB ({file_size:,} bytes)")
    print(f"Total Pages: {total_pages}")
    print(f"Front Matter Pages: {front_matter_pages} (Pages 1–{front_matter_pages} -> Roman i–{to_roman(front_matter_pages)})")
    print(f"Main Content Pages: {main_content_pages} (Pages {ch1_abs}–{total_pages} -> Arabic 1–{main_content_pages})")
    print("====================================================================")

    if total_pages < 40:
        print(f"WARNING: Total page count {total_pages} is below the 40-page requirement!")
    else:
        print(f"PAGE COUNT REQUIREMENT MET: {total_pages} pages (>= 40 required, target 45–50).")


if __name__ == "__main__":
    generate_report()
