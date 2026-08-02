from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from functools import wraps
import mysql.connector
from mysql.connector import Error
from calendar import monthrange
from io import BytesIO
from exchange_api import exchange_api, COMMON_CURRENCIES
from fred_api import fred_api, FRED_SERIES
from db_config import get_db_connection, get_dict_cursor
import os

app = Flask(__name__)
app.secret_key = 'FinanTrack_MySQL_Clave_Segura_2024'

# ==================== DECORADOR ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== NOTIFICACIONES Y RECORDATORIOS ====================

def crear_notificacion(usuario_id, mensaje, tipo='info'):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notificaciones (usuario_id, mensaje, tipo)
            VALUES (%s, %s, %s)
        """, (usuario_id, mensaje, tipo))
        conn.commit()
        cursor.close()
        conn.close()

def verificar_presupuestos_notificacion(usuario_id):
    conn = get_db_connection()
    if not conn:
        return
    cursor = get_dict_cursor(conn)
    
    mes_actual = datetime.now().month
    anio_actual = datetime.now().year
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT c.nombre as categoria, p.limite, COALESCE(SUM(m.monto), 0) as gastado
            FROM presupuestos p
            JOIN categorias c ON p.categoria_id = c.id
            LEFT JOIN movimientos m ON c.id = m.categoria_id 
                AND m.tipo = 'gasto' AND m.usuario_id = %s
                AND EXTRACT(MONTH FROM m.fecha) = %s AND EXTRACT(YEAR FROM m.fecha) = %s
            WHERE p.usuario_id = %s AND p.mes = %s AND p.anio = %s
            GROUP BY c.id, c.nombre, p.limite
            HAVING gastado > limite
        """, (usuario_id, mes_actual, anio_actual, usuario_id, mes_actual, anio_actual))
    else:
        cursor.execute("""
            SELECT c.nombre as categoria, p.limite, COALESCE(SUM(m.monto), 0) as gastado
            FROM presupuestos p
            JOIN categorias c ON p.categoria_id = c.id
            LEFT JOIN movimientos m ON c.id = m.categoria_id 
                AND m.tipo = 'gasto' AND m.usuario_id = %s
                AND MONTH(m.fecha) = %s AND YEAR(m.fecha) = %s
            WHERE p.usuario_id = %s AND p.mes = %s AND p.anio = %s
            GROUP BY c.id, c.nombre, p.limite
            HAVING gastado > limite
        """, (usuario_id, mes_actual, anio_actual, usuario_id, mes_actual, anio_actual))
    
    presupuestos_excedidos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    for p in presupuestos_excedidos:
        porcentaje = (p['gastado'] / p['limite'] * 100)
        mensaje = f"Has excedido el presupuesto de {p['categoria']} en {porcentaje:.0f}% (${p['gastado'] - p['limite']:,.2f})"
        crear_notificacion(usuario_id, mensaje, 'peligro')

