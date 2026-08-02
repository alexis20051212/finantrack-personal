import os
import json

class Config:
    # Configuración general
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tu-clave-secreta-para-flask'
    
    # ==================== DATABASE ====================
    # Detectar entorno
    ENV = os.environ.get('FLASK_ENV', 'development')
    RENDER = os.environ.get('RENDER', False)
    
    if RENDER:
        # Render usa PostgreSQL con URL
        DATABASE_URL = os.environ.get('DATABASE_URL')
        
        if DATABASE_URL:
            # Parsear URL de PostgreSQL
            import re
            # Ejemplo: postgresql://user:password@host:port/database
            pattern = r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)'
            match = re.match(pattern, DATABASE_URL)
            
            if match:
                user, password, host, port, database = match.groups()
                DB_CONFIG = {
                    'host': host,
                    'user': user,
                    'password': password,
                    'database': database,
                    'port': int(port),
                    'use_pure': True
                }
            else:
                # Si no se puede parsear, usar variables individuales
                DB_CONFIG = {
                    'host': os.environ.get('PGHOST', 'localhost'),
                    'user': os.environ.get('PGUSER', 'postgres'),
                    'password': os.environ.get('PGPASSWORD', ''),
                    'database': os.environ.get('PGDATABASE', 'postgres'),
                    'port': int(os.environ.get('PGPORT', 5432)),
                    'use_pure': True
                }
        else:
            # Fallback a SQLite en Render
            DB_CONFIG = None
            print("⚠️ Usando SQLite en Render (sin DATABASE_URL)")
    else:
        # Desarrollo: MySQL
        DB_CONFIG = {
            'host': os.environ.get('MYSQL_HOST', 'localhost'),
            'user': os.environ.get('MYSQL_USER', 'root'),
            'password': os.environ.get('MYSQL_PASSWORD', 'jisa2005'),
            'database': os.environ.get('MYSQL_DB', 'FinanTrackDB'),
            'port': int(os.environ.get('MYSQL_PORT', 3306)),
            'use_pure': True
        }
    
    # ==================== EXCHANGE RATE API ====================
    EXCHANGE_RATE_API_KEY = os.environ.get('EXCHANGE_RATE_API_KEY', '')
    
    # ==================== OTRAS CONFIGURACIONES ====================
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    TESTING = False

# Diccionario de configuraciones disponibles
config = {
    'development': Config,
    'production': Config,
    'default': Config
}

# Para compatibilidad con código existente
DevelopmentConfig = Config
ProductionConfig = Config