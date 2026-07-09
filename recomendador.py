# -*- coding: utf-8 -*-
# ============================================================================
# Universidad Politecnica de Victoria - Proyecto ITIENDITA (Unidad 2)
# Modulo RECOMENDADOR DE PC BUILDS (basado en reglas + indice de rendimiento)
#
# Dos modos:
#   1) Por uso: resolucion (1080p/1440p/4K) x exigencia del juego
#      (indie / esports / aaa / aaa_rt). Un indie en 4K != un AAA en 4K.
#   2) Por juegos: el usuario marca los juegos que quiere jugar y se arma la
#      PC minima que los corre a la resolucion elegida.
#
# INTEGRACION EN app.py (2 lineas):
#   from recomendador import recomendador_bp
#   app.register_blueprint(recomendador_bp)
# ============================================================================

import os
from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for
from pymongo import MongoClient
from bson import ObjectId

client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))
db = client["ITIendita"]
productos = db["productos"]
juegos = db["juegos"]
usuarios = db["usuarios"]
laptops_col = db["productos"]  # las laptops viven en productos (tipo="laptop")

recomendador_bp = Blueprint("recomendador", __name__)

# --- Parametros -------------------------------------------------------------
TIPOS_BUILD = ["gpu", "cpu", "tarjeta_madre", "ram", "almacenamiento", "fuente", "gabinete"]
OVERHEAD_WATTS = 80
MARGEN_FUENTE = 1.3
JERARQUIA_FF = {"ATX": 3, "mATX": 2, "mITX": 1}

# Cuanta mas GPU se necesita al subir la resolucion (respecto a 1080p).
RES_MULT_GPU = {"1080p": 1.0, "1440p": 1.5, "4K": 2.3}

# Presets del "modo por uso": exigencia -> (base_gpu, base_cpu) a 1080p.
EXIGENCIA = {
    "indie":   (15, 28),   # juegos indie / ligeros
    "esports": (32, 65),   # competitivos, prioriza CPU (muchos fps)
    "aaa":     (52, 56),   # AAA bien optimizados
    "aaa_rt":  (68, 62),   # AAA exigentes con ray tracing
}
ETIQ_EXIGENCIA = {
    "indie": "Indies / juegos ligeros", "esports": "Competitivos / eSports",
    "aaa": "AAA", "aaa_rt": "AAA exigentes (Ray Tracing)",
}
ETIQ_CAT_JUEGO = {
    "indie": "Indies / Ligeros", "esports": "Competitivos / eSports",
    "aaa": "AAA", "aaa_rt": "AAA exigentes (Ray Tracing)",
}
PERFILES_USO = {
    "oficina":     (10, 40, 16),   # home office / ofimatica: GPU minima, CPU modesto
    "escuela":     (8, 35, 16),    # estudio / clases
    "programacion":(12, 55, 32),   # desarrollo: mas CPU y RAM
    "edicion":     (60, 70, 32),   # edicion/diseno/video: CPU+GPU fuertes, 32GB
}
ETIQ_PERFIL = {"oficina": "Home office / Oficina", "escuela": "Escuela / Estudio",
               "programacion": "Programacion / Desarrollo", "edicion": "Edicion / Diseno"}
ETIQ_USO_LAPTOP = {"oficina": "oficina", "escuela": "escuela", "programacion": "programacion",
                   "edicion": "edicion", "gaming": "gaming", "general": "uso general"}

ETIQUETAS = {"cpu": "Procesador", "tarjeta_madre": "Tarjeta madre", "ram": "Memoria RAM",
             "gpu": "Tarjeta grafica", "almacenamiento": "Almacenamiento",
             "fuente": "Fuente de poder", "gabinete": "Gabinete"}

# ============================================================================
# LOGICA PURA (sin Flask ni Mongo -> testeable)
# ============================================================================

def _por_tipo(comps, tipo):
    return [c for c in comps if c.get("tipo") == tipo and c.get("stock", 0) > 0]

def _rend(c):
    return c["specs"].get("rendimiento", 0)

