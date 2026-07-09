#Universidad Politécnica de Victoria, Ciudad Victoria. Tamaulipas (18 de Abril de 2025)
#Ingeniería en Tecnologías de la información
#Proyecto final de la materia de "Base de datos", cursada con el maestro: ING. LUIS ANTONIO GONZALEZ CASTRO 
#Integrantes del proyecto: Joshua André Alvarado Tovar, Ingridh Maricela Gracia Flores, Juan Antonio Manzano Ceja, Angel Guadalupe Rivera Portillo.
#El presente código forma parte de nuestro proyecto final, donde encontrará la estructura necesitada para el correcto funcionamiento de nuestro proyecto:
from flask import Flask, render_template, abort, request, redirect, url_for, session, flash, render_template, send_file
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from io import BytesIO
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from recomendador import recomendador_bp  # Modulo recomendador de PC builds
from chatbot import chatbot_bp  # Chatbot de hardware

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'una_clave_secreta_segura')
app.config['UPLOAD_FOLDER'] = 'static/imagenesgamerxD/productos'
client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))
db = client["ITIendita"]
productos = db["productos"]
usuarios = db["usuarios"]
app.register_blueprint(recomendador_bp)  # Recomendador de PC builds
app.register_blueprint(chatbot_bp)  # Chatbot de hardware

# Helper para imagenes: acepta URLs externas (placeholder) o archivos locales en static
@app.context_processor
def _utilidades_img():
    def imagen_url(path):
        if path and (str(path).startswith("http://") or str(path).startswith("https://")):
            return path
        return url_for("static", filename=path)
    return dict(imagen_url=imagen_url)

@app.context_processor
def cart_count():
    return { 'cart_count': len(session.get('carrito', [])) }

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if usuarios.find_one({'username': request.form['username']}):
            return redirect(url_for('registro'))
        
        nuevo_usuario = {
            "nombre": request.form['nombre'],
            "apellido": request.form['apellido'],
            "email": request.form['email'],
            "password": generate_password_hash(request.form['password']),
            "username": request.form['username'],
            'rango': 'Usuario',
            "ofertas_novedades": 'newsletter' in request.form,
            "acepta_terminos": 'terms' in request.form,
            "carrito": [],
            "pedidos": []
        }
        usuario = request.form['username']
        usuarios.insert_one(nuevo_usuario)
        usuario_db = usuarios.find_one({'username': usuario})
        session['usuario_logeado'] = True
        session['usuario'] = usuario
        session['carrito'] = usuario_db.get('carrito', [])
        session['rango'] = usuario_db.get('rango')
        return redirect(url_for('inicio'))
    
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        contraseña = request.form['password']
        usuario_db = usuarios.find_one({'username': usuario})
        
        if usuario_db and check_password_hash(usuario_db['password'], contraseña):
            session['usuario_logeado'] = True
            session['usuario'] = usuario
            session['carrito'] = usuario_db.get('carrito', [])
            session['rango'] = usuario_db.get('rango')
            return redirect(url_for('inicio'))
        else:
            return render_template('login.html', error='Usuario o contraseña incorrectos')
    
    return render_template('login.html')
@app.route('/')
def inicio():
    # Carga todos los productos y los pasa a la plantilla
    productos_destacados = list(productos.find({"descuento": {"$gt": 0}}).limit(4))
    nuevos_lanzamientos = list(productos.find({"es_nuevo": True}).limit(4))
    ofertas = list(productos.find({"descuento": {"$gt": 0}}).limit(4))
    if 'usuario_logeado' in session:
        usuario = session.get('usuario')
    else:
        usuario = None
    return render_template('inicio.html', productos_destacados=productos_destacados,
        nuevos_lanzamientos=nuevos_lanzamientos,
        ofertas=ofertas, usuario=usuario)

