import sqlite3
import datetime
import re
from typing import Optional

class FerreteriaDB:
    def __init__(self, db_path: str = "ferreteria.db"):
        """
        Inicializa la base de datos
        db_path: ruta donde se guardará el archivo de la base de datos
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Crea las tablas si no existen"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Crear tabla productos
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS productos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        precio REAL NOT NULL,
                        categoria TEXT NOT NULL,
                        codigo TEXT,
                        descripcion TEXT NOT NULL,
                        fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        usuario_telegram INTEGER NOT NULL,
                        usuario_nombre TEXT
                    )
                """)
                
                conn.commit()
                print("✅ Base de datos inicializada correctamente")
                
        except sqlite3.Error as e:
            print(f"❌ Error creando la base de datos: {e}")
    
    def insertar_producto(self, precio: float, categoria: str, codigo: str, 
                         descripcion: str, usuario_telegram: int, usuario_nombre: str = None) -> bool:
        """
        Inserta un nuevo producto en la base de datos
        
        Args:
            precio: Precio del producto
            categoria: Categoría (Verde-Agricultura, Rojo-Construcción, Amarillo-Pintura)
            codigo: Código del producto (puede ser None)
            descripcion: Descripción del producto
            usuario_telegram: ID del usuario de Telegram
            usuario_nombre: Nombre del usuario (opcional)
        
        Returns:
            bool: True si se insertó correctamente, False si hubo error
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO productos (precio, categoria, codigo, descripcion, usuario_telegram, usuario_nombre)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (precio, categoria, codigo, descripcion, usuario_telegram, usuario_nombre))
                
                conn.commit()
                producto_id = cursor.lastrowid
                print(f"✅ Producto insertado con ID: {producto_id}")
                return True
                
        except sqlite3.Error as e:
            print(f"❌ Error insertando producto: {e}")
            return False
    
    def obtener_ventas_hoy(self) -> list:
        """Obtiene todas las ventas del día actual"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Obtener fecha de hoy
                hoy = datetime.date.today()
                
                cursor.execute("""
                    SELECT * FROM productos 
                    WHERE DATE(fecha_hora) = DATE(?)
                    ORDER BY fecha_hora DESC
                """, (hoy,))
                
                return cursor.fetchall()
                
        except sqlite3.Error as e:
            print(f"❌ Error obteniendo ventas: {e}")
            return []
    
    def obtener_total_ventas_hoy(self) -> float:
        """Calcula el total de ventas del día"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                hoy = datetime.date.today()
                
                cursor.execute("""
                    SELECT SUM(precio) FROM productos 
                    WHERE DATE(fecha_hora) = DATE(?)
                """, (hoy,))
                
                resultado = cursor.fetchone()[0]
                return resultado if resultado else 0.0
                
        except sqlite3.Error as e:
            print(f"❌ Error calculando total: {e}")
            return 0.0
    
    def obtener_productos_por_categoria(self) -> dict:
        """Cuenta productos por categoría del día"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                hoy = datetime.date.today()
                
                cursor.execute("""
                    SELECT categoria, COUNT(*), SUM(precio) 
                    FROM productos 
                    WHERE DATE(fecha_hora) = DATE(?)
                    GROUP BY categoria
                """, (hoy,))
                
                resultados = cursor.fetchall()
                return {categoria: {"cantidad": cantidad, "total": total} 
                       for categoria, cantidad, total in resultados}
                
        except sqlite3.Error as e:
            print(f"❌ Error obteniendo categorías: {e}")
            return {}
    
    def obtener_todos_productos(self) -> list:
        """Obtiene todos los productos (para debugging)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM productos ORDER BY fecha_hora DESC")
                return cursor.fetchall()
                
        except sqlite3.Error as e:
            print(f"❌ Error obteniendo productos: {e}")
            return []

# Función de utilidad para extraer precio de texto
def extraer_precio_de_texto(texto: str) -> Optional[float]:
    """
    Extrae el precio de un texto que contiene información del producto
    Busca patrones como: $1234, $1,234.56, etc.
    """
    import re
    
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