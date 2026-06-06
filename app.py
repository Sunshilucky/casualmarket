from flask import Flask, render_template, request, redirect, session
import pymysql
from config import db_config

# aqui importamos los models
from models.producto import obtener_todos, obtener_por_id
from models.categoria import obtener_categorias
from models.usuario import buscar_usuario, registrar_usuario
from models.pedido import crear_pedido, agregar_detalle

app = Flask(__name__)
app.secret_key = "clave_secreta"

def get_db():
    return pymysql.connect(
        host=db_config["host"],
        user=db_config["user"],
        password=db_config["password"],
        database=db_config["database"],
        port=db_config["port"],
        cursorclass=pymysql.cursors.DictCursor
    )




#Funcion para verificar si el usuario es admin
def solo_admin():
    return session.get("rol") == "admin"

#para obtener productos por los id
def obtener_productos_por_ids(ids):
    if not ids:
        return []
    formato = ",".join(["%s"] * len(ids))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(f"SELECT * FROM productos WHERE id IN ({formato})", tuple(ids))
    productos = cursor.fetchall()
    cursor.close()
    db.close()
    return productos

#Aqui es la pagina principal, quisimos que hubieran productos destacados como en las tiendas reales, lo que mas destaco de aqui es que decidimos poner 6 productos destacados como maximo.
@app.route('/')
def index():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos WHERE destacado = 1 LIMIT 6")
    productos = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('index.html', productos=productos)

#Mostrar todos los productos
@app.route('/productos')
def productos():
    return render_template('productos.html', productos=obtener_todos())

#Pagina para escoger productos destacados (solo admin)
@app.route('/destacados')
def destacados():
    if not solo_admin():
        return redirect('/')

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos")
    productos = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('destacados.html', productos=productos)

#Guardar los productos destacados
@app.route('/guardar_destacados', methods=['POST'])
def guardar_destacados():
    if not solo_admin():
        return redirect('/')

    ids_destacados = request.form.getlist('destacados')

    db = get_db()
    cursor = db.cursor()

    #Primero poner todos en 0
    cursor.execute("UPDATE productos SET destacado = 0")

    #Luego activar solo los seleccionados
    if ids_destacados:
        formato = ",".join(["%s"] * len(ids_destacados))
        cursor.execute(f"UPDATE productos SET destacado = 1 WHERE id IN ({formato})", tuple(ids_destacados))

    db.commit()
    cursor.close()
    db.close()

    return redirect('/destacados')

#Mostrar los productos por categoria
@app.route('/categoria/<int:id>')
def categoria(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM productos WHERE categoria_id = %s", (id,))
    productos = cursor.fetchall()

    cursor.execute("SELECT nombre FROM categorias WHERE id = %s", (id,))
    categoria = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template('categoria.html', productos=productos, categoria=categoria)

# Agregar productos al carrito
@app.route('/agregar_carrito/<int:id>', methods=['POST'])
def agregar_carrito(id):
    cantidad = int(request.form.get('cantidad', 1))
    carrito = session.setdefault("carrito", [])

    for item in carrito:
        if item["id"] == id:
            item["cantidad"] += cantidad
            session.modified = True
            return redirect('/carrito')

    carrito.append({"id": id, "cantidad": cantidad})
    session.modified = True
    return redirect('/carrito')

# Eliminar productos del carrito
@app.route('/eliminar/<int:id>')
def eliminar_producto(id):
    carrito = session.get("carrito", [])
    for item in carrito:
        if item["id"] == id:
            if item["cantidad"] > 1:
                item["cantidad"] -= 1
            else:
                carrito.remove(item)
            break
    session.modified = True
    return redirect('/carrito')

# ver el carrito
@app.route('/carrito')
def carrito():
    carrito = session.get("carrito", [])
    if not carrito:
        return render_template('carrito.html', productos=[], total=0)

    ids = [item["id"] for item in carrito]
    productos_db = obtener_productos_por_ids(ids)
    productos = []
    total = 0
    
    for item in carrito:
        for p in productos_db:
            if p["id"] == item["id"]:
                precio = float(p["precio"])
                subtotal = precio * item["cantidad"]
                total += subtotal
                productos.append({
                    "id": p["id"],
                    "titulo": p["titulo"],
                    "precio": precio,
                    "cantidad": item["cantidad"],
                    "subtotal": subtotal})

    return render_template('carrito.html', productos=productos, total=total)

# Para vaciar el carrito
@app.route('/limpiar_carrito')
def limpiar_carrito():
    session.pop("carrito", None)
    return redirect('/carrito')

# Para pagar
@app.route('/pagar', methods=['GET', 'POST'])
def pagar():
    carrito = session.get("carrito", [])
    if not carrito:
        return render_template('pagar.html', total=0)
    if "usuario_id" not in session:
        return redirect('/login')

    ids = [item["id"] for item in carrito]
    productos_db = obtener_productos_por_ids(ids)
    total = sum(float(p["precio"]) * item["cantidad"]
                for item in carrito
                for p in productos_db if p["id"] == item["id"])
    
    if request.method == 'POST':
        monto = float(request.form['monto'])
        cambio = monto - total
        pedido_id = crear_pedido(session["usuario_id"], total)

        for item in carrito:
            for p in productos_db:
                if p["id"] == item["id"]:
                    subtotal = float(p["precio"]) * item["cantidad"]
                    agregar_detalle(pedido_id, p["id"], item["cantidad"], subtotal)

        session["carrito"] = []
        return render_template('pedido_exito.html', total=total, monto=monto, cambio=cambio)

    return render_template('pagar.html', total=total)

#Para ver todos los pedidos (solo el admin)
@app.route('/pedidos')
def ver_pedidos():
    if not solo_admin():
        return redirect('/')

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
    SELECT p.id, p.fecha, p.total,
           u.nombre AS usuario_nombre
    FROM pedidos p
    JOIN usuarios u ON p.usuario_id = u.id
    """)

    pedidos = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('pedidos.html', pedidos=pedidos)

#Ver detalles del pedido (solo admin)
@app.route('/detalle_pedido/<int:id>')
def ver_detalle_pedido(id):
    if not solo_admin():
        return redirect('/')

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT dp.cantidad,
               dp.subtotal,
               pr.titulo,
               pr.precio
        FROM detalle_pedido dp
        JOIN productos pr ON dp.producto_id = pr.id
        WHERE dp.pedido_id = %s
    """, (id,))
    detalles = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('detalle_pedido.html', detalles=detalles)