@app.route("/buscar")
def buscar():
    termino = request.args.get("q", "")
    categorias = request.args.getlist("categorias")
    marcas = request.args.getlist("marcas")
    min_precio = request.args.get("min", type=float)
    max_precio = request.args.get("max", type=float)
    orden = request.args.get("orden")

    filtro = {}
    if termino:
        filtro["nombre"] = {"$regex": termino, "$options": "i"}
    if categorias:
        filtro["categoria"] = {"$in": categorias}
    if marcas:
        filtro["marca"] = {"$in": marcas}
    if min_precio is not None or max_precio is not None:
        filtro["precio_actual"] = {}
        if min_precio is not None:
            filtro["precio_actual"]["$gte"] = min_precio
        if max_precio is not None:
            filtro["precio_actual"]["$lte"] = max_precio

    sort = []
    if orden == "precio-asc":
        sort = [("precio_actual", 1)]
    elif orden == "precio-desc":
        sort = [("precio_actual", -1)]
    elif orden == "valoracion":
        sort = [("estrellas", -1)]

    cursor = productos.find(filtro).sort(sort) if sort else productos.find(filtro)
    resultados = list(cursor)  # Convertimos el cursor a lista

    return render_template("resultados.html",resultados=resultados,termino=termino,categorias_seleccionadas=categorias,
    marcas_seleccionadas=marcas,
    min_precio=min_precio,
    max_precio=max_precio,
    orden=orden)

@app.route('/logout')
def logout():
    if 'usuario_logeado' in session:
        session.clear()
    return redirect(url_for('inicio'))

@app.route('/mi-cuenta')
def mi_cuenta():
    if 'usuario_logeado' in session:
        usuario = usuarios.find_one({'username': session['usuario']})
        return render_template('mi_cuenta.html', usuario=usuario)
    return redirect(url_for('inicio'))

@app.route('/agregar-al-carrito/<prod_id>', methods=['POST'])
def agregar_al_carrito(prod_id):
    if 'usuario_logeado' in session:
        producto = productos.find_one({'_id': ObjectId(prod_id)})
        if not producto or producto.get('stock', 0) <= 0:
            #Agotado
            return redirect(request.referrer or url_for('inicio'))

        # Reducir stock en la BD
        productos.update_one({'_id': ObjectId(prod_id)}, {'$inc': {'stock': -1}})

        carrito = session.get('carrito', [])
        encontrado = False
        for item in carrito:
            if item['prod_id'] == prod_id:
                item['cantidad'] += 1
                encontrado = True
                break
        if not encontrado:
            carrito.append({'prod_id': prod_id, 'cantidad': 1})

        session['carrito'] = carrito
        usuarios.update_one(
            {'username': session['usuario']},
            {'$set': {'carrito': carrito}}
        )
        return redirect(request.referrer or url_for('inicio'))
    return redirect(url_for('inicio'))

@app.route('/limpiar-carrito')
def limpiar_carrito():
    session['carrito'] = []
    if 'usuario' in session:
        usuarios.update_one(
            {'username': session['usuario']},
            {'$set': {'carrito': []}}
        )
        flash('Carrito limpiado correctamente.', 'success')
    return redirect(url_for('inicio'))

@app.route('/remover-del-carrito/<prod_id>', methods=['POST'])
def remover_del_carrito(prod_id):
    if 'usuario_logeado' in session:
        # Devolver stock en la BD
        producto = productos.find_one({'_id': ObjectId(prod_id)})

        if not producto:
            flash('Producto no encontrado', 'error')
            return redirect(url_for('mi_carrito'))

        carrito = session.get('carrito', [])

        # Buscar el producto en el carrito
        for item in carrito:
            if item['prod_id'] == prod_id:
                if item['cantidad'] > 1:
                    item['cantidad'] -= 1  # Reducir cantidad
                else:
                    carrito.remove(item)  # Eliminar producto si la cantidad es 1
                break

        # Actualizar el carrito en la sesión
        session['carrito'] = carrito

        # Actualizar el carrito en la base de datos
        usuarios.update_one(
            {'username': session['usuario']},
            {'$set': {'carrito': carrito}}
        )

        # Devolver el stock en la base de datos
        productos.update_one(
            {'_id': ObjectId(prod_id)},
            {'$inc': {'stock': 1}}
        )

        flash('Producto eliminado del carrito.', 'success')
        return redirect(url_for('mi_carrito'))
    return redirect(url_for('inicio'))

