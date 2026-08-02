import os
from db_config import init_db, get_db_connection

def initialize_database():
    """Inicializa la base de datos solo si es necesario"""
    
    # En Render, verificar si las tablas existen
    if os.environ.get('RENDER'):
        print("🚀 Inicializando en Render...")
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Verificar si existe la tabla users
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM information_schema.tables 
                        WHERE table_name = 'users'
                    );
                """)
                exists = cursor.fetchone()[0]
                cursor.close()
                conn.close()
                
                if not exists:
                    print("🔄 Creando tablas por primera vez...")
                    init_db()
                else:
                    print("✅ Tablas ya existen, omitiendo inicialización")
            else:
                print("⚠️ No se pudo conectar a la base de datos")
        except Exception as e:
            print(f"⚠️ Error verificando tablas: {e}")
            print("   Intentando inicializar...")
            init_db()
    else:
        # En desarrollo local, inicializar MySQL
        print("🖥️ Inicializando MySQL en desarrollo...")
        init_db()

# Llamar a la función de inicialización
if __name__ == "__main__":
    initialize_database()