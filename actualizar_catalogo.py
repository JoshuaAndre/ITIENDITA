import os
import json
from pymongo import MongoClient, UpdateOne

MONGO_URI = os.environ.get("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("Falta MONGO_URI. Exporta tu conexión de MongoDB Atlas antes de ejecutar.")

client = MongoClient(MONGO_URI)
db = client["ITIendita"]
productos_col = db["productos"]

with open("productos_gamer.json", "r", encoding="utf-8") as f:
    productos = json.load(f)

operaciones = []

for producto in productos:
    operaciones.append(
        UpdateOne(
            {"nombre": producto["nombre"]},
            {"$set": producto},
            upsert=True
        )
    )

if operaciones:
    resultado = productos_col.bulk_write(operaciones)
    print("Catálogo actualizado correctamente.")
    print("Insertados:", resultado.upserted_count)
    print("Modificados:", resultado.modified_count)
    print("Coincidencias:", resultado.matched_count)
else:
    print("No se encontraron productos.")
