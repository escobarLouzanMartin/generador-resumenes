import os
import re
from collections import defaultdict

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

from models import db, User, Auction, Purchase, ahora

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-local-desarrollo")

# ── Base de datos ──────────────────────────────────────────────
db_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("RENDER", False)
db.init_app(app)

# ── Seguridad: headers HTTP ────────────────────────────────────
EN_PRODUCCION = bool(os.environ.get("RENDER"))
Talisman(
    app,
    force_https=EN_PRODUCCION,
    strict_transport_security=EN_PRODUCCION,
    content_security_policy=False,  # CSP separado si se necesita
    frame_options="DENY",
    referrer_policy="strict-origin-when-cross-origin",
)

# ── Rate limiting ──────────────────────────────────────────────
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["300 per hour"],
    storage_uri="memory://",
)

# ── Login ───────────────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_message = None


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for("landing"))


with app.app_context():
    db.create_all()


@app.template_filter("precio")
def formato_precio(valor):
    return "$" + f"{valor:,.0f}".replace(",", ".")


# ── Validación de contraseña ───────────────────────────────────
def validar_password(password):
    errores = []
    if len(password) < 8:
        errores.append("Debe tener al menos 8 caracteres.")
    if not re.search(r"[A-Za-z]", password):
        errores.append("Debe incluir al menos una letra.")
    if not re.search(r"[0-9]", password):
        errores.append("Debe incluir al menos un número.")
    return errores


# ── Helpers ────────────────────────────────────────────────────
def get_subasta_actual():
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


# ── Landing ────────────────────────────────────────────────────
@app.route("/landing")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("landing.html")


# ── Auth ───────────────────────────────────────────────────────
@app.route("/registro", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def registro():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirmar = request.form.get("confirmar", "")

        if not username or not password or not email:
            flash("Completá todos los campos.")
            return render_template("registro.html")

        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            flash("El email no es válido.")
            return render_template("registro.html")

        if len(username) < 3 or len(username) > 32:
            flash("El nombre de usuario debe tener entre 3 y 32 caracteres.")
            return render_template("registro.html")

        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", username):
            flash("El usuario solo puede contener letras, números, _, - y .")
            return render_template("registro.html")

        errores_pw = validar_password(password)
        if errores_pw:
            for e in errores_pw:
                flash(e)
            return render_template("registro.html")

        if password != confirmar:
            flash("Las contraseñas no coinciden.")
            return render_template("registro.html")

        if User.query.filter_by(username=username).first():
            flash("Ese usuario ya existe.")
            return render_template("registro.html")

        if User.query.filter_by(email=email).first():
            flash("Ese email ya está registrado.")
            return render_template("registro.html")

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("index"))

    return render_template("registro.html")


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    usernames = [u.username for u in User.query.order_by(User.username).all()]

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        # Siempre tomamos el mismo tiempo para no filtrar si el usuario existe
        if user is None or not user.check_password(password):
            flash("Usuario o contraseña incorrectos.")
            return render_template("login.html", usernames=usernames)

        login_user(user)
        return redirect(url_for("index"))

    return render_template("login.html", usernames=usernames)


@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    if request.method == "POST":
        alias = request.form.get("alias", "").strip()[:80]
        current_user.alias = alias if alias else None
        db.session.commit()
        flash("Perfil actualizado.")
    return render_template("perfil.html", activo="perfil")


