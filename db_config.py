import os
import mysql.connector
from mysql.connector import Error
import psycopg2
import sqlite3

def get_db_connection():
    """Establece conexión según el entorno"""
    
    # En Render con PostgreSQL
    if os.environ.get('RENDER'):
        return get_postgres_connection()
    
    # En desarrollo con MySQL
    return get_mysql_connection()

def get_mysql_connection():
    """Conectar a MySQL (desarrollo)"""
    try:
        from config import Config
        config = Config()
        connection = mysql.connector.connect(**config.DB_CONFIG)
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"❌ Error de conexión a MySQL: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_postgres_connection():
    """Conectar a PostgreSQL (producción en Render)"""
    try:
        from config import Config
        config = Config()
        conn = psycopg2.connect(
            host=config.DB_CONFIG['host'],
            user=config.DB_CONFIG['user'],
            password=config.DB_CONFIG['password'],
            database=config.DB_CONFIG['database'],
            port=config.DB_CONFIG['port']
        )
        return conn
    except Exception as e:
        print(f"❌ Error de conexión a PostgreSQL: {e}")
        return None

def init_db():
    """Inicializa la base de datos según el entorno"""
    if os.environ.get('RENDER'):
        return init_postgres_db()
    return init_mysql_db()

def init_mysql_db():
    """Inicializa MySQL (desarrollo)"""
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='jisa2005',
            port=3306
        )
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS FinanTrackDB")
        cursor.execute("USE FinanTrackDB")
        
        # Crear todas las tablas (usando tu código existente)
        create_tables_mysql(cursor)
        
        conn.commit()
        conn.close()
        print("✅ Base de datos MySQL inicializada correctamente")
        return True
    except Exception as e:
        print(f"❌ Error inicializando MySQL: {e}")
        return False

def init_postgres_db():
    """Inicializa PostgreSQL (producción)"""
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        
        # Crear tablas en PostgreSQL
        create_tables_postgres(cursor)
        
        conn.commit()
        conn.close()
        print("✅ Base de datos PostgreSQL inicializada correctamente")
        return True
    except Exception as e:
        print(f"❌ Error inicializando PostgreSQL: {e}")
        return False

def create_tables_mysql(cursor):
    """Crear tablas en MySQL"""
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre VARCHAR(100) NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        telefono VARCHAR(20) NULL,
        password VARCHAR(255) NOT NULL,
        default_currency VARCHAR(10) DEFAULT 'USD',
        fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS categorias (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nombre VARCHAR(50) UNIQUE NOT NULL
    )''')
    
    categorias = [
        'Alimentación', 'Transporte', 'Entretenimiento', 'Salud', 'Educación',
        'Servicios', 'Otros', 'Trabajo', 'Inversión', 'Compras', 'Vivienda',
        'Mascotas', 'Regalos', 'Suscripciones', 'Deportes', 'Viajes', 'Tecnología'
    ]
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
        currency VARCHAR(10) DEFAULT 'USD',
        FOREIGN KEY (usuario_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (categoria_id) REFERENCES categorias(id)
    )''')
    
    # Resto de tablas (metas, presupuestos, etc.)

def create_tables_postgres(cursor):
    """Crear tablas en PostgreSQL"""
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(100) NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        telefono VARCHAR(20),
        password VARCHAR(255) NOT NULL,
        default_currency VARCHAR(10) DEFAULT 'USD',
        fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS categorias (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(50) UNIQUE NOT NULL
    )''')
    
    categorias = [
        'Alimentación', 'Transporte', 'Entretenimiento', 'Salud', 'Educación',
        'Servicios', 'Otros', 'Trabajo', 'Inversión', 'Compras', 'Vivienda',
        'Mascotas', 'Regalos', 'Suscripciones', 'Deportes', 'Viajes', 'Tecnología'
    ]
    for cat in categorias:
        cursor.execute("INSERT INTO categorias (nombre) SELECT %s WHERE NOT EXISTS (SELECT 1 FROM categorias WHERE nombre = %s)", (cat, cat))
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS movimientos (
        id SERIAL PRIMARY KEY,
        usuario_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        tipo VARCHAR(10) NOT NULL,
        monto DECIMAL(10,2) NOT NULL,
        categoria_id INT NOT NULL REFERENCES categorias(id),
        descripcion TEXT,
        fecha DATE NOT NULL,
        currency VARCHAR(10) DEFAULT 'USD'
    )''')
    
    # Resto de tablas (metas, presupuestos, etc.)

# Inicializar la base de datos
init_db()