@app.route('/mi-carrito')
def mi_carrito():
    if 'usuario_logeado' in session:
        ids = session.get('carrito', [])
        productos_carrito = []
        
        for item in ids:
            # Obtener el producto completo usando el ID
            producto = productos.find_one({'_id': ObjectId(item['prod_id'])})
            if producto:
                # Añadir el producto y la cantidad al carrito
                producto['cantidad'] = item['cantidad']
                productos_carrito.append(producto)
        
        return render_template('mi_carrito.html', productos_carrito=productos_carrito)
    return redirect(url_for('inicio'))

@app.route('/pagar', methods=['GET', 'POST'])
def pagar():
    if 'usuario_logeado' in session:
        if len(session.get('carrito', [])) != 0:
            if request.method == 'POST':
                recibidor = request.form['recibidor']
                direccion = request.form['direccion']
                caracteristicas = request.form['caracteristicas']
                metodo_pago = request.form['metodo_pago']
                carrito = session['carrito']

                productos_pedido = []
                for item in carrito:
                    producto = productos.find_one({'_id': ObjectId(item['prod_id'])})
                    if producto:
                        productos_pedido.append({
                            'nombre': producto['nombre'],
                            'precio': producto['precio_actual'],
                            'cantidad': item['cantidad'],
                            'prod_id': str(producto['_id'])  # Guarda el ID del producto como string
                        })
                
                total_pedido = sum(item['precio'] * item['cantidad'] for item in productos_pedido)

                nuevo_pedido = {
                    '_id': ObjectId(),  # Se asigna un ID único al pedido
                    'recibidor': recibidor,
                    'direccion': direccion,
                    'caracteristicas_lugar_entrega': caracteristicas,
                    'metodo_pago': metodo_pago,
                    'productos': productos_pedido,
                    'total': total_pedido,
                    'estado': 'en proceso',
                    'fecha_creacion': datetime.now()
                }

                # Guardar el pedido en la lista del usuario
                usuarios.update_one(
                    {'username': session['usuario']},
                    {
                        '$push': {'pedidos': nuevo_pedido},
                        '$set': {'carrito': []}
                    }
                )

                session['carrito'] = []
                return redirect(url_for('mis_pedidos'))

            return render_template('pagar.html')
        return redirect(url_for('inicio'))
    return redirect(url_for('login'))

@app.route('/mis-pedidos')
def mis_pedidos():
    if 'usuario_logeado' in session:
        usuario = usuarios.find_one({'username': session['usuario']})
        pedidos_usuario = usuario.get('pedidos', [])
        return render_template('mis_pedidos.html', pedidos=pedidos_usuario)
    return redirect(url_for('inicio'))

