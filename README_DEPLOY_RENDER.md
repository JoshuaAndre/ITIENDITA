# Publicar ITIENDITA en internet (Render + MongoDB Atlas)

Este paquete ya trae los ajustes mínimos para despliegue:

- `requirements.txt` con dependencias de Python.
- `Procfile` con Gunicorn.
- Uso de `MONGO_URI` desde variables de entorno, manteniendo fallback local a `mongodb://localhost:27017/`.
- Uso de `SECRET_KEY` desde variables de entorno.

## 1. Crear MongoDB Atlas

1. Crea un cluster en MongoDB Atlas.
2. Crea un usuario de base de datos.
3. En Network Access agrega la IP del servicio de hosting o temporalmente `0.0.0.0/0` para pruebas académicas.
4. Copia el connection string tipo `mongodb+srv://...`.

## 2. Subir el proyecto a GitHub

Sube el contenido de esta carpeta como repositorio. La raíz debe contener `app.py`, `requirements.txt` y `Procfile`.

## 3. Crear Web Service en Render

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
- Variables de entorno:
  - `MONGO_URI`: connection string de Atlas
  - `SECRET_KEY`: una cadena larga y privada

## 4. Cargar datos iniciales

Después de configurar `MONGO_URI`, ejecuta una vez:

```bash
python subida.py
python subida_laptops.py
python subida_juegos.py
python subida2.py
```

Esto carga productos, laptops, juegos y el usuario admin.

Admin inicial:

- Usuario: `admin`
- Contraseña: `admin123`

Cambia esa contraseña al presentar el proyecto si vas a dejarlo público.

## Nota importante sobre imágenes subidas

Las imágenes que ya vienen en `static/` sí se despliegan. Si desde la app subes imágenes nuevas a `static/imagenesgamerxD/productos`, algunos hostings gratuitos pueden borrarlas al reiniciar o redeplegar. Para conservar esa función en producción real, usa almacenamiento persistente o un servicio como Cloudinary/S3.
