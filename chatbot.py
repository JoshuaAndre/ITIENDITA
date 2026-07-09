# -*- coding: utf-8 -*-
# ============================================================================
# Universidad Politecnica de Victoria - Proyecto ITIENDITA (Unidad 2)
# CHATBOT DE HARDWARE (basado en reglas)
#
# Responde dudas de hardware usando la coleccion "productos" y la logica del
# recomendador: precios, socket, compatibilidad, fuente/consumo, si una GPU
# cabe en un gabinete, y arma builds por juego o presupuesto.
#
# INTEGRACION EN app.py (2 lineas):
#   from chatbot import chatbot_bp
#   app.register_blueprint(chatbot_bp)
# ============================================================================

import re
import unicodedata
import os
from flask import Blueprint, render_template, request, jsonify, session
from pymongo import MongoClient

import recomendador as R  # reutiliza la logica del recomendador

client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))
db = client["ITIendita"]
productos = db["productos"]
juegos = db["juegos"]

chatbot_bp = Blueprint("chatbot", __name__)

# --- utilidades de texto ----------------------------------------------------
def _norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.lower()

def _tokens_modelo(nombre):
    toks = re.findall(r"[a-z0-9]+", _norm(nombre))
    return set(t for t in toks if (any(c.isdigit() for c in t) and len(t) >= 3) or len(t) >= 4)

def _detectar_productos(msg, comps):
    """Empareja componentes cuyo token de modelo (ej. '5070', '9700x', 'b650') aparezca en el mensaje."""
    m = set(re.findall(r"[a-z0-9]+", _norm(msg)))
    hits = []
    for c in comps:
        toks = _tokens_modelo(c["nombre"])
        digit = set(t for t in toks if any(ch.isdigit() for ch in t))
        clave = digit if digit else toks
        if clave & m:
            hits.append(c)
    return hits

def _detectar_juegos(msg, juegos_cat):
    n = _norm(msg)
    return [j for j in juegos_cat
            if any(len(w) >= 4 and w in n for w in _norm(j["nombre"]).split())]

def _detectar_resolucion(msg):
    n = _norm(msg)
    if "4k" in n or "2160" in n: return "4K"
    if "1440" in n or "2k" in n: return "1440p"
    if "1080" in n or "full hd" in n or "fullhd" in n: return "1080p"
    return None

def _detectar_exigencia(msg):
    n = _norm(msg)
    if "ray tracing" in n or "raytracing" in n or " rt" in n or "exigente" in n: return "aaa_rt"
    if "esport" in n or "competitiv" in n: return "esports"
    if "indie" in n or "ligero" in n: return "indie"
    if "aaa" in n: return "aaa"
    return None

def _detectar_fps(msg):
    n = _norm(msg)
    m = re.search(r"(\d{2,3})\s*fps", n)
    if m:
        return int(m.group(1))
    return None

SINONIMOS_USO = {
    "edicion":     ["editar", "edicion", "video", "diseno", "render", "photoshop", "premiere",
                     "creador", "creacion de contenido", "modelado 3d"],
    "programacion":["programar", "programacion", "codigo", "desarrollo", "developer", "code",
                    "compilar", "software"],
    "escuela":     ["escuela", "estudiar", "estudio", "clases", "universidad", "tareas",
                    "escolar", "estudiante", "colegio"],
    "oficina":     ["home office", "homeoffice", "oficina", "trabajar", "trabajo", "ofimatica",
                    "office", "documentos", "excel", "ver videos", "navegar", "netflix"],
}

def _detectar_perfil_uso(msg):
    n = _norm(msg)
    # prioridad: edicion > programacion > escuela > oficina (mas exigente primero)
    for perfil in ("edicion", "programacion", "escuela", "oficina"):
        if any(k in n for k in SINONIMOS_USO[perfil]):
            return perfil
    return None

def _es_laptop(msg):
    n = _norm(msg)
    return bool(re.search(r"\b(laptop|portatil|notebook|lap top)\b", n))

def _es_gaming(msg, jgs):
    n = _norm(msg)
    return bool(jgs) or bool(re.search(r"(jugar|gaming|gamer|videojuego|juegos)", n))

def _detectar_presupuesto(msg):
    n = _norm(msg).replace(",", "")
    m = re.search(r"(\d{1,3})\s*(k|mil)\b", n)
    if m:
        v = float(m.group(1)) * 1000
        return v if v >= 8000 else None
    m = re.search(r"\b(\d{4,6})\b", n)
    if m:
        v = float(m.group(1))
        return v if v >= 8000 else None
    return None

