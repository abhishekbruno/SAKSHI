"""
Academic Report Typography, Styles, and Page Layout Engine.
Complies with university B.Tech CS formatting guidelines:
- A4 size with 1.0 inch (72 pt) margins
- 12 pt body font with 1.5 line spacing (18 pt leading)
- 16–18 pt chapter headings, 14–16 pt section headings
- Roman numerals for Front Matter (suppressed on pages 1–3)
- Arabic numerals starting at 1 for Chapter 1
- Running headers and footers with academic rule lines
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Flowable
from reportlab.pdfgen import canvas

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 72.0  # 1.0 inch
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN  # 451.27 pt

page_registry = {}
ch1_page_number = 11  # dynamically updated during multi-pass build


class PageTracker(Flowable):
    """Flowable that captures its exact rendering page number into page_registry."""
    def __init__(self, key: str):
        super().__init__()
        self.key = key
        self.width = 0
        self.height = 0

    def draw(self):
        page_registry[self.key] = self.canv._pageNumber


def to_roman(n: int) -> str:
    """Convert integer to lowercase Roman numeral."""
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syb = ["m", "cm", "d", "cd", "c", "xc", "l", "xl", "x", "ix", "v", "iv", "i"]
    roman_num = ""
    i = 0
    while n > 0:
        for _ in range(n // val[i]):
            roman_num += syb[i]
            n -= val[i]
        i += 1
    return roman_num


def get_pg(key: str, default: str = "1") -> str:
    """Lookup page number for TOC, LOF, LOT."""
    if key not in page_registry:
        return default
    actual_pg = page_registry[key]
    if actual_pg < ch1_page_number:
        return to_roman(actual_pg)
    else:
        return str(actual_pg - ch1_page_number + 1)


class AcademicNumberedCanvas(canvas.Canvas):
    """Custom canvas that renders running headers and footers with academic formatting."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self._draw_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_decorations(self, total_pages: int):
        pg = self._pageNumber
        if pg <= 3:
            return  # Suppress headers, footers and page numbers on Title, Certificate, Declaration

        self.saveState()
        self.setFont("Times-Roman", 9)
        self.setFillColor(colors.HexColor("#4A5568"))

        is_chapter_title_page = False
        for ch_key in ["ch1", "ch2", "ch3", "ch4", "ch5", "ch6", "concl", "ref", "app"]:
            if ch_key in page_registry and page_registry[ch_key] == pg:
                is_chapter_title_page = True
                break

        # Running Header (only on main chapter content pages, not chapter title pages)
        if not is_chapter_title_page and pg >= ch1_page_number:
            self.drawString(MARGIN, PAGE_HEIGHT - 48, "SAKSHI: Explainable AI Investigation Companion (EC-MORE)")
            self.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 48, "B.Tech Project Report")
            self.setStrokeColor(colors.HexColor("#CBD5E0"))
            self.setLineWidth(0.6)
            self.line(MARGIN, PAGE_HEIGHT - 54, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 54)

        # Running Footer
        self.setStrokeColor(colors.HexColor("#CBD5E0"))
        self.setLineWidth(0.6)
        self.line(MARGIN, 56, PAGE_WIDTH - MARGIN, 56)

        self.drawString(MARGIN, 42, "Department of Computer Science and Engineering")

        if pg < ch1_page_number:
            pg_str = to_roman(pg)
        else:
            arabic_num = pg - ch1_page_number + 1
            pg_str = f"Page {arabic_num}"

        self.drawRightString(PAGE_WIDTH - MARGIN, 42, pg_str)
        self.restoreState()


def get_academic_styles():
    """Build complete typography style sheet matching exact university specifications."""
    styles = getSampleStyleSheet()

    C_NAVY = colors.HexColor("#0F294A")
    C_CHARCOAL = colors.HexColor("#1A202C")
    C_MUTED = colors.HexColor("#4A5568")

    # Title Page Styles
    styles.add(ParagraphStyle(
        name="AcademicTitle",
        fontName="Times-Bold",
        fontSize=18,
        leading=24,
        textColor=C_NAVY,
        alignment=1,  # Center
        spaceAfter=15,
    ))

    styles.add(ParagraphStyle(
        name="AcademicSubtitle",
        fontName="Times-Roman",
        fontSize=13,
        leading=18,
        textColor=C_CHARCOAL,
        alignment=1,
        spaceAfter=10,
    ))

    styles.add(ParagraphStyle(
        name="ChapterHeading",
        fontName="Times-Bold",
        fontSize=17,
        leading=23,
        textColor=C_NAVY,
        alignment=0,  # Left
        spaceAfter=12,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="FrontMatterHeading",
        fontName="Times-Bold",
        fontSize=17,
        leading=23,
        textColor=C_NAVY,
        alignment=1,  # Center
        spaceAfter=14,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="SectionHeading",
        fontName="Times-Bold",
        fontSize=14,
        leading=19,
        textColor=C_NAVY,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="SubSectionHeading",
        fontName="Times-Bold",
        fontSize=12,
        leading=16,
        textColor=C_CHARCOAL,
        spaceBefore=11,
        spaceAfter=4,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="SubSubSectionHeading",
        fontName="Times-BoldItalic",
        fontSize=11,
        leading=15,
        textColor=C_CHARCOAL,
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    ))

    # Body: 12 pt font, 18 pt leading (1.5 line spacing), justified
    styles.add(ParagraphStyle(
        name="AcademicBody",
        fontName="Times-Roman",
        fontSize=11,
        leading=16.5,  # 1.5 line spacing
        textColor=C_CHARCOAL,
        alignment=4,  # Justified
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        name="AcademicBodyBold",
        fontName="Times-Bold",
        fontSize=11,
        leading=16.5,
        textColor=C_CHARCOAL,
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        name="BulletText",
        fontName="Times-Roman",
        fontSize=10.5,
        leading=15.5,
        textColor=C_CHARCOAL,
        leftIndent=16,
        firstLineIndent=-10,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name="FigureCaption",
        fontName="Times-Italic",
        fontSize=9.5,
        leading=13.5,
        textColor=C_MUTED,
        alignment=1,  # Center
        spaceBefore=6,
        spaceAfter=12,
    ))

    styles.add(ParagraphStyle(
        name="TableCaption",
        fontName="Times-Bold",
        fontSize=10,
        leading=14,
        textColor=C_NAVY,
        alignment=0,  # Left
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="TableHeader",
        fontName="Times-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=1,
    ))

    styles.add(ParagraphStyle(
        name="TableCell",
        fontName="Times-Roman",
        fontSize=8,
        leading=11,
        textColor=C_CHARCOAL,
    ))

    styles.add(ParagraphStyle(
        name="TableCellBold",
        fontName="Times-Bold",
        fontSize=8,
        leading=11,
        textColor=C_CHARCOAL,
    ))

    styles.add(ParagraphStyle(
        name="AlgorithmText",
        fontName="Courier",
        fontSize=7.5,
        leading=10.5,
        textColor=C_CHARCOAL,
    ))

    styles.add(ParagraphStyle(
        name="TOCLine",
        fontName="Times-Roman",
        fontSize=10,
        leading=15.5,
        textColor=C_CHARCOAL,
    ))

    styles.add(ParagraphStyle(
        name="TOCPage",
        fontName="Times-Bold",
        fontSize=10,
        leading=15.5,
        textColor=C_NAVY,
        alignment=2,
    ))

    return styles
