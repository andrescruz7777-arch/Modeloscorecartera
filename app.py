import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import unicodedata

# ============================================
# 🔒 CONTROL DE FLUJO ENTRE PASOS
# ============================================
if "df_unificado" not in st.session_state:
    st.session_state["df_unificado"] = None
if "df_limpio" not in st.session_state:
    st.session_state["df_limpio"] = None

# ============================================
# 📂 PASO 1: CARGA DE DATOS
# ============================================
st.title("📈 Paso 1 — Carga y Exploración de Datos (Enero a Septiembre)")

st.markdown("""
Sube las dos bases en formato **Excel (.xlsx)**:
- Base de **enero a marzo**
- Base de **abril a septiembre**
""")

file_ene_mar = st.file_uploader("📘 Cargar archivo Enero-Marzo", type=["xlsx"])
file_abr_sep = st.file_uploader("📗 Cargar archivo Abril-Septiembre", type=["xlsx"])

if file_ene_mar and file_abr_sep:
    df_ene_mar = pd.read_excel(file_ene_mar)
    df_abr_sep = pd.read_excel(file_abr_sep)

    st.subheader("🧩 Vista previa Enero-Marzo")
    st.dataframe(df_ene_mar.head())

    st.subheader("🧩 Vista previa Abril-Septiembre")
    st.dataframe(df_abr_sep.head())

    col_diff_1 = set(df_ene_mar.columns) - set(df_abr_sep.columns)
    col_diff_2 = set(df_abr_sep.columns) - set(df_ene_mar.columns)

    st.markdown("### 🔍 Comparación de columnas entre bases")
    st.write("**En enero-marzo pero no en abril-septiembre:**", col_diff_1)
    st.write("**En abril-septiembre pero no en enero-marzo:**", col_diff_2)

    df_unificado = pd.concat([df_ene_mar, df_abr_sep], ignore_index=True, sort=False)
    st.session_state["df_unificado"] = df_unificado

    st.markdown("### ✅ Base unificada")
    st.write("Filas totales:", df_unificado.shape[0])
    st.write("Columnas totales:", df_unificado.shape[1])
    st.dataframe(df_unificado.head())

else:
    st.info("⬆️ Sube ambos archivos para iniciar la exploración.")

# ============================================
# 🧩 PASO 2 — LIMPIEZA Y TRANSFORMACIÓN
# ============================================
st.title("🧩 Paso 2 — Limpieza y Transformación de Datos (Versión Final)")

if st.session_state["df_unificado"] is not None:
    df = st.session_state["df_unificado"].copy()

    # 1️⃣ Estandarizar nombres
    df.columns = (
        df.columns.str.strip()
                  .str.lower()
                  .str.replace(" ", "_")
                  .str.replace("[^a-z0-9_]", "", regex=True)
    )

    # 2️⃣ Eliminar columna "sand"
    if "sand" in df.columns:
        df = df.drop(columns=["sand"])
        st.info("🧹 Columna 'sand' eliminada correctamente.")

    # 3️⃣ Agregar columnas nuevas
    columnas_nuevas = [
        "año_pase_juridico",
        "mes_pase_juridico",
        "ciclo_mora_ini",
        "cod_convenio",
        "nom_convenio"
    ]
    for col in columnas_nuevas:
        if col not in df.columns:
            df[col] = None

    # 4️⃣ Función robusta para limpiar texto
    def limpiar_texto(texto):
        if pd.isna(texto):
            return texto
        try:
            texto = str(texto).encode("utf-8", "ignore").decode("utf-8", "ignore")
            texto = (
                texto.replace("√ë", "Ñ")
                .replace("√±", "ñ")
                .replace("√©", "é")
                .replace("√¡", "á")
                .replace("√³", "ó")
                .replace("√º", "ú")
            )
            texto = unicodedata.normalize("NFKD", texto)
            return texto.strip()
        except Exception:
            return str(texto)

    # Aplicar limpieza
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(limpiar_texto)
    st.info("✅ Se corrigieron caracteres mal codificados en texto (eñes, tildes, etc.)")

    # 5️⃣ Conversión de columnas numéricas
    columnas_numericas = [c for c in df.columns if any(x in c for x in ["monto", "valor", "saldo", "cuota"])]
    for col in columnas_numericas:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 6️⃣ Resumen
    st.subheader("📊 Vista previa del DataFrame limpio")
    st.dataframe(df.head(10), use_container_width=True)
    st.markdown("### 📋 Columnas finales:")
    st.write(list(df.columns))

    st.markdown("### 📈 Resumen estadístico (variables numéricas)")
    st.dataframe(df.describe())

    # 7️⃣ Guardar resultado limpio
    st.session_state["df_limpio"] = df
    st.success("✅ Base lista y guardada como `df_limpio` para el siguiente paso.")
