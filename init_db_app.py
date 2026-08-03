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
                users_exists = cursor.fetchone()[0]
                
                # Verificar si existe la tabla aportaciones_meta
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM information_schema.tables 
                        WHERE table_name = 'aportaciones_meta'
                    );
                """)
                aportaciones_exists = cursor.fetchone()[0]
                
                cursor.close()
                conn.close()
                
                if not users_exists:
                    print("🔄 Creando todas las tablas por primera vez...")
                    init_db()
                elif not aportaciones_exists:
                    print("🔄 Creando tabla 'aportaciones_meta'...")
                    # Crear solo la tabla que falta
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS aportaciones_meta (
                                id SERIAL PRIMARY KEY,
                                meta_id INT NOT NULL REFERENCES metas(id) ON DELETE CASCADE,
                                monto DECIMAL(10,2) NOT NULL,
                                fecha DATE NOT NULL,
                                descripcion TEXT
                            );
                        """)
                        conn.commit()
                        cursor.close()
                        conn.close()
                        print("✅ Tabla 'aportaciones_meta' creada exitosamente")
                else:
                    print("✅ Todas las tablas ya existen, omitiendo inicialización")
            else:
                print("⚠️ No se pudo conectar a la base de datos")
        except Exception as e:
            print(f"⚠️ Error verificando tablas: {e}")
            print("   Intentando inicialización completa...")
            init_db()
    else:
        # En desarrollo local, inicializar MySQL
        print("🖥️ Inicializando MySQL en desarrollo...")
        init_db()

# Llamar a la función de inicialización
if __name__ == "__main__":
    initialize_database()