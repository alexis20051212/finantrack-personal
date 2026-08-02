import os
import mysql.connector
from mysql.connector import Error
import psycopg2
import psycopg2.extras

def get_db_connection():
    """Establece conexión según el entorno"""
    
    # En Render con PostgreSQL
    if os.environ.get('RENDER'):
        print("🔄 Modo Render: Conectando a PostgreSQL...")
        return get_postgres_connection()
    
    # En desarrollo local con MySQL
    print("🔄 Modo Desarrollo: Conectando a MySQL...")
    return get_mysql_connection()

def get_postgres_connection():
    """Conectar a PostgreSQL en Render"""
    try:
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            print("❌ No se encontró DATABASE_URL en las variables de entorno")
            print("   Asegúrate de configurar DATABASE_URL en Render")
            return None
        
        print("✅ Conectando a PostgreSQL...")
        # Añadir sslmode si es necesario
        if '?' not in database_url:
            database_url += '?sslmode=require'
        
        conn = psycopg2.connect(database_url)
        print("✅ Conexión a PostgreSQL establecida exitosamente")
        return conn
        
    except Exception as e:
        print(f"❌ Error de conexión a PostgreSQL: {e}")
        return None

def get_mysql_connection():
    """Conectar a MySQL (desarrollo local)"""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='jisa2005',
            database='FinanTrackDB',
            port=3306
        )
        if connection.is_connected():
            print("✅ Conexión a MySQL establecida")
            return connection
    except Error as e:
        print(f"❌ Error de conexión a MySQL: {e}")
        return None
    return None

def init_db():
    """Inicializa la base de datos según el entorno"""
    if os.environ.get('RENDER'):
        print("🔄 Inicializando PostgreSQL en Render...")
        return init_postgres_db()
    else:
        print("🔄 Inicializando MySQL en desarrollo...")
        return init_mysql_db()

def init_postgres_db():
    """Inicializa PostgreSQL en Render"""
    try:
        conn = get_postgres_connection()
        if not conn:
            print("❌ No se pudo conectar a PostgreSQL")
            return False
        
        cursor = conn.cursor()
        
        print("📦 Creando tablas en PostgreSQL...")
        create_tables_postgres(cursor)
        
        conn.commit()
        conn.close()
        print("✅ Base de datos PostgreSQL inicializada correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error inicializando PostgreSQL: {e}")
        return False

def init_mysql_db():
    """Inicializa MySQL (desarrollo local)"""
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='jisa2005',
            port=3306
        )
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS FinanTrackDB")
        cursor.execute("USE FinanTrackDB")
        
        print("📦 Creando tablas en MySQL...")
        create_tables_mysql(cursor)
        
        conn.commit()
        conn.close()
        print("✅ Base de datos MySQL inicializada correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error inicializando MySQL: {e}")
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
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS metas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        usuario_id INT NOT NULL,
        nombre VARCHAR(100) NOT NULL,
        monto_objetivo DECIMAL(10,2) NOT NULL,
        monto_actual DECIMAL(10,2) DEFAULT 0,
        fecha_limite DATE,
        currency VARCHAR(10) DEFAULT 'USD',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES users(id) ON DELETE CASCADE
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS aportaciones_meta (
        id INT AUTO_INCREMENT PRIMARY KEY,
        meta_id INT NOT NULL,
        monto DECIMAL(10,2) NOT NULL,
        fecha DATE NOT NULL,
        descripcion TEXT,
        FOREIGN KEY (meta_id) REFERENCES metas(id) ON DELETE CASCADE
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS presupuestos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        usuario_id INT NOT NULL,
        categoria_id INT NOT NULL,
        mes INT NOT NULL,
        anio INT NOT NULL,
        limite DECIMAL(10,2) NOT NULL,
        currency VARCHAR(10) DEFAULT 'USD',
        FOREIGN KEY (usuario_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (categoria_id) REFERENCES categorias(id),
        UNIQUE KEY unique_presupuesto (usuario_id, categoria_id, mes, anio)
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS recordatorios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        usuario_id INT NOT NULL,
        titulo VARCHAR(100) NOT NULL,
        descripcion TEXT,
        fecha DATE NOT NULL,
        tipo ENUM('pago', 'recordatorio', 'meta') DEFAULT 'recordatorio',
        completado BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (usuario_id) REFERENCES users(id) ON DELETE CASCADE
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS notificaciones (
        id INT AUTO_INCREMENT PRIMARY KEY,
        usuario_id INT NOT NULL,
        mensaje TEXT NOT NULL,
        tipo ENUM('exito', 'alerta', 'info', 'peligro') DEFAULT 'info',
        leido BOOLEAN DEFAULT FALSE,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES users(id) ON DELETE CASCADE
    )''')
    
    print("✅ Tablas MySQL creadas/verificadas")

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
        cursor.execute(
            "INSERT INTO categorias (nombre) SELECT %s WHERE NOT EXISTS (SELECT 1 FROM categorias WHERE nombre = %s)",
            (cat, cat)
        )
    
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
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS metas (
        id SERIAL PRIMARY KEY,
        usuario_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        nombre VARCHAR(100) NOT NULL,
        monto_objetivo DECIMAL(10,2) NOT NULL,
        monto_actual DECIMAL(10,2) DEFAULT 0,
        fecha_limite DATE,
        currency VARCHAR(10) DEFAULT 'USD',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS aportaciones_meta (
        id SERIAL PRIMARY KEY,
        meta_id INT NOT NULL REFERENCES metas(id) ON DELETE CASCADE,
        monto DECIMAL(10,2) NOT NULL,
        fecha DATE NOT NULL,
        descripcion TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS presupuestos (
        id SERIAL PRIMARY KEY,
        usuario_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        categoria_id INT NOT NULL REFERENCES categorias(id),
        mes INT NOT NULL,
        anio INT NOT NULL,
        limite DECIMAL(10,2) NOT NULL,
        currency VARCHAR(10) DEFAULT 'USD',
        UNIQUE(usuario_id, categoria_id, mes, anio)
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS recordatorios (
        id SERIAL PRIMARY KEY,
        usuario_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        titulo VARCHAR(100) NOT NULL,
        descripcion TEXT,
        fecha DATE NOT NULL,
        tipo VARCHAR(20) DEFAULT 'recordatorio',
        completado BOOLEAN DEFAULT FALSE
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS notificaciones (
        id SERIAL PRIMARY KEY,
        usuario_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        mensaje TEXT NOT NULL,
        tipo VARCHAR(20) DEFAULT 'info',
        leido BOOLEAN DEFAULT FALSE,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    print("✅ Tablas PostgreSQL creadas/verificadas")