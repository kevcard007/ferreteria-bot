import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from PIL import Image
import io
from database import FerreteriaDB  # Usar tu clase existente

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# URL del dashboard (cambiar por tu URL real de Railway)
DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://marvelous-enchantment-production-b36d.up.railway.app/')

# Configurar logging para ver qué pasa
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configurar Google Gemini
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

# Inicializar base de datos PostgreSQL
print("🗄️ Inicializando PostgreSQL...")
try:
    db = FerreteriaDB()
    print("✅ PostgreSQL conectado correctamente")
    USING_POSTGRES = True
except Exception as e:
    print(f"❌ Error conectando PostgreSQL: {e}")
    print("🔄 Cayendo a SQLite como backup...")
    USING_POSTGRES = False
    
    # Función de respaldo SQLite (solo por si falla PostgreSQL)
    import sqlite3
    def init_sqlite():
        conn = sqlite3.connect('ferreteria.db')
        cursor = conn.cursor()
        cursor.execute('''
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
        ''')
        conn.commit()
        conn.close()
    
    def insertar_producto_sqlite(precio, categoria, codigo, descripcion, usuario_telegram, usuario_nombre):
        try:
            conn = sqlite3.connect('ferreteria.db')
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO productos (precio, categoria, codigo, descripcion, usuario_telegram, usuario_nombre)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (precio, categoria, codigo, descripcion, usuario_telegram, usuario_nombre))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Error SQLite: {e}")
            return False
    
    init_sqlite()

# Funciones de utilidad (las mismas que tenías)
def extraer_precio_de_texto(texto):
    import re
    patrones = [
        r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*\$',
        r'(\d+(?:\.\d{2})?)'
    ]
    for patron in patrones:
        match = re.search(patron, texto)
        if match:
            precio_str = match.group(1).replace(',', '')
            try:
                return float(precio_str)
            except ValueError:
                continue
    return None

def normalizar_categoria(texto):
    texto_lower = texto.lower()
    if 'verde' in texto_lower or 'agricultura' in texto_lower:
        return 'Verde-Agricultura'
    elif 'rojo' in texto_lower or 'construcción' in texto_lower or 'construccion' in texto_lower:
        return 'Rojo-Construcción'
    elif 'amarillo' in texto_lower or 'pintura' in texto_lower:
        return 'Amarillo-Pintura'
    else:
        return 'Sin categoría'

# Función que se ejecuta cuando alguien escribe /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensaje de bienvenida cuando inician el bot"""
    db_status = "PostgreSQL ✅" if USING_POSTGRES else "SQLite (backup) ⚠️"
    
    welcome_message = f"""
🔧 *¡Bienvenido al Bot de Ferretería!* 🔧

Envíame una foto de la etiqueta de tu producto y yo:
• Extraeré precio, categoría, código y descripción
• Guardaré el registro en la base de datos ({db_status})
• Te daré un resumen del análisis

*Categorías que reconozco:*
🟢 Verde = Agricultura
🔴 Rojo = Construcción  
🟡 Amarillo = Pintura

¡Solo envía la foto y yo me encargo del resto!

📊 *Ver dashboard en tiempo real*: [Click aquí]({DASHBOARD_URL})
🌐 *Datos sincronizados automáticamente*
    """
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

# Función que se ejecuta cuando reciben una foto
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa las fotos que envían los usuarios"""
    try:
        # Obtener información del usuario
        user = update.effective_user
        user_id = user.id
        user_name = user.first_name or "Usuario"
        
        # Obtener la foto
        photo = update.message.photo[-1]  # La última es la de mayor calidad
        
        # Descargar la foto
        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Convertir bytes a imagen PIL
        image = Image.open(io.BytesIO(photo_bytes))
        
        # Enviar mensaje de que estamos procesando
        await update.message.reply_text("📸 Analizando la etiqueta... Un momento por favor.")
        
        # Prompt mejorado para Google Gemini
        prompt = """Analiza esta etiqueta de producto de ferretería y extrae la siguiente información:

