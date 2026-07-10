import os
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("Falta MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["ITIendita"]

faltantes = []

for p in db["productos"].find({}, {"nombre": 1, "imagen": 1}):
    imagen = p.get("imagen", "")
    ruta = imagen.replace("/static/", "").replace("static/", "")
    ruta_local = os.path.join("static", ruta)

    if not os.path.exists(ruta_local):
        faltantes.append((p.get("nombre"), imagen, ruta_local))

print("Imágenes faltantes:", len(faltantes))

for nombre, imagen, ruta in faltantes:
    print("----")
    print("Producto:", nombre)
    print("Imagen DB:", imagen)
    print("Ruta esperada:", ruta)
