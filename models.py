from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def ahora():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    creado = db.Column(db.DateTime, default=ahora)

    subastas = db.relationship(
        "Auction", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Auction(db.Model):
    __tablename__ = "auctions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    numero = db.Column(db.Integer, nullable=False)  # nº de subasta correlativo por usuario
    fecha_inicio = db.Column(db.DateTime, default=ahora)
    fecha_cierre = db.Column(db.DateTime, nullable=True)
    abierta = db.Column(db.Boolean, default=True, nullable=False, index=True)

    compras = db.relationship(
        "Purchase", backref="auction", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def total(self):
        return sum(c.precio for c in self.compras)

    @property
    def compradores_unicos(self):
        return len({c.comprador for c in self.compras})

    def to_summary_dict(self):
        return {
            "id": self.id,
            "numero": self.numero,
            "fecha_inicio": self.fecha_inicio.isoformat(),
            "fecha_cierre": self.fecha_cierre.isoformat() if self.fecha_cierre else None,
            "abierta": self.abierta,
            "total": self.total,
            "compradores": self.compradores_unicos,
            "items": len(self.compras),
        }


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(db.Integer, db.ForeignKey("auctions.id"), nullable=False, index=True)
    comprador = db.Column(db.String(120), nullable=False, index=True)
    contacto = db.Column(db.String(120), nullable=True)
    carta = db.Column(db.String(200), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    creado = db.Column(db.DateTime, default=ahora)

    def to_dict(self):
        return {
            "id": self.id,
            "comprador": self.comprador,
            "contacto": self.contacto or "",
            "carta": self.carta,
            "precio": self.precio,
        }
