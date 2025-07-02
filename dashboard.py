import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
from database import FerreteriaDB  # Importar tu clase existente

# Configurar la página
st.set_page_config(
    page_title="Dashboard Ferretería",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Función para inicializar la base de datos
@st.cache_resource
def init_database():
    """
    Inicializa la conexión usando tu clase FerreteriaDB existente
    """
    try:
        db = FerreteriaDB()
        # Probar la conexión
        conn = db.get_connection()
        if conn:
            conn.close()
            return db, 'postgresql', 'conectado'
        else:
            return None, 'error', 'no_conectado'
    except Exception as e:
        st.error(f"Error inicializando base de datos: {e}")
        return None, 'error', str(e)

# Inicializar base de datos
db_instance, db_type, db_status = init_database()

# Título principal
st.title("🔧 Dashboard Ferretería")
st.markdown(f"📊 **Datos en tiempo real desde PostgreSQL**")

# Sidebar con información de debug
st.sidebar.markdown("### 🔧 Debug Info")
st.sidebar.info(f"**Tipo BD**: {db_type}")

# Mostrar estado de conexión
if db_type == 'postgresql' and db_status == 'conectado':
    st.sidebar.success("✅ PostgreSQL conectado")
    st.success("✅ Conectado a PostgreSQL de Railway - Datos sincronizados con el bot")
else:
    st.sidebar.error(f"❌ Error: {db_status}")
    st.error(f"❌ Error conectando a PostgreSQL: {db_status}")
    
    # Mostrar información de debug para ayudar a diagnosticar
    st.markdown("### 🔍 Información de Debug")
    st.write("**Variables de entorno disponibles:**")
    
    variables_importantes = [
        'DATABASE_URL', 'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD',
        'DB_POSTGRESDB_HOST', 'DB_POSTGRESDB_PORT', 'DB_POSTGRESDB_DATABASE', 
        'DB_POSTGRESDB_USER', 'DB_POSTGRESDB_PASSWORD'
    ]
    
    for var in variables_importantes:
        value = os.getenv(var)
        if value:
            # Ocultar contraseñas por seguridad
            if 'PASSWORD' in var.upper():
                display_value = '***CONFIGURADA***'
            else:
                display_value = value[:20] + "..." if len(value) > 20 else value
            st.write(f"✅ {var}: {display_value}")
        else:
            st.write(f"❌ {var}: No configurada")
    
    st.markdown("""
    ### 📋 Pasos para solucionar:
    
    1. **Ve a tu proyecto en Railway**
    2. **Selecciona el servicio de tu dashboard**
    3. **Ve a la pestaña "Variables"**
    4. **Copia las variables de tu servicio PostgreSQL:**
       - `DATABASE_URL` (la más importante)
       - O las variables individuales: `PGHOST`, `PGPORT`, etc.
    5. **Pega estas variables en tu servicio dashboard**
    6. **Redeploy el dashboard**
    """)
    st.stop()

# Variables de entorno para debugging (solo mostrar si está conectado)
st.sidebar.markdown("**Variables disponibles:**")
variables_check = ['DATABASE_URL', 'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER']
for var in variables_check:
    value = os.getenv(var)
    if value:
        if 'PASSWORD' in var.upper():
            display_value = '***'
        else:
            display_value = value[:15] + "..." if len(value) > 15 else value
        st.sidebar.text(f"{var}: ✅")
    else:
        st.sidebar.text(f"{var}: ❌")

# Función para obtener datos usando tu clase existente
@st.cache_data(ttl=30)
def obtener_todos_los_datos():
    """
    Obtiene todos los productos usando tu clase FerreteriaDB
    """
    try:
        if db_instance is None:
            return pd.DataFrame()
        
        # Usar tu método existente
        productos = db_instance.obtener_todos_productos()
        
        if not productos:
            return pd.DataFrame()
        
        # Convertir a DataFrame
        df = pd.DataFrame(productos)
        
        # Asegurar que fecha_hora sea datetime
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

st.markdown("---")

# Obtener datos
df = obtener_todos_los_datos()

if df.empty:
    st.warning("📭 No hay datos disponibles.")
    st.info("""
    **PostgreSQL conectado pero sin datos:**
    
    1. ✅ La conexión a PostgreSQL está funcionando
    2. 🤖 Verifica que el bot esté funcionando en Railway
    3. 📸 Envía una foto al bot para crear el primer registro
    4. 🔄 Los datos aparecerán aquí automáticamente
    
    **Para probar:** Ve a Telegram y envía una foto de una etiqueta al bot.
    """)
    st.stop()

# Sidebar para filtros
st.sidebar.header("📅 Filtros")
st.sidebar.success("🔗 Sincronizado con el bot")
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

# Métricas principales usando tus datos
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

# Gráfico de línea temporal (nuevo)
st.subheader("📈 Evolución de Ventas en el Tiempo")

if len(df_filtrado) > 1:
    # Agrupar por día
    df_temporal = df_filtrado.groupby(df_filtrado['fecha']).agg({
        'precio': 'sum',
        'id': 'count'
    }).reset_index()
    df_temporal.columns = ['Fecha', 'Total_Ventas', 'Cantidad_Productos']
    
    fig_line = px.line(
        df_temporal,
        x='Fecha',
        y='Total_Ventas',
        title='Ventas Diarias',
        markers=True
    )
    fig_line.update_layout(
        xaxis_title="Fecha",
        yaxis_title="Ventas ($)"
    )
    st.plotly_chart(fig_line, use_container_width=True)

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

# Estadísticas adicionales
st.subheader("📊 Estadísticas Detalladas")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**📈 Por Categorías:**")
    for categoria, data in df_filtrado.groupby('categoria').agg({
        'precio': ['sum', 'count', 'mean']
    }).iterrows():
        total = data[('precio', 'sum')]
        cantidad = data[('precio', 'count')]
        promedio = data[('precio', 'mean')]
        
        st.markdown(f"""
        **{categoria}:**
        - Total: ${total:,.2f}
        - Productos: {cantidad}
        - Promedio: ${promedio:,.2f}
        """)

with col2:
    st.markdown("**⏰ Por Horas del Día:**")
    ventas_por_hora = df_filtrado.groupby('hora')['precio'].sum().sort_index()
    
    fig_hora = px.bar(
        x=ventas_por_hora.index,
        y=ventas_por_hora.values,
        title="Ventas por Hora del Día",
        labels={'x': 'Hora', 'y': 'Ventas ($)'}
    )
    st.plotly_chart(fig_hora, use_container_width=True)

# Botón para refrescar datos
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("🔄 Refrescar Datos", type="primary"):
        st.cache_data.clear()
        st.rerun()

# Footer
st.markdown("---")
st.markdown(
    f"<div style='text-align: center; color: #666;'>"
    f"🔧 Dashboard Ferretería | PostgreSQL | Sincronizado con el bot"
    "</div>", 
    unsafe_allow_html=True
)