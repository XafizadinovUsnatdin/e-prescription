from flask import Flask, request, render_template, redirect, url_for, flash, send_file, session
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import pandas as pd
import pickle
import uuid
import qrcode
import io
from datetime import datetime
import os
import requests
import urllib.parse
import time
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///eprescription.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Load CSV and model
df = pd.read_csv("diseases.csv", encoding='utf-8')
with open('medication_model.pkl', 'rb') as f:
    model = pickle.load(f)

# Expanded mock pharmacy data
PHARMACIES = [
    {
        "name": "Oson Apteka Chilanzar",
        "address": "Tashkent, Chilanzar",
        "regionId": 21,
        "distance": 5.2,
        "medications": ["Metformin", "Paracetamol", "Парастамик", "Beromed"],
        "price": 15000
    },
    {
        "name": "Samarqand Apteka",
        "address": "Samarkand, Center",
        "regionId": 22,
        "distance": 10.0,
        "medications": ["Paracetamol", "Beromed", "Metformin"],
        "price": 18000
    },
    {
        "name": "Buxoro Apteka",
        "address": "Bukhara, Center",
        "regionId": 23,
        "distance": 15.0,
        "medications": ["Парастамик", "Metformin"],
        "price": 17000
    },
    {
        "name": "Andijon Apteka",
        "address": "Andijan, Center",
        "regionId": 24,
        "distance": 12.0,
        "medications": ["Metformin", "Beromed"],
        "price": 20000
    }
]


# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # doctor or admin
    rating = db.Column(db.Float, default=0.0)  # AI-based rating


