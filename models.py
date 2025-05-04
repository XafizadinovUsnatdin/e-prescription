from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy obyekti yaratish
db = SQLAlchemy()


# Bemorlar uchun model
class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    diagnosis = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Patient {self.name}, Age: {self.age}, Diagnosis: {self.diagnosis}>"


# Shifokorlar uchun model
class Doctor(db.Model):
    __tablename__ = 'doctors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialty = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f"<Doctor {self.name}, Specialty: {self.specialty}>"


# Retseptlar uchun model
class Prescription(db.Model):
    __tablename__ = 'prescriptions'

    id = db.Column(db.Integer, primary_key=True)
    medication = db.Column(db.String(255), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)

    patient = db.relationship('Patient', backref=db.backref('prescriptions', lazy=True))
    doctor = db.relationship('Doctor', backref=db.backref('prescriptions', lazy=True))

    def __repr__(self):
        return f"<Prescription {self.medication}, Patient ID: {self.patient_id}, Doctor ID: {self.doctor_id}>"
