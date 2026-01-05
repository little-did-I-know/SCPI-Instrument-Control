"""
Quick test script to diagnose PDF generation issue.
Run this to see detailed output without the GUI.
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Set UTF-8 output for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Test if ReportLab works
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    print("[OK] ReportLab imported successfully")

    # Try to generate a simple PDF
    temp_pdf = Path(tempfile.gettempdir()) / "test_reportlab.pdf"
    doc = SimpleDocTemplate(str(temp_pdf), pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph("Test PDF Generation", styles["Title"])]

    print(f"Generating test PDF to: {temp_pdf}")
    doc.build(story)

    if temp_pdf.exists():
        size = temp_pdf.stat().st_size
        print(f"[OK] Test PDF created: {size} bytes")

        # Check header
        with open(temp_pdf, "rb") as f:
            header = f.read(10)
            print(f"[OK] PDF header: {header}")

        # Try to load with QPdfDocument
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtPdf import QPdfDocument

            pdf_doc = QPdfDocument(None)
            status = pdf_doc.load(str(temp_pdf))
            print(f"QPdfDocument load status: {status}")
            print(f"QPdfDocument.Status.Ready = {QPdfDocument.Status.Ready}")

            if status == QPdfDocument.Status.Ready:
                print(f"[OK] QPdfDocument loaded successfully")
                print(f"  Pages: {pdf_doc.pageCount()}")
            else:
                print(f"[FAIL] QPdfDocument failed to load")
                print(f"  Error: {pdf_doc.error()}")

        except ImportError as e:
            print(f"[FAIL] QPdfDocument not available: {e}")

        # Cleanup
        temp_pdf.unlink()
    else:
        print("[FAIL] Test PDF was not created")

except ImportError as e:
    print(f"[FAIL] ReportLab not available: {e}")
except Exception as e:
    print(f"[FAIL] Error during test: {e}")
    import traceback

    traceback.print_exc()

print("\n=== Summary ===")
print("If all tests passed, the issue might be with the actual report generation.")
print("If QPdfDocument failed, try the QWebEngineView fallback.")
