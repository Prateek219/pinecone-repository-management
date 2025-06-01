from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
import fitz  # PyMuPDF
import uuid
import os
import re
from pinecone import Pinecone, ServerlessSpec
import time
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi.responses import JSONResponse
from typing import List,Dict,Any, Optional,Union
import base64
import json
from mistralai import Mistral
from datetime import datetime
from pydantic import BaseModel
from app.prompts.prompts_library import first_prompt, middle_prompt, last_prompt
from app.service_log.combine_answer import merge_json_blocks
from datetime import datetime
from dotenv import load_dotenv
from enum import Enum

load_dotenv()



# Initialize Firebase app with service account
cred = credentials.Certificate(os.environ.get("FIREBASE_CRED"))
firebase_admin.initialize_app(cred, {
    'projectId': 'resource-rag-management',
})

# Firestore client
db = firestore.client()

class ImageRequest(BaseModel):
    encoded_images: List[str]


# ---- Config ----
API_KEY = os.environ.get("API_KEY")
INDEX_NAME = os.environ.get("INDEX_NAME")
REGION = os.environ.get("REGION")
CLOUD = os.environ.get("CLOUD")

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
    text = re.sub(r'[^\x20-\x7E\u0900-\u097F.,!?()"\':; \n]', '', text)
    return text.strip()



MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
client = Mistral(api_key=MISTRAL_API_KEY)

class FeedbackItem(BaseModel):
    concernedFeedback: str
    relatedText: str

class PDFData(BaseModel):
    extractedText: str

class FinetuningData(BaseModel):
    question: str
    answer: str
    feedback: List[FeedbackItem]  # corrected to list of objects
    total_marks: Optional[Union[float, int]]
    maximum_marks: Optional[int]
    word_limit: Optional[int]
    hand_writting_and_clarity: str
    login_id: str
    paperType : str

# Function to encode image content to base64
def encode_image(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")

# Summarization function for multiple images
def summarize_images(encoded_images: List[str]) -> str:
    if not encoded_images:
        return {"error": "No images provided"}

    outputs = []
    system_message = {
        "role": "system",
        "content": """You are an expert summarizer.
                    Always focus only on the meaningful educational content, such as study material, questions, instructions, and diagrams.
                    Ignore irrelevant information such as notebook headers, coaching institute names (e.g., "Ravi IAS"), page margins, watermarks, "don't write on this side," or any other non-content markings.
                    Your task is to extract and summarize only the core content clearly and precisely
                     **Strict JSON Output**  
                        - Your response MUST be pure, valid JSON  
                        - NO Markdown code blocks (```json) or extra text outside the JSON  
                        - Use double quotes for all strings  """
    }
    for idx, img in enumerate(encoded_images):
        if idx == 0:
            prompt = first_prompt
        elif idx == len(encoded_images) - 1:
            prompt = last_prompt
        else:
            prompt = middle_prompt

        message = [
            system_message,
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": f"data:image/jpeg;base64,{img}"}
                ]
            }
        ]

        response = client.chat.complete(
            model="pixtral-large-latest",
            messages=message,
            max_tokens=2000,
            temperature=0.2,
        )

        output_text = response.choices[0].message.content
        outputs.append(output_text)

    # Send each message to model and collect outputs 
    merge_output = merge_json_blocks(outputs)
    return merge_output
    

@app.post("/upload-pdf")
async def upload_pdf(data: dict):
    file_name = data.get("fileName")
    extracted_text = data.get("extracted_text")

    if not file_name or not file_name.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF filenames are supported.")

    if not extracted_text:
        raise HTTPException(status_code=400, detail="No extracted text provided.")

    try:
        chunks = text_splitter.split_text(extracted_text)
        embeddings = model.encode(chunks).tolist()

        # IDs
        document_id = str(uuid.uuid4())
        book_title = file_name.rsplit(".", 1)[0]
   
        doc_data = {
            "document_id": document_id,
            "timestamp": datetime.utcnow().isoformat(),
            "file_name": file_name,
        }
        db.collection("Resource-list").add(doc_data)
        print(f"📚 Resource saved: {book_title} ({document_id})")

        # Upsert to Pinecone
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = [
                (
                    str(uuid.uuid4()),  # vector ID
                    emb,
                    {
                        "text": chunk,
                        "document_id": document_id,
                    }
                )
                for chunk, emb in zip(chunks[i:i + batch_size], embeddings[i:i + batch_size])
            ]
            index.upsert(batch)
            print(f"✅ Batch {i // batch_size + 1}: Upserted {len(batch)} chunks")

        return {
            "message": "Extracted text indexed successfully.",
            "document_id": document_id,
            "total_chunks": len(chunks)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/review-pdf")
async def review_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF Review")

    try:
        contents = await file.read()
        doc = fitz.open(stream=contents, filetype="pdf")
        text = "".join([clean_text(page.get_text()) for page in doc])
        return text
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
@app.get("/resources-list")
def list_documents():
    try:
        docs_ref = db.collection("Resource-list")
        docs = docs_ref.stream()

        documents_list = []
        for doc in docs:
            data = doc.to_dict()
            documents_list.append({
                "book_title": data.get("book_title", data.get("file_name", "Unknown")),
                "document_id": data.get("document_id"),
                "timestamp": data.get("timestamp")
            })

        return {"documents": documents_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "Welcome to the UPSC Answer Processing API"}

@app.post("/summarize")
async def summarize_images_endpoint(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    base64_images = []
    

    for file in files:
        print(len(files)) 
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"{file.filename} is not a valid image.")
        content = await file.read()
        base64_images.append(encode_image(content))

    raw_output = summarize_images(base64_images)   
    return JSONResponse(content={"output": raw_output}, media_type="application/json")


@app.post("/api/save-finetuning")
async def save_finetuning(data: FinetuningData):
    try:
        unique_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        doc_data = {
            "unique_id": unique_id,
            "timestamp": timestamp,
            "login_id": data.login_id,
            "question": data.question,
            "answer": data.answer,
            "feedback": [item.dict() for item in data.feedback],
            "total_marks": data.total_marks,
            "maximum_marks": data.maximum_marks,
            "word_limit": data.word_limit,
            "hand_writting_and_clarity": data.hand_writting_and_clarity,
            "paperType": data.paperType
        }

        db.collection("handWrittenAnswerData").document(unique_id).set(doc_data)

        return {"message": "Data saved successfully", "unique_id": unique_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/get-finetuning-stats")
async def get_finetuning_stats():
    try:
        docs = db.collection("handWrittenAnswerData").limit(1000).stream()
        total = sum(1 for _ in docs)
        return {"total_count": total}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PaperEnum(str, Enum):
    GS1 = "GS1"
    GS2 = "GS2"
    GS3 = "GS3"
    GS4 = "GS4"
    ESSAY = "ESSAY"

@app.get("/paper-types")
async def get_paper_types():
    return [paper.value for paper in PaperEnum]