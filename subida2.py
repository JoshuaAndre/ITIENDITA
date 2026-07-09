#Universidad Politécnica de Victoria, Ciudad Victoria. Tamaulipas (18 de Abril de 2025)
#Ingeniería en Tecnologías de la información
#Proyecto final de la materia de "Base de datos", cursada con el maestro: ING. LUIS ANTONIO GONZALEZ CASTRO 
#Integrantes del proyecto: Joshua André Alvarado Tovar, Ingridh Maricela Gracia Flores, Juan Antonio Manzano Ceja, Angel Guadalupe Rivera Portillo.
#El presente código forma parte de nuestro proyecto final, donde encontrará la estructura necesitada para el correcto funcionamiento de nuestro proyecto:
import os
import json
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))
db = client["ITIendita"]
coleccion = db["usuarios"]

usuarios_data = [
    {
        "nombre": "Admin",
        "apellido": "Principal",
        "email": "admin@tienda.com",
        "password": "admin123",
        "username": "admin",
        "rango": "Admin",
        "ofertas_novedades": True,
        "acepta_terminos": True,
        "carrito": [],
        "pedidos": []
    }
]

for usuario in usuarios_data:
    usuario['password'] = generate_password_hash(usuario['password'], method='scrypt')
    coleccion.insert_one(usuario)