#Editar pedido (solo admin)
@app.route('/editar_pedido/<int:id>')
def editar_pedido(id):
    if not solo_admin():
        return redirect('/')

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Obtener datos del pedido
    cursor.execute("SELECT * FROM pedidos WHERE id = %s", (id,))
    pedido = cursor.fetchone()

    # Obtener productos dentro del pedido
    cursor.execute("""
        SELECT dp.id,
               dp.cantidad,
               dp.subtotal,
               p.titulo,
               p.imagen,
               p.precio
        FROM detalle_pedido dp
        JOIN productos p ON dp.producto_id = p.id
        WHERE dp.pedido_id = %s
    """, (id,))
    detalles = cursor.fetchall()

    # Obtener todos los productos para agregarlos al pedido
    cursor.execute("SELECT * FROM productos")
    productos = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('editar_pedido.html', pedido=pedido, detalles=detalles, productos=productos)

#Eliminar pedido (solo admin)
@app.route('/eliminar_pedido/<int:id>')
def eliminar_pedido(id):
    if not solo_admin():
        return redirect('/')

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM detalle_pedido WHERE pedido_id = %s", (id,))
    cursor.execute("DELETE FROM pedidos WHERE id = %s", (id,))
    db.commit()
    cursor.close()
    db.close()
    return redirect('/pedidos')

#Guardar cambios del pedido editado
@app.route('/guardar_pedido/<int:id>', methods=['POST'])
def guardar_pedido(id):
    if not solo_admin():
        return redirect('/')

    db = get_db()
    cursor = db.cursor()

    # 1. Actualizar cantidades
    cursor.execute("SELECT id, cantidad FROM detalle_pedido WHERE pedido_id = %s", (id,))
    detalles = cursor.fetchall()

    for d in detalles:
        nueva_cantidad = request.form.get(f"cantidad_{d[0]}")
        if nueva_cantidad:
            cursor.execute("""
                UPDATE detalle_pedido
                SET cantidad = %s
                WHERE id = %s
            """, (nueva_cantidad, d[0]))

    # 2. Eliminar productos marcados
    eliminar_id = request.form.getlist("eliminar")
    for det_id in eliminar_id:
        cursor.execute("DELETE FROM detalle_pedido WHERE id = %s", (det_id,))

    # 3. Agregar nuevo producto
    nuevo_producto = request.form.get("nuevo_producto")
    nueva_cantidad = request.form.get("nueva_cantidad")

    if nuevo_producto and nueva_cantidad:
        cursor.execute("SELECT precio FROM productos WHERE id = %s", (nuevo_producto,))
        precio = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO detalle_pedido (pedido_id, producto_id, cantidad, subtotal)
            VALUES (%s, %s, %s, %s)
        """, (id, nuevo_producto, nueva_cantidad, float(precio) * int(nueva_cantidad)))

    # 4. Recalcular total
    cursor.execute("""
        SELECT SUM(subtotal)
        FROM detalle_pedido
        WHERE pedido_id = %s
    """, (id,))
    total = cursor.fetchone()[0] or 0

    cursor.execute("UPDATE pedidos SET total = %s WHERE id = %s", (total, id))

    db.commit()
    cursor.close()
    db.close()

    return redirect('/pedidos')

#Agregar producto (solo el admin)
@app.route('/agregar_producto')
def agregar_producto():
    if not solo_admin():
        return redirect('/')
    return render_template('agregar_producto.html')

#Guardar producto (solo el admin)
@app.route('/guardar_producto', methods=['POST'])
def guardar_producto():
    if not solo_admin():
        return redirect('/')

    titulo = request.form['titulo']
    precio = request.form['precio']
    categoria = request.form['categoria']
    imagen = request.form['imagen']

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO productos (titulo, precio, categoria_id, imagen)
        VALUES (%s, %s, %s, %s)
    """, (titulo, precio, categoria, imagen))
    db.commit()
    cursor.close()
    db.close()
    return redirect('/productos')

