import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

file_path = "backend/data/uploads/9866530f-7074-45d0-9eb5-3bb263a74fc8.pdf"

print("--- Testing PDFPlumberLoader to file ---")
try:
    from langchain_community.document_loaders import PDFPlumberLoader
    loader2 = PDFPlumberLoader(file_path)
    docs2 = loader2.load()
    
    with open("pdfplumber_test.txt", "w", encoding="utf-8") as f:
        for i, doc in enumerate(docs2):
            f.write(f"--- Page {i+1} ---\n")
            f.write(doc.page_content)
            f.write("\n\n")
    print("Wrote PDFPlumber output to pdfplumber_test.txt")
except Exception as e:
    print(f"PDFPlumberLoader failed: {e}")

print("--- Testing PyMuPDFLoader to file ---")
try:
    from langchain_community.document_loaders import PyMuPDFLoader
    loader1 = PyMuPDFLoader(file_path)
    docs1 = loader1.load()
    
    with open("pymupdf_test.txt", "w", encoding="utf-8") as f:
        for i, doc in enumerate(docs1):
            f.write(f"--- Page {i+1} ---\n")
            f.write(doc.page_content)
            f.write("\n\n")
    print("Wrote PyMuPDFLoader output to pymupdf_test.txt")
except Exception as e:
    print(f"PyMuPDFLoader failed: {e}")
