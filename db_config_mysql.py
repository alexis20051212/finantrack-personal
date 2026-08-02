import mysql.connector
from mysql.connector import Error

def get_db_connection():
    """Conectar a MySQL"""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='jisa2005',  # Tu contraseña de MySQL
            database='FinanTrackDB',
            port=3306
        )
        return connection
    except Error as e:
        print(f"Error de conexión MySQL: {e}")
        return None

def init_db_mysql():
    """Inicializar base de datos en MySQL"""
    conn = get_db_connection()
    if not conn:
        # Intentar crear la base de datos primero
        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                port=3306
            )
            cursor = conn.cursor()
            cursor.execute("CREATE DATABASE IF NOT EXISTS FinanTrackDB")
            cursor.execute("USE FinanTrackDB")
            
            # Crear tablas
            cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS categorias (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nombre VARCHAR(50) UNIQUE NOT NULL
            )''')
            
            # Insertar categorías
            categorias = ['Alimentación', 'Transporte', 'Entretenimiento', 'Salud', 'Educación', 'Servicios', 'Otros']
            for cat in categorias:
                cursor.execute("INSERT IGNORE INTO categorias (nombre) VALUES (%s)", (cat,))
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS movimientos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                usuario_id INT NOT NULL,
                tipo ENUM('ingreso', 'gasto') NOT NULL,
                monto DECIMAL(10,2) NOT NULL,
                categoria_id INT NOT NULL,
                descripcion TEXT,
                fecha DATE NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (categoria_id) REFERENCES categorias(id)
            )''')
            
            conn.commit()
            conn.close()
            print("✅ Base de datos MySQL inicializada")
            return True
        except Error as e:
            print(f"❌ Error MySQL: {e}")
            return False
    return True

# Inicializar
init_db_mysql()