1. PRECIO: El precio del producto (busca números con $ o signos de moneda)
2. CATEGORÍA: Identifica el color de la etiqueta y clasifícala:
   - Si es Verde → "Verde-Agricultura"
   - Si es Rojo → "Rojo-Construcción"  
   - Si es Amarillo → "Amarillo-Pintura"
3. CÓDIGO: Cualquier código, referencia, SKU o ID del producto
4. DESCRIPCIÓN: Nombre completo o descripción del producto

Responde EXACTAMENTE en este formato:
PRECIO: $[cantidad]
CATEGORÍA: [Color-Tipo]
CÓDIGO: [código o "No visible"]
DESCRIPCIÓN: [nombre del producto]

Si no puedes ver claramente algún dato, escribe "No visible" en esa sección.
Sé muy preciso con los números y textos."""
        
        # Analizar con Google Gemini
        response = model.generate_content([prompt, image])
        resultado_gemini = response.text
        
        # Procesar la respuesta de Gemini para extraer datos estructurados
        precio = None
        categoria = "Sin categoría"
        codigo = "No visible"
        descripcion = "Sin descripción"
        
        # Parsear la respuesta línea por línea
        lineas = resultado_gemini.strip().split('\n')
        for linea in lineas:
            linea = linea.strip()
            if linea.startswith('PRECIO:'):
                precio_texto = linea.replace('PRECIO:', '').strip()
                precio = extraer_precio_de_texto(precio_texto)
            elif linea.startswith('CATEGORÍA:') or linea.startswith('CATEGORIA:'):
                categoria_texto = linea.replace('CATEGORÍA:', '').replace('CATEGORIA:', '').strip()
                categoria = normalizar_categoria(categoria_texto)
            elif linea.startswith('CÓDIGO:') or linea.startswith('CODIGO:'):
                codigo = linea.replace('CÓDIGO:', '').replace('CODIGO:', '').strip()
                if codigo.lower() in ['no visible', 'no encontrado', '']:
                    codigo = "No visible"
            elif linea.startswith('DESCRIPCIÓN:') or linea.startswith('DESCRIPCION:'):
                descripcion = linea.replace('DESCRIPCIÓN:', '').replace('DESCRIPCION:', '').strip()
        
        # Guardar en base de datos
        guardado_exitoso = False
        if precio and precio > 0:
            if USING_POSTGRES:
                # Usar PostgreSQL (sincronizado con dashboard)
                guardado_exitoso = db.insertar_producto(
                    precio, categoria, codigo, descripcion, user_id, user_name
                )
                db_usado = "PostgreSQL ✅"
            else:
                # Fallback a SQLite
                guardado_exitoso = insertar_producto_sqlite(
                    precio, categoria, codigo, descripcion, user_id, user_name
                )
                db_usado = "SQLite (backup) ⚠️"
        
        # Preparar respuesta para el usuario
        if guardado_exitoso:
            sync_status = "🌐 Sincronizado con dashboard web" if USING_POSTGRES else "⚠️ No sincronizado con dashboard"
            
            respuesta = f"""✅ *Producto registrado exitosamente*

📋 *Información extraída:*
💰 Precio: ${precio:,.2f}
📂 Categoría: {categoria}
🏷️ Código: {codigo}
📝 Descripción: {descripcion}
👤 Registrado por: {user_name}

💾 *Estado*: Guardado en {db_usado}
{sync_status}

📊 *Ver en dashboard*: [Click aquí]({DASHBOARD_URL})"""
        else:
            respuesta = f"""⚠️ *Análisis completado (no guardado)*

📋 *Información extraída:*
{resultado_gemini}

❌ *No se pudo guardar*: Precio no detectado o inválido
💡 *Consejo*: Asegúrate de que el precio sea visible en la etiqueta

