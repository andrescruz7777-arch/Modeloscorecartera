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
# 💰 PASO 3 — CRUCE JURÍDICO VS PAGOS (VERSIÓN CORREGIDA)
# ============================================
st.title("💰 Paso 3 — Cruce de Base Jurídica con Pagos")

# Subir archivo de pagos
file_pagos = st.file_uploader("📘 Cargar base de pagos (pagos_sudameris.xlsx)", type=["xlsx"])

if "df_limpio" not in st.session_state:
    st.warning("⚠️ Primero completa los pasos anteriores (base jurídica limpia).")

elif file_pagos:
    # Leer base de pagos
    df_pagos = pd.read_excel(file_pagos)

    st.subheader("🧾 Vista previa de la base de pagos")
    st.dataframe(df_pagos.head())

    # ------------------------------
    # 🔧 Estandarizar columnas
    # ------------------------------
    df_pagos.columns = (
        df_pagos.columns.str.strip()
                        .str.lower()
                        .str.replace(" ", "_")
                        .str.replace("[^a-z0-9_]", "", regex=True)
    )

    # Renombrar columnas principales
    df_pagos = df_pagos.rename(columns={
        "total_de_pago": "valor_pago",
        "fecha_pago": "fecha_pago",
        "documento": "documento"
    })

    # Convertir tipos
    if "valor_pago" in df_pagos.columns:
        df_pagos["valor_pago"] = pd.to_numeric(df_pagos["valor_pago"], errors="coerce")
    if "fecha_pago" in df_pagos.columns:
        df_pagos["fecha_pago"] = pd.to_datetime(df_pagos["fecha_pago"], errors="coerce")

    # ------------------------------
    # 💡 Agrupar pagos por documento (versión robusta)
    # ------------------------------
    if "valor_pago" in df_pagos.columns:
        resumen_pagos = (
            df_pagos.groupby("documento", dropna=False)
            .agg({
                "valor_pago": ["sum", "count"],
                "fecha_pago": "max"
            })
        )

        resumen_pagos.columns = ["total_pagado", "cantidad_pagos", "fecha_ultimo_pago"]
        resumen_pagos = resumen_pagos.reset_index()
    else:
        resumen_pagos = pd.DataFrame(columns=[
            "documento", "total_pagado", "cantidad_pagos", "fecha_ultimo_pago"
        ])

    # Asegurar columnas y tipos
    resumen_pagos["total_pagado"] = pd.to_numeric(resumen_pagos.get("total_pagado", 0), errors="coerce").fillna(0)
    resumen_pagos["cantidad_pagos"] = resumen_pagos.get("cantidad_pagos", 0).fillna(0).astype(int)
    resumen_pagos["tiene_pago"] = (resumen_pagos["cantidad_pagos"] > 0).astype(int)

    # ------------------------------
    # 🔗 Cruce con la base jurídica
    # ------------------------------
    df_jur = st.session_state["df_limpio"].copy()
    df_jur["deudor"] = df_jur["deudor"].astype(str)
    resumen_pagos["documento"] = resumen_pagos["documento"].astype(str)

    df_cruce = df_jur.merge(
        resumen_pagos,
        how="left",
        left_on="deudor",
        right_on="documento"
    )

    # Completar nulos
    for col in ["tiene_pago", "total_pagado", "cantidad_pagos"]:
        if col in df_cruce.columns:
            if col == "tiene_pago":
                df_cruce[col] = df_cruce[col].fillna(0).astype(int)
            else:
                df_cruce[col] = df_cruce[col].fillna(0)

    # ------------------------------
    # 📊 Resumen y vista previa
    # ------------------------------
    st.success("✅ Cruce realizado correctamente.")
    st.write(f"Total de registros jurídicos: {len(df_jur):,}")
    st.write(f"Deudores con pago registrado: {df_cruce['tiene_pago'].sum():,}")

    st.subheader("📊 Vista previa del consolidado jurídico + pagos")
    columnas_prev = ["deudor", "tiene_pago", "cantidad_pagos", "total_pagado", "fecha_ultimo_pago"]
    columnas_prev = [c for c in columnas_prev if c in df_cruce.columns]
    st.dataframe(df_cruce[columnas_prev].head(20))

    # ------------------------------
    # 💾 Guardar consolidado
    # ------------------------------
    st.session_state["df_cruce_pagos"] = df_cruce

else:
    st.info("⬆️ Carga la base de pagos para realizar el cruce.")
    # ============================================
# 🤝 PASO 4 — CRUCE CON PROMESAS DE PAGO (incluye RECURSO)
# ============================================
st.title("🤝 Paso 4 — Cruce de Base Jurídica + Pagos con Promesas de Pago")

