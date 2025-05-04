from flask import Flask, request, jsonify, render_template
from models import db, Patient, Doctor, Prescription
import ai_model

app = Flask(__name__)

# Configure the database URI (using SQLite for simplicity)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///e_prescription.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database
db.init_app(app)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()  # Get input data as JSON
    diagnosis = data.get('diagnosis')  # Extract the diagnosis
    medication = ai_model.predict_medication(diagnosis)  # Call the prediction function
    return jsonify({'predicted_medication': medication})


# API to add a patient
@app.route('/add_patient', methods=['POST'])
def add_patient():
    name = request.form['name']
    age = request.form['age']
    diagnosis = request.form['diagnosis']

    # Bemor ma'lumotlarini saqlash
    new_patient = Patient(name=name, age=age, diagnosis=diagnosis)
    db.session.add(new_patient)
    db.session.commit()
    return "Patient added successfully!"


# API to add a doctor
@app.route('/add_doctor', methods=['POST'])
def add_doctor():
    name = request.form['name']
    specialty = request.form['specialty']

    # Shifokor ma'lumotlarini saqlash
    new_doctor = Doctor(name=name, specialty=specialty)
    db.session.add(new_doctor)
    db.session.commit()
    return "Doctor added successfully!"


# API to create a prescription
@app.route('/create_prescription', methods=['POST'])
def create_prescription():
    medication = request.form['medication']
    patient_id = request.form['patient_id']
    doctor_id = request.form['doctor_id']

    # Retsept ma'lumotlarini saqlash
    new_prescription = Prescription(
        medication=medication,
        patient_id=patient_id,
        doctor_id=doctor_id
    )
    db.session.add(new_prescription)
    db.session.commit()
    return "Prescription created successfully!"


if __name__ == '__main__':
    app.run(debug=True)