@app.route("/api/mi-alias")
@login_required
def mi_alias():
    return jsonify({"alias": current_user.alias or current_user.username})


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/fecha-pago", methods=["POST"])
@login_required
def guardar_fecha_pago():
    data = request.get_json()
    fecha = data.get("fecha_pago", "").strip()
    subasta = get_subasta_actual()
    subasta.fecha_pago = fecha if fecha else None
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/historial/<int:subasta_id>/fecha-pago", methods=["POST"])
@login_required
def guardar_fecha_pago_historial(subasta_id):
    subasta = Auction.query.filter_by(id=subasta_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    fecha = data.get("fecha_pago", "").strip()
    subasta.fecha_pago = fecha if fecha else None
    db.session.commit()
    return jsonify({"ok": True})


# ── Página principal ────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    subasta = get_subasta_actual()
    return render_template("index.html", subasta=subasta, activo="actual")


# ── Compras de la subasta actual ────────────────────────────────
@app.route("/agregar", methods=["POST"])
@login_required
@limiter.limit("200 per hour")
def agregar():
    data = request.get_json()
    comprador = data.get("comprador", "").strip()[:100]
    contacto = data.get("contacto", "").strip()[:50]
    carta = data.get("carta", "").strip()[:200]
    precio = data.get("precio", "").strip()

    if not comprador or not carta or not precio:
        return jsonify({"error": "Faltan datos"}), 400

    try:
        precio_num = float(precio.replace(".", "").replace(",", "."))
    except ValueError:
        return jsonify({"error": "Precio inválido"}), 400

    if precio_num < 0:
        return jsonify({"error": "El precio no puede ser negativo"}), 400

    if precio_num > 100_000_000:
        return jsonify({"error": "Precio demasiado alto"}), 400

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


# ── Autocompletado global ──────────────────────────────────────
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


# ── Edición de subastas cerradas ────────────────────────────────
@app.route("/historial/<int:subasta_id>/agregar", methods=["POST"])
@login_required
@limiter.limit("200 per hour")
def historial_agregar(subasta_id):
    subasta = Auction.query.filter_by(id=subasta_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    comprador = data.get("comprador", "").strip()[:100]
    contacto = data.get("contacto", "").strip()[:50]
    carta = data.get("carta", "").strip()[:200]
    precio = data.get("precio", "").strip()

    if not comprador or not carta or not precio:
        return jsonify({"error": "Faltan datos"}), 400

    try:
        precio_num = float(precio.replace(".", "").replace(",", "."))
    except ValueError:
        return jsonify({"error": "Precio inválido"}), 400

    if precio_num < 0:
        return jsonify({"error": "El precio no puede ser negativo"}), 400

    compra = Purchase(
        auction_id=subasta.id,
        comprador=comprador,
        contacto=contacto,
        carta=carta,
        precio=precio_num,
    )
    db.session.add(compra)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/historial/<int:subasta_id>/actualizar/<int:compra_id>", methods=["POST"])
@login_required
def historial_actualizar(subasta_id, compra_id):
    subasta = Auction.query.filter_by(id=subasta_id, user_id=current_user.id).first_or_404()
    compra = Purchase.query.filter_by(id=compra_id, auction_id=subasta.id).first_or_404()

    data = request.get_json()
    comprador = data.get("comprador", "").strip()[:100]
    contacto  = data.get("contacto", "").strip()[:50]
    carta     = data.get("carta", "").strip()[:200]
    precio    = data.get("precio", "").strip()

    if not comprador or not carta or not precio:
        return jsonify({"error": "Faltan datos"}), 400

    try:
        precio_num = float(precio.replace(".", "").replace(",", "."))
    except ValueError:
        return jsonify({"error": "Precio inválido"}), 400

    if precio_num < 0:
        return jsonify({"error": "El precio no puede ser negativo"}), 400

    compra.comprador = comprador
    compra.contacto  = contacto
    compra.carta     = carta
    compra.precio    = precio_num
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


# ── Sección compradores ────────────────────────────────────────
@app.route("/compradores_lista")
@login_required
def compradores_lista():
    subastas = Auction.query.filter_by(user_id=current_user.id).all()
    datos = {}

    for s in subastas:
        for c in s.compras:
            if c.comprador not in datos:
                datos[c.comprador] = {
                    "contacto": c.contacto or "",
                    "subastas": set(),
                    "total": 0.0,
                    "compras": 0,
                }
            d = datos[c.comprador]
            if c.contacto and not d["contacto"]:
                d["contacto"] = c.contacto
            d["subastas"].add(s.numero)
            d["total"] += c.precio
            d["compras"] += 1

    resultado = sorted([
        {
            "nombre": n,
            "contacto": d["contacto"],
            "subastas": sorted(d["subastas"]),
            "total": d["total"],
            "compras": d["compras"],
        }
        for n, d in datos.items()
    ], key=lambda x: x["nombre"].lower())

    return render_template("compradores.html", compradores=resultado, activo="compradores")


@app.route("/compradores/<nombre>/editar", methods=["POST"])
@login_required
def editar_comprador(nombre):
    data = request.get_json()
    nuevo_nombre = data.get("nombre", "").strip()[:100]
    nuevo_contacto = data.get("contacto", "").strip()[:50]

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
        c.contacto = nuevo_contacto

    db.session.commit()
    return jsonify({"ok": True})


@app.route("/compradores/<nombre>/eliminar", methods=["POST"])
@login_required
def eliminar_comprador(nombre):
    compras = (
        db.session.query(Purchase)
        .join(Auction)
        .filter(
            Auction.user_id == current_user.id,
            Purchase.comprador == nombre
        )
        .all()
    )

    if not compras:
        return jsonify({"error": "Comprador no encontrado"}), 404

    for compra in compras:
        db.session.delete(compra)

    db.session.commit()
    return jsonify({"ok": True})


@app.route("/historial/<int:subasta_id>/eliminar_subasta", methods=["POST"])
@login_required
def eliminar_subasta(subasta_id):
    subasta = Auction.query.filter_by(id=subasta_id, user_id=current_user.id).first_or_404()
    db.session.delete(subasta)
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
        agrupado.setdefault(c.comprador, []).append({
            "carta": c.carta,
            "precio": c.precio,
        })
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
        "historial_detalle.html",
        subasta=subasta,
        resumenes=resumenes_subasta,
        activo="historial",
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
    promedio_por_subasta = (
        total_generado / cantidad_subastas if cantidad_subastas else 0
    )

    gasto_por_comprador = defaultdict(float)
    subastas_por_comprador = defaultdict(set)

    for s in subastas_cerradas:
        for c in s.compras:
            gasto_por_comprador[c.comprador] += c.precio
            subastas_por_comprador[c.comprador].add(s.id)

    top_por_gasto = sorted(
        gasto_por_comprador.items(), key=lambda x: x[1], reverse=True
    )[:5]

    top_por_frecuencia = sorted(
        subastas_por_comprador.items(), key=lambda x: len(x[1]), reverse=True
    )[:5]

    evolucion = [
        {
            "numero": s.numero,
            "fecha": (
                s.fecha_cierre.isoformat()
                if s.fecha_cierre
                else s.fecha_inicio.isoformat()
            ),
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
