# Carga el catalogo de juegos para el recomendador por juegos (coleccion "juegos").
import os
import json
from pymongo import MongoClient

client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))
db = client["ITIendita"]
coleccion = db["juegos"]
coleccion.delete_many({})  # recarga limpia

with open("juegos.json", encoding="utf-8") as archivo:
    juegos = json.load(archivo)

resultado = coleccion.insert_many(juegos)
print(f"Insertados {len(resultado.inserted_ids)} juegos en la coleccion 'juegos'.")