#Eliminar producto (solo el  admin)
@app.route('/eliminar_producto/<int:id>')
def eliminar_producto_admin(id):
    if not solo_admin():
        return redirect('/')

    db = get_db()
    cursor = db.cursor()

    #Primero eliminar detalles de pedidos que usen este producto
    cursor.execute("DELETE FROM detalle_pedido WHERE producto_id = %s", (id,))
    #Luego eliminar el producto
    cursor.execute("DELETE FROM productos WHERE id = %s", (id,))

    db.commit()
    cursor.close()
    db.close()
    return redirect('/productos')

# Pagina para ver todos los productos y poder eliminarlos (solo el admin)
@app.route('/eliminar_producto')
def pagina_eliminar_producto():
    if not solo_admin():
        return redirect('/')

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos")
    productos = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('eliminar_producto.html', productos=productos)

# Pagina para ver todos los productos y poder editarlos. (solo el admin)
@app.route('/editar_producto')
def pagina_editar_producto():
    if not solo_admin():
        return redirect('/')

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos")
    productos = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('editar_producto.html', productos=productos)

# Formulario para editar un producto
@app.route('/editar_producto/<int:id>')
def editar_producto_form(id):
    if not solo_admin():
        return redirect('/')

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos WHERE id = %s", (id,))
    producto = cursor.fetchone()
    cursor.close()
    db.close()

    return render_template('editar_producto_form.html', producto=producto)

# Guardar cambios del producto editado
@app.route('/guardar_edicion/<int:id>', methods=['POST'])
def guardar_edicion(id):
    if not solo_admin():
        return redirect('/')

    titulo = request.form['titulo']
    precio = request.form['precio']
    categoria = request.form['categoria']
    imagen = request.form['imagen']

    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        UPDATE productos
        SET titulo = %s, precio = %s, categoria_id = %s, imagen = %s
        WHERE id = %s
    """, (titulo, precio, categoria, imagen, id))
    db.commit()
    cursor.close()
    db.close()

    return redirect('/editar_producto')


# Las funciones de usuarios que pueden hacer solo los admins:

@app.route('/admin_usuarios')
def admin_usuarios():
    if not solo_admin():
        return redirect('/')

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre, correo, rol FROM usuarios")
    usuarios = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('admin_usuarios.html', usuarios=usuarios)


@app.route('/admin_usuarios_editar/<int:id>', methods=['GET', 'POST'])
def admin_usuarios_editar(id):
    if not solo_admin():
        return redirect('/')
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        rol = request.form['rol']

        # El admin no puede cambiar su rol
        if id == 1:
            rol = 'admin'
        cursor.execute("""
            UPDATE usuarios
            SET nombre=%s, correo=%s, rol=%s
            WHERE id=%s
        """, (nombre, correo, rol, id))
        db.commit()
        cursor.close()
        db.close()
        return redirect('/admin_usuarios')
    cursor.execute("SELECT id, nombre, correo, rol FROM usuarios WHERE id=%s", (id,))
    usuario = cursor.fetchone()
    cursor.close()
    db.close()
    return render_template('admin_usuarios_editar.html', usuario=usuario)


@app.route('/admin_usuarios_eliminar/<int:id>')
def admin_usuarios_eliminar(id):
    if not solo_admin():
        return redirect('/')

    # Esto no permite eliminar al admin principal
    if id == 1:
        return "No puedes eliminar al administrador principal"
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id=%s", (id,))
    db.commit()
    cursor.close()
    db.close()
    return redirect('/admin_usuarios')


# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        clave = request.form['clave']
        usuario = buscar_usuario(correo, clave)
        if usuario:
            session['usuario_id'] = usuario['id']
            session['rol'] = usuario['rol']
            return redirect('/')
        return render_template('login.html', error="Datos incorrectos")
    return render_template('login.html')

# Registro
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        registrar_usuario(
            request.form['nombre'],
            request.form['correo'],
            request.form['clave']
        )
        return redirect('/login')
    return render_template('registro.html')

if __name__ == '__main__':
    app.run(debug=True)
