import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import unicodedata
import io
import base64

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

file_ene_mar = st.file_uploader("📘 Cargar archivo Enero-Marzo", type=["xlsx"])
file_abr_sep = st.file_uploader("📗 Cargar archivo Abril-Septiembre", type=["xlsx"])

if file_ene_mar and file_abr_sep:
    df_ene_mar = pd.read_excel(file_ene_mar)
    df_abr_sep = pd.read_excel(file_abr_sep)
    df_unificado = pd.concat([df_ene_mar, df_abr_sep], ignore_index=True, sort=False)
    st.session_state["df_unificado"] = df_unificado
    st.success(f"✅ Bases unificadas correctamente ({len(df_unificado):,} registros)")
    st.dataframe(df_unificado.head())
else:
    st.info("⬆️ Sube ambas bases para iniciar.")

# ============================================
# 🧩 PASO 2 — LIMPIEZA Y TRANSFORMACIÓN
# ============================================
st.title("🧩 Paso 2 — Limpieza y Transformación de Datos (Versión Final)")

if st.session_state["df_unificado"] is not None:
    df = st.session_state["df_unificado"].copy()

    # Estandarizar nombres
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("[^a-z0-9_]", "", regex=True)
    )

    # Eliminar columna innecesaria
    if "sand" in df.columns:
        df = df.drop(columns=["sand"])

    # Limpiar texto
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
            return unicodedata.normalize("NFKD", texto).strip()
        except Exception:
            return str(texto)

    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].apply(limpiar_texto)

    st.session_state["df_limpio"] = df
    st.success("✅ Base jurídica limpia y lista.")
else:
    st.warning("⚠️ Primero completa el Paso 1.")

# ============================================
# 💰 PASO 3 — CRUCE CON PAGOS
# ============================================
st.title("💰 Paso 3 — Cruce de Base Jurídica con Pagos")

file_pagos = st.file_uploader("📘 Cargar base de pagos (pagos_sudameris.xlsx)", type=["xlsx"])

if "df_limpio" not in st.session_state:
    st.warning("⚠️ Primero completa los pasos anteriores (base jurídica limpia).")
elif file_pagos:
    df_pagos = pd.read_excel(file_pagos)
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

    # Agrupar pagos
    resumen_pagos = (
        df_pagos.groupby("documento", dropna=False)
        .agg({
            "valor_pago": ["sum", "count"],
            "fecha_pago": "max"
        })
    )
    resumen_pagos.columns = ["total_pagado", "cantidad_pagos", "fecha_ultimo_pago"]
    resumen_pagos = resumen_pagos.reset_index()
    resumen_pagos["tiene_pago"] = (resumen_pagos["cantidad_pagos"] > 0).astype(int)

    df_jur = st.session_state["df_limpio"].copy()
    df_jur["deudor"] = df_jur["deudor"].astype(str)
    resumen_pagos["documento"] = resumen_pagos["documento"].astype(str)

    df_cruce = df_jur.merge(
        resumen_pagos,
        how="left",
        left_on="deudor",
        right_on="documento"
    )

    for col in ["tiene_pago", "total_pagado", "cantidad_pagos"]:
        if col in df_cruce.columns:
            df_cruce[col] = df_cruce[col].fillna(0)
            if col == "tiene_pago":
                df_cruce[col] = df_cruce[col].astype(int)

    st.session_state["df_cruce_pagos"] = df_cruce
    st.success("✅ Cruce realizado correctamente.")
else:
    st.info("⬆️ Carga la base de pagos para continuar.")

# ============================================
# 🤝 PASO 4 — CRUCE CON PROMESAS
# ============================================
st.title("🤝 Paso 4 — Cruce con Promesas de Pago")

file_promesas = st.file_uploader("📗 Cargar base de promesas (promesas_sudameris.xlsx)", type=["xlsx"])

if "df_cruce_pagos" not in st.session_state:
    st.warning("⚠️ Primero completa los pasos anteriores.")
