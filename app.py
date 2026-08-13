import os
from collections import defaultdict

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)

from models import db, User, Auction, Purchase, ahora

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-local-desarrollo")

# ── Base de datos ──────────────────────────────────────────────
db_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
# Render entrega postgres:// pero SQLAlchemy espera postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
db.init_app(app)

# ── Login ───────────────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Iniciá sesión para continuar."


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


with app.app_context():
    db.create_all()


@app.template_filter("precio")
def formato_precio(valor):
    return "$" + f"{valor:,.0f}".replace(",", ".")


# ── Helpers ────────────────────────────────────────────────────
def get_subasta_actual():
    """Devuelve la subasta abierta del usuario, creando una si no existe."""
    subasta = Auction.query.filter_by(user_id=current_user.id, abierta=True).first()
    if subasta is None:
        ultimo_numero = (
            db.session.query(db.func.max(Auction.numero))
            .filter_by(user_id=current_user.id)
            .scalar()
            or 0
        )
        subasta = Auction(user_id=current_user.id, numero=ultimo_numero + 1)
        db.session.add(subasta)
        db.session.commit()
    return subasta


# ── Auth ───────────────────────────────────────────────────────
@app.route("/registro", methods=["GET", "POST"])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirmar = request.form.get("confirmar", "")

        if not username or not password:
            flash("Completá usuario y contraseña.")
            return render_template("registro.html")

        if password != confirmar:
            flash("Las contraseñas no coinciden.")
            return render_template("registro.html")

        if len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.")
            return render_template("registro.html")

        if User.query.filter_by(username=username).first():
            flash("Ese usuario ya existe.")
            return render_template("registro.html")

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("index"))

    return render_template("registro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    usernames = [u.username for u in User.query.order_by(User.username).all()]

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash("Usuario o contraseña incorrectos.")
            return render_template("login.html", usernames=usernames)

        login_user(user)
        return redirect(url_for("index"))

    return render_template("login.html", usernames=usernames)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ── Página principal (subasta actual) ────────────────────────────
@app.route("/")
@login_required
def index():
    subasta = get_subasta_actual()
    return render_template("index.html", subasta=subasta, activo="actual")


# ── Compras de la subasta actual ─────────────────────────────────
@app.route("/agregar", methods=["POST"])
@login_required
def agregar():
    data = request.get_json()
    comprador = data.get("comprador", "").strip()
    contacto = data.get("contacto", "").strip()
    carta = data.get("carta", "").strip()
    precio = data.get("precio", "").strip()

    if not comprador or not carta or not precio:
        return jsonify({"error": "Faltan datos"}), 400

    try:
        precio_num = float(precio.replace(".", "").replace(",", "."))
    except ValueError:
        return jsonify({"error": "Precio inválido"}), 400

    if precio_num < 0:
        return jsonify({"error": "El precio no puede ser negativo"}), 400

    subasta = get_subasta_actual()
    compra = Purchase(
        auction_id=subasta.id,
        comprador=comprador,
        contacto=contacto,
        carta=carta,
        precio=precio_num,
    )
    db.session.add(compra)
    db.session.commit()

    return jsonify({"ok": True, "total_compras": len(subasta.compras)})


@app.route("/compras", methods=["GET"])
@login_required
def listar_compras():
    subasta = get_subasta_actual()
    return jsonify([c.to_dict() for c in subasta.compras])


@app.route("/resumenes", methods=["GET"])
@login_required
def resumenes():
    subasta = get_subasta_actual()
    agrupado = {}
    contactos = {}
    for c in subasta.compras:
        agrupado.setdefault(c.comprador, []).append({"carta": c.carta, "precio": c.precio})
        if c.contacto and not contactos.get(c.comprador):
            contactos[c.comprador] = c.contacto

    resultado = []
    for nombre in sorted(agrupado.keys()):
        items = agrupado[nombre]
        total = sum(i["precio"] for i in items)
        resultado.append({
            "comprador": nombre,
            "contacto": contactos.get(nombre, ""),
            "items": items,
            "total": total,
        })

    return jsonify(resultado)


@app.route("/eliminar", methods=["POST"])
@login_required
def eliminar():
    data = request.get_json()
    idx = data.get("index")
    subasta = get_subasta_actual()
    compras = subasta.compras
    if idx is None or idx < 0 or idx >= len(compras):
        return jsonify({"error": "Índice inválido"}), 400
    db.session.delete(compras[idx])
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/limpiar", methods=["POST"])
@login_required
def limpiar():
    subasta = get_subasta_actual()
    for c in list(subasta.compras):
        db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/cerrar_subasta", methods=["POST"])
@login_required
def cerrar_subasta():
    subasta = get_subasta_actual()
    if not subasta.compras:
        return jsonify({"error": "No hay compras cargadas en esta subasta."}), 400
    subasta.abierta = False
    subasta.fecha_cierre = ahora()
    db.session.commit()
    return jsonify({"ok": True})


# ── Autocompletado global (todas las subastas del usuario) ──────
@app.route("/compradores", methods=["GET"])
@login_required
def compradores():
    compras = (
        db.session.query(Purchase)
        .join(Auction)
        .filter(Auction.user_id == current_user.id)
        .order_by(Purchase.creado.desc())
        .all()
    )
    vistos = {}
    orden = []
    for c in compras:
        if c.comprador not in vistos:
            vistos[c.comprador] = c.contacto or ""
            orden.append(c.comprador)
        elif not vistos[c.comprador] and c.contacto:
            vistos[c.comprador] = c.contacto
    return jsonify([{"comprador": n, "contacto": vistos[n]} for n in orden])


# ── Edición de subastas cerradas ─────────────────────────────
@app.route("/historial/<int:subasta_id>/agregar", methods=["POST"])
@login_required
def historial_agregar(subasta_id):
    subasta = Auction.query.filter_by(id=subasta_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    comprador = data.get("comprador", "").strip()
    contacto  = data.get("contacto", "").strip()
    carta     = data.get("carta", "").strip()
    precio    = data.get("precio", "").strip()

    if not comprador or not carta or not precio:
        return jsonify({"error": "Faltan datos"}), 400
    try:
        precio_num = float(precio.replace(".", "").replace(",", "."))
    except ValueError:
        return jsonify({"error": "Precio inválido"}), 400
    if precio_num < 0:
        return jsonify({"error": "El precio no puede ser negativo"}), 400

    compra = Purchase(auction_id=subasta.id, comprador=comprador, contacto=contacto, carta=carta, precio=precio_num)
    db.session.add(compra)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/historial/<int:subasta_id>/eliminar", methods=["POST"])
@login_required
def historial_eliminar(subasta_id):
    subasta = Auction.query.filter_by(id=subasta_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    idx = data.get("index")
    compras = subasta.compras
    if idx is None or idx < 0 or idx >= len(compras):
        return jsonify({"error": "Índice inválido"}), 400
    db.session.delete(compras[idx])
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/historial/<int:subasta_id>/compras")
@login_required
def historial_compras(subasta_id):
    subasta = Auction.query.filter_by(id=subasta_id, user_id=current_user.id).first_or_404()
    return jsonify([c.to_dict() for c in subasta.compras])


# ── Sección compradores ───────────────────────────────────────
@app.route("/compradores_lista")
@login_required
def compradores_lista():
    subastas = Auction.query.filter_by(user_id=current_user.id).all()
    datos = {}  # nombre -> {contacto, subastas: set, total, compras}
    for s in subastas:
        for c in s.compras:
            if c.comprador not in datos:
                datos[c.comprador] = {"contacto": c.contacto or "", "subastas": set(), "total": 0.0, "compras": 0}
            d = datos[c.comprador]
            if c.contacto and not d["contacto"]:
                d["contacto"] = c.contacto
            d["subastas"].add(s.numero)
            d["total"] += c.precio
            d["compras"] += 1

    resultado = sorted([
        {"nombre": n, "contacto": d["contacto"], "subastas": sorted(d["subastas"]), "total": d["total"], "compras": d["compras"]}
        for n, d in datos.items()
    ], key=lambda x: x["nombre"].lower())

    return render_template("compradores.html", compradores=resultado, activo="compradores")


@app.route("/compradores/<nombre>/editar", methods=["POST"])
@login_required
def editar_comprador(nombre):
    data = request.get_json()
    nuevo_nombre  = data.get("nombre", "").strip()
    nuevo_contacto = data.get("contacto", "").strip()

    if not nuevo_nombre:
        return jsonify({"error": "El nombre no puede estar vacío"}), 400

    compras = (
        db.session.query(Purchase)
        .join(Auction)
        .filter(Auction.user_id == current_user.id, Purchase.comprador == nombre)
        .all()
    )
    if not compras:
        return jsonify({"error": "Comprador no encontrado"}), 404

    for c in compras:
        c.comprador = nuevo_nombre
        if nuevo_contacto:
            c.contacto = nuevo_contacto
    db.session.commit()
    return jsonify({"ok": True})
@app.route("/historial")
@login_required
def historial():
    subastas = (
        Auction.query.filter_by(user_id=current_user.id, abierta=False)
        .order_by(Auction.numero.desc())
        .all()
    )
    return render_template("historial.html", subastas=subastas, activo="historial")


@app.route("/historial/<int:subasta_id>")
@login_required
def historial_detalle(subasta_id):
    subasta = Auction.query.filter_by(id=subasta_id, user_id=current_user.id).first_or_404()

    agrupado = {}
    contactos = {}
    for c in subasta.compras:
        agrupado.setdefault(c.comprador, []).append({"carta": c.carta, "precio": c.precio})
        if c.contacto and not contactos.get(c.comprador):
            contactos[c.comprador] = c.contacto

    resumenes_subasta = []
    for nombre in sorted(agrupado.keys()):
        items = agrupado[nombre]
        total = sum(i["precio"] for i in items)
        resumenes_subasta.append({
            "comprador": nombre,
            "contacto": contactos.get(nombre, ""),
            "items": items,
            "total": total,
        })

    return render_template(
        "historial_detalle.html", subasta=subasta, resumenes=resumenes_subasta, activo="historial"
    )


# ── Estadísticas ──────────────────────────────────────────────
@app.route("/estadisticas")
@login_required
def estadisticas():
    return render_template("estadisticas.html", activo="estadisticas")


@app.route("/api/estadisticas")
@login_required
def api_estadisticas():
    subastas_cerradas = (
        Auction.query.filter_by(user_id=current_user.id, abierta=False)
        .order_by(Auction.numero.asc())
        .all()
    )

    total_generado = sum(s.total for s in subastas_cerradas)
    cantidad_subastas = len(subastas_cerradas)
    promedio_por_subasta = (total_generado / cantidad_subastas) if cantidad_subastas else 0

    # Compradores más fieles: por cantidad de subastas distintas en las que compraron
    # y por monto total gastado.
    gasto_por_comprador = defaultdict(float)
    subastas_por_comprador = defaultdict(set)
    compras_por_comprador = defaultdict(int)

    for s in subastas_cerradas:
        for c in s.compras:
            gasto_por_comprador[c.comprador] += c.precio
            subastas_por_comprador[c.comprador].add(s.id)
            compras_por_comprador[c.comprador] += 1

    top_por_gasto = sorted(
        gasto_por_comprador.items(), key=lambda x: x[1], reverse=True
    )[:5]
    top_por_frecuencia = sorted(
        subastas_por_comprador.items(), key=lambda x: len(x[1]), reverse=True
    )[:5]

    evolucion = [
        {
            "numero": s.numero,
            "fecha": s.fecha_cierre.isoformat() if s.fecha_cierre else s.fecha_inicio.isoformat(),
            "total": s.total,
            "compradores": s.compradores_unicos,
        }
        for s in subastas_cerradas
    ]

    return jsonify({
        "total_generado": total_generado,
        "cantidad_subastas": cantidad_subastas,
        "promedio_por_subasta": promedio_por_subasta,
        "top_por_gasto": [{"comprador": n, "total": t} for n, t in top_por_gasto],
        "top_por_frecuencia": [
            {"comprador": n, "subastas": len(s), "gastado": gasto_por_comprador[n]}
            for n, s in top_por_frecuencia
        ],
        "evolucion": evolucion,
    })


if __name__ == "__main__":
    app.run(debug=True)