else:
    st.warning("⚠️ Primero completa el Paso 1 (Carga de datos).")

# ============================================
# 📊 PASO 3 — ANÁLISIS EXPLORATORIO DE DATOS
# ============================================
st.title("📊 Paso 3 — Análisis Exploratorio de Datos (EDA)")

# Recuperar o restaurar DataFrame limpio
if st.session_state["df_limpio"] is None and st.session_state["df_unificado"] is not None:
    st.session_state["df_limpio"] = st.session_state["df_unificado"].copy()
    st.info("⚙️ Se restauró automáticamente la base limpia desde df_unificado.")

if st.session_state["df_limpio"] is not None:
    df = st.session_state["df_limpio"]

    # 🔍 1️⃣ Resumen General
    st.subheader("📋 Información General del DataFrame")
    st.write(f"Filas totales: **{df.shape[0]:,}**")
    st.write(f"Columnas totales: **{df.shape[1]:,}**")
    st.dataframe(df.describe(include="all").transpose())

    # ⚠️ 2️⃣ Valores Nulos
    st.subheader("🚨 Valores Nulos por Columna")
    nulos = df.isnull().sum().sort_values(ascending=False)
    st.bar_chart(nulos)

    # 📈 3️⃣ Distribución de Variables Numéricas
    st.subheader("📈 Distribución de Variables Numéricas")
    columnas_numericas = df.select_dtypes(include=["int64", "float64"]).columns.tolist()
    if columnas_numericas:
        columna = st.selectbox("Selecciona una variable numérica para graficar:", columnas_numericas)
        fig, ax = plt.subplots()
        ax.hist(df[columna].dropna(), bins=30)
        ax.set_title(f"Distribución de {columna}")
        st.pyplot(fig)
    else:
        st.info("No se encontraron variables numéricas para graficar.")

    # 🔗 4️⃣ Correlaciones
    st.subheader("🔗 Correlaciones entre Variables Numéricas")
    if len(columnas_numericas) >= 2:
        corr = df[columnas_numericas].corr()
        st.dataframe(corr)
        fig, ax = plt.subplots()
        cax = ax.matshow(corr, cmap="coolwarm")
        fig.colorbar(cax)
        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.columns)))
        ax.set_xticklabels(corr.columns, rotation=90)
        ax.set_yticklabels(corr.columns)
        st.pyplot(fig)
    else:
        st.info("No hay suficientes variables numéricas para calcular correlaciones.")

    # 🧠 5️⃣ Recomendación de Variables
    st.subheader("🧠 Variables candidatas para el modelo")
    st.dataframe(
        pd.DataFrame({
            "Columna": df.columns,
            "% Nulos": (df.isnull().sum() / len(df) * 100).round(2),
            "Tipo de Dato": df.dtypes.astype(str)
        }).sort_values("% Nulos")
    )
else:
    st.warning("⚠️ Aún no hay base cargada ni limpia. Completa los pasos anteriores.")

