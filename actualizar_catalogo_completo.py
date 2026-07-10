import os
import json
from pymongo import MongoClient, UpdateOne

MONGO_URI = os.environ.get("MONGO_URI")
CATALOGO = os.environ.get("CATALOGO", "productos_catalogo_completo.json")

if not MONGO_URI:
    raise RuntimeError("Falta MONGO_URI. Exporta la conexión de MongoDB Atlas antes de ejecutar.")

with open(CATALOGO, "r", encoding="utf-8") as f:
    productos = json.load(f)

client = MongoClient(MONGO_URI)
db = client["ITIendita"]
col = db["productos"]
ops = [UpdateOne({"nombre": p["nombre"]}, {"$set": p}, upsert=True) for p in productos]
if ops:
    r = col.bulk_write(ops)
    print("Catálogo actualizado sin duplicar por nombre.")
    print("Insertados:", r.upserted_count)
    print("Modificados:", r.modified_count)
    print("Coincidencias:", r.matched_count)
else:
    print("No hay productos para cargar.")
