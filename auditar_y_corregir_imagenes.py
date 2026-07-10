import os
import re
import unicodedata
import difflib
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("Falta MONGO_URI. Exporta primero tu conexión de MongoDB Atlas.")

BASE_DIR = "static/imagenesgamerxD/productos"
DB_NAME = "ITIendita"
COLLECTION = "productos"


def slug(texto):
    texto = str(texto).lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto


def normalizar_ruta(imagen):
    imagen = str(imagen or "").strip()

    if imagen.startswith("/static/"):
        imagen = imagen.replace("/static/", "", 1)

    if imagen.startswith("static/"):
        imagen = imagen.replace("static/", "", 1)

    return imagen


client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col = db[COLLECTION]

archivos = []

for root, dirs, files in os.walk(BASE_DIR):
    for f in files:
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            ruta_local = os.path.join(root, f)
            ruta_db = ruta_local.replace("static/", "", 1)

            archivos.append({
                "archivo": f,
                "ruta_local": ruta_local,
                "ruta_db": ruta_db,
                "slug": slug(os.path.splitext(f)[0])
            })

productos = list(col.find({}, {
    "nombre": 1,
    "imagen": 1,
    "categoria": 1,
    "marca": 1,
    "tipo": 1
}))

faltantes = []
corregidos = []
correctos = []

for p in productos:
    nombre = p.get("nombre", "")
    imagen_db = normalizar_ruta(p.get("imagen", ""))
    ruta_local = os.path.join("static", imagen_db)

    if imagen_db and os.path.exists(ruta_local):
        correctos.append(nombre)
        continue

    nombre_slug = slug(nombre)
    mejor = None
    mejor_score = 0

    for a in archivos:
        score = difflib.SequenceMatcher(None, nombre_slug, a["slug"]).ratio()

        if nombre_slug in a["slug"] or a["slug"] in nombre_slug:
            score += 0.25

        if score > mejor_score:
            mejor_score = score
            mejor = a

    if mejor and mejor_score >= 0.62:
        col.update_one(
            {"_id": p["_id"]},
            {"$set": {"imagen": mejor["ruta_db"]}}
        )

        corregidos.append({
            "producto": nombre,
            "antes": p.get("imagen", ""),
            "despues": mejor["ruta_db"],
            "coincidencia": round(mejor_score, 3)
        })
    else:
        faltantes.append({
            "producto": nombre,
            "categoria": p.get("categoria"),
            "marca": p.get("marca"),
            "imagen_actual": p.get("imagen", ""),
            "ruta_esperada": ruta_local
        })

print("===== AUDITORÍA DE IMÁGENES =====")
print("Productos revisados:", len(productos))
print("Imágenes correctas:", len(correctos))
print("Rutas corregidas automáticamente:", len(corregidos))
print("Imágenes todavía faltantes:", len(faltantes))

if corregidos:
    print("\n===== CORREGIDOS =====")
    for c in corregidos:
        print("- " + c["producto"])
        print("  Antes:", c["antes"])
        print("  Después:", c["despues"])
        print("  Coincidencia:", c["coincidencia"])

if faltantes:
    print("\n===== FALTANTES =====")
    for f in faltantes:
        print("----")
        print("Producto:", f["producto"])
        print("Categoría:", f["categoria"])
        print("Marca:", f["marca"])
        print("Imagen actual:", f["imagen_actual"])
        print("Ruta esperada:", f["ruta_esperada"])