class Prescription(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    patient_id = db.Column(db.String(50), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    diagnosis = db.Column(db.String(100), nullable=False)
    symptoms = db.Column(db.Text)
    medications = db.Column(db.Text, nullable=False)
    drug_type = db.Column(db.String(50))
    duration = db.Column(db.String(50))
    usage = db.Column(db.String(100))
    info = db.Column(db.Text)
    ai_score = db.Column(db.Integer)
    correct_meds = db.Column(db.Text)
    incorrect_meds = db.Column(db.Text)
    essential_meds = db.Column(db.Text)
    non_essential_meds = db.Column(db.Text)
    confidence_scores = db.Column(db.Text)  # Per-medication confidence
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    doctor = db.relationship('User', backref='prescriptions')


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.String(36), db.ForeignKey('prescription.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    doctor = db.relationship('User', backref='comments')


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    prescription_id = db.Column(db.String(36), nullable=True)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='audit_logs')


# Create database
with app.app_context():
    db.create_all()


# Update doctor rating
def update_doctor_rating(doctor_id):
    prescriptions = Prescription.query.filter_by(doctor_id=doctor_id).all()
    if prescriptions:
        total_score = sum(p.ai_score for p in prescriptions)
        rating = total_score / len(prescriptions)
        doctor = User.query.get(doctor_id)
        doctor.rating = rating
        db.session.commit()


# Fetch pharmacy data from API
def fetch_pharmacy_data(medication):
    url = "https://osonapteka.uz/api/web/Product/Search"
    payload = {
        "pageSize": 20,
        "page": 1,
        "searchText": medication,
        "showOnlyExistonStore": True
    }
    headers = {'Content-Type': 'application/json'}
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=5, verify=False)
            response.raise_for_status()
            raw_data = response.json()
            print(f"API raw response for {medication}: {json.dumps(raw_data, ensure_ascii=False)}")
            data = raw_data.get('data', []) if isinstance(raw_data, dict) else []
            print(f"API success for {medication}: {len(data)} results")
            return data
        except requests.RequestException as e:
            print(f"API error for {medication}: {e}")
            time.sleep(1)
    # Fallback to mock data
    mock_data = [
        {
            "medication": medication,
            "pharmacy": p,
            "inStock": medication in p["medications"],
            "price": p["price"]
        } for p in PHARMACIES if medication in p["medications"]
    ]
    print(f"Using mock data for {medication}: {len(mock_data)} results")
    return mock_data


# Aggregate pharmacy data
def get_pharmacy_availability(medications):
    pharmacies = {}
    for med in medications:
        results = fetch_pharmacy_data(med)
        for result in results:
            try:
                # Handle string results (e.g., API returns list of medication names)
                if isinstance(result, str):
                    print(f"Unexpected string result for {med}: {result}")
                    # Assume string is medication name, use mock-like structure
                    for p in PHARMACIES:
                        if med in p["medications"]:
                            name = p["name"]
                            pharmacies[name] = {
                                "name": name,
                                "address": p["address"],
                                "regionId": p["regionId"],
                                "distance": p["distance"],
                                "available_meds": [med],
                                "total_price": p["price"],
                                "all_meds_available": False,
                                "link": f"https://osonapteka.uz/search?query={urllib.parse.quote(med)}"
                            }
                    continue

                # Handle dictionary results
                med_name = result.get('medication', med) if isinstance(result, dict) else med
                pharmacy_info = result.get('pharmacy', {}) if isinstance(result, dict) else {}
                name = pharmacy_info.get('name', 'Unknown Pharmacy')
                address = pharmacy_info.get('address', 'Unknown Address')
                regionId = pharmacy_info.get('regionId', 0)
                price = pharmacy_info.get('price', 999999)
                inStock = result.get('inStock', False) if isinstance(result, dict) else True

                if name not in pharmacies:
                    pharmacies[name] = {
                        "name": name,
                        "address": address,
                        "regionId": regionId,
                        "distance": pharmacy_info.get('distance', 9999),
                        "available_meds": [],
                        "total_price": 0,
                        "all_meds_available": False,
                        "link": f"https://osonapteka.uz/search?query={urllib.parse.quote(med)}"
                    }
                if inStock:
                    pharmacies[name]["available_meds"].append(med_name)
                    pharmacies[name]["total_price"] += price
            except (KeyError, TypeError) as e:
                print(f"Error parsing API result for {med}: {e}")
                continue

    # Check if all medications are available
    pharmacy_list = list(pharmacies.values())
    for p in pharmacy_list:
        p["all_meds_available"] = set(p["available_meds"]) == set(medications)
        p["distance"] = float(p["distance"]) if p["distance"] else 9999
        p["total_price"] = float(p["total_price"]) if p["total_price"] else 999999
        p["regionId"] = int(p["regionId"]) if p["regionId"] else 0

    print(f"Aggregated {len(pharmacy_list)} pharmacies: {[p['name'] for p in pharmacy_list]}")
    return pharmacy_list


# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        print(f"Register attempt: username={username}, role={role}")
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
        else:
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            user = User(username=username, password=hashed, role=role)
            db.session.add(user)
            db.session.commit()
            print(f"User registered: {username}")
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print(f"Login attempt: username={username}")
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"User found: {user.username}, role={user.role}")
            if bcrypt.checkpw(password.encode('utf-8'), user.password):
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                print(f"Session set: {session}")
                flash('Logged in successfully!', 'success')
                audit_log = AuditLog(user_id=user.id, action="Login", details=f"User {username} logged in")
                db.session.add(audit_log)
                db.session.commit()
                return redirect(url_for('dashboard'))
        flash('Invalid credentials!', 'danger')
        print("Login failed: Invalid credentials")
    return render_template('login.html')