def _mas_barato_que_cumple(items, req):
    """El mas barato con rendimiento >= req; si ninguno alcanza, el de mayor rendimiento."""
    if not items:
        return None
    validos = [i for i in items if _rend(i) >= req]
    return min(validos, key=lambda i: i["precio_actual"]) if validos \
        else max(items, key=_rend)

def consumo_total(build):
    piezas = [build.get(k) for k in ("cpu", "gpu", "ram", "almacenamiento")]
    return sum(p["specs"].get("consumo_watts", 0) for p in piezas if p) + OVERHEAD_WATTS

def total_build(build):
    return round(sum(p["precio_actual"] for p in build.values() if p), 2)

def completar_build(comps, cpu, gpu, cap_ram=16):
    """Dado CPU y GPU, elige placa, RAM, almacenamiento, fuente y gabinete compatibles."""
    b = {"cpu": cpu, "gpu": gpu}
    # Tarjeta madre compatible con el CPU (socket + tipo de RAM), la mas barata
    mbs = [m for m in _por_tipo(comps, "tarjeta_madre")
           if cpu and m["specs"]["socket"] == cpu["specs"]["socket"]
           and m["specs"]["tipo_ram"] == cpu["specs"]["tipo_ram"]]
    b["tarjeta_madre"] = min(mbs, key=lambda m: m["precio_actual"]) if mbs else None
    mb = b["tarjeta_madre"]
    # RAM compatible; se prefiere capacidad >= cap_ram, la mas barata
    rams = [r for r in _por_tipo(comps, "ram")
            if mb and r["specs"]["tipo_ram"] == mb["specs"]["tipo_ram"]]
    con_cap = [r for r in rams if r["specs"].get("capacidad_gb", 0) >= cap_ram]
    fuente_ram = con_cap if con_cap else rams
    b["ram"] = min(fuente_ram, key=lambda r: r["precio_actual"]) if fuente_ram else None
    # Almacenamiento: preferir >= 1TB, el mas barato
    alm = _por_tipo(comps, "almacenamiento")
    grandes = [a for a in alm if a["specs"].get("capacidad_gb", 0) >= 1000]
    fuente_alm = grandes if grandes else alm
    b["almacenamiento"] = min(fuente_alm, key=lambda a: a["precio_actual"]) if fuente_alm else None
    # Fuente: la mas barata que cubra el consumo con margen
    req_w = round(consumo_total(b) * MARGEN_FUENTE)
    psus = [p for p in _por_tipo(comps, "fuente") if p["specs"]["potencia_watts"] >= req_w]
    b["fuente"] = min(psus, key=lambda p: p["precio_actual"]) if psus else \
        max(_por_tipo(comps, "fuente"), key=lambda p: p["specs"]["potencia_watts"], default=None)
    # Gabinete: el mas barato que admita la placa y donde quepa la GPU
    req_mb = JERARQUIA_FF.get(mb["specs"].get("factor_forma"), 2) if mb else 2
    lg = gpu["specs"].get("longitud_mm", 0) if gpu else 0
    gabs = [g for g in _por_tipo(comps, "gabinete")
            if JERARQUIA_FF.get(g["specs"].get("factor_forma"), 3) >= req_mb
            and g["specs"].get("max_gpu_mm", 9999) >= lg]
    b["gabinete"] = min(gabs, key=lambda g: g["precio_actual"]) if gabs else None
    return b

