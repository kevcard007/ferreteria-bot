import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

# Configurar la página
st.set_page_config(
    page_title="Dashboard Ferretería",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Función para conectar a la base de datos
@st.cache_resource
def init_database():
    """Inicializa conexión a la base de datos"""
    
    # Usar solo SQLite - más simple y confiable
    import sqlite3
    db_path = '/data/ferreteria.db'  # Usar volumen compartido en Railway
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("""
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
        conn.close()
        return 'sqlite', db_path
    except Exception as e:
        # Fallback a SQLite local si no hay volumen
        db_path = 'ferreteria.db'
        conn = sqlite3.connect(db_path)
        conn.execute("""
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
        conn.close()
        return 'sqlite', db_path

# Obtener configuración de BD
db_type, db_connection = init_database()

# Mostrar información de debugging
st.sidebar.markdown("### 🔧 Debug Info")
st.sidebar.info(f"**Tipo BD**: {db_type}")
if db_type == 'postgresql':
    st.sidebar.success("✅ PostgreSQL conectado")
else:
    st.sidebar.warning("⚠️ Usando SQLite")

# Variables de entorno para debugging
st.sidebar.markdown("**Variables disponibles:**")
variables = ['DATABASE_URL', 'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER']
for var in variables:
    value = os.getenv(var)
    if value:
        display_value = value[:15] + "..." if len(value) > 15 else value
        st.sidebar.text(f"{var}: {display_value}")
    else:
        st.sidebar.text(f"{var}: ❌")

# Función para obtener datos
@st.cache_data(ttl=30)
def obtener_todos_los_datos():
    """Obtiene todos los productos de la base de datos"""
    try:
        if db_type == 'postgresql':
            import psycopg2
            
            if isinstance(db_connection, str):
                # URL completa
                conn = psycopg2.connect(db_connection)
            else:
                # Parámetros individuales
                conn = psycopg2.connect(**db_connection)
            
            query = """
            SELECT id, precio, categoria, codigo, descripcion, fecha_hora, usuario_telegram, usuario_nombre
            FROM productos 
            ORDER BY fecha_hora DESC
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            
        else:
            # SQLite
            import sqlite3
            conn = sqlite3.connect(db_connection)
            query = """
            SELECT id, precio, categoria, codigo, descripcion, fecha_hora, usuario_telegram, usuario_nombre
            FROM productos 
            ORDER BY fecha_hora DESC
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
        
        if not df.empty:
            df['fecha_hora'] = pd.to_datetime(df['fecha_hora'])
            df['fecha'] = df['fecha_hora'].dt.date
            df['hora'] = df['fecha_hora'].dt.hour
        
        return df
    except Exception as e:
        st.error(f"❌ Error obteniendo datos: {e}")
        return pd.DataFrame()

# Función para filtrar datos por fechas
def filtrar_por_fechas(df, dias_atras):
    """Filtra el dataframe por número de días hacia atrás"""
    if df.empty:
        return df
    fecha_limite = datetime.now() - timedelta(days=dias_atras)
    return df[df['fecha_hora'] >= fecha_limite]

# Título principal
st.title("🔧 Dashboard Ferretería")
st.markdown(f"📊 **Datos en tiempo real desde {db_type.upper()}**")

# Mostrar estado de conexión
if db_type == 'postgresql':
    st.success("✅ Conectado a PostgreSQL de Railway - Datos sincronizados con el bot")
elif db_type == 'sqlite':
    st.warning("⚠️ Usando SQLite local - Para sincronizar, verifica las variables de PostgreSQL")
else:
    st.error("❌ Error de conexión a base de datos")
    st.stop()

st.markdown("---")

# Obtener datos
df = obtener_todos_los_datos()

if df.empty:
    st.warning("📭 No hay datos disponibles.")
    
    if db_type == 'postgresql':
        st.info("""
        **PostgreSQL conectado pero sin datos:**
        
        1. Verifica que el bot esté funcionando en Railway
        2. Envía una foto al bot para crear el primer registro
        3. Los datos aparecerán aquí automáticamente
        
        **Para probar:** Ve a Telegram y envía una foto de una etiqueta al bot.
        """)
    else:
        st.info("""
        **SQLite sin datos:**
        
        Los datos están en PostgreSQL pero el dashboard usa SQLite local.
        Verifica las variables de entorno de PostgreSQL.
        """)
    st.stop()

# Sidebar para filtros
st.sidebar.header("📅 Filtros")

# Mostrar información de la BD
st.sidebar.info(f"🔗 **Base de datos**: {db_type.upper()}")
if db_type == 'postgresql':
    st.sidebar.success("✅ Sincronizado con el bot")
else:
    st.sidebar.warning("⚠️ No sincronizado")

# Mostrar información de registros
st.sidebar.metric("📊 Total registros", len(df))

# Selector de período
periodo = st.sidebar.selectbox(
    "Seleccionar período:",
    ["Hoy", "Últimos 7 días", "Últimos 30 días", "Todo el tiempo"]
)

# Aplicar filtro de período
if periodo == "Hoy":
    df_filtrado = df[df['fecha'] == datetime.now().date()]
    titulo_periodo = "HOY"
elif periodo == "Últimos 7 días":
    df_filtrado = filtrar_por_fechas(df, 7)
    titulo_periodo = "ÚLTIMOS 7 DÍAS"
elif periodo == "Últimos 30 días":
    df_filtrado = filtrar_por_fechas(df, 30)
    titulo_periodo = "ÚLTIMOS 30 DÍAS"
else:
    df_filtrado = df
    titulo_periodo = "TODO EL TIEMPO"

# Filtro por categoría
categorias_disponibles = ["Todas"] + list(df['categoria'].unique())
categoria_seleccionada = st.sidebar.selectbox("Filtrar por categoría:", categorias_disponibles)

if categoria_seleccionada != "Todas":
    df_filtrado = df_filtrado[df_filtrado['categoria'] == categoria_seleccionada]

# Mostrar información del período seleccionado
st.subheader(f"📊 Resumen: {titulo_periodo}")

if df_filtrado.empty:
    st.info("No hay datos para el período seleccionado.")
    st.stop()

# Métricas principales
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_ventas = df_filtrado['precio'].sum()
    st.metric(
        label="💰 Total Vendido",
        value=f"${total_ventas:,.2f}"
    )

with col2:
    total_productos = len(df_filtrado)
    st.metric(
        label="📦 Productos Registrados",
        value=total_productos
    )

with col3:
    precio_promedio = df_filtrado['precio'].mean()
    st.metric(
        label="📊 Precio Promedio",
        value=f"${precio_promedio:,.2f}"
    )

with col4:
    producto_mas_caro = df_filtrado['precio'].max()
    st.metric(
        label="🎯 Producto Más Caro",
        value=f"${producto_mas_caro:,.2f}"
    )

st.markdown("---")

# Gráficos en dos columnas
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Ventas por Categoría")
    
    # Gráfico de pastel - Ventas por categoría
    ventas_categoria = df_filtrado.groupby('categoria').agg({
        'precio': 'sum',
        'id': 'count'
    }).reset_index()
    ventas_categoria.columns = ['Categoría', 'Total_Ventas', 'Cantidad']
    
    if not ventas_categoria.empty:
        fig_pie = px.pie(
            ventas_categoria, 
            values='Total_Ventas', 
            names='Categoría',
            title="Distribución de Ventas por Categoría",
            color_discrete_map={
                'Verde-Agricultura': '#2E8B57',
                'Rojo-Construcción': '#DC143C',
                'Amarillo-Pintura': '#FFD700',
                'Sin categoría': '#808080'
            }
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No hay datos suficientes para mostrar el gráfico.")

with col2:
    st.subheader("📊 Productos por Categoría")
    
    # Gráfico de barras - Cantidad por categoría
    if not ventas_categoria.empty:
        fig_bar = px.bar(
            ventas_categoria,
            x='Categoría',
            y='Cantidad',
            title="Número de Productos por Categoría",
            color='Categoría',
            color_discrete_map={
                'Verde-Agricultura': '#2E8B57',
                'Rojo-Construcción': '#DC143C',
                'Amarillo-Pintura': '#FFD700',
                'Sin categoría': '#808080'
            }
        )
        fig_bar.update_layout(showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

# Tabla de productos recientes
st.subheader("📋 Productos Registrados Recientemente")

# Preparar datos para la tabla
tabla_productos = df_filtrado[['fecha_hora', 'descripcion', 'precio', 'categoria', 'codigo', 'usuario_nombre']].copy()
tabla_productos['fecha_hora'] = tabla_productos['fecha_hora'].dt.strftime('%Y-%m-%d %H:%M')
tabla_productos = tabla_productos.rename(columns={
    'fecha_hora': 'Fecha y Hora',
    'descripcion': 'Producto',
    'precio': 'Precio ($)',
    'categoria': 'Categoría',
    'codigo': 'Código',
    'usuario_nombre': 'Registrado por'
})

# Mostrar tabla
st.dataframe(
    tabla_productos,
    use_container_width=True,
    hide_index=True
)

# Botón para refrescar datos
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("🔄 Refrescar Datos", type="primary"):
        st.cache_data.clear()
        st.rerun()

# Footer
st.markdown("---")
status_text = "sincronizado con el bot" if db_type == 'postgresql' else "datos locales"
st.markdown(
    f"<div style='text-align: center; color: #666;'>"
    f"🔧 Dashboard Ferretería | {db_type.upper()} | {status_text}"
    "</div>", 
    unsafe_allow_html=True
)