@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    username = session.get('username')
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('role', None)
    flash('Logged out successfully!', 'success')
    audit_log = AuditLog(user_id=user_id, action="Logout", details=f"User {username} logged out")
    db.session.add(audit_log)
    db.session.commit()
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in!', 'danger')
        print("Dashboard access denied: No user_id in session")
        return redirect(url_for('login'))
    print(f"Dashboard accessed: role={session['role']}")
    audit_log = AuditLog(user_id=session['user_id'], action="Access Dashboard",
                         details=f"User accessed dashboard, role={session['role']}")
    db.session.add(audit_log)
    db.session.commit()
    if session['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('doctor_dashboard'))


@app.route('/doctor')
def doctor_dashboard():
    if 'user_id' not in session or session['role'] != 'doctor':
        flash('Access denied!', 'danger')
        print("Doctor dashboard access denied")
        return redirect(url_for('login'))
    user_id = session['user_id']
    prescriptions = Prescription.query.filter_by(doctor_id=user_id).all()
    print(f"Doctor dashboard: user_id={user_id}, prescriptions={len(prescriptions)}")
    audit_log = AuditLog(user_id=user_id, action="Access Doctor Dashboard",
                         details=f"Doctor viewed dashboard with {len(prescriptions)} prescriptions")
    db.session.add(audit_log)
    db.session.commit()
    return render_template('doctor_dashboard.html', prescriptions=prescriptions)


@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Access denied!', 'danger')
        print("Admin dashboard access denied")
        return redirect(url_for('login'))
    prescriptions = Prescription.query.all()
    doctors = User.query.filter_by(role='doctor').all()
    user_count = User.query.count()
    prescription_count = Prescription.query.count()
    comment_count = Comment.query.count()
    audit_log_count = AuditLog.query.count()
    print(f"Admin dashboard: prescriptions={len(prescriptions)}, doctors={len(doctors)}")
    audit_log = AuditLog(user_id=session['user_id'], action="Access Admin Dashboard",
                         details=f"Admin viewed dashboard with {len(prescriptions)} prescriptions")
    db.session.add(audit_log)
    db.session.commit()
    return render_template('admin_dashboard.html', prescriptions=prescriptions, doctors=doctors,
                           user_count=user_count, prescription_count=prescription_count,
                           comment_count=comment_count, audit_log_count=audit_log_count)


@app.route('/create_prescription', methods=['GET', 'POST'])
def create_prescription():
    if 'user_id' not in session or session['role'] != 'doctor':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        prescription_id = str(uuid.uuid4())
        last_prescription = Prescription.query.order_by(Prescription.patient_id.desc()).first()
        patient_id = str(int(last_prescription.patient_id) + 1) if last_prescription else '1'
        diagnosis = request.form['diagnosis']
        symptoms = request.form.get('symptoms', '')
        medications_input = request.form['medications']
        drug_type = request.form.get('drug_type', '')
        duration = request.form.get('duration', '')
        usage = request.form.get('usage', '')
        info = request.form.get('info', '')
        medications = [med.strip() for med in medications_input.split(',') if med.strip()]

        if not medications:
            flash('Kamida bitta dori kiritish kerak!', 'danger')
            return render_template('create_prescription.html')

        match = df[df['Kasallik nomi'].str.lower() == diagnosis.lower()]
        if not match.empty:
            row = match.iloc[0]
            recommended_meds = [med.strip() for med in row['Tavsiya etilgan dorilar'].split(',')]
            feature_input = f"{diagnosis} {symptoms}"

            correct_meds = []
            incorrect_meds = []
            confidence_scores = []
            confidence_dict = {}
            for med in medications:
                prediction = model.predict_proba([f"{feature_input} {med}"])[0]
                is_correct_prob = prediction[1]
                confidence_dict[med] = is_correct_prob
                if med in recommended_meds or is_correct_prob > 0.7:
                    correct_meds.append(med)
                    confidence_scores.append(is_correct_prob)
                else:
                    incorrect_meds.append(med)

            ai_score = int((len(correct_meds) / len(medications)) * 100) if medications else 0
            if confidence_scores:
                ai_score = min(ai_score, int(sum(confidence_scores) / len(confidence_scores) * 100))

            essential_meds = recommended_meds
            non_essential_meds = [med for med in medications if med not in recommended_meds]
            confidence_str = ','.join([f"{med}:{confidence_dict[med]:.2f}" for med in medications])

            prescription = Prescription(
                id=prescription_id,
                patient_id=patient_id,
                doctor_id=session['user_id'],
                diagnosis=diagnosis,
                symptoms=symptoms,
                medications=','.join(medications),
                drug_type=drug_type,
                duration=duration,
                usage=usage,
                info=info,
                ai_score=ai_score,
                correct_meds=','.join(correct_meds),
                incorrect_meds=','.join(incorrect_meds),
                essential_meds=','.join(essential_meds),
                non_essential_meds=','.join(non_essential_meds),
                confidence_scores=confidence_str
            )
            db.session.add(prescription)
            db.session.commit()
            update_doctor_rating(session['user_id'])
            audit_log = AuditLog(
                user_id=session['user_id'],
                action="Create Prescription",
                prescription_id=prescription_id,
                details=f"Prescription created for patient {patient_id}, diagnosis: {diagnosis}"
            )
            db.session.add(audit_log)
            db.session.commit()
            flash('Retsept muvaffaqiyatli yaratildi!', 'success')
            return redirect(url_for('doctor_dashboard'))
        else:
            flash('Tashxis topilmadi!', 'danger')

    return render_template('create_prescription.html')


@app.route('/prescriptions')
def view_prescriptions():
    if 'user_id' not in session or session['role'] != 'doctor':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    prescriptions = Prescription.query.all()
    audit_log = AuditLog(
        user_id=session['user_id'],
        action="View All Prescriptions",
        details=f"User viewed all prescriptions, total: {len(prescriptions)}"
    )
    db.session.add(audit_log)
    db.session.commit()
    return render_template('view_prescriptions.html', prescriptions=prescriptions)


@app.route('/prescription/<id>', methods=['GET', 'POST'])
def prescription_details(id):
    prescription = Prescription.query.get_or_404(id)
    comments = Comment.query.filter_by(prescription_id=id).all()

    if request.method == 'POST' and 'user_id' in session and session['role'] == 'doctor':
        text = request.form['comment']
        comment = Comment(prescription_id=id, doctor_id=session['user_id'], text=text)
        db.session.add(comment)
        db.session.commit()
        audit_log = AuditLog(
            user_id=session['user_id'],
            action="Add Comment",
            prescription_id=id,
            details=f"Comment added to prescription {id}: {text[:50]}..."
        )
        db.session.add(audit_log)
        db.session.commit()
        flash('Izoh qo\'shildi!', 'success')
        return redirect(url_for('prescription_details', id=id))

    audit_log = AuditLog(
        user_id=session.get('user_id'),
        action="View Prescription Details",
        prescription_id=id,
        details=f"User viewed prescription {id}"
    )
    db.session.add(audit_log)
    db.session.commit()
    return render_template('prescription_details.html', prescription=prescription, comments=comments)


@app.route('/prescription/<id>/print')
def print_prescription(id):
    prescription = Prescription.query.get_or_404(id)
    audit_log = AuditLog(
        user_id=session.get('user_id'),
        action="View Print Page",
        prescription_id=id,
        details=f"User accessed print page for prescription {id}"
    )
    db.session.add(audit_log)
    db.session.commit()
    return render_template('print_prescription.html', prescription=prescription)


@app.route('/prescription/<id>/qr')
def generate_qr(id):
    prescription = Prescription.query.get_or_404(id)
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url_for('patient_view', prescription_id=id, _external=True))
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    audit_log = AuditLog(
        user_id=session.get('user_id'),
        action="Generate QR Code",
        prescription_id=id,
        details=f"QR code generated for prescription {id}"
    )
    db.session.add(audit_log)
    db.session.commit()
    return send_file(img_io, mimetype='image/png')


@app.route('/admin/audit_logs')
def view_audit_logs():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).all()
    audit_log = AuditLog(
        user_id=session['user_id'],
        action="View Audit Logs",
        details=f"Admin viewed audit logs, total: {len(logs)}"
    )
    db.session.add(audit_log)
    db.session.commit()
    return render_template('audit_logs.html', logs=logs)


@app.route('/patient/<prescription_id>')
def patient_view(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    medications = prescription.medications.split(',')
    pharmacies = get_pharmacy_availability(medications)
    audit_log = AuditLog(
        user_id=None,
        action="Patient View Prescription",
        prescription_id=prescription_id,
        details=f"Patient viewed prescription {prescription_id} with {len(pharmacies)} pharmacies"
    )
    db.session.add(audit_log)
    db.session.commit()
    return render_template('patient_prescription.html', prescription=prescription, pharmacies=pharmacies)


if __name__ == '__main__':
    app.run(debug=True)