def validar_compatibilidad(build):
    problemas, checks = [], []
    cpu, mb, ram = build.get("cpu"), build.get("tarjeta_madre"), build.get("ram")
    gpu, psu, gab = build.get("gpu"), build.get("fuente"), build.get("gabinete")
    if cpu and mb:
        (checks if cpu["specs"]["socket"] == mb["specs"]["socket"] else problemas).append(
            f"Socket {cpu['specs']['socket']}: CPU y tarjeta madre coinciden."
            if cpu["specs"]["socket"] == mb["specs"]["socket"]
            else f"Socket incompatible: CPU {cpu['specs']['socket']} vs placa {mb['specs']['socket']}.")
    if mb and ram:
        (checks if mb["specs"]["tipo_ram"] == ram["specs"]["tipo_ram"] else problemas).append(
            f"Memoria {ram['specs']['tipo_ram']} compatible con la placa."
            if mb["specs"]["tipo_ram"] == ram["specs"]["tipo_ram"]
            else f"RAM incompatible: {ram['specs']['tipo_ram']} vs placa {mb['specs']['tipo_ram']}.")
    if psu:
        req = round(consumo_total(build) * MARGEN_FUENTE)
        (checks if psu["specs"]["potencia_watts"] >= req else problemas).append(
            f"Fuente de {psu['specs']['potencia_watts']}W cubre el consumo ({req}W con margen)."
            if psu["specs"]["potencia_watts"] >= req
            else f"Fuente insuficiente: {psu['specs']['potencia_watts']}W < {req}W.")
    if gpu and gab:
        lg, mx = gpu["specs"].get("longitud_mm", 0), gab["specs"].get("max_gpu_mm", 9999)
        (checks if lg <= mx else problemas).append(
            f"La GPU ({lg}mm) cabe en el gabinete ({mx}mm)."
            if lg <= mx else f"La GPU no cabe: {lg}mm > {mx}mm.")
    if mb and gab:
        cap = JERARQUIA_FF.get(gab["specs"].get("factor_forma"), 3)
        req_mb = JERARQUIA_FF.get(mb["specs"].get("factor_forma"), 2)
        (checks if cap >= req_mb else problemas).append(
            f"El gabinete {gab['specs'].get('factor_forma')} admite la placa {mb['specs'].get('factor_forma')}."
            if cap >= req_mb
            else f"El gabinete {gab['specs'].get('factor_forma')} no admite placa {mb['specs'].get('factor_forma')}.")
    return (len(problemas) == 0, problemas, checks)

def armar_build(comps, req_gpu, req_cpu, presupuesto=None, aprovechar=False, cap_ram=16):
    """Arma la PC mas barata que cumple req_gpu/req_cpu; ajusta al presupuesto si se da."""
    gpus, cpus = _por_tipo(comps, "gpu"), _por_tipo(comps, "cpu")
    gpu = _mas_barato_que_cumple(gpus, req_gpu)
    cpu = _mas_barato_que_cumple(cpus, req_cpu)
    build = completar_build(comps, cpu, gpu, cap_ram)
    avisos = []

    if presupuesto:
        # Si excede, baja GPU (y luego CPU) al escalon mas barato hasta entrar
        guard = 0
        while total_build(build) > presupuesto and guard < 20:
            guard += 1
            g_baratas = [g for g in gpus if g["precio_actual"] < build["gpu"]["precio_actual"]]
            c_baratas = [c for c in cpus if c["precio_actual"] < build["cpu"]["precio_actual"]]
            if g_baratas:
                build = completar_build(comps, build["cpu"], max(g_baratas, key=lambda g: g["precio_actual"]), cap_ram)
            elif c_baratas:
                build = completar_build(comps, max(c_baratas, key=lambda c: c["precio_actual"]), build["gpu"], cap_ram)
            else:
                break
        if total_build(build) > presupuesto:
            avisos.append("Con ese presupuesto no se alcanza el objetivo; esta es la configuracion mas cercana.")
        elif _rend(build["gpu"]) < req_gpu or _rend(build["cpu"]) < req_cpu:
            avisos.append("Para entrar en el presupuesto se bajo el rendimiento; algunos juegos podrian no ir al maximo.")

        # Si sobra presupuesto (modo por uso), sube la GPU aprovechando el dinero
        if aprovechar:
            for g in sorted(gpus, key=lambda g: g["precio_actual"]):
                if _rend(g) >= req_gpu and g["precio_actual"] > build["gpu"]["precio_actual"]:
                    tent = completar_build(comps, build["cpu"], g, cap_ram)
                    if total_build(tent) <= presupuesto:
                        build = tent

    return build, avisos

def _mult_fps_gpu(fps):
    # 60fps = base; mas fps exige mas GPU (120->x2.0, 144->x2.4, 240->x4.0)
    return max(1.0, fps / 60.0)

def _mult_fps_cpu(fps):
    # el CPU pesa mas en altas tasas de fps (120->x1.25, 144->x1.35, 240->x1.75)
    return max(1.0, 1.0 + (fps - 60) / 240.0)

