from flask import Flask, render_template, request, jsonify, session
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-local-desarrollo")

def get_compras():
    if "compras" not in session:
        session["compras"] = []
    return session["compras"]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/agregar", methods=["POST"])
def agregar():
    data = request.get_json()
    comprador = data.get("comprador", "").strip()
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

    compras = get_compras()
    compras.append({
        "comprador": comprador,
        "carta": carta,
        "precio": precio_num
    })
    session["compras"] = compras
    session.modified = True

    return jsonify({"ok": True, "total_compras": len(compras)})

@app.route("/compras", methods=["GET"])
def listar_compras():
    return jsonify(get_compras())

@app.route("/resumenes", methods=["GET"])
def resumenes():
    compras = get_compras()
    agrupado = {}
    for c in compras:
        nombre = c["comprador"]
        if nombre not in agrupado:
            agrupado[nombre] = []
        agrupado[nombre].append({"carta": c["carta"], "precio": c["precio"]})

    resultado = []
    for nombre in sorted(agrupado.keys()):
        items = agrupado[nombre]
        total = sum(i["precio"] for i in items)
        resultado.append({
            "comprador": nombre,
            "items": items,
            "total": total
        })

    return jsonify(resultado)

@app.route("/limpiar", methods=["POST"])
def limpiar():
    session["compras"] = []
    session.modified = True
    return jsonify({"ok": True})

@app.route("/eliminar", methods=["POST"])
def eliminar():
    data = request.get_json()
    idx = data.get("index")
    compras = get_compras()
    if idx is None or idx < 0 or idx >= len(compras):
        return jsonify({"error": "Índice inválido"}), 400
    compras.pop(idx)
    session["compras"] = compras
    session.modified = True
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True)