📊 *Ver dashboard*: [Click aquí]({DASHBOARD_URL})"""
        
        await update.message.reply_text(respuesta, parse_mode='Markdown')
        
        # Log para debugging
        logger.info(f"Análisis para usuario {user_id}: precio={precio}, categoria={categoria}, db={db_usado}")
        
    except Exception as e:
        logger.error(f"Error procesando foto: {e}")
        await update.message.reply_text(
            "❌ Hubo un error procesando la imagen. "
            "Por favor, asegúrate de que sea una foto clara de la etiqueta e intenta de nuevo."
        )

# Función para mostrar estadísticas del día
async def estadisticas_hoy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra las estadísticas de ventas del día actual"""
    try:
        if USING_POSTGRES:
            # Usar PostgreSQL
            total_ventas = db.obtener_total_ventas_hoy()
            ventas_hoy = db.obtener_ventas_hoy()
            productos_por_categoria = db.obtener_productos_por_categoria()
            total_productos = len(ventas_hoy)
            db_status = "PostgreSQL ✅ (sincronizado con dashboard)"
        else:
            # Fallback SQLite
            import sqlite3
            conn = sqlite3.connect('ferreteria.db')
            cursor = conn.cursor()
            
            # Total del día
            cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(precio), 0) 
                FROM productos 
                WHERE DATE(fecha_hora) = DATE('now')
            """)
            total_productos, total_ventas = cursor.fetchone()
            
            # Por categorías del día
            cursor.execute("""
                SELECT categoria, COUNT(*), SUM(precio) 
                FROM productos 
                WHERE DATE(fecha_hora) = DATE('now')
                GROUP BY categoria
            """)
            categorias_raw = cursor.fetchall()
            productos_por_categoria = {}
            for cat, count, total in categorias_raw:
                productos_por_categoria[cat] = {"cantidad": count, "total": total}
            
            conn.close()
            db_status = "SQLite ⚠️ (no sincronizado)"
        
        # Preparar mensaje
        mensaje = f"""📊 *Estadísticas del día*

💰 *Total vendido hoy*: ${total_ventas:,.2f}
📦 *Productos registrados*: {total_productos}
🗄️ *Base de datos*: {db_status}

📂 *Por categoría:*"""
        
        if productos_por_categoria:
            for categoria, datos in productos_por_categoria.items():
                mensaje += f"\n• {categoria}: {datos['cantidad']} productos (${datos['total']:,.2f})"
        else:
            mensaje += "\n• No hay registros del día"
        
        # Últimos productos registrados (solo para PostgreSQL)
        if USING_POSTGRES and len(ventas_hoy) > 0:
            mensaje += "\n\n🕒 *Últimos registros:*"
            for i, producto in enumerate(ventas_hoy[:3]):  # Solo los primeros 3
                descripcion = producto.get('descripcion', 'Sin descripción')
                precio = producto.get('precio', 0)
                mensaje += f"\n• {descripcion} - ${precio:,.2f}"
        
        # Agregar enlace al dashboard
        mensaje += f"\n\n📊 *Ver dashboard completo*: [Click aquí]({DASHBOARD_URL})"
        
        await update.message.reply_text(mensaje, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        await update.message.reply_text("❌ Error obteniendo estadísticas.")

# Función para mensajes de texto
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde a mensajes de texto normales"""
    db_status = "PostgreSQL (sincronizado)" if USING_POSTGRES else "SQLite (no sincronizado)"
    
    await update.message.reply_text(
        f"📸 Por favor envía una foto de la etiqueta del producto para analizarla.\n\n"
        f"📊 Escribe /estadisticas para ver el resumen del día\n"
        f"🆘 Escribe /help para más información\n"
        f"📊 *Dashboard web*: [Click aquí]({DASHBOARD_URL})\n\n"
        f"🗄️ *Base de datos activa*: {db_status}",
        parse_mode='Markdown'
    )

