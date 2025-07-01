import os
import datetime
import re
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

class FerreteriaDB:
    def __init__(self):
        """
        Inicializa la base de datos PostgreSQL usando variables de entorno de Railway
        """
        self.db_params = self._get_db_params()
        self.init_database()
    
    def _get_db_params(self):
        """Obtiene parámetros de conexión desde variables de entorno"""
        # Intentar usar DATABASE_URL primero (formato completo)
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            url = urlparse(database_url)
            return {
                'host': url.hostname,
                'port': url.port,
                'database': url.path[1:],  # Remover el '/' inicial
                'user': url.username,
                'password': url.password
            }
        
        # Si no existe DATABASE_URL, usar variables individuales de Railway
        return {
            'host': os.getenv('DB_POSTGRESDB_HOST', 'localhost'),
            'port': os.getenv('DB_POSTGRESDB_PORT', '5432'),
            'database': os.getenv('DB_POSTGRESDB_DATABASE', 'ferreteria'),
            'user': os.getenv('DB_POSTGRESDB_USER', 'postgres'),
            'password': os.getenv('DB_POSTGRESDB_PASSWORD', '')
        }
    
    def get_connection(self):
        """Crea y retorna una conexión a PostgreSQL"""
        try:
            # Intentar con DATABASE_URL primero
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                conn = psycopg2.connect(database_url)
                return conn
            else:
                # Fallback a parámetros individuales
                conn = psycopg2.connect(**self.db_params)
                return conn
        except psycopg2.Error as e:
            print(f"❌ Error conectando a PostgreSQL: {e}")
            print(f"❌ Parámetros de conexión: {self.db_params}")
            return None
        except Exception as e:
            print(f"❌ Error general de conexión: {e}")
            return None
    
    def init_database(self):
        """Crea las tablas si no existen"""
        try:
            conn = self.get_connection()
            if conn is None:
                print("❌ No se pudo conectar a la base de datos")
                return
            
            with conn:
                with conn.cursor() as cursor:
                    # Crear tabla productos
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS productos (
                            id SERIAL PRIMARY KEY,
                            precio DECIMAL(10,2) NOT NULL,
                            categoria VARCHAR(100) NOT NULL,
                            codigo VARCHAR(100),
                            descripcion TEXT NOT NULL,
                            fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            usuario_telegram BIGINT NOT NULL,
                            usuario_nombre VARCHAR(100)
                        )
                    """)
                    
                    # Crear índices para mejorar performance
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_productos_fecha 
                        ON productos(fecha_hora)
                    """)
                    
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_productos_categoria 
                        ON productos(categoria)
                    """)
                    
                    print("✅ Base de datos PostgreSQL inicializada correctamente")
            
            conn.close()
                    
        except psycopg2.Error as e:
            print(f"❌ Error creando la base de datos: {e}")
        except Exception as e:
            print(f"❌ Error general inicializando BD: {e}")
    
    def insertar_producto(self, precio: float, categoria: str, codigo: str, 
                         descripcion: str, usuario_telegram: int, usuario_nombre: str = None) -> bool:
        """
        Inserta un nuevo producto en la base de datos PostgreSQL
        """
        try:
            with self.get_connection() as conn:
                if conn is None:
                    return False
                
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO productos (precio, categoria, codigo, descripcion, usuario_telegram, usuario_nombre)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (precio, categoria, codigo, descripcion, usuario_telegram, usuario_nombre))
                    
                    producto_id = cursor.fetchone()[0]
                    conn.commit()
                    print(f"✅ Producto insertado con ID: {producto_id}")
                    return True
                    
        except psycopg2.Error as e:
            print(f"❌ Error insertando producto: {e}")
            return False
    
    def obtener_ventas_hoy(self) -> list:
        """Obtiene todas las ventas del día actual"""
        try:
            with self.get_connection() as conn:
                if conn is None:
                    return []
                
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    hoy = datetime.date.today()
                    
                    cursor.execute("""
                        SELECT * FROM productos 
                        WHERE DATE(fecha_hora) = %s
                        ORDER BY fecha_hora DESC
                    """, (hoy,))
                    
                    return [dict(row) for row in cursor.fetchall()]
                    
        except psycopg2.Error as e:
            print(f"❌ Error obteniendo ventas: {e}")
            return []
    
    def obtener_total_ventas_hoy(self) -> float:
        """Calcula el total de ventas del día"""
        try:
            with self.get_connection() as conn:
                if conn is None:
                    return 0.0
                
                with conn.cursor() as cursor:
                    hoy = datetime.date.today()
                    
                    cursor.execute("""
                        SELECT COALESCE(SUM(precio), 0) FROM productos 
                        WHERE DATE(fecha_hora) = %s
                    """, (hoy,))
                    
                    resultado = cursor.fetchone()[0]
                    return float(resultado) if resultado else 0.0
                    
        except psycopg2.Error as e:
            print(f"❌ Error calculando total: {e}")
            return 0.0
    
    def obtener_productos_por_categoria(self) -> dict:
        """Cuenta productos por categoría del día"""
        try:
            with self.get_connection() as conn:
                if conn is None:
                    return {}
                
                with conn.cursor() as cursor:
                    hoy = datetime.date.today()
                    
                    cursor.execute("""
                        SELECT categoria, COUNT(*), SUM(precio) 
                        FROM productos 
                        WHERE DATE(fecha_hora) = %s
                        GROUP BY categoria
                    """, (hoy,))
                    
                    resultados = cursor.fetchall()
                    return {categoria: {"cantidad": cantidad, "total": float(total)} 
                           for categoria, cantidad, total in resultados}
                    
        except psycopg2.Error as e:
            print(f"❌ Error obteniendo categorías: {e}")
            return {}
    
    def obtener_todos_productos(self) -> list:
        """Obtiene todos los productos para el dashboard"""
        try:
            with self.get_connection() as conn:
                if conn is None:
                    return []
                
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SELECT * FROM productos ORDER BY fecha_hora DESC")
                    return [dict(row) for row in cursor.fetchall()]
                    
        except psycopg2.Error as e:
            print(f"❌ Error obteniendo productos: {e}")
            return []

# Función de utilidad para extraer precio de texto
def extraer_precio_de_texto(texto: str) -> Optional[float]:
    """
    Extrae el precio de un texto que contiene información del producto
    Busca patrones como: $1234, $1,234.56, etc.
    """
    # Buscar patrones de precio
    patrones = [
        r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $1,234.56
        r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*\$',  # 1234.56$
        r'(\d+(?:\.\d{2})?)',  # 1234.56
    ]
    
    for patron in patrones:
        match = re.search(patron, texto)
        if match:
            # Limpiar el precio (quitar comas)
            precio_str = match.group(1).replace(',', '')
            try:
                return float(precio_str)
            except ValueError:
                continue
    
    return None

# Función para normalizar categoría
def normalizar_categoria(texto: str) -> str:
    """
    Normaliza el texto de categoría basado en colores
    """
    texto_lower = texto.lower()
    
    if 'verde' in texto_lower or 'agricultura' in texto_lower:
        return 'Verde-Agricultura'
    elif 'rojo' in texto_lower or 'construcción' in texto_lower or 'construccion' in texto_lower:
        return 'Rojo-Construcción'
    elif 'amarillo' in texto_lower or 'pintura' in texto_lower:
        return 'Amarillo-Pintura'
    else:
        return 'Sin categoría'