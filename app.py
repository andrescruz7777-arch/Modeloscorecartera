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