# Comando específico para el dashboard (NUEVO)
async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando para enviar directamente el enlace del dashboard"""
    db_status = "sincronizado" if USING_POSTGRES else "no sincronizado"
    
    mensaje = f"""📊 *Dashboard de Ferretería*

🌐 *Ver datos en tiempo real*: [Click aquí]({DASHBOARD_URL})

*¿Qué puedes ver en el dashboard?*
• 💰 Total de ventas del día
• 📦 Número de productos registrados
• 📊 Gráficos por categoría
• 📈 Evolución temporal
• 📋 Lista detallada de productos

*Estado*: {db_status} con el bot
*Actualización*: Los datos aparecen automáticamente cuando registras productos"""

    await update.message.reply_text(mensaje, parse_mode='Markdown')

# Función para mostrar ayuda
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra información de ayuda"""
    db_status = "PostgreSQL ✅" if USING_POSTGRES else "SQLite (backup) ⚠️"
    sync_status = "🌐 Datos sincronizados con dashboard web" if USING_POSTGRES else "⚠️ Datos NO sincronizados con dashboard"
    
    help_text = f"""
🆘 *Ayuda - Bot de Ferretería*

*📸 ¿Cómo registrar productos?*
1. Envía una foto clara de la etiqueta
2. El bot analizará automáticamente la información
3. Si detecta un precio válido, se guardará en la base de datos

*📊 Estado actual:*
🗄️ Base de datos: {db_status}
{sync_status}

*📊 Comandos disponibles:*
/start - Mensaje de bienvenida
/estadisticas - Ver resumen de ventas del día
/dashboard - Enlace directo al dashboard web
/help - Esta ayuda

*🌐 Dashboard web:*
[Ver dashboard en tiempo real]({DASHBOARD_URL})

*🎯 Consejos para mejores resultados:*
• Foto con buena iluminación
• Etiqueta completamente visible
• Sin reflejos o sombras
• Texto del precio legible

*🏷️ Categorías automáticas:*
🟢 Etiquetas verdes = Agricultura
🔴 Etiquetas rojas = Construcción
🟡 Etiquetas amarillas = Pintura

¿Problemas? Intenta con otra foto más clara.
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main() -> None:
    """Función principal que ejecuta el bot"""
    # Verificar que tenemos los tokens necesarios
    telegram_token = os.getenv('TELEGRAM_TOKEN')
    google_api_key = os.getenv('GOOGLE_API_KEY')
    
    if not telegram_token:
        print("❌ Error: TELEGRAM_TOKEN no encontrado en el archivo .env")
        return
    
    if not google_api_key:
        print("❌ Error: GOOGLE_API_KEY no encontrado en el archivo .env")
        return
    
    # Mostrar información de configuración
    print(f"🌐 Dashboard URL configurada: {DASHBOARD_URL}")
    
    # Mostrar estado de la base de datos
    db_info = "PostgreSQL (sincronizado con dashboard)" if USING_POSTGRES else "SQLite (backup, no sincronizado)"
    print(f"🗄️ Base de datos activa: {db_info}")
    
    if not USING_POSTGRES:
        print("⚠️  IMPORTANTE: Para sincronizar con el dashboard, configura las variables de PostgreSQL")
        print("   Variables necesarias: DATABASE_URL, PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD")
    
    # Crear la aplicación del bot
    application = Application.builder().token(telegram_token).build()
    
    # Agregar manejadores (handlers)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("estadisticas", estadisticas_hoy))
    application.add_handler(CommandHandler("dashboard", dashboard_command))  # COMANDO AGREGADO
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Iniciar el bot
    print("🤖 Bot iniciando con Google Gemini y Base de Datos...")
    print("📊 Enlaces al dashboard incluidos en todas las respuestas")
    print("✅ Bot activo. Presiona Ctrl+C para detener.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()