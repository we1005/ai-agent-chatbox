import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "backend", ".env"))

def check_chroma_db():
    print("--- Inspecting Chroma DB ---")
    from app.services.rag_service import rag_service
    
    collection = rag_service.vector_store.get()
    
    ids = collection.get("ids", [])
    metadatas = collection.get("metadatas", [])
    documents = collection.get("documents", [])
    
    print(f"Total chunks in Chroma DB: {len(ids)}")
    
    if len(ids) > 0:
        print("\nSample of first 3 chunks:")
        for i in range(min(3, len(ids))):
            print(f"ID: {ids[i]}")
            print(f"Metadata: {metadatas[i]}")
            print(f"Content (first 100 chars): {documents[i][:100]}")
            print("-" * 20)

if __name__ == "__main__":
    check_chroma_db()
