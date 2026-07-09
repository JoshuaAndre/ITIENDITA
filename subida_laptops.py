# Carga el catalogo de laptops en la coleccion "productos" (tipo="laptop"),
# asi el carrito existente funciona sin cambios.
import os
import json
from pymongo import MongoClient
client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))
db = client["ITIendita"]
coleccion = db["productos"]
coleccion.delete_many({"tipo": "laptop"})  # recarga limpia solo de laptops
with open("laptops.json", encoding="utf-8") as archivo:
    laptops = json.load(archivo)
resultado = coleccion.insert_many(laptops)
print(f"Insertadas {len(resultado.inserted_ids)} laptops en 'productos' (tipo=laptop).")
