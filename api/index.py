import os
import sys
import shutil
import pickle
import json
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add project root to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv()

from rag.pipeline import answer, index_exists, INDEX_PATH, CHUNKS_PATH, KB_PATH
from ingestion.build_index import build_index

app = FastAPI(title="DPU EduBot API", version="2.0")

# CORS middleware for local testing and deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str
    batch_id: str = "mba_jan_26_sem1"
    language: str = "English"
    erp_id: Optional[str] = None

class RebuildResponse(BaseModel):
    success: bool
    message: str
    padding: int = 0
    chunks_count: int

@app.post("/api/chat")
async def chat_endpoint(payload: ChatRequest):
    try:
        res = answer(payload.query, payload.batch_id, payload.language, payload.erp_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/kb_status")
async def kb_status():
    try:
        # Load KB
        if not os.path.exists(KB_PATH):
            return {"ready": False, "message": "Knowledge base schema not found."}
            
        with open(KB_PATH, encoding="utf-8") as f:
            kb = json.load(f)
            
        total_faqs = sum(len(v.get("faqs", [])) for v in kb.get("layer_1_faqs", {}).values())
        
        # Load chunks size if built
        chunks_count = 0
        if os.path.exists(CHUNKS_PATH):
            with open(CHUNKS_PATH, "rb") as f:
                chunks = pickle.load(f)
                chunks_count = len(chunks)
                
        return {
            "ready": index_exists(),
            "total_faqs": total_faqs,
            "chunks_count": chunks_count,
            "batches_count": len(kb.get("layer_2_batch_specific", {})),
            "redirect_triggers_count": len(kb.get("layer_0_redirect_rules", {}).get("triggers", []))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rebuild_index", response_model=RebuildResponse)
async def rebuild_index():
    try:
        # Clear cache and run build_index
        from rag.pipeline import invalidate_cache
        invalidate_cache()
        count = build_index()
        return {
            "success": True if count > 0 else False,
            "message": f"Successfully indexed {count} chunks!" if count > 0 else "Index build failed.",
            "chunks_count": count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload_doc")
async def upload_document(
    batch_id: str = Form(...),
    doc_type: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        # Save temporary file
        os.makedirs("data/batch_uploads", exist_ok=True)
        filename = file.filename.replace(" ", "_")
        tmp_path = os.path.join("data/batch_uploads", filename)
        
        with open(tmp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Parse document using the parsers in ingestion.parse_docs
        from ingestion.parse_docs import parse_pdf, parse_docx, parse_excel
        
        if filename.endswith(".pdf"):
            chunks = parse_pdf(tmp_path, batch_id, doc_type)
        elif filename.endswith(".docx"):
            chunks = parse_docx(tmp_path, batch_id, doc_type)
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            chunks = parse_excel(tmp_path, batch_id, doc_type)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format.")
            
        return {
            "success": True,
            "chunks_count": len(chunks),
            "message": f"Extracted {len(chunks)} chunks from {file.filename}. Click 'Rebuild Index' to activate."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static folder for local UI rendering (dev only)
if not os.environ.get("VERCEL"):
    os.makedirs("public", exist_ok=True)
    app.mount("/", StaticFiles(directory="public", html=True), name="public")

