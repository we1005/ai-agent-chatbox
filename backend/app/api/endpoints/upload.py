import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.rag_service import get_rag_service, SUPPORTED_EXTENSIONS
from app.models.knowledge_document import KnowledgeDocument

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    import os
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式 '{file_ext}'，支持：{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    # 前置检查：Embedding 服务是否就绪
    rag = get_rag_service()
    if not rag.is_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "EMBEDDING_NOT_READY",
                "message": "Embedding 模型未加载，请先在知识库设置中下载并启用模型。"
            }
        )
    try:
        result = await rag.upload_document(file)
        return {"message": "File uploaded, vectorization started", "details": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def list_documents():
    try:
        docs = await KnowledgeDocument.find_all().to_list()
        return [
            {
                "filename": d.original_name,
                "file_id": d.file_id,
                "extension": d.extension,
                "size": d.file_size,
                "chunks": d.chunk_count,
                "status": d.vectorize_status,
                "error_message": d.error_message,
                "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
                "vectorized_at": d.vectorized_at.isoformat() if d.vectorized_at else None,
            }
            for d in docs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{file_id}/status")
async def document_status(file_id: str):
    doc = await KnowledgeDocument.find_one(KnowledgeDocument.file_id == file_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "file_id": doc.file_id,
        "status": doc.vectorize_status,
        "chunks": doc.chunk_count,
        "error_message": doc.error_message,
    }


@router.delete("/documents/{file_id}")
async def delete_document(file_id: str):
    try:
        await get_rag_service().delete_document(file_id)
        return {"message": f"Document {file_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Delete failed for {file_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{file_id}/revectorize")
async def revectorize_document(file_id: str):
    rag = get_rag_service()
    if not rag.is_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "EMBEDDING_NOT_READY",
                "message": "Embedding 模型未加载，请先在知识库设置中加载模型。"
            }
        )
    try:
        result = await rag.revectorize_document(file_id)
        return {"message": f"Document {file_id} revectorized successfully", "details": result}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Revectorize failed for {file_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


