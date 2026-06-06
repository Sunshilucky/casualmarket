from config import Config
import mysql.connector

def crear_pedido(usuario_id, total):
    db = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO pedidos (usuario_id, fecha, total)
        VALUES (%s, NOW(), %s)
    """, (usuario_id, total))
    db.commit()
    pedido_id = cursor.lastrowid
    cursor.close()
    db.close()
    return pedido_id



def agregar_detalle(pedido_id, producto_id, cantidad, subtotal):
    db = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )
    
    cursor = db.cursor()

    cursor.execute(
        "INSERT INTO detalle_pedido (pedido_id, producto_id, cantidad, subtotal) VALUES (%s, %s, %s, %s)",
        (pedido_id, producto_id, cantidad, subtotal)
    )


    db.commit()
    cursor.close()
    db.close()
    
    