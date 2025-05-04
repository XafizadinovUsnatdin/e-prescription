from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import uuid
import sqlite3  # Using SQLite for simplicity; replace with PostgreSQL in production
from datetime import datetime

app = FastAPI()


# Database setup
def init_db():
    conn = sqlite3.connect('prescriptions.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS prescriptions (
            id TEXT PRIMARY KEY,
            patient_id TEXT,
            doctor_id TEXT,
            diagnosis TEXT,
            medications TEXT,
            created_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS evaluations (
            prescription_id TEXT,
            medication TEXT,
            is_appropriate BOOLEAN,
            score INTEGER,
            FOREIGN KEY (prescription_id) REFERENCES prescriptions (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS doctor_ratings (
            doctor_id TEXT PRIMARY KEY,
            rating FLOAT
        )
    ''')
    conn.commit()
    conn.close()


init_db()


# Pydantic models
class PrescriptionCreate(BaseModel):
    patient_id: str
    diagnosis: str
    medications: List[str]
    doctor_id: str


class PrescriptionResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    diagnosis: str
    medications: List[str]
    created_at: str
    evaluation: Dict


class PharmacyCheck(BaseModel):
    medications: List[str]


# Mock AI evaluation (replace with real AI model in production)
def evaluate_prescription(diagnosis: str, medications: List[str]) -> Dict:
    # Mock rules: e.g., "Painkiller" is appropriate for "Headache" but not for "Flu"
    evaluation = {}
    for med in medications:
        if diagnosis.lower() == "headache" and med.lower() == "painkiller":
            evaluation[med] = {"is_appropriate": True, "score": 90}
        elif diagnosis.lower() == "flu" and med.lower() == "antiviral":
            evaluation[med] = {"is_appropriate": True, "score": 85}
        else:
            evaluation[med] = {"is_appropriate": False, "score": 20}
    return evaluation


# Mock pharmacy check (replace with real osonapteka.uz API or scraping)
def check_pharmacies(medications: List[str]) -> List[Dict]:
    # Mock data simulating osonapteka.uz pharmacy list
    pharmacies = [
        {"name": "Oson Apteka 1", "address": "Tashkent, Chilanzar", "medications": ["Painkiller"]},
        {"name": "Oson Apteka 2", "address": "Tashkent, Yunusabad", "medications": ["Antiviral"]}
    ]
    results = []
    for pharmacy in pharmacies:
        available_meds = [med for med in medications if med in pharmacy["medications"]]
        results.append({
            "name": pharmacy["name"],
            "address": pharmacy["address"],
            "availability": f"Available: {', '.join(available_meds)}" if available_meds else "None available"
        })
    return results


# Update doctor rating based on evaluations
def update_doctor_rating(doctor_id: str):
    conn = sqlite3.connect('prescriptions.db')
    c = conn.cursor()
    c.execute('''
        SELECT score FROM evaluations e
        JOIN prescriptions p ON e.prescription_id = p.id
        WHERE p.doctor_id = ?
    ''', (doctor_id,))
    scores = [row[0] for row in c.fetchall()]
    avg_rating = sum(scores) / len(scores) if scores else 0
    c.execute('''
        INSERT OR REPLACE INTO doctor_ratings (doctor_id, rating)
        VALUES (?, ?)
    ''', (doctor_id, avg_rating))
    conn.commit()
    conn.close()


# API endpoints
@app.post("/prescriptions", response_model=PrescriptionResponse)
async def create_prescription(prescription: PrescriptionCreate):
    prescription_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    medications_str = ','.join(prescription.medications)

    # Save to database
    conn = sqlite3.connect('prescriptions.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO prescriptions (id, patient_id, doctor_id, diagnosis, medications, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (prescription_id, prescription.patient_id, prescription.doctor_id, prescription.diagnosis, medications_str,
          created_at))

    # Evaluate prescription
    evaluation = evaluate_prescription(prescription.diagnosis, prescription.medications)
    for med, eval_data in evaluation.items():
        c.execute('''
            INSERT INTO evaluations (prescription_id, medication, is_appropriate, score)
            VALUES (?, ?, ?, ?)
        ''', (prescription_id, med, eval_data["is_appropriate"], eval_data["score"]))

    conn.commit()
    conn.close()

    # Update doctor rating
    update_doctor_rating(prescription.doctor_id)

    return {
        "id": prescription_id,
        "patient_id": prescription.patient_id,
        "doctor_id": prescription.doctor_id,
        "diagnosis": prescription.diagnosis,
        "medications": prescription.medications,
        "created_at": created_at,
        "evaluation": evaluation
    }


@app.get("/prescriptions", response_model=List[PrescriptionResponse])
async def get_prescriptions():
    conn = sqlite3.connect('prescriptions.db')
    c = conn.cursor()
    c.execute('SELECT * FROM prescriptions')
    prescriptions = c.fetchall()
    results = []
    for pres in prescriptions:
        c.execute('SELECT medication, is_appropriate, score FROM evaluations WHERE prescription_id = ?', (pres[0],))
        eval_rows = c.fetchall()
        evaluation = {row[0]: {"is_appropriate": row[1], "score": row[2]} for row in eval_rows}
        results.append({
            "id": pres[0],
            "patient_id": pres[1],
            "doctor_id": pres[2],
            "diagnosis": pres[3],
            "medications": pres[4].split(','),
            "created_at": pres[5],
            "evaluation": evaluation
        })
    conn.close()
    return results


@app.get("/prescriptions/{id}", response_model=PrescriptionResponse)
async def get_prescription(id: str):
    conn = sqlite3.connect('prescriptions.db')
    c = conn.cursor()
    c.execute('SELECT * FROM prescriptions WHERE id = ?', (id,))
    pres = c.fetchone()
    if not pres:
        raise HTTPException(status_code=404, detail="Prescription not found")
    c.execute('SELECT medication, is_appropriate, score FROM evaluations WHERE prescription_id = ?', (id,))
    eval_rows = c.fetchall()
    evaluation = {row[0]: {"is_appropriate": row[1], "score": row[2]} for row in eval_rows}
    conn.close()
    return {
        "id": pres[0],
        "patient_id": pres[1],
        "doctor_id": pres[2],
        "diagnosis": pres[3],
        "medications": pres[4].split(','),
        "created_at": pres[5],
        "evaluation": evaluation
    }


@app.post("/check-pharmacies")
async def check_pharmacies_endpoint(data: PharmacyCheck):
    return check_pharmacies(data.medications)


@app.get("/doctor-ratings")
async def get_doctor_ratings():
    conn = sqlite3.connect('prescriptions.db')
    c = conn.cursor()
    c.execute('SELECT doctor_id, rating FROM doctor_ratings')
    ratings = [{"doctor_id": row[0], "rating": row[1]} for row in c.fetchall()]
    conn.close()
    return ratings