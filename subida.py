#Universidad Politécnica de Victoria, Ciudad Victoria. Tamaulipas (18 de Abril de 2025)
#Ingeniería en Tecnologías de la información
#Proyecto final de la materia de "Base de datos", cursada con el maestro: ING. LUIS ANTONIO GONZALEZ CASTRO 
#Integrantes del proyecto: Joshua André Alvarado Tovar, Ingridh Maricela Gracia Flores, Juan Antonio Manzano Ceja, Angel Guadalupe Rivera Portillo.
#El presente código forma parte de nuestro proyecto final, donde encontrará la estructura necesitada para el correcto funcionamiento de nuestro proyecto:
import os
import json
from pymongo import MongoClient

client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))
db = client["ITIendita"]
coleccion = db["productos"]

with open("productos_gamer.json", encoding='utf-8') as archivo:
    productos = json.load(archivo)

resultado = coleccion.insert_many(productos)