@app.route('/producto/<prod_id>', methods=['GET', 'POST'])
def ver_producto(prod_id):
    try:
        producto = productos.find_one({'_id': ObjectId(prod_id)})
    except:
        producto = None

    if not producto:
        return redirect(url_for('inicio'))

    usuario = usuarios.find_one({'username': session.get('usuario')})
    puede_opinar = False
    reseña_existente = None

    if usuario:
        for pedido in usuario.get('pedidos', []):
            if pedido.get('estado') == 'entregado':
                for prod in pedido.get('productos', []):
                    if str(prod.get('prod_id')) == str(prod_id):
                        puede_opinar = True
                        break

        reseña_existente = next(
            (r for r in producto.get('reseñas', []) if r['usuario'] == session['usuario']),
            None
        )

    if request.method == 'POST' and puede_opinar:
        nueva_puntuacion = float(request.form['estrellas'])
        nuevo_comentario = request.form['comentario']

        nuevas_reseñas = producto.get('reseñas', [])

        if reseña_existente:
            for r in nuevas_reseñas:
                if r['usuario'] == session['usuario']:
                    r['estrellas'] = nueva_puntuacion
                    r['comentario'] = nuevo_comentario
                    r['fecha'] = datetime.now()
                    break
        else:
            nuevas_reseñas.append({
                'usuario': session['usuario'],
                'estrellas': nueva_puntuacion,
                'comentario': nuevo_comentario,
                'fecha': datetime.now()
            })

        total_estrellas = sum(r['estrellas'] for r in nuevas_reseñas)
        promedio = round(total_estrellas / len(nuevas_reseñas), 1)

        productos.update_one(
            {'_id': ObjectId(prod_id)},
            {
                '$set': {
                    'reseñas': nuevas_reseñas,
                    'estrellas': promedio,
                    'opiniones': len(nuevas_reseñas)
                }
            }
        )

        return redirect(url_for('ver_producto', prod_id=prod_id))

    return render_template('producto.html',
                           producto=producto,
                           puede_opinar=puede_opinar,
                           reseña_existente=reseña_existente)

# Ruta para generar y descargar la factura
@app.route('/factura/<pedido_id>')
def generar_factura(pedido_id):
    # Buscar al usuario logueado
    usuario = usuarios.find_one({'username': session['usuario']})

    # Buscar el pedido en la lista de pedidos del usuario
    pedido = next((p for p in usuario['pedidos'] if str(p['_id']) == pedido_id), None)

    if not pedido:
        return redirect(url_for('inicio'))

    # Crear PDF en memoria
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Logo centrado en la parte superior
    logo_path = "static/imagenesgamerxD/Logo.png"  # Ruta al logo
    logo_width = 100  # Ajusta el tamaño del logo
    logo_height = 50  # Ajusta el tamaño del logo
    logo_y_position = height - logo_height - 30  
    c.drawImage(logo_path, (width - logo_width) / 2, logo_y_position, width=logo_width, height=logo_height)

    c.setFont("Helvetica-Bold", 16)
    c.setFillColorRGB(0, 0, 0)  # Color negro para todo el texto
    c.drawString(150, logo_y_position - 30, f"Factura de Pedido #{pedido['_id']}")

    # Información de la factura
    c.setFont("Helvetica", 10)
    c.drawString(100, logo_y_position - 50, f"Fecha: {pedido['fecha_creacion'].strftime("%d/%m/%Y %H:%M:%S")}")
    c.drawString(100, logo_y_position - 70, f"Receptor: {pedido['recibidor']}")
    c.drawString(100, logo_y_position - 90, f"Dirección: {pedido['direccion']}")
    c.drawString(100, logo_y_position - 110, f"Método de Pago: {pedido['metodo_pago']}")
    c.drawString(100, logo_y_position - 130, f"Total: ${"{:.2f}".format(pedido['total'])}")

    # Dibujar una línea horizontal debajo de la información básica
    c.setLineWidth(1)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)  # Color gris para la línea
    c.line(100, logo_y_position - 140, width - 100, logo_y_position - 140)

    # Encabezado de productos
    y_position = logo_y_position - 160
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, y_position, "Productos:")
    y_position -= 20
    c.setFont("Helvetica-Bold", 8)
    c.drawString(100, y_position, "Producto")
    c.drawString(300, y_position, "Cantidad")
    c.drawString(400, y_position, "Precio Unitario")
    c.drawString(500, y_position, "Total")
    y_position -= 15
    c.setFont("Helvetica", 8)

    # Dibujar una línea debajo del encabezado de productos
    c.line(100, y_position + 10, width - 100, y_position + 10)

    # Listar productos
    for producto in pedido['productos']:
        y_position -= 20
        c.drawString(100, y_position, f"{producto['nombre']}")
        c.drawString(300, y_position, f"x{producto['cantidad']}")
        c.drawString(400, y_position, f"${producto['precio']}")
        c.drawString(500, y_position, f"${producto['precio'] * producto['cantidad']}")
        
        # Si la página se llena, crear una nueva
        if y_position < 100:
            c.showPage()
            y_position = height - 50

    # Dibujar una línea final
    c.line(100, y_position - 10, width - 100, y_position - 10)

    # Pie de página con el mensaje
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0, 0, 0)  # Asegurando que el texto del pie también sea negro
    c.drawString(100, y_position - 30, "Gracias por comprar con nosotros!")

    # Guardar el PDF en memoria
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="factura.pdf", mimetype="application/pdf")