def verificar_recordatorios_pendientes():
    conn = get_db_connection()
    if not conn:
        return
    cursor = get_dict_cursor(conn)
    
    fecha_limite = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT r.*, u.email, u.nombre as usuario_nombre
            FROM recordatorios r
            JOIN users u ON r.usuario_id = u.id
            WHERE r.fecha <= %s AND r.fecha >= CURRENT_DATE AND r.completado = FALSE
        """, (fecha_limite,))
    else:
        cursor.execute("""
            SELECT r.*, u.email, u.nombre as usuario_nombre
            FROM recordatorios r
            JOIN users u ON r.usuario_id = u.id
            WHERE r.fecha <= %s AND r.fecha >= CURDATE() AND r.completado = FALSE
        """, (fecha_limite,))
    
    recordatorios = cursor.fetchall()
    cursor.close()
    conn.close()
    
    for r in recordatorios:
        dias = (r['fecha'] - datetime.now().date()).days
        if dias == 0:
            mensaje = f"HOY: {r['titulo']}"
        elif dias == 1:
            mensaje = f"Mañana: {r['titulo']}"
        else:
            mensaje = f"En {dias} días: {r['titulo']}"
        
        if r['descripcion']:
            mensaje += f" - {r['descripcion']}"
        
        crear_notificacion(r['usuario_id'], mensaje, 'alerta')

def convertir_movimiento_a_moneda(monto, from_currency='USD', to_currency=None):
    """Convierte un monto a la moneda del usuario"""
    if to_currency is None:
        to_currency = session.get('default_currency', 'USD')
    
    if from_currency == to_currency:
        return monto
    
    converted = exchange_api.convert_currency(monto, from_currency, to_currency)
    return converted if converted is not None else monto

# ==================== CAMBIAR TEMA ====================
@app.route('/cambiar-tema', methods=['GET', 'POST'])
def cambiar_tema():
    if request.method == 'POST':
        data = request.get_json()
        nuevo_tema = data.get('tema', 'dark')
        session['tema'] = nuevo_tema
        return {'tema': nuevo_tema}
    else:
        tema_actual = session.get('tema', 'dark')
        return {'tema': tema_actual}

# ==================== RUTAS PRINCIPALES ====================
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip().lower()
        telefono = request.form.get('telefono', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        default_currency = request.form.get('default_currency', 'USD')
        
        errores = []
        
        if not nombre or not email or not password:
            errores.append('Todos los campos son obligatorios')
        
        if telefono and not telefono.isdigit():
            errores.append('El teléfono solo debe contener números')
        
        if len(password) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres')
        
        if not any(c.isupper() for c in password):
            errores.append('La contraseña debe contener al menos una letra mayúscula')
        
        caracteres_especiales = "!@#$%^&*(),.?\":{}|<>"
        if not any(c in caracteres_especiales for c in password):
            errores.append('La contraseña debe contener al menos un carácter especial (!@#$%^&*)')
        
        if password != confirm_password:
            errores.append('Las contraseñas no coinciden')
        
        if errores:
            for error in errores:
                flash(error, 'danger')
            return render_template('register.html', currencies=COMMON_CURRENCIES)
        
        conn = get_db_connection()
        if not conn:
            flash('Error de conexión a la base de datos', 'danger')
            return render_template('register.html', currencies=COMMON_CURRENCIES)
        
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('Este correo ya está registrado', 'danger')
                return render_template('register.html', currencies=COMMON_CURRENCIES)
            
            hashed_password = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (nombre, email, telefono, password, default_currency) VALUES (%s, %s, %s, %s, %s)",
                (nombre, email, telefono if telefono else None, hashed_password, default_currency)
            )
            conn.commit()
            
            if not os.environ.get('RENDER'):
                user_id = cursor.lastrowid
            else:
                # PostgreSQL usa RETURNING para obtener el ID
                cursor.execute("SELECT lastval()")
                user_id = cursor.fetchone()[0]
            
            crear_notificacion(user_id, '¡Bienvenido a FinanTrack! Comienza registrando tus primeros movimientos.', 'exito')
            
            flash('¡Registro exitoso!', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            print(f"Error: {e}")
            flash('Error en la base de datos', 'danger')
            return render_template('register.html', currencies=COMMON_CURRENCIES)
        finally:
            cursor.close()
            conn.close()
    
    return render_template('register.html', currencies=COMMON_CURRENCIES)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Email y contraseña son obligatorios', 'danger')
            return render_template('login.html')
        
        conn = get_db_connection()
        if not conn:
            flash('Error de conexión', 'danger')
            return render_template('login.html')
        
        cursor = get_dict_cursor(conn)
        
        try:
            cursor.execute("SELECT id, nombre, password, default_currency FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['user_name'] = user['nombre']
                session['default_currency'] = user['default_currency'] or 'USD'
                flash(f'¡Bienvenido {user["nombre"]}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Email o contraseña incorrectos', 'danger')
        except Exception as e:
            print(f"Error: {e}")
            flash('Error al iniciar sesión', 'danger')
        finally:
            cursor.close()
            conn.close()
    
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    if not conn:
        flash('Error de conexión', 'danger')
        return redirect(url_for('login'))
    
    cursor = get_dict_cursor(conn)
    user_currency = session.get('default_currency', 'USD')
    
    mes_actual = datetime.now().month
    anio_actual = datetime.now().year
    mes_anterior = mes_actual - 1 if mes_actual > 1 else 12
    anio_anterior = anio_actual if mes_actual > 1 else anio_actual - 1
    
    verificar_presupuestos_notificacion(session['user_id'])
    verificar_recordatorios_pendientes()
    
    meses_nombres = []
    ingresos_mensuales = []
    gastos_mensuales = []
    
    for i in range(5, -1, -1):
        mes_num = mes_actual - i
        año_num = anio_actual
        if mes_num <= 0:
            mes_num += 12
            año_num -= 1
        
        meses_nombres.append(date(2000, mes_num, 1).strftime('%b'))
        
        if os.environ.get('RENDER'):
            cursor.execute("""
                SELECT COALESCE(SUM(monto), 0) as total FROM movimientos 
                WHERE usuario_id = %s AND tipo = 'ingreso' 
                AND EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s
            """, (session['user_id'], mes_num, año_num))
        else:
            cursor.execute("""
                SELECT COALESCE(SUM(monto), 0) as total FROM movimientos 
                WHERE usuario_id = %s AND tipo = 'ingreso' 
                AND MONTH(fecha) = %s AND YEAR(fecha) = %s
            """, (session['user_id'], mes_num, año_num))
        ingresos_mensuales.append(float(cursor.fetchone()['total'] or 0))
        
        if os.environ.get('RENDER'):
            cursor.execute("""
                SELECT COALESCE(SUM(monto), 0) as total FROM movimientos 
                WHERE usuario_id = %s AND tipo = 'gasto'
                AND EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s
            """, (session['user_id'], mes_num, año_num))
        else:
            cursor.execute("""
                SELECT COALESCE(SUM(monto), 0) as total FROM movimientos 
                WHERE usuario_id = %s AND tipo = 'gasto'
                AND MONTH(fecha) = %s AND YEAR(fecha) = %s
            """, (session['user_id'], mes_num, año_num))
        gastos_mensuales.append(float(cursor.fetchone()['total'] or 0))
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT c.nombre as categoria_nombre, COALESCE(SUM(m.monto), 0) as total
            FROM categorias c
            JOIN movimientos m ON c.id = m.categoria_id 
                AND m.tipo = 'gasto' AND m.usuario_id = %s
                AND EXTRACT(MONTH FROM m.fecha) = %s AND EXTRACT(YEAR FROM m.fecha) = %s
            GROUP BY c.id, c.nombre
            HAVING total > 0 ORDER BY total DESC LIMIT 6
        """, (session['user_id'], mes_actual, anio_actual))
    else:
        cursor.execute("""
            SELECT c.nombre as categoria_nombre, COALESCE(SUM(m.monto), 0) as total
            FROM categorias c
            JOIN movimientos m ON c.id = m.categoria_id 
                AND m.tipo = 'gasto' AND m.usuario_id = %s
                AND MONTH(m.fecha) = %s AND YEAR(m.fecha) = %s
            GROUP BY c.id, c.nombre
            HAVING total > 0 ORDER BY total DESC LIMIT 6
        """, (session['user_id'], mes_actual, anio_actual))
    categorias_top = cursor.fetchall()
    
    categorias_nombres = [cat['categoria_nombre'] for cat in categorias_top]
    categorias_totales = [float(cat['total']) for cat in categorias_top]
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0) as total FROM movimientos 
            WHERE usuario_id = %s AND tipo = 'ingreso' 
            AND EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s
        """, (session['user_id'], mes_actual, anio_actual))
    else:
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0) as total FROM movimientos 
            WHERE usuario_id = %s AND tipo = 'ingreso' 
            AND MONTH(fecha) = %s AND YEAR(fecha) = %s
        """, (session['user_id'], mes_actual, anio_actual))
    total_ingresos = cursor.fetchone()['total'] or 0
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0) as total FROM movimientos 
            WHERE usuario_id = %s AND tipo = 'gasto'
            AND EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s
        """, (session['user_id'], mes_actual, anio_actual))
    else:
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0) as total FROM movimientos 
            WHERE usuario_id = %s AND tipo = 'gasto'
            AND MONTH(fecha) = %s AND YEAR(fecha) = %s
        """, (session['user_id'], mes_actual, anio_actual))
    total_gastos = cursor.fetchone()['total'] or 0
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0) as total FROM movimientos 
            WHERE usuario_id = %s AND tipo = 'ingreso' 
            AND EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s
        """, (session['user_id'], mes_anterior, anio_anterior))
    else:
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0) as total FROM movimientos 
            WHERE usuario_id = %s AND tipo = 'ingreso' 
            AND MONTH(fecha) = %s AND YEAR(fecha) = %s
        """, (session['user_id'], mes_anterior, anio_anterior))
    ingresos_anterior = cursor.fetchone()['total'] or 0
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0) as total FROM movimientos 
            WHERE usuario_id = %s AND tipo = 'gasto'
            AND EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s
        """, (session['user_id'], mes_anterior, anio_anterior))
    else:
        cursor.execute("""
            SELECT COALESCE(SUM(monto), 0) as total FROM movimientos 
            WHERE usuario_id = %s AND tipo = 'gasto'
            AND MONTH(fecha) = %s AND YEAR(fecha) = %s
        """, (session['user_id'], mes_anterior, anio_anterior))
    gastos_anterior = cursor.fetchone()['total'] or 0
    
    variacion_ingresos = ((total_ingresos - ingresos_anterior) / ingresos_anterior * 100) if ingresos_anterior > 0 else 0
    variacion_gastos = ((total_gastos - gastos_anterior) / gastos_anterior * 100) if gastos_anterior > 0 else 0
    
    balance = total_ingresos - total_gastos
    ahorro = balance if balance > 0 else 0
    
    dias_del_mes = monthrange(anio_actual, mes_actual)[1]
    gasto_diario_promedio = total_gastos / dias_del_mes if dias_del_mes > 0 else 0
    
    cursor.execute("SELECT COUNT(*) as total FROM movimientos WHERE usuario_id = %s", (session['user_id'],))
    total_transacciones = cursor.fetchone()['total'] or 0
    
    porcentaje_meta = 100 if total_ingresos > 0 and balance >= 0 else (balance / total_ingresos * 100) if total_ingresos > 0 else 0
    porcentaje_meta = max(0, min(100, porcentaje_meta))
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT c.nombre as categoria_nombre, COALESCE(SUM(m.monto), 0) as total
            FROM categorias c
            JOIN movimientos m ON c.id = m.categoria_id 
                AND m.tipo = 'gasto' AND m.usuario_id = %s
                AND EXTRACT(MONTH FROM m.fecha) = %s AND EXTRACT(YEAR FROM m.fecha) = %s
            GROUP BY c.id, c.nombre
            HAVING total > 0 ORDER BY total DESC LIMIT 3
        """, (session['user_id'], mes_actual, anio_actual))
    else:
        cursor.execute("""
            SELECT c.nombre as categoria_nombre, COALESCE(SUM(m.monto), 0) as total
            FROM categorias c
            JOIN movimientos m ON c.id = m.categoria_id 
                AND m.tipo = 'gasto' AND m.usuario_id = %s
                AND MONTH(m.fecha) = %s AND YEAR(m.fecha) = %s
            GROUP BY c.id, c.nombre
            HAVING total > 0 ORDER BY total DESC LIMIT 3
        """, (session['user_id'], mes_actual, anio_actual))
    top_categorias_raw = cursor.fetchall()
    
    top_categorias = []
    if total_gastos > 0:
        for item in top_categorias_raw:
            top_categorias.append({
                'categoria_nombre': item['categoria_nombre'],
                'total': item['total'],
                'porcentaje': (item['total'] / total_gastos) * 100
            })
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT c.nombre as categoria_nombre, COALESCE(SUM(m.monto), 0) as total
            FROM categorias c
            LEFT JOIN movimientos m ON c.id = m.categoria_id 
                AND m.tipo = 'gasto' AND m.usuario_id = %s
                AND EXTRACT(MONTH FROM m.fecha) = %s AND EXTRACT(YEAR FROM m.fecha) = %s
            GROUP BY c.id, c.nombre
            HAVING total > 0 ORDER BY total DESC
        """, (session['user_id'], mes_actual, anio_actual))
    else:
        cursor.execute("""
            SELECT c.nombre as categoria_nombre, COALESCE(SUM(m.monto), 0) as total
            FROM categorias c
            LEFT JOIN movimientos m ON c.id = m.categoria_id 
                AND m.tipo = 'gasto' AND m.usuario_id = %s
                AND MONTH(m.fecha) = %s AND YEAR(m.fecha) = %s
            GROUP BY c.id, c.nombre
            HAVING total > 0 ORDER BY total DESC
        """, (session['user_id'], mes_actual, anio_actual))
    gastos_por_categoria_raw = cursor.fetchall()
    
    gastos_por_categoria = []
    if total_gastos > 0:
        for item in gastos_por_categoria_raw:
            gastos_por_categoria.append({
                'categoria_nombre': item['categoria_nombre'],
                'total': item['total'],
                'porcentaje': (item['total'] / total_gastos) * 100
            })
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT c.nombre as categoria_nombre, COALESCE(SUM(m.monto), 0) as total
            FROM categorias c
            LEFT JOIN movimientos m ON c.id = m.categoria_id 
                AND m.tipo = 'ingreso' AND m.usuario_id = %s
                AND EXTRACT(MONTH FROM m.fecha) = %s AND EXTRACT(YEAR FROM m.fecha) = %s
            GROUP BY c.id, c.nombre
            HAVING total > 0 ORDER BY total DESC
        """, (session['user_id'], mes_actual, anio_actual))
    else:
        cursor.execute("""
            SELECT c.nombre as categoria_nombre, COALESCE(SUM(m.monto), 0) as total
            FROM categorias c
            LEFT JOIN movimientos m ON c.id = m.categoria_id 
                AND m.tipo = 'ingreso' AND m.usuario_id = %s
                AND MONTH(m.fecha) = %s AND YEAR(m.fecha) = %s
            GROUP BY c.id, c.nombre
            HAVING total > 0 ORDER BY total DESC
        """, (session['user_id'], mes_actual, anio_actual))
    ingresos_por_categoria_raw = cursor.fetchall()
    
    ingresos_por_categoria = []
    if total_ingresos > 0:
        for item in ingresos_por_categoria_raw:
            ingresos_por_categoria.append({
                'categoria_nombre': item['categoria_nombre'],
                'total': item['total'],
                'porcentaje': (item['total'] / total_ingresos) * 100
            })
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT m.id, m.tipo, m.monto, m.descripcion, 
                   TO_CHAR(m.fecha, 'DD/MM/YYYY') as fecha, 
                   c.nombre as categoria_nombre, m.currency
            FROM movimientos m
            JOIN categorias c ON m.categoria_id = c.id
            WHERE m.usuario_id = %s
            ORDER BY m.fecha DESC, m.id DESC
            LIMIT 10
        """, (session['user_id'],))
    else:
        cursor.execute("""
            SELECT m.id, m.tipo, m.monto, m.descripcion, 
                   DATE_FORMAT(m.fecha, '%d/%m/%Y') as fecha, 
                   c.nombre as categoria_nombre, m.currency
            FROM movimientos m
            JOIN categorias c ON m.categoria_id = c.id
            WHERE m.usuario_id = %s
            ORDER BY m.fecha DESC, m.id DESC
            LIMIT 10
        """, (session['user_id'],))
    ultimos_movimientos = cursor.fetchall()
    
    cursor.execute("""
        SELECT COUNT(*) as total FROM notificaciones 
        WHERE usuario_id = %s AND leido = FALSE
    """, (session['user_id'],))
    notificaciones_no_leidas = cursor.fetchone()['total'] or 0
    
    # Consejo del zorro
    consejo_zorro = {}
    
    if total_ingresos == 0 and total_gastos == 0:
        consejo_zorro = {
            'icono': '🦊',
            'titulo': '¡Bienvenido a FinanTrack!',
            'mensaje': 'Comienza registrando tus primeros ingresos y gastos.',
            'color': '#60A5FA',
            'accion': 'agregar_movimiento',
            'texto_boton': 'Primer Movimiento'
        }
    elif balance > 500:
        consejo_zorro = {
            'icono': '🏆',
            'titulo': '¡Excelente ahorro!',
            'mensaje': f'Has ahorrado ${balance:.2f} este mes. ¡Sigue así!',
            'color': '#34D399',
            'accion': None,
            'texto_boton': None
        }
    elif balance > 0:
        consejo_zorro = {
            'icono': '👍',
            'titulo': 'Buen trabajo',
            'mensaje': f'Has ahorrado ${balance:.2f} este mes.',
            'color': '#FBBF24',
            'accion': None,
            'texto_boton': None
        }
    elif balance == 0 and total_ingresos > 0:
        consejo_zorro = {
            'icono': '⚖️',
            'titulo': 'Balance en cero',
            'mensaje': 'Tus ingresos igualan a tus gastos. Busca formas de ahorrar.',
            'color': '#FBBF24',
            'accion': None,
            'texto_boton': None
        }
    elif balance < 0:
        consejo_zorro = {
            'icono': '⚠️',
            'titulo': 'Cuidado',
            'mensaje': f'Tus gastos superan tus ingresos por ${abs(balance):.2f}.',
            'color': '#F87171',
            'accion': None,
            'texto_boton': None
        }
    elif total_gastos == 0 and total_ingresos > 0:
        consejo_zorro = {
            'icono': '💰',
            'titulo': '¡Puro ingreso!',
            'mensaje': 'Registra tus gastos para tener una visión completa.',
            'color': '#34D399',
            'accion': 'agregar_movimiento',
            'texto_boton': 'Registrar Gasto'
        }
    elif total_ingresos == 0 and total_gastos > 0:
        consejo_zorro = {
            'icono': '📉',
            'titulo': 'Sin ingresos',
            'mensaje': 'Agrega tus fuentes de ingreso.',
            'color': '#FBBF24',
            'accion': 'agregar_movimiento',
            'texto_boton': 'Registrar Ingreso'
        }
    else:
        consejo_zorro = {
            'icono': '🦊',
            'titulo': 'Consejo del día',
            'mensaje': 'Mantén un registro constante de tus gastos.',
            'color': '#60A5FA',
            'accion': None,
            'texto_boton': None
        }
    
    cursor.close()
    conn.close()
    
    return render_template('dashboard.html', 
                         nombre=session['user_name'],
                         total_ingresos=total_ingresos,
                         total_gastos=total_gastos,
                         balance=balance,
                         ahorro=ahorro,
                         variacion_ingresos=variacion_ingresos,
                         variacion_gastos=variacion_gastos,
                         gasto_diario_promedio=gasto_diario_promedio,
                         total_transacciones=total_transacciones,
                         porcentaje_meta=porcentaje_meta,
                         top_categorias=top_categorias,
                         gastos_por_categoria=gastos_por_categoria,
                         ingresos_por_categoria=ingresos_por_categoria,
                         movimientos=ultimos_movimientos,
                         meses_nombres=meses_nombres,
                         ingresos_mensuales=ingresos_mensuales,
                         gastos_mensuales=gastos_mensuales,
                         categorias_nombres=categorias_nombres,
                         categorias_totales=categorias_totales,
                         consejo_zorro=consejo_zorro,
                         notificaciones_no_leidas=notificaciones_no_leidas,
                         user_currency=user_currency,
                         currencies=COMMON_CURRENCIES)

# ==================== CRUD MOVIMIENTOS ====================
@app.route('/agregar-movimiento', methods=['GET', 'POST'])
@login_required
def agregar_movimiento():
    conn = get_db_connection()
    if not conn:
        flash('Error de conexión', 'danger')
        return redirect(url_for('dashboard'))
    
    cursor = get_dict_cursor(conn)
    cursor.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
    categorias = cursor.fetchall()
    cursor.close()
    conn.close()
    
    user_currency = session.get('default_currency', 'USD')
    
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        categoria_id = request.form.get('categoria_id')
        monto = float(request.form.get('monto'))
        descripcion = request.form.get('descripcion', '')
        fecha = request.form.get('fecha')
        currency = request.form.get('currency', user_currency)
        
        if not fecha:
            fecha = datetime.now().strftime('%Y-%m-%d')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO movimientos (usuario_id, tipo, monto, categoria_id, descripcion, fecha, currency)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (session['user_id'], tipo, monto, categoria_id, descripcion, fecha, currency))
        conn.commit()
        cursor.close()
        conn.close()
        
        crear_notificacion(session['user_id'], f"Movimiento registrado: {tipo} de ${monto:,.2f} {currency}", 'exito')
        
        flash('Movimiento agregado', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('movimiento.html', categorias=categorias, movimiento=None, currencies=COMMON_CURRENCIES, user_currency=user_currency)

@app.route('/editar-movimiento/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_movimiento(id):
    conn = get_db_connection()
    if not conn:
        flash('Error de conexión', 'danger')
        return redirect(url_for('dashboard'))
    
    cursor = get_dict_cursor(conn)
    user_currency = session.get('default_currency', 'USD')
    
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        categoria_id = request.form.get('categoria_id')
        monto = float(request.form.get('monto'))
        descripcion = request.form.get('descripcion', '')
        fecha = request.form.get('fecha')
        currency = request.form.get('currency', user_currency)
        
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE movimientos 
            SET tipo=%s, monto=%s, categoria_id=%s, descripcion=%s, fecha=%s, currency=%s
            WHERE id=%s AND usuario_id=%s
        """, (tipo, monto, categoria_id, descripcion, fecha, currency, id, session['user_id']))
        conn.commit()
        cursor.close()
        conn.close()
        
        crear_notificacion(session['user_id'], f"Movimiento editado correctamente", 'info')
        
        flash('Movimiento actualizado', 'success')
        return redirect(url_for('dashboard'))
    
    cursor = get_dict_cursor(conn)
    cursor.execute("SELECT * FROM movimientos WHERE id=%s AND usuario_id=%s", (id, session['user_id']))
    movimiento = cursor.fetchone()
    cursor.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
    categorias = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not movimiento:
        flash('Movimiento no encontrado', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('movimiento.html', categorias=categorias, movimiento=movimiento, currencies=COMMON_CURRENCIES, user_currency=user_currency)

@app.route('/eliminar-movimiento/<int:id>')
@login_required
def eliminar_movimiento(id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movimientos WHERE id=%s AND usuario_id=%s", (id, session['user_id']))
        conn.commit()
        cursor.close()
        conn.close()
        
        crear_notificacion(session['user_id'], f"Movimiento eliminado", 'info')
        
        flash('Movimiento eliminado', 'success')
    else:
        flash('Error de conexión', 'danger')
    
    return redirect(url_for('dashboard'))

# ==================== METAS DE AHORRO ====================
@app.route('/metas')
@login_required
def listar_metas():
    conn = get_db_connection()
    cursor = get_dict_cursor(conn)
    user_currency = session.get('default_currency', 'USD')
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT m.*, 
                   (m.monto_actual / m.monto_objetivo * 100) as porcentaje,
                   EXTRACT(DAY FROM (m.fecha_limite - CURRENT_DATE)) as dias_restantes
            FROM metas m
            WHERE m.usuario_id = %s
            ORDER BY (m.monto_actual / m.monto_objetivo) ASC
        """, (session['user_id'],))
    else:
        cursor.execute("""
            SELECT m.*, 
                   (m.monto_actual / m.monto_objetivo * 100) as porcentaje,
                   DATEDIFF(m.fecha_limite, CURDATE()) as dias_restantes
            FROM metas m
            WHERE m.usuario_id = %s
            ORDER BY (m.monto_actual / m.monto_objetivo) ASC
        """, (session['user_id'],))
    metas = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('metas.html', metas=metas, user_currency=user_currency, currencies=COMMON_CURRENCIES)

@app.route('/metas/nueva', methods=['POST'])
@login_required
def nueva_meta():
    nombre = request.form.get('nombre')
    monto_objetivo = float(request.form.get('monto_objetivo'))
    fecha_limite = request.form.get('fecha_limite')
    currency = request.form.get('currency', session.get('default_currency', 'USD'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO metas (usuario_id, nombre, monto_objetivo, fecha_limite, currency)
        VALUES (%s, %s, %s, %s, %s)
    """, (session['user_id'], nombre, monto_objetivo, fecha_limite if fecha_limite else None, currency))
    conn.commit()
    cursor.close()
    conn.close()
    
    crear_notificacion(session['user_id'], f"¡Nueva meta creada: {nombre} por ${monto_objetivo:,.2f} {currency}!", 'exito')
    
    flash('Meta de ahorro creada exitosamente', 'success')
    return redirect(url_for('listar_metas'))

@app.route('/metas/aportar/<int:id>', methods=['POST'])
@login_required
def aportar_meta(id):
    monto = float(request.form.get('monto'))
    descripcion = request.form.get('descripcion', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE metas 
        SET monto_actual = monto_actual + %s
        WHERE id = %s AND usuario_id = %s
    """, (monto, id, session['user_id']))
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            INSERT INTO aportaciones_meta (meta_id, monto, fecha, descripcion)
            VALUES (%s, %s, CURRENT_DATE, %s)
        """, (id, monto, descripcion))
    else:
        cursor.execute("""
            INSERT INTO aportaciones_meta (meta_id, monto, fecha, descripcion)
            VALUES (%s, %s, CURDATE(), %s)
        """, (id, monto, descripcion))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    crear_notificacion(session['user_id'], f"Aportaste ${monto:,.2f} a tu meta", 'exito')
    
    flash('Aportación registrada', 'success')
    return redirect(url_for('listar_metas'))

@app.route('/metas/eliminar/<int:id>')
@login_required
def eliminar_meta(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM metas WHERE id = %s AND usuario_id = %s", (id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    crear_notificacion(session['user_id'], f"Meta eliminada", 'info')
    
    flash('Meta eliminada', 'success')
    return redirect(url_for('listar_metas'))

# ==================== PRESUPUESTOS ====================
@app.route('/presupuestos')
@login_required
def listar_presupuestos():
    conn = get_db_connection()
    cursor = get_dict_cursor(conn)
    user_currency = session.get('default_currency', 'USD')
    
    mes_actual = datetime.now().month
    anio_actual = datetime.now().year
    
    cursor.execute("""
        SELECT p.*, c.nombre as categoria_nombre
        FROM presupuestos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE p.usuario_id = %s AND p.mes = %s AND p.anio = %s
    """, (session['user_id'], mes_actual, anio_actual))
    presupuestos = cursor.fetchall()
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT c.id as categoria_id, c.nombre, COALESCE(SUM(m.monto), 0) as gastado
            FROM categorias c
            LEFT JOIN movimientos m ON c.id = m.categoria_id 
                AND m.tipo = 'gasto' 
                AND m.usuario_id = %s
                AND EXTRACT(MONTH FROM m.fecha) = %s 
                AND EXTRACT(YEAR FROM m.fecha) = %s
            GROUP BY c.id, c.nombre
        """, (session['user_id'], mes_actual, anio_actual))
    else:
        cursor.execute("""
            SELECT c.id as categoria_id, c.nombre, COALESCE(SUM(m.monto), 0) as gastado
            FROM categorias c
            LEFT JOIN movimientos m ON c.id = m.categoria_id 
                AND m.tipo = 'gasto' 
                AND m.usuario_id = %s
                AND MONTH(m.fecha) = %s 
                AND YEAR(m.fecha) = %s
            GROUP BY c.id, c.nombre
        """, (session['user_id'], mes_actual, anio_actual))
    gastos_reales = cursor.fetchall()
    
    for p in presupuestos:
        for g in gastos_reales:
            if p['categoria_id'] == g['categoria_id']:
                p['gastado'] = g['gastado']
                p['porcentaje'] = (g['gastado'] / p['limite'] * 100) if p['limite'] > 0 else 0
                break
        else:
            p['gastado'] = 0
            p['porcentaje'] = 0
    
    categorias_sin_presupuesto = []
    for g in gastos_reales:
        if not any(p['categoria_id'] == g['categoria_id'] for p in presupuestos):
            categorias_sin_presupuesto.append(g)
    
    cursor.close()
    conn.close()
    
    return render_template('presupuestos.html', 
                         presupuestos=presupuestos,
                         categorias_sin_presupuesto=categorias_sin_presupuesto,
                         mes=mes_actual,
                         anio=anio_actual,
                         user_currency=user_currency,
                         currencies=COMMON_CURRENCIES)

@app.route('/presupuestos/nuevo', methods=['POST'])
@login_required
def nuevo_presupuesto():
    categoria_id = request.form.get('categoria_id')
    limite = float(request.form.get('limite'))
    mes = int(request.form.get('mes', datetime.now().month))
    anio = int(request.form.get('anio', datetime.now().year))
    currency = request.form.get('currency', session.get('default_currency', 'USD'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if os.environ.get('RENDER'):
            cursor.execute("""
                INSERT INTO presupuestos (usuario_id, categoria_id, mes, anio, limite, currency)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (usuario_id, categoria_id, mes, anio) 
                DO UPDATE SET limite = %s, currency = %s
            """, (session['user_id'], categoria_id, mes, anio, limite, currency, limite, currency))
        else:
            cursor.execute("""
                INSERT INTO presupuestos (usuario_id, categoria_id, mes, anio, limite, currency)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE limite = %s, currency = %s
            """, (session['user_id'], categoria_id, mes, anio, limite, currency, limite, currency))
        conn.commit()
        
        crear_notificacion(session['user_id'], f"Presupuesto creado con límite de ${limite:,.2f} {currency}", 'exito')
        
        flash('Presupuesto guardado', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('listar_presupuestos'))

@app.route('/presupuestos/eliminar/<int:id>')
@login_required
def eliminar_presupuesto(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM presupuestos WHERE id = %s AND usuario_id = %s", (id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    crear_notificacion(session['user_id'], f"Presupuesto eliminado", 'info')
    
    flash('Presupuesto eliminado', 'success')
    return redirect(url_for('listar_presupuestos'))

# ==================== RECORDATORIOS ====================
@app.route('/recordatorios')
@login_required
def listar_recordatorios():
    conn = get_db_connection()
    cursor = get_dict_cursor(conn)
    
    cursor.execute("""
        SELECT * FROM recordatorios 
        WHERE usuario_id = %s AND completado = FALSE
        ORDER BY fecha ASC
    """, (session['user_id'],))
    recordatorios_pendientes = cursor.fetchall()
    
    cursor.execute("""
        SELECT * FROM recordatorios 
        WHERE usuario_id = %s AND completado = TRUE
        ORDER BY fecha DESC
        LIMIT 10
    """, (session['user_id'],))
    recordatorios_completados = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('recordatorios.html', 
                         pendientes=recordatorios_pendientes,
                         completados=recordatorios_completados,
                         now_date=datetime.now().date(),
                         timedelta=timedelta)

@app.route('/recordatorios/nuevo', methods=['POST'])
@login_required
def nuevo_recordatorio():
    titulo = request.form.get('titulo')
    descripcion = request.form.get('descripcion', '')
    fecha = request.form.get('fecha')
    tipo = request.form.get('tipo', 'recordatorio')
    
    if not fecha:
        flash('La fecha es obligatoria', 'danger')
        return redirect(url_for('listar_recordatorios'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO recordatorios (usuario_id, titulo, descripcion, fecha, tipo)
        VALUES (%s, %s, %s, %s, %s)
    """, (session['user_id'], titulo, descripcion, fecha, tipo))
    conn.commit()
    cursor.close()
    conn.close()
    
    crear_notificacion(session['user_id'], f"Recordatorio creado: {titulo}", 'exito')
    
    flash('Recordatorio creado correctamente', 'success')
    return redirect(url_for('listar_recordatorios'))

@app.route('/recordatorios/completar/<int:id>')
@login_required
def completar_recordatorio(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE recordatorios 
        SET completado = TRUE 
        WHERE id = %s AND usuario_id = %s
    """, (id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    crear_notificacion(session['user_id'], f"¡Completaste un recordatorio!", 'exito')
    
    flash('Recordatorio marcado como completado', 'success')
    return redirect(url_for('listar_recordatorios'))

@app.route('/recordatorios/eliminar/<int:id>')
@login_required
def eliminar_recordatorio(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recordatorios WHERE id = %s AND usuario_id = %s", (id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    crear_notificacion(session['user_id'], f"Recordatorio eliminado", 'info')
    
    flash('Recordatorio eliminado', 'success')
    return redirect(url_for('listar_recordatorios'))

# ==================== NOTIFICACIONES ====================
@app.route('/notificaciones')
@login_required
def listar_notificaciones():
    conn = get_db_connection()
    cursor = get_dict_cursor(conn)
    cursor.execute("""
        SELECT * FROM notificaciones 
        WHERE usuario_id = %s 
        ORDER BY fecha_creacion DESC
    """, (session['user_id'],))
    notificaciones = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('notificaciones.html', notificaciones=notificaciones)

@app.route('/notificaciones/marcar-leida/<int:id>')
@login_required
def marcar_notificacion_leida(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE notificaciones 
        SET leido = TRUE 
        WHERE id = %s AND usuario_id = %s
    """, (id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('listar_notificaciones'))

@app.route('/notificaciones/marcar-todas')
@login_required
def marcar_todas_notificaciones():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE notificaciones 
        SET leido = TRUE 
        WHERE usuario_id = %s
    """, (session['user_id'],))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Todas las notificaciones marcadas como leídas', 'success')
    return redirect(url_for('listar_notificaciones'))

@app.route('/api/notificaciones/no-leidas')
@login_required
def api_notificaciones_no_leidas():
    conn = get_db_connection()
    cursor = get_dict_cursor(conn)
    cursor.execute("""
        SELECT COUNT(*) as total FROM notificaciones 
        WHERE usuario_id = %s AND leido = FALSE
    """, (session['user_id'],))
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return {'total': resultado['total'] if resultado else 0}

# ==================== EXCHANGE RATE API ====================
@app.route('/cambiar-divisa', methods=['POST'])
@login_required
def cambiar_divisa():
    data = request.get_json()
    currency = data.get('currency', 'USD')
    
    if currency:
        session['default_currency'] = currency
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET default_currency = %s WHERE id = %s", (currency, session['user_id']))
            conn.commit()
            cursor.close()
            conn.close()
        
        return {'success': True, 'currency': currency}
    return {'success': False, 'error': 'Moneda no válida'}, 400

@app.route('/api/exchange-rates')
@login_required
def api_exchange_rates():
    base = request.args.get('base', 'USD')
    rates_data = exchange_api.get_exchange_rates(base)
    
    if rates_data:
        return {
            'success': True,
            'base': base,
            'rates': rates_data.get('conversion_rates', {}),
            'last_updated': rates_data.get('time_last_update_utc', '')
        }
    return {'success': False, 'error': 'No se pudieron obtener las tasas de cambio'}

@app.route('/api/convert-currency', methods=['POST'])
@login_required
def api_convert_currency():
    data = request.get_json()
    amount = data.get('amount')
    from_currency = data.get('from_currency', 'USD')
    to_currency = data.get('to_currency', 'MXN')
    
    if not amount:
        return {'success': False, 'error': 'Monto requerido'}
    
    converted = exchange_api.convert_currency(amount, from_currency, to_currency)
    
    if converted is not None:
        return {
            'success': True,
            'amount': amount,
            'from_currency': from_currency,
            'to_currency': to_currency,
            'converted_amount': converted,
            'rate': converted / amount if amount > 0 else 0
        }
    return {'success': False, 'error': 'Error al convertir la moneda'}

@app.route('/api/currencies')
@login_required
def api_currencies():
    return {
        'success': True,
        'currencies': [{'code': code, 'name': name} for code, name in COMMON_CURRENCIES]
    }

@app.route('/configuracion-divisas')
@login_required
def configuracion_divisas():
    user_currency = session.get('default_currency', 'USD')
    return render_template('divisas.html', 
                         currencies=COMMON_CURRENCIES,
                         user_currency=user_currency)

# ==================== FRED API ====================
@app.route('/fred')
@login_required
def fred_dashboard():
    return render_template('fred.html', 
                         series=FRED_SERIES,
                         user_currency=session.get('default_currency', 'USD'))

@app.route('/api/fred/series')
@login_required
def api_fred_series():
    return {
        'success': True,
        'series': [{'id': k, 'name': v} for k, v in FRED_SERIES.items()]
    }

@app.route('/api/fred/series/<series_id>/info')
@login_required
def api_fred_series_info(series_id):
    info = fred_api.get_series_info(series_id)
    if info:
        return {'success': True, 'info': info}
    return {'success': False, 'error': 'Serie no encontrada'}

@app.route('/api/fred/series/<series_id>/data')
@login_required
def api_fred_series_data(series_id):
    days = request.args.get('days', 365, type=int)
    data = fred_api.get_historical_data(series_id, days)
    
    if data:
        return {
            'success': True,
            'series_id': series_id,
            'data': data,
            'latest_value': data[0]['value'] if data else None
        }
    return {'success': False, 'error': 'No se pudieron obtener los datos'}

@app.route('/api/fred/series/<series_id>/latest')
@login_required
def api_fred_series_latest(series_id):
    value = fred_api.get_latest_value(series_id)
    if value is not None:
        return {'success': True, 'series_id': series_id, 'latest_value': value}
    return {'success': False, 'error': 'No se pudo obtener el valor'}

@app.route('/api/fred/search')
@login_required
def api_fred_search():
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)
    
    if not query:
        return {'success': False, 'error': 'Se requiere un término de búsqueda'}
    
    results = fred_api.search_series(query, limit)
    return {'success': True, 'results': results}

# ==================== GRÁFICOS ====================
@app.route('/api/datos-graficos')
@login_required
def datos_graficos():
    conn = get_db_connection()
    cursor = get_dict_cursor(conn)
    
    anio_actual = datetime.now().year
    
    meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    ingresos_por_mes = []
    gastos_por_mes = []
    
    for mes in range(1, 13):
        if os.environ.get('RENDER'):
            cursor.execute("""
                SELECT COALESCE(SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE 0 END), 0) as ingresos,
                       COALESCE(SUM(CASE WHEN tipo = 'gasto' THEN monto ELSE 0 END), 0) as gastos
                FROM movimientos
                WHERE usuario_id = %s AND EXTRACT(MONTH FROM fecha) = %s AND EXTRACT(YEAR FROM fecha) = %s
            """, (session['user_id'], mes, anio_actual))
        else:
            cursor.execute("""
                SELECT COALESCE(SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE 0 END), 0) as ingresos,
                       COALESCE(SUM(CASE WHEN tipo = 'gasto' THEN monto ELSE 0 END), 0) as gastos
                FROM movimientos
                WHERE usuario_id = %s AND MONTH(fecha) = %s AND YEAR(fecha) = %s
            """, (session['user_id'], mes, anio_actual))
        resultado = cursor.fetchone()
        ingresos_por_mes.append(float(resultado['ingresos']))
        gastos_por_mes.append(float(resultado['gastos']))
    
    saldo_acumulado = 0
    evolucion_ahorro = []
    
    for mes in range(1, 13):
        if os.environ.get('RENDER'):
            cursor.execute("""
                SELECT COALESCE(SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE 0 END), 0) as ingresos,
                       COALESCE(SUM(CASE WHEN tipo = 'gasto' THEN monto ELSE 0 END), 0) as gastos
                FROM movimientos
                WHERE usuario_id = %s AND EXTRACT(MONTH FROM fecha) <= %s AND EXTRACT(YEAR FROM fecha) = %s
            """, (session['user_id'], mes, anio_actual))
        else:
            cursor.execute("""
                SELECT COALESCE(SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE 0 END), 0) as ingresos,
                       COALESCE(SUM(CASE WHEN tipo = 'gasto' THEN monto ELSE 0 END), 0) as gastos
                FROM movimientos
                WHERE usuario_id = %s AND MONTH(fecha) <= %s AND YEAR(fecha) = %s
            """, (session['user_id'], mes, anio_actual))
        resultado = cursor.fetchone()
        saldo_acumulado = float(resultado['ingresos']) - float(resultado['gastos'])
        evolucion_ahorro.append(saldo_acumulado)
    
    if os.environ.get('RENDER'):
        cursor.execute("""
            SELECT c.nombre, COUNT(*) as frecuencia, SUM(m.monto) as total
            FROM movimientos m
            JOIN categorias c ON m.categoria_id = c.id
            WHERE m.usuario_id = %s AND m.tipo = 'gasto' AND m.monto < 100
            GROUP BY c.id, c.nombre
            ORDER BY frecuencia DESC
            LIMIT 5
        """, (session['user_id'],))
    else:
        cursor.execute("""
            SELECT c.nombre, COUNT(*) as frecuencia, SUM(m.monto) as total
            FROM movimientos m
            JOIN categorias c ON m.categoria_id = c.id
            WHERE m.usuario_id = %s AND m.tipo = 'gasto' AND m.monto < 100
            GROUP BY c.id, c.nombre
            ORDER BY frecuencia DESC
            LIMIT 5
        """, (session['user_id'],))
    gastos_hormiga = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return {
        'meses': meses,
        'ingresos_mensuales': ingresos_por_mes,
        'gastos_mensuales': gastos_por_mes,
        'evolucion_ahorro': evolucion_ahorro,
        'gastos_hormiga': [
            {'categoria': g['nombre'], 'frecuencia': g['frecuencia'], 'total': float(g['total'])} 
            for g in gastos_hormiga
        ]
    }

# ==================== LOGOUT ====================
@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))

# ==================== RUTAS DE PRUEBA ====================
@app.route('/ver-usuarios')
def ver_usuarios():
    conn = get_db_connection()
    if not conn:
        return "Error de conexión"
    
    cursor = get_dict_cursor(conn)
    cursor.execute("SELECT id, nombre, email, default_currency, fecha_registro FROM users")
    usuarios = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not usuarios:
        return "<h3>No hay usuarios</h3><a href='/register'>Registro</a>"
    
    html = "<h2>Usuarios:</h2><ul>"
    for u in usuarios:
        html += f"<li>{u['nombre']} - {u['email']} - Moneda: {u['default_currency']}</li>"
    html += "</ul><a href='/register'>Volver</a>"
    return html

@app.route('/test-db')
def test_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        if os.environ.get('RENDER'):
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return f"DB OK - Version: {version} - Usuarios: {count}"
    else:
        return "Error de conexion a la base de datos"

# ==================== INICIALIZAR BASE DE DATOS ====================
from init_db_app import initialize_database

# Inicializar la base de datos según el entorno
initialize_database()

# ==================== INICIAR APLICACIÓN ====================
if __name__ == '__main__':
    print("\n" + "="*60)
    print("FINANTRACK - Control de Gastos Personales")
    print("="*60)
    print(f"🌍 Entorno: {'Render' if os.environ.get('RENDER') else 'Desarrollo Local'}")
    print("Servidor: http://127.0.0.1:5000")
    print("Registro: http://127.0.0.1:5000/register")
    print("Divisas: http://127.0.0.1:5000/configuracion-divisas")
    print("="*60 + "\n")
    app.run(debug=True, host='127.0.0.1', port=5000)