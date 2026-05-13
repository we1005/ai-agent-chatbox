import sys
import os
import asyncio

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "backend", ".env"))

async def test_retrieval():
    print("--- Testing RAG Retrieval Chain ---")
    from app.services.rag_service import rag_service
    
    query = "计算所复试名单有哪些人？"
    print(f"Query: {query}")
    
    retriever = rag_service.get_retriever()
    docs = await retriever.ainvoke(query)
    
    print(f"\nFound {len(docs)} chunks:")
    for i, doc in enumerate(docs):
        print(f"\n--- Chunk {i+1} ---")
        print(f"Metadata: {doc.metadata}")
        print("Content:")
        print(doc.page_content)
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(test_retrieval())