#admin

@app.route('/gestionar-roles', methods=['GET', 'POST'])
def gestionar_roles():
    if 'usuario_logeado' not in session or session.get('rango') != 'Admin':
        return redirect(url_for('inicio'))
    
    if request.method == 'POST':
        username = request.form['username']
        nuevo_rango = request.form['rango']
        
        # Verificar que no sea el propio admin
        if username != session['usuario']:
            usuarios.update_one(
                {'username': username},
                {'$set': {'rango': nuevo_rango}}
            )
        else:
            return redirect(url_for('inicio'))
    lista_usuarios = list(usuarios.find({'rango': {'$ne': 'Admin'}}, {'username': 1, 'nombre': 1, 'email': 1, 'rango': 1}))
    return render_template('gestionar_roles.html', usuarios=lista_usuarios)

@app.route('/crear-producto', methods=['GET', 'POST'])
def crear_producto():
    if 'usuario_logeado' not in session or session.get('rango') != 'Admin':
        return redirect(url_for('inicio'))
    if request.method == 'POST':
        archivo_imagen = request.files['imagen']
        
        if archivo_imagen:
            nombre_archivo = secure_filename(archivo_imagen.filename)
            ruta_completa = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo)
            archivo_imagen.save(ruta_completa)

            imagen_url = f"imagenesgamerxD/productos/{nombre_archivo}"

            precio_original = float(request.form['precio_original'])
            descuento = float(request.form['descuento'])
            precio_actual = round(precio_original * (1 - descuento / 100), 2)

            nuevo_producto = {
                'nombre': request.form['nombre'],
                'imagen': imagen_url,
                'precio_original': precio_original,
                'precio_actual': precio_actual,
                'descuento': descuento,
                'estrellas': 5,
                'descripcion': request.form['descripcion'],
                'marca': request.form['marca'],
                'categoria': request.form['categoria'],
                'stock': int(request.form['stock'])
            }

            productos.insert_one(nuevo_producto)
            return redirect(url_for('crear_producto'))

    return render_template('crear_producto.html')


@app.route('/modificar-stock', methods=['GET', 'POST'])
def modificar_stock():
    if 'usuario_logeado' not in session or session.get('rango') != 'Admin':
        return redirect(url_for('inicio'))
    if request.method == 'POST':
        producto_id = request.form['producto_id']
        nuevo_stock = int(request.form['nuevo_stock'])
            
        productos.update_one({'_id': ObjectId(producto_id)},{'$set': {'stock': nuevo_stock}})
    lista_productos = list(productos.find({}, {'nombre': 1, 'stock': 1, '_id': 1}))
    return render_template('modificar_stock.html', productos=lista_productos)

#repartidor

@app.route('/confirmar-pedidos', methods=['GET', 'POST'])
def confirmar_pedidos():
    if request.method == 'POST':
        pedido_id = request.form['pedido_id']
        
        # Actualizar el estado del pedido a "entregado"
        usuarios.update_many({'pedidos._id': ObjectId(pedido_id)},{'$set': {'pedidos.$.estado': 'entregado'}})
    
    # Obtener todos los pedidos en proceso
    pedidos_en_proceso = list(usuarios.aggregate([{'$unwind': '$pedidos'},{'$match': {'pedidos.estado': 'en proceso'}},
        {'$project': {
            'username': 1,
            'nombre': 1,
            'pedido': '$pedidos'
        }}
    ]))
    return render_template('confirmar_pedidos.html', pedidos=pedidos_en_proceso)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
