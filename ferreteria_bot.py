import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from PIL import Image
import io

# Importar nuestro módulo de base de datos
from database import FerreteriaDB, extraer_precio_de_texto, normalizar_categoria

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Configurar logging para ver qué pasa
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configurar Google Gemini
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

# Inicializar base de datos
db = FerreteriaDB()

# Función que se ejecuta cuando alguien escribe /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensaje de bienvenida cuando inician el bot"""
    welcome_message = """
🔧 ¡Bienvenido al Bot de Ferretería! 🔧

Envíame una foto de la etiqueta de tu producto y yo:
• Extraeré precio, categoría, código y descripción
• Guardaré el registro en la base de datos
• Te daré un resumen del análisis

**Categorías que reconozco:**
🟢 Verde = Agricultura
🔴 Rojo = Construcción  
🟡 Amarillo = Pintura

¡Solo envía la foto y yo me encargo del resto!
    """
    await update.message.reply_text(welcome_message)

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
        
        # Guardar en base de datos solo si tenemos precio válido
        guardado_exitoso = False
        if precio and precio > 0:
            guardado_exitoso = db.insertar_producto(
                precio=precio,
                categoria=categoria,
                codigo=codigo,
                descripcion=descripcion,
                usuario_telegram=user_id,
                usuario_nombre=user_name
            )
        
        # Preparar respuesta para el usuario
        if guardado_exitoso:
            respuesta = f"""✅ **Producto registrado exitosamente**

📋 **Información extraída:**
💰 Precio: ${precio:,.2f}
📂 Categoría: {categoria}
🏷️ Código: {codigo}
📝 Descripción: {descripcion}
👤 Registrado por: {user_name}

💾 **Estado**: Guardado en base de datos"""
        else:
            respuesta = f"""⚠️ **Análisis completado (no guardado)**

📋 **Información extraída:**
{resultado_gemini}

❌ **No se pudo guardar**: Precio no detectado o inválido
💡 **Consejo**: Asegúrate de que el precio sea visible en la etiqueta"""
        
        await update.message.reply_text(respuesta)
        
        # Log para debugging
        logger.info(f"Análisis para usuario {user_id}: precio={precio}, categoria={categoria}")
        
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
        # Obtener datos del día
        total_ventas = db.obtener_total_ventas_hoy()
        productos_por_categoria = db.obtener_productos_por_categoria()
        ventas_hoy = db.obtener_ventas_hoy()
        
        # Preparar mensaje
        mensaje = f"""📊 **Estadísticas del día**

💰 **Total vendido hoy**: ${total_ventas:,.2f}
📦 **Productos registrados**: {len(ventas_hoy)}

📂 **Por categoría:**"""
        
        if productos_por_categoria:
            for categoria, datos in productos_por_categoria.items():
                mensaje += f"\n• {categoria}: {datos['cantidad']} productos (${datos['total']:,.2f})"
        else:
            mensaje += "\n• No hay registros del día"
        
        # Últimos 3 productos registrados
        if ventas_hoy:
            mensaje += "\n\n🕒 **Últimos registros:**"
            for i, producto in enumerate(ventas_hoy[:3]):  # Solo los primeros 3
                id_prod, precio, categoria, codigo, descripcion, fecha_hora, user_id, user_name = producto
                mensaje += f"\n• {descripcion} - ${precio:,.2f}"
        
        await update.message.reply_text(mensaje)
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        await update.message.reply_text("❌ Error obteniendo estadísticas.")

# Función para mensajes de texto
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde a mensajes de texto normales"""
    await update.message.reply_text(
        "📸 Por favor envía una foto de la etiqueta del producto para analizarla.\n\n"
        "📊 Escribe /estadisticas para ver el resumen del día\n"
        "🆘 Escribe /help para más información"
    )

# Función para mostrar ayuda
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra información de ayuda"""
    help_text = """
🆘 **Ayuda - Bot de Ferretería**

**📸 ¿Cómo registrar productos?**
1. Envía una foto clara de la etiqueta
2. El bot analizará automáticamente la información
3. Si detecta un precio válido, se guardará en la base de datos

**📊 Comandos disponibles:**
/start - Mensaje de bienvenida
/estadisticas - Ver resumen de ventas del día
/help - Esta ayuda

**🎯 Consejos para mejores resultados:**
• Foto con buena iluminación
• Etiqueta completamente visible
• Sin reflejos o sombras
• Texto del precio legible

**🏷️ Categorías automáticas:**
🟢 Etiquetas verdes = Agricultura
🔴 Etiquetas rojas = Construcción
🟡 Etiquetas amarillas = Pintura

¿Problemas? Intenta con otra foto más clara.
    """
    await update.message.reply_text(help_text)

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
    
    # Crear la aplicación del bot
    application = Application.builder().token(telegram_token).build()
    
    # Agregar manejadores (handlers)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("estadisticas", estadisticas_hoy))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Iniciar el bot
    print("🤖 Bot iniciando con Google Gemini y Base de Datos...")
    print("📊 Base de datos: ferreteria.db")
    print("✅ Bot activo. Presiona Ctrl+C para detener.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()