from config import Config
import mysql.connector

def buscar_usuario(correo, clave):
    db = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )
    
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE correo = %s AND contraseña = %s", (correo, clave))
    usuario = cursor.fetchone()
    cursor.close()
    db.close()
    return usuario


def registrar_usuario(nombre, correo, clave):
    db = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )
    
    cursor = db.cursor()
    cursor.execute("INSERT INTO usuarios (nombre, correo, contraseña) VALUES (%s, %s, %s)", (nombre, correo, clave))
    db.commit()
    cursor.close()
    db.close()
    
    