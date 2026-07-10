import os
import json
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI")
CATALOGO = os.environ.get("CATALOGO", "productos_catalogo_completo.json")
CONFIRMAR = os.environ.get("CONFIRMAR_REEMPLAZO")
if not MONGO_URI:
    raise RuntimeError("Falta MONGO_URI. Exporta la conexión de MongoDB Atlas antes de ejecutar.")
if CONFIRMAR != "SI":
    raise RuntimeError("Protección activa. Ejecuta primero: export CONFIRMAR_REEMPLAZO=SI")
with open(CATALOGO, "r", encoding="utf-8") as f:
    productos = json.load(f)
client = MongoClient(MONGO_URI)
db = client["ITIendita"]
col = db["productos"]
backup_name = "productos_backup_pre_catalogo_completo"
db[backup_name].delete_many({})
actuales = list(col.find({}, {"_id": 0}))
if actuales:
    db[backup_name].insert_many(actuales)
col.delete_many({})
if productos:
    col.insert_many(productos)
print(f"Colección productos reemplazada correctamente con {len(productos)} productos.")
print(f"Respaldo previo guardado en la colección: {backup_name}")