def req_por_escenario(exigencia, resolucion, fps=60):
    base_g, base_c = EXIGENCIA.get(exigencia, EXIGENCIA["aaa"])
    rg = base_g * RES_MULT_GPU.get(resolucion, 1.5) * _mult_fps_gpu(fps)
    rc = base_c * _mult_fps_cpu(fps)
    return round(rg), round(rc)

def req_por_juegos(juegos_sel, resolucion, fps=60):
    """Requerimiento = el mas exigente de los juegos elegidos."""
    if not juegos_sel:
        return 0, 0, 16
    mult = RES_MULT_GPU.get(resolucion, 1.5) * _mult_fps_gpu(fps)
    req_gpu = max(j["base_gpu"] * mult for j in juegos_sel)
    req_cpu = max(j["base_cpu"] * _mult_fps_cpu(fps) for j in juegos_sel)
    cap = 32 if (resolucion == "4K" or any(j["categoria"] in ("aaa", "aaa_rt") for j in juegos_sel)) else 16
    return round(req_gpu), round(req_cpu), cap

def req_por_perfil(perfil):
    """Requerimiento (req_gpu, req_cpu, cap_ram) para un uso NO gaming."""
    return PERFILES_USO.get(perfil, PERFILES_USO["oficina"])

def recomendar_laptops(laptops, uso, presupuesto=None, n=3):
    """Devuelve hasta n laptops que sirven para el uso, dentro del presupuesto si se da."""
    cand = [l for l in laptops if uso in l["specs"].get("usos", []) and l.get("stock", 0) > 0]
    if not cand:
        cand = [l for l in laptops if l.get("stock", 0) > 0]
    aviso = None
    if presupuesto:
        dentro = [l for l in cand if l["precio_actual"] <= presupuesto]
        if dentro:
            cand = dentro
        else:
            aviso = "Ninguna laptop para ese uso entra en el presupuesto; te muestro las mas economicas."
    cand = sorted(cand, key=lambda l: l["precio_actual"])
    return cand[:n], aviso

def estado_juego(build, juego, resolucion):
    """Como corre un juego con el build final a esa resolucion."""
    rg = juego["base_gpu"] * RES_MULT_GPU.get(resolucion, 1.5)
    rc = juego["base_cpu"]
    ratio = min(_rend(build["gpu"]) / rg if rg else 9, _rend(build["cpu"]) / rc if rc else 9)
    if ratio >= 1.0:
        return juego["nombre"], "Optimo", "opt"
    if ratio >= 0.8:
        return juego["nombre"], "Jugable (ajustando graficos)", "med"
    return juego["nombre"], "No recomendado", "bad"

def empaquetar(build, presupuesto, resolucion, modo, avisos, objetivo, estados=None, fps=None):
    ok, problemas, checks = validar_compatibilidad(build)
    total = total_build(build)
    ids = [build[t].get("_id") for t in TIPOS_BUILD if build.get(t) and build[t].get("_id")]
    return {
        "ids": ids, "fps": fps,
        "build": build, "total": total, "presupuesto": presupuesto,
        "dentro_presupuesto": (presupuesto is None) or (total <= presupuesto),
        "sin_presupuesto": presupuesto is None,
        "consumo_estimado": consumo_total(build),
        "compatible": ok, "problemas": problemas, "checks": checks,
        "avisos": avisos, "modo": modo, "resolucion": resolucion, "objetivo": objetivo,
        "estados": estados or [], "orden": TIPOS_BUILD, "etiquetas": ETIQUETAS,
    }

# ============================================================================
# RUTA FLASK
# ============================================================================

