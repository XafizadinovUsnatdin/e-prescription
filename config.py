import os

class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///e_prescription.db'  # SQLite URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.urandom(24)
