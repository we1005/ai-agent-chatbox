import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

file_path = "backend/data/uploads/9866530f-7074-45d0-9eb5-3bb263a74fc8.pdf"

print("--- Testing PyMuPDFLoader ---")
try:
    from langchain_community.document_loaders import PyMuPDFLoader
    loader1 = PyMuPDFLoader(file_path)
    docs1 = loader1.load()
    for i, doc in enumerate(docs1):
        print(f"Page {i+1} content (first 200 chars):")
        print(doc.page_content[:200])
        print("-" * 20)
except Exception as e:
    print(f"PyMuPDFLoader failed: {e}")

print("\n--- Testing PDFPlumberLoader ---")
try:
    from langchain_community.document_loaders import PDFPlumberLoader
    loader2 = PDFPlumberLoader(file_path)
    docs2 = loader2.load()
    for i, doc in enumerate(docs2):
        print(f"Page {i+1} content (first 200 chars):")
        print(doc.page_content[:200])
        print("-" * 20)
except Exception as e:
    print(f"PDFPlumberLoader failed: {e}")
