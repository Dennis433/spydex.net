from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(64))
    country = db.Column(db.String(64))
    city = db.Column(db.String(64))
    device = db.Column(db.String(128))
    browser = db.Column(db.String(128))
    page = db.Column(db.String(256))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(64), unique=True)
    country = db.Column(db.String(64))
    city = db.Column(db.String(64))
    device = db.Column(db.String(128))
    browser = db.Column(db.String(128))
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    visit_count = db.Column(db.Integer, default=1)