@recomendador_bp.route("/recomendador", methods=["GET", "POST"])
def recomendador():
    cart_count = len(session.get("carrito", []))
    # Catalogo de juegos agrupado por categoria para las casillas
    juegos_cat = list(juegos.find())
    for j in juegos_cat:
        j["_id"] = str(j["_id"])
    grupos = {}
    for cat, etiq in ETIQ_CAT_JUEGO.items():
        items = [j for j in juegos_cat if j.get("categoria") == cat]
        if items:
            grupos[etiq] = items

    resultado = None
    if request.method == "POST":
        modo = request.form.get("modo", "uso")
        resolucion = request.form.get("resolucion", "1440p")
        try:
            presupuesto = float(request.form.get("presupuesto") or 0) or None
        except (TypeError, ValueError):
            presupuesto = None
        try:
            fps = int(request.form.get("fps") or 60)
        except (TypeError, ValueError):
            fps = 60

        comps = list(productos.find({"tipo": {"$in": TIPOS_BUILD}}))
        for c in comps:
            c["_id"] = str(c["_id"])

        if modo == "juegos":
            ids = request.form.getlist("juegos")
            sel = [j for j in juegos_cat if j["_id"] in ids]
            if sel:
                req_gpu, req_cpu, cap = req_por_juegos(sel, resolucion, fps)
                build, avisos = armar_build(comps, req_gpu, req_cpu, presupuesto, aprovechar=False, cap_ram=cap)
                estados = [estado_juego(build, j, resolucion) for j in sel]
                objetivo = f"Correr {len(sel)} juego(s) en {resolucion} a {fps}fps"
                resultado = empaquetar(build, presupuesto, resolucion, modo, avisos, objetivo, estados, fps)
            else:
                resultado = {"error": "Selecciona al menos un juego para armar tu PC."}
        else:
            exigencia = request.form.get("exigencia", "aaa")
            req_gpu, req_cpu = req_por_escenario(exigencia, resolucion, fps)
            cap = 32 if (exigencia in ("aaa", "aaa_rt") or resolucion == "4K") else 16
            build, avisos = armar_build(comps, req_gpu, req_cpu, presupuesto,
                                        aprovechar=bool(presupuesto), cap_ram=cap)
            objetivo = f"{ETIQ_EXIGENCIA.get(exigencia, exigencia)} en {resolucion} a {fps}fps"
            resultado = empaquetar(build, presupuesto, resolucion, modo, avisos, objetivo, fps=fps)

    return render_template("recomendador.html", resultado=resultado,
                           grupos_juegos=grupos, cart_count=cart_count)


def _agregar_ids_al_carrito(ids):
    """Agrega una lista de prod_ids al carrito de la sesion. Devuelve (agregados, sin_stock)."""
    carrito = session.get("carrito", [])
    agregados, sin_stock = 0, 0
    for pid in ids:
        try:
            prod = productos.find_one({"_id": ObjectId(pid)})
        except Exception:
            continue
        if not prod or prod.get("stock", 0) <= 0:
            sin_stock += 1
            continue
        productos.update_one({"_id": ObjectId(pid)}, {"$inc": {"stock": -1}})
        for item in carrito:
            if item["prod_id"] == pid:
                item["cantidad"] += 1
                break
        else:
            carrito.append({"prod_id": pid, "cantidad": 1})
        agregados += 1
    session["carrito"] = carrito
    if "usuario" in session:
        usuarios.update_one({"username": session["usuario"]}, {"$set": {"carrito": carrito}})
    return agregados, sin_stock


@recomendador_bp.route("/recomendador/agregar-build", methods=["POST"])
def agregar_build():
    # No logueado: avisar (el chat mostrara el enlace de login)
    if "usuario_logeado" not in session:
        if request.is_json:
            return jsonify({"ok": False, "login": True,
                            "texto": "Inicia sesion para agregar los componentes al carrito."})
        return redirect(url_for("login"))

    if request.is_json:
        ids = (request.get_json(silent=True) or {}).get("ids", [])
    else:
        ids = request.form.getlist("ids")

    agregados, sin_stock = _agregar_ids_al_carrito(ids)
    cart_count = len(session.get("carrito", []))

    if request.is_json:
        texto = f"Listo, agregue {agregados} componente(s) a tu carrito." 
        if sin_stock:
            texto += f" ({sin_stock} sin stock quedaron fuera.)"
        return jsonify({"ok": True, "agregados": agregados, "sin_stock": sin_stock,
                        "cart_count": cart_count, "texto": texto})
    return redirect(url_for("mi_carrito"))
