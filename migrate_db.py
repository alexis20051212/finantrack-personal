# migrate_db.py
import mysql.connector
from mysql.connector import Error

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'jisa2005',
    'database': 'FinanTrackDB',
    'port': 3306
}

def agregar_columna_si_no_existe(cursor, tabla, columna, definicion):
    """Agrega una columna a una tabla si no existe"""
    try:
        cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
        print(f"✅ Columna '{columna}' agregada a '{tabla}'")
        return True
    except Error as e:
        if "Duplicate column name" in str(e):
            print(f"ℹ️ Columna '{columna}' ya existe en '{tabla}'")
            return True
        else:
            print(f"⚠️ Error al agregar '{columna}' a '{tabla}': {e}")
            return False

def migrate_database():
    """Agrega las nuevas columnas para soportar múltiples divisas"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("🔧 Iniciando migración de base de datos...")
        print("="*50)
        
        # 1. Agregar columna a users
        print("\n📌 Tabla: users")
        agregar_columna_si_no_existe(cursor, "users", "default_currency", "VARCHAR(10) DEFAULT 'USD'")
        
        # 2. Agregar columna a movimientos
        print("\n📌 Tabla: movimientos")
        agregar_columna_si_no_existe(cursor, "movimientos", "currency", "VARCHAR(10) DEFAULT 'USD'")
        
        # 3. Agregar columna a metas
        print("\n📌 Tabla: metas")
        agregar_columna_si_no_existe(cursor, "metas", "currency", "VARCHAR(10) DEFAULT 'USD'")
        
        # 4. Agregar columna a presupuestos
        print("\n📌 Tabla: presupuestos")
        agregar_columna_si_no_existe(cursor, "presupuestos", "currency", "VARCHAR(10) DEFAULT 'USD'")
        
        # Confirmar cambios
        conn.commit()
        
        print("\n" + "="*50)
        print("✅ Migración completada exitosamente!")
        
        # Mostrar estructura de las tablas
        print("\n📊 Estructura de tablas actualizada:")
        tablas = ['users', 'movimientos', 'metas', 'presupuestos']
        for tabla in tablas:
            cursor.execute(f"DESCRIBE {tabla}")
            resultados = cursor.fetchall()
            print(f"\nTabla: {tabla}")
            for col in resultados:
                if col[0] in ['default_currency', 'currency']:
                    print(f"  ✅ {col[0]} - {col[1]} (agregada)")
        
    except Error as e:
        print(f"❌ Error en la migración: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
            print("\n🔌 Conexión cerrada")

if __name__ == '__main__':
    migrate_database()