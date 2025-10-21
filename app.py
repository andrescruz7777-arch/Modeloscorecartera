import streamlit as st
import pandas as pd

# ==========================
# 📂 PASO 1: CARGA DE DATOS
# ==========================

st.title("📈 Paso 1 — Carga y Exploración de Datos (Enero a Septiembre)")

st.markdown("""
Sube las dos bases en formato **Excel (.xlsx)**:
- Base de **enero a marzo**
- Base de **abril a septiembre**
""")

# Cargar archivos
file_ene_mar = st.file_uploader("📘 Cargar archivo Enero-Marzo", type=["xlsx"])
file_abr_sep = st.file_uploader("📗 Cargar archivo Abril-Septiembre", type=["xlsx"])

if file_ene_mar and file_abr_sep:
    # Leer los archivos
    df_ene_mar = pd.read_excel(file_ene_mar)
    df_abr_sep = pd.read_excel(file_abr_sep)

    st.subheader("🧩 Vista previa Enero-Marzo")
    st.dataframe(df_ene_mar.head())

    st.subheader("🧩 Vista previa Abril-Septiembre")
    st.dataframe(df_abr_sep.head())

    # Mostrar diferencias en columnas
    col_diff_1 = set(df_ene_mar.columns) - set(df_abr_sep.columns)
    col_diff_2 = set(df_abr_sep.columns) - set(df_ene_mar.columns)

    st.markdown("### 🔍 Comparación de columnas entre bases")
    st.write("**En enero-marzo pero no en abril-septiembre:**", col_diff_1)
    st.write("**En abril-septiembre pero no en enero-marzo:**", col_diff_2)

    # Unificar
    df_unificado = pd.concat([df_ene_mar, df_abr_sep], ignore_index=True, sort=False)

    st.markdown("### ✅ Base unificada")
    st.write("Filas totales:", df_unificado.shape[0])
    st.write("Columnas totales:", df_unificado.shape[1])
    st.dataframe(df_unificado.head())

    # Guardar en sesión para siguientes pasos
    st.session_state["df_unificado"] = df_unificado
else:
    st.info("⬆️ Sube ambos archivos para iniciar la exploración.")
     # ------------------------------
    #🧩 Paso 2 — Limpieza y Transformación de Datos
    # ------------------------------
st.title("🧩 Paso 2 — Limpieza y Transformación de Datos (Versión Final)")

# =====================================
#  Recuperar el DataFrame unificado
# =====================================
if "df_unificado" not in st.session_state:
    st.warning("⚠️ Primero completa el Paso 1 (Carga de datos).")
else:
    df = st.session_state["df_unificado"].copy()

    # ------------------------------
    # 1️⃣ Estandarizar nombres de columnas
    # ------------------------------
    df.columns = (
        df.columns.str.strip()
                  .str.lower()
                  .str.replace(" ", "_")
                  .str.replace("[^a-z0-9_]", "", regex=True)
    )

    # ------------------------------
    # 2️⃣ Eliminar columna "sand" si existe
    # ------------------------------
    if "sand" in df.columns:
        df = df.drop(columns=["sand"])
        st.info("🧹 Columna 'sand' eliminada correctamente.")

    # ------------------------------
    # 3️⃣ Agregar columnas faltantes (de abril-septiembre)
    # ------------------------------
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

    # ------------------------------
    # 4️⃣ Corrección de caracteres especiales (encoding)
    # ------------------------------
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
        # Normaliza caracteres Unicode y elimina espacios raros
        texto = unicodedata.normalize("NFKD", texto)
        return texto.strip()
    except Exception:
        return str(texto)

    # ------------------------------
    # 5️⃣ Validar tipos de datos básicos
    # ------------------------------
    columnas_numericas = [c for c in df.columns if any(x in c for x in ["monto", "valor", "saldo", "cuota"])]
    for col in columnas_numericas:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ------------------------------
    # 6️⃣ Mostrar resumen de la limpieza
    # ------------------------------
    st.subheader("📊 Vista previa del DataFrame limpio")
    st.dataframe(df.head(10), use_container_width=True)

    st.markdown("### 📋 Columnas finales:")
    st.write(list(df.columns))

    st.markdown("### 📈 Resumen estadístico (variables numéricas)")
    st.dataframe(df.describe())

    # ------------------------------
    # 7️⃣ Guardar resultado final
    # ------------------------------
    st.session_state["df_limpio"] = df
    st.success("✅ Base lista y guardada como `df_limpio` para el siguiente paso (análisis exploratorio o modelo).")




