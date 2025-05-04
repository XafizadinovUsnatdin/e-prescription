CREATE TABLE patient (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    age INTEGER
);

CREATE TABLE doctor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE diagnosis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disease_name TEXT NOT NULL
);

CREATE TABLE medication (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE prescription (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    diagnosis_id INTEGER,
    medication_id INTEGER,
    patient_id INTEGER,
    dosage TEXT,
    date_issued DATETIME,
    FOREIGN KEY (diagnosis_id) REFERENCES diagnosis(id),
    FOREIGN KEY (medication_id) REFERENCES medication(id),
    FOREIGN KEY (patient_id) REFERENCES patient(id)
);
