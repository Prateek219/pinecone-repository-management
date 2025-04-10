from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
import fitz  # PyMuPDF
import uuid
import os
import re
from pinecone import Pinecone, ServerlessSpec
import time



# ---- Config ----
API_KEY = "pcsk_7Wh7eu_4V9CacarBGTZzW2oGtsXFv4bsJEB75QCen7pQ7eco6rcZ2X5BnTXRy2gFi9nAHo"
INDEX_NAME = "upsc-langchain-pinecone"
REGION = "us-east-1"
CLOUD = "aws"
EMBEDDING_MODEL = 'BAAI/bge-large-en-v1.5'

# ---- Init ----
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
model = SentenceTransformer(EMBEDDING_MODEL)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
pc = Pinecone(api_key=API_KEY)

if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX_NAME,
        dimension=model.get_sentence_embedding_dimension(),
        metric='dotproduct',
        spec=ServerlessSpec(cloud=CLOUD, region=REGION)
    )
index = pc.Index(INDEX_NAME)

# ---- Utils ----
def clean_text(text):
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

# ---- 1. Upload PDF ----
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        contents = await file.read()
        doc = fitz.open(stream=contents, filetype="pdf")
        text = "".join([clean_text(page.get_text()) for page in doc])

        chunks = text_splitter.split_text(text)
        embeddings = model.encode(chunks).tolist()

        document_id = str(uuid.uuid4())
        resource_id = file.filename

        batch_size = 50
        total_upserted = 0

        for i in range(0, len(chunks), batch_size):
            batch = [
                (
                    str(uuid.uuid4()), 
                    emb, 
                    {
                        "text": chunk,
                        "document_id": document_id,
                        "resource_id": resource_id
                    }
                )
                for chunk, emb in zip(chunks[i:i + batch_size], embeddings[i:i + batch_size])
            ]

            index.upsert(batch)
            total_upserted += len(batch)
            print(f"✅ Batch {i // batch_size + 1}: Upserted {len(batch)} vectors")

        return {
            "message": "PDF uploaded and indexed.",
            "document_id": document_id,
            "resource_id": resource_id,
            "total_chunks": total_upserted
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ---- 2. Delete Document ----
@app.delete("/documents/{document_id}")
def delete_document(document_id: str):
    try:
        # Find vector ids with the given document_id (this only works if metadata filtering is supported)
        response = index.delete(filter={"document_id": {"$eq": document_id}})
        return {"message": "Document deleted successfully.", "result": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---- 3. Query ----
@app.post("/query")
def query_pinecone(payload: dict):
    try:
        query = payload.get("query")
        query_vector = model.encode(query).tolist()
        response = index.query(vector=query_vector, top_k=10, include_metadata=True)

        results = [
            {"text": match.metadata.get("text"), "score": match.score}
            for match in response.matches
        ]
        return {"matches": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---- 4. List Documents (optional) ----
@app.get("/documents")
def list_documents():
    try:
        return {"message": "Listing documents not implemented — requires external DB or caching."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