elif file_promesas:
    df_prom = pd.read_excel(file_promesas)
    df_prom.columns = (
        df_prom.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("[^a-z0-9_]", "", regex=True)
    )

    col_doc = next((c for c in df_prom.columns if "identific" in c or "document" in c), None)
    df_prom = df_prom.rename(columns={col_doc: "documento"})

    df_prom = df_prom.rename(columns={
        "valor_acuerdo": "valor_prometido",
        "valor_cuota_prometida": "valor_cuota_prometida",
        "fecha_de_pago_prometida": "fecha_promesa",
        "estado_final": "estado_promesa"
    })

    df_prom["valor_prometido"] = pd.to_numeric(df_prom.get("valor_prometido", 0), errors="coerce").fillna(0)
    df_prom["valor_cuota_prometida"] = pd.to_numeric(df_prom.get("valor_cuota_prometida", 0), errors="coerce").fillna(0)
    df_prom["fecha_promesa"] = pd.to_datetime(df_prom.get("fecha_promesa"), errors="coerce")

    cantidad_promesas = df_prom.groupby("documento").size().reset_index(name="cantidad_promesas")
    ultima_promesa = (
        df_prom.sort_values("fecha_promesa")
        .groupby("documento", as_index=False)
        .tail(1)
        [["documento", "fecha_promesa", "valor_cuota_prometida", "estado_promesa", "recurso"]]
    )

    resumen_promesas = ultima_promesa.merge(cantidad_promesas, on="documento", how="left")
    resumen_promesas = resumen_promesas.rename(columns={
        "valor_cuota_prometida": "valor_ultima_promesa",
        "fecha_promesa": "fecha_ultima_promesa",
        "estado_promesa": "estado_ultima_promesa"
    })
    resumen_promesas["tiene_promesa"] = (resumen_promesas["cantidad_promesas"] > 0).astype(int)

    df_base = st.session_state["df_cruce_pagos"].copy()
    df_cruce_promesas = df_base.merge(
        resumen_promesas,
        how="left",
        left_on="deudor",
        right_on="documento"
    )

    for col in ["tiene_promesa", "valor_ultima_promesa", "cantidad_promesas"]:
        df_cruce_promesas[col] = df_cruce_promesas[col].fillna(0)

    st.session_state["df_cruce_promesas"] = df_cruce_promesas
    st.success("✅ Cruce con promesas realizado correctamente.")
else:
    st.info("⬆️ Carga la base de promesas.")

# ============================================
# 📞 PASO 5 — GESTIONES Y DESCARGA FINAL
# ============================================
st.title("📞 Paso 5 — Cruce de Gestiones y Consolidado Final")

file_gestion = st.file_uploader("📘 Cargar base de gestiones (gestion_sudameris.xlsx)", type=["xlsx"])

if file_gestion and "df_cruce_promesas" in st.session_state:
    df_gest = pd.read_excel(file_gestion)
    df = st.session_state["df_cruce_promesas"].copy()

    df_gest.columns = df_gest.columns.str.strip().str.lower()
    col_id = next((c for c in df_gest.columns if "identific" in c), None)
    col_mejor = next((c for c in df_gest.columns if "mejor" in c), None)

    jerarquia = {
        "1. gestion efectiva soluciona mora": 1,
        "2. gestion efectiva sin pago": 2,
        "3. no efectiva mensaje con tercero": 3,
        "4. no efectiva mensaje maquina": 4,
        "5. no efectiva contacto con tercero": 5,
        "6. no efectiva": 6,
        "7. operativo": 7
    }
    df_gest["nivel_efectividad"] = df_gest[col_mejor].astype(str).str.lower().map(jerarquia)
    df_mejor = df_gest.sort_values("nivel_efectividad").groupby(col_id, as_index=False).first()
    df_cant = df_gest.groupby(col_id, as_index=False).size().rename(columns={"size": "cantidad_gestiones"})

    df_gest_final = pd.merge(df_mejor, df_cant, on=col_id, how="left")
    df_gest_final["tiene_gestion_efectiva"] = df_gest_final["nivel_efectividad"].apply(lambda x: 1 if x in [1, 2] else 0)
    df_gest_final = df_gest_final.rename(columns={col_id: "deudor"})

    df_final = pd.merge(df, df_gest_final, on="deudor", how="left")
    df_final["cantidad_gestiones"] = df_final["cantidad_gestiones"].fillna(0).astype(int)
    df_final["tiene_gestion_efectiva"] = df_final["tiene_gestion_efectiva"].fillna(0).astype(int)

    st.success("✅ Base final consolidada con pagos, promesas y gestiones.")
    st.dataframe(df_final.head(10), use_container_width=True)

    # 👉 Descargar base final consolidada
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_final.to_excel(writer, index=False, sheet_name="Base Consolidada Final")
    buffer.seek(0)
    b64 = base64.b64encode(buffer.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="Base_Consolidada_Final.xlsx">📥 Descargar Base Consolidada Final</a>'
    st.markdown(href, unsafe_allow_html=True)
else:
    st.info("⬆️ Carga la base de gestiones después de los pasos previos.")