# Subir archivo de promesas
file_promesas = st.file_uploader("📗 Cargar base de promesas (promesas_sudameris.xlsx)", type=["xlsx"])

if "df_cruce_pagos" not in st.session_state:
    st.warning("⚠️ Primero completa los pasos anteriores (base jurídica + pagos).")

elif file_promesas:
    # Leer base de promesas
    df_prom = pd.read_excel(file_promesas)

    st.subheader("🧾 Vista previa de la base de promesas")
    st.dataframe(df_prom.head())

    # ------------------------------
    # 🔧 Estandarizar columnas
    # ------------------------------
    df_prom.columns = (
        df_prom.columns.str.strip()
                       .str.lower()
                       .str.replace(" ", "_")
                       .str.replace("[^a-z0-9_]", "", regex=True)
    )

    # ------------------------------
# 🧩 Detección automática de la columna de documento
# ------------------------------
col_doc = None
for col in df_prom.columns:
    if "identific" in col.lower() or "document" in col.lower():
        col_doc = col
        break

if col_doc is None:
    st.error("❌ No se encontró columna de identificación del deudor en la base de promesas.")
else:
    df_prom = df_prom.rename(columns={col_doc: "documento"})

# Renombrar columnas clave restantes
df_prom = df_prom.rename(columns={
    "valor_acuerdo": "valor_prometido",
    "fecha_de_pago_prometida": "fecha_promesa",
    "estado_final": "estado_promesa"
})
    # Convertir tipos
    df_prom["valor_prometido"] = pd.to_numeric(df_prom["valor_prometido"], errors="coerce").fillna(0)
    df_prom["fecha_promesa"] = pd.to_datetime(df_prom["fecha_promesa"], errors="coerce")

    # ------------------------------
    # 🧮 Agrupar promesas por documento
    # ------------------------------
    resumen_promesas = (
        df_prom.groupby("documento", dropna=False)
        .agg({
            "valor_prometido": ["sum", "count"],
            "fecha_promesa": "max",
            "estado_promesa": "last",
            "recurso": "last"
        })
    )

    resumen_promesas.columns = [
        "valor_total_prometido",
        "cantidad_promesas",
        "fecha_ultima_promesa",
        "estado_promesa",
        "recurso"
    ]
    resumen_promesas = resumen_promesas.reset_index()

    # Normalizar la variable RECURSO
    resumen_promesas["recurso"] = (
        resumen_promesas["recurso"]
        .astype(str)
        .str.upper()
        .str.strip()
        .replace({
            "NAN": None,
            "": None,
            "COMPRA": "COMPRA_CARTERA",
            "PROPIO": "PROPIO"
        })
    )

    resumen_promesas["tiene_promesa"] = (resumen_promesas["cantidad_promesas"] > 0).astype(int)

    # ------------------------------
    # 🔗 Cruce con la base jurídica + pagos
    # ------------------------------
    df_base = st.session_state["df_cruce_pagos"].copy()
    df_base["deudor"] = df_base["deudor"].astype(str)
    resumen_promesas["documento"] = resumen_promesas["documento"].astype(str)

    df_cruce_promesas = df_base.merge(
        resumen_promesas,
        how="left",
        left_on="deudor",
        right_on="documento"
    )

    # Rellenar valores nulos
    for col in ["tiene_promesa", "valor_total_prometido", "cantidad_promesas"]:
        df_cruce_promesas[col] = df_cruce_promesas[col].fillna(0).astype(int)
    df_cruce_promesas["recurso"] = df_cruce_promesas["recurso"].fillna("SIN_DATOS")

    # ------------------------------
    # 📊 Resumen y vista previa
    # ------------------------------
    st.success("✅ Cruce con promesas realizado correctamente.")
    st.write(f"Total de registros jurídicos: {len(df_base):,}")
    st.write(f"Deudores con promesa registrada: {df_cruce_promesas['tiene_promesa'].sum():,}")

    st.subheader("📊 Vista previa del consolidado jurídico + pagos + promesas")
    cols_prev = [
        "deudor", "tiene_pago", "cantidad_pagos", "total_pagado", "fecha_ultimo_pago",
        "tiene_promesa", "cantidad_promesas", "valor_total_prometido",
        "fecha_ultima_promesa", "estado_promesa", "recurso"
    ]
    cols_prev = [c for c in cols_prev if c in df_cruce_promesas.columns]
    st.dataframe(df_cruce_promesas[cols_prev].head(20))

    # Guardar para el siguiente paso
    st.session_state["df_cruce_promesas"] = df_cruce_promesas

else:
    st.info("⬆️ Carga la base de promesas para realizar el cruce.")
