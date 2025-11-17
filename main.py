import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import db, create_document, get_documents
from schemas import MpuUser, TrainingSession, ChecklistItem, AnalysisReport

app = FastAPI(title="MPU Prep Platform API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "MPU Prep Platform Backend Running"}

# --- Health & DB test ---
@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, 'name', None) or ("✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set")
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# --- Simple AI-like analysis stub (no external model, deterministic rules) ---
class AnalysisInput(BaseModel):
    text: str
    user_id: Optional[str] = None

@app.post("/api/analyze", response_model=dict)
def analyze_text(payload: AnalysisInput):
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Very simple rule-based signals to simulate AI
    lowered = text.lower()
    negative_keywords = ["angst", "sorge", "problem", "rückfall", "unsicher", "stress", "alkohol", "drogen"]
    positive_keywords = ["vorbereitet", "bereit", "besser", "verändert", "therapie", "kontrolle", "motivation"]

    neg_hits = sum(k in lowered for k in negative_keywords)
    pos_hits = sum(k in lowered for k in positive_keywords)

    sentiment = "neutral"
    if pos_hits > neg_hits and pos_hits > 0:
        sentiment = "positive"
    elif neg_hits > pos_hits and neg_hits > 0:
        sentiment = "negative"

    risk_score = min(1.0, max(0.0, 0.2 + 0.15 * neg_hits - 0.1 * pos_hits))

    key_themes = [k for k in (negative_keywords + positive_keywords) if k in lowered][:6]

    recs: List[str] = []
    if risk_score >= 0.6:
        recs.append("Empfohlen: zusätzliche Beratungsgespräche und Selbstreflexion zu Risikosituationen")
    if "alkohol" in lowered or "drogen" in lowered:
        recs.append("Dokumentiere Abstinenznachweise und Teilnahme an Programmen")
    if pos_hits == 0:
        recs.append("Erarbeite klare Beispiele für Verhaltensänderungen")
    if "therapie" in lowered:
        recs.append("Heb hervor, welche konkreten Fortschritte du in der Therapie gemacht hast")
    if not recs:
        recs.append("Weiter so: strukturiert deine Argumentation mit Ich-Botschaften und konkreten Beispielen")

    report = AnalysisReport(
        user_id=payload.user_id,
        input_text=text,
        sentiment=sentiment, 
        risk_score=risk_score,
        key_themes=key_themes,
        recommendations=recs
    )

    try:
        doc_id = create_document("analysisreport", report)
    except Exception:
        doc_id = None

    return {
        "sentiment": sentiment,
        "risk_score": risk_score,
        "key_themes": key_themes,
        "recommendations": recs,
        "id": doc_id
    }

# --- Live training session endpoints (simplified) ---
class StartSessionInput(BaseModel):
    user_id: str

@app.post("/api/session/start")
def start_session(payload: StartSessionInput):
    questions = [
        {"id": 1, "q": "Was war der Auslöser deiner Verkehrsauffälligkeit?"},
        {"id": 2, "q": "Welche Verhaltensänderungen hast du seitdem umgesetzt?"},
        {"id": 3, "q": "Wie gehst du heute mit Risikosituationen um?"}
    ]
    session = TrainingSession(user_id=payload.user_id, status='started', questions=questions)
    try:
        session_id = create_document("trainingsession", session)
    except Exception:
        session_id = None

    return {"session_id": session_id, "questions": questions}

class SubmitSessionInput(BaseModel):
    session_id: Optional[str] = None
    user_id: str
    answers: List[dict]

@app.post("/api/session/submit")
def submit_session(payload: SubmitSessionInput):
    answers = payload.answers
    completeness = sum(1 for a in answers if a.get("text")) / max(1, len(answers))
    depth = sum(min(1.0, len(a.get("text", "")) / 120) for a in answers) / max(1, len(answers))
    score = round(100 * (0.4 * completeness + 0.6 * depth), 1)

    feedback_parts = []
    if completeness < 0.8:
        feedback_parts.append("Beantworte alle Fragen vollständig.")
    if depth < 0.6:
        feedback_parts.append("Geh tiefer auf Einsichten, Auslöser und Strategien ein.")
    if not feedback_parts:
        feedback_parts.append("Sehr gut strukturiert – weiter so!")

    feedback = " ".join(feedback_parts)

    result = TrainingSession(
        user_id=payload.user_id,
        status='submitted',
        questions=[],
        answers=answers,
        score=score,
        feedback=feedback
    )
    try:
        res_id = create_document("trainingsession", result)
    except Exception:
        res_id = None

    return {"score": score, "feedback": feedback, "id": res_id}

# --- Personalized checklist endpoints ---
class ChecklistInput(BaseModel):
    user_id: str

@app.get("/api/checklist", response_model=List[dict])
def get_checklist(user_id: str):
    try:
        items = get_documents("checklistitem", {"user_id": user_id}, limit=100)
        # convert ObjectId to str
        for it in items:
            _id = it.get("_id")
            if _id is not None:
                it["id"] = str(_id)
                del it["_id"]
        return items
    except Exception:
        # Fallback demo list when DB unavailable
        return [
            {"id": "1", "title": "Führungszeugnis prüfen", "completed": False},
            {"id": "2", "title": "Abstinenznachweise sammeln", "completed": False},
            {"id": "3", "title": "Probeinterview durchführen", "completed": False},
        ]

class ChecklistCreate(BaseModel):
    user_id: str
    title: str

@app.post("/api/checklist")
def add_checklist_item(payload: ChecklistCreate):
    item = ChecklistItem(user_id=payload.user_id, title=payload.title, completed=False)
    try:
        item_id = create_document("checklistitem", item)
    except Exception:
        item_id = None
    return {"id": item_id, "title": item.title, "completed": item.completed}

# --- Schema exposure for admin tooling ---
@app.get("/schema")
def get_schema():
    return {
        "mpuuser": MpuUser.model_json_schema(),
        "trainingsession": TrainingSession.model_json_schema(),
        "checklistitem": ChecklistItem.model_json_schema(),
        "analysisreport": AnalysisReport.model_json_schema(),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