def _tipo_en_msg(msg):
    n = _norm(msg)
    mapa = [("gpu", ["gpu", "grafica", "video", "tarjeta de video"]),
            ("cpu", ["cpu", "procesador"]),
            ("tarjeta_madre", ["tarjeta madre", "motherboard", "placa", "board"]),
            ("ram", ["ram", "memoria"]),
            ("fuente", ["fuente", "psu", "poder"]),
            ("almacenamiento", ["ssd", "almacenamiento", "disco", "nvme"]),
            ("gabinete", ["gabinete", "case", "chasis"])]
    for tipo, claves in mapa:
        if any(k in n for k in claves): return tipo
    return None

def _precio(c): return f"${c['precio_actual']:,.2f}"

def _build_items(build):
    return [{"cat": R.ETIQUETAS[t], "nombre": build[t]["nombre"], "precio": _precio(build[t])}
            for t in R.TIPOS_BUILD if build.get(t)]

# --- motor de respuestas (logica pura) -------------------------------------
def responder(msg, comps, juegos_cat):
    n = _norm(msg)
    prods = _detectar_productos(msg, comps)
    jgs = _detectar_juegos(msg, juegos_cat)
    res = _detectar_resolucion(msg)
    exi = _detectar_exigencia(msg)
    presu = _detectar_presupuesto(msg)
    fps = _detectar_fps(msg)
    tipo = _tipo_en_msg(msg)

    chips = ["Arma una PC para jugar Fortnite a 1080p 120fps",
             "Quiero una PC para home office", "Una laptop para la escuela",
             "Laptop para gaming"]

    # 1) Saludo / ayuda
    if re.search(r"\b(hola|buenas|hey|holi|que tal|saludos)\b", n) and len(n) < 25:
        return {"texto": "¡Hola! Soy el asistente de hardware de ITIENDITA. Puedo decirte precios, "
                "sockets, si dos piezas son compatibles, si te alcanza la fuente, o armarte una PC "
                "por juego o presupuesto. ¿Qué necesitas?", "chips": chips}
    if re.search(r"(ayuda|que puedes|que sabes|para que sirves|opciones)", n):
        return {"texto": "Puedo ayudarte con:\n• Precios de componentes\n• Socket y tipo de RAM de un CPU/placa\n"
                "• Compatibilidad entre dos piezas\n• Si una fuente alcanza para una GPU\n"
                "• Si una GPU cabe en un gabinete\n• Armar una PC por juego o por presupuesto", "chips": chips}

    # 2) Precio
    if re.search(r"(precio|cuesta|cuanto vale|cuanto cuesta|vale|cuanto es)", n) and prods:
        lineas = [f"• {c['nombre']}: {_precio(c)}" for c in prods[:4]]
        return {"texto": "Estos son los precios:\n" + "\n".join(lineas)}

    # 3) Socket
    if "socket" in n or "zocalo" in n:
        cs = [c for c in prods if c["tipo"] in ("cpu", "tarjeta_madre")]
        if cs:
            lineas = [f"• {c['nombre']}: socket {c['specs'].get('socket','?')} ({c['specs'].get('tipo_ram','?')})" for c in cs[:4]]
            return {"texto": "\n".join(lineas)}
        return {"texto": "Dime de qué CPU o tarjeta madre quieres saber el socket (ej. 'socket del Ryzen 7 9700X')."}

    # 4) ¿La GPU cabe en el gabinete?
    if re.search(r"(cabe|entra|caber)", n) and any(c["tipo"] == "gpu" for c in prods):
        gpu = next(c for c in prods if c["tipo"] == "gpu")
        gab = next((c for c in prods if c["tipo"] == "gabinete"), None)
        lg = gpu["specs"].get("longitud_mm", 0)
        if gab:
            mx = gab["specs"].get("max_gpu_mm", 9999)
            ok = lg <= mx
            return {"texto": f"La {gpu['nombre']} mide {lg}mm y el {gab['nombre']} admite hasta {mx}mm: "
                    + ("sí cabe. ✅" if ok else "no cabe. ❌")}
        gabs = [c for c in comps if c["tipo"] == "gabinete" and c["specs"].get("max_gpu_mm", 0) >= lg]
        nombres = ", ".join(sorted(set(g["nombre"] for g in gabs))[:4]) or "ninguno del catálogo"
        return {"texto": f"La {gpu['nombre']} mide {lg}mm. Gabinetes donde cabe: {nombres}."}

    # 5) Fuente / consumo
    if re.search(r"(fuente|psu|watts|consumo|alcanza|poder)", n):
        gpu = next((c for c in prods if c["tipo"] == "gpu"), None)
        cpu = next((c for c in prods if c["tipo"] == "cpu"), None)
        if gpu or cpu:
            consumo = (gpu["specs"].get("consumo_watts", 0) if gpu else 0) \
                    + (cpu["specs"].get("consumo_watts", 65) if cpu else 65) + 40 + R.OVERHEAD_WATTS
            req = round(consumo * R.MARGEN_FUENTE)
            base = gpu["nombre"] if gpu else cpu["nombre"]
            watts_msg = re.search(r"(\d{3,4})\s*w", n)
            if watts_msg:
                tengo = int(watts_msg.group(1))
                ok = tengo >= req
                return {"texto": f"Con una {base}, el consumo estimado del sistema es ~{consumo}W, así que "
                        f"conviene una fuente de al menos {req}W. Tu fuente de {tengo}W "
                        + ("sí alcanza. ✅" if ok else "se queda corta. ❌")}
            psus = [p for p in comps if p["tipo"] == "fuente" and p["specs"]["potencia_watts"] >= req]
            sug = min(psus, key=lambda p: p["precio_actual"]) if psus else None
            extra = f" Te sugiero: {sug['nombre']} ({_precio(sug)})." if sug else ""
            return {"texto": f"Con una {base}, el consumo estimado es ~{consumo}W; necesitas una fuente de "
                    f"al menos ~{req}W (30% de margen).{extra}"}
        return {"texto": "Dime qué GPU (y opcionalmente qué CPU) vas a usar y calculo la fuente que necesitas."}

    # 6) Compatibilidad entre dos piezas
    if re.search(r"(compatible|compatibilidad|sirve con|funciona con|va con|le queda|puedo usar)", n) and len(prods) >= 2:
        cpu = next((c for c in prods if c["tipo"] == "cpu"), None)
        mb = next((c for c in prods if c["tipo"] == "tarjeta_madre"), None)
        ram = next((c for c in prods if c["tipo"] == "ram"), None)
        if cpu and mb:
            ok = cpu["specs"]["socket"] == mb["specs"]["socket"]
            return {"texto": f"{cpu['nombre']} usa socket {cpu['specs']['socket']} y {mb['nombre']} es {mb['specs']['socket']}: "
                    + ("son compatibles. ✅" if ok else "NO son compatibles. ❌")}
        if mb and ram:
            ok = mb["specs"]["tipo_ram"] == ram["specs"]["tipo_ram"]
            return {"texto": f"{mb['nombre']} usa {mb['specs']['tipo_ram']} y {ram['nombre']} es {ram['specs']['tipo_ram']}: "
                    + ("compatibles. ✅" if ok else "NO compatibles. ❌")}
        return {"texto": "Para revisar compatibilidad dime un CPU y una tarjeta madre (o una placa y una RAM)."}

    # 7) Listar por tipo
    if re.search(r"(lista|muestrame|muestra|que .* tienen|cuales|opciones de|catalogo)", n) and tipo:
        items = sorted([c for c in comps if c["tipo"] == tipo], key=lambda c: c["precio_actual"])
        lineas = [f"• {c['nombre']} — {_precio(c)}" for c in items[:6]]
        return {"texto": f"Opciones de {R.ETIQUETAS.get(tipo, tipo)}:\n" + "\n".join(lineas)}

    # 8a) LAPTOP: recomendar una laptop segun uso + presupuesto
    if _es_laptop(msg):
        laptops = list(R.laptops_col.find({"tipo": "laptop"}))
        for l in laptops:
            l["_id"] = str(l["_id"])
        perfil = _detectar_perfil_uso(msg)
        uso = "gaming" if _es_gaming(msg, jgs) else (perfil or "oficina")
        elegidas, aviso = R.recomendar_laptops(laptops, uso, presu, n=3)
        if not elegidas:
            return {"texto": "Por ahora no tengo laptops en el catálogo para ese uso."}
        etiqueta = R.ETIQ_USO_LAPTOP.get(uso, uso)
        texto = f"Estas laptops te sirven para {etiqueta}"
        texto += f" (hasta ${presu:,.0f})" if presu else ""
        texto += ":"
        if aviso:
            texto += "\n⚠ " + aviso
        lap_items = [{"nombre": l["nombre"], "precio": f"${l['precio_actual']:,.2f}",
                      "resumen": l["descripcion"], "id": l["_id"]} for l in elegidas]
        return {"texto": texto, "laptops": lap_items,
                "chips": ["Laptop para gaming", "Laptop para la escuela", "Laptop para edición de video"]}

    # 8b) PC de escritorio para uso NO gaming (home office, escuela, edicion, programacion)
    perfil_uso = _detectar_perfil_uso(msg)
    if perfil_uso and not _es_gaming(msg, jgs) and not jgs:
        req_gpu, req_cpu, cap = R.req_por_perfil(perfil_uso)
        build, avisos = R.armar_build(comps, req_gpu, req_cpu, presu,
                                      aprovechar=bool(presu), cap_ram=cap)
        total = R.total_build(build)
        texto = f"Te recomiendo esta PC para {R.ETIQ_PERFIL.get(perfil_uso, perfil_uso)} (~${total:,.2f}):"
        if avisos:
            texto += "\n⚠ " + " ".join(avisos)
        texto += "\n\n¿Quieres que agregue estos componentes a tu carrito?"
        ids = [build[t]["_id"] for t in R.TIPOS_BUILD if build.get(t) and build[t].get("_id")]
        return {"texto": texto, "items": _build_items(build),
                "accion": "agregar_build", "ids": ids, "total": total}

    # 8c) Recomendar build gaming (por juego, por presupuesto, o por resolucion+tipo)
    if jgs or presu or exi or re.search(r"(recomiend|arma|armar|build|para jugar|quiero jugar|pc para)", n):
        resolucion = res or "1440p"
        fps_obj = fps or 60
        etiqueta_fps = f" a {fps_obj}fps" if fps else ""
        if jgs:
            req_gpu, req_cpu, cap = R.req_por_juegos(jgs, resolucion, fps_obj)
            build, avisos = R.armar_build(comps, req_gpu, req_cpu, presu, aprovechar=False, cap_ram=cap)
            objetivo = f"correr {', '.join(j['nombre'] for j in jgs[:3])} en {resolucion}{etiqueta_fps}"
        else:
            exigencia = exi or "aaa"
            req_gpu, req_cpu = R.req_por_escenario(exigencia, resolucion, fps_obj)
            cap = 32 if (exigencia in ("aaa", "aaa_rt") or resolucion == "4K") else 16
            build, avisos = R.armar_build(comps, req_gpu, req_cpu, presu, aprovechar=bool(presu), cap_ram=cap)
            objetivo = f"{R.ETIQ_EXIGENCIA.get(exigencia, exigencia)} en {resolucion}{etiqueta_fps}"
        total = R.total_build(build)
        texto = f"Te recomiendo esta PC para {objetivo} (~${total:,.2f}):"
        if avisos: texto += "\n⚠ " + " ".join(avisos)
        texto += "\n\n¿Quieres que agregue estos componentes a tu carrito?"
        ids = [build[t]["_id"] for t in R.TIPOS_BUILD if build.get(t) and build[t].get("_id")]
        return {"texto": texto, "items": _build_items(build),
                "accion": "agregar_build", "ids": ids, "total": total}

    # 9) Tipo de RAM
    if re.search(r"(ram|memoria|ddr)", n) and prods:
        cs = [c for c in prods if "tipo_ram" in c.get("specs", {})]
        if cs:
            lineas = [f"• {c['nombre']}: usa {c['specs']['tipo_ram']}" for c in cs[:4]]
            return {"texto": "\n".join(lineas)}

    # 10) Fallback
    return {"texto": "No estoy seguro de haber entendido 😅. Puedo darte precios, sockets, compatibilidad, "
            "cálculo de fuente, o armarte una PC. Prueba con algo como los botones de abajo.", "chips": chips}

# --- rutas ------------------------------------------------------------------
@chatbot_bp.route("/chatbot")
def chatbot():
    cart_count = len(session.get("carrito", []))
    return render_template("chatbot.html", cart_count=cart_count)

@chatbot_bp.route("/chatbot/mensaje", methods=["POST"])
def chatbot_mensaje():
    data = request.get_json(silent=True) or {}
    msg = (data.get("mensaje") or "").strip()
    if not msg:
        return jsonify({"texto": "Escríbeme una pregunta sobre hardware 🙂"})
    comps = list(productos.find({"tipo": {"$in": R.TIPOS_BUILD}}))
    for c in comps:
        c["_id"] = str(c["_id"])
    juegos_cat = list(juegos.find())
    return jsonify(responder(msg, comps, juegos_cat))
