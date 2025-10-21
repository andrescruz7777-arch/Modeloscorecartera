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

# =============================================
# 💰 PASO 3 — CRUCE JURÍDICO VS PAGOS (VERSIÓN CORREGIDA)
# =============================================
st.title("💰 Paso 3 — Cruce de Base Jurídica con Pagos")

# Subir archivo de pagos
file_pagos = st.file_uploader("📘 Cargar base de pagos (pagos_sudameris.xlsx)", type=["xlsx"])

if "df_limpio" not in st.session_state:
    st.warning("⚠️ Primero completa los pasos anteriores (base jurídica limpia).")

elif file_pagos:
    df_pagos = pd.read_excel(file_pagos)
    st.subheader("🧾 Vista previa de la base de pagos")
    st.dataframe(df_pagos.head())

    # 🔧 Estandarizar columnas
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

    # 💡 Agrupar pagos por documento
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

    resumen_pagos["total_pagado"] = pd.to_numeric(resumen_pagos.get("total_pagado", 0), errors="coerce").fillna(0)
    resumen_pagos["cantidad_pagos"] = resumen_pagos.get("cantidad_pagos", 0).fillna(0).astype(int)
    resumen_pagos["tiene_pago"] = (resumen_pagos["cantidad_pagos"] > 0).astype(int)

    # 🔗 Cruce con la base jurídica
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
            if col == "tiene_pago":
                df_cruce[col] = df_cruce[col].fillna(0).astype(int)
            else:
                df_cruce[col] = df_cruce[col].fillna(0)

    st.success("✅ Cruce realizado correctamente.")
    st.subheader("📊 Vista previa del consolidado jurídico + pagos")
    st.dataframe(df_cruce.head(20))

    st.session_state["df_cruce_pagos"] = df_cruce
else:
    st.info("⬆️ Carga la base de pagos para realizar el cruce.")

# =============================================
# 🤝 PASO 4 — CRUCE CON PROMESAS DE PAGO
# =============================================
st.title("🤝 Paso 4 — Cruce con Promesas de Pago")

file_promesas = st.file_uploader("📗 Cargar base de promesas (promesas_sudameris.xlsx)", type=["xlsx"])

if "df_cruce_pagos" not in st.session_state:
    st.warning("⚠️ Primero completa los pasos anteriores (base jurídica + pagos).")

elif file_promesas:
    df_prom = pd.read_excel(file_promesas)
    st.subheader("🧾 Vista previa de la base de promesas")
    st.dataframe(df_prom.head())

    df_prom.columns = df_prom.columns.str.strip().str.lower()
    col_doc = next((c for c in df_prom.columns if "identific" in c or "document" in c), None)
    if col_doc is None:
        st.error("❌ No se encontró columna de identificación.")
    else:
        df_prom = df_prom.rename(columns={col_doc: "documento"})
        df_prom["valor_cuota_prometida"] = pd.to_numeric(df_prom.get("valor_cuota_prometida", 0), errors="coerce")
        df_prom["fecha_de_pago_prometida"] = pd.to_datetime(df_prom.get("fecha_de_pago_prometida"), errors="coerce")
        prom_agg = (
            df_prom.groupby("documento")
            .agg(cantidad_promesas=("valor_cuota_prometida", "count"),
                 valor_prometido=("valor_cuota_prometida", "sum"),
                 fecha_ultima_promesa=("fecha_de_pago_prometida", "max"))
            .reset_index()
        )

        df_base = st.session_state["df_cruce_pagos"].copy()
        df_base["deudor"] = df_base["deudor"].astype(str)
        prom_agg["documento"] = prom_agg["documento"].astype(str)

        df_cruce_promesas = df_base.merge(prom_agg, how="left", left_on="deudor", right_on="documento")
        st.session_state["df_cruce_promesas"] = df_cruce_promesas

        st.success("✅ Cruce con promesas completado.")
        st.dataframe(df_cruce_promesas.head(20))
else:
    st.info("⬆️ Carga la base de promesas para realizar el cruce.")

# =============================================
# 📞 PASO 5 — CRUCE DE GESTIONES
# =============================================
st.title("📞 Paso 5 — Cruce de Gestiones")

file_gestion = st.file_uploader("📘 Cargar base de gestiones (gestion_sudameris.xlsx)", type=["xlsx"])

if file_gestion and "df_cruce_promesas" in st.session_state:
    df_gest = pd.read_excel(file_gestion)
    df = st.session_state["df_cruce_promesas"].copy()

    df_gest.columns = df_gest.columns.str.strip().str.lower()
    df.columns = df.columns.str.strip().str.lower()

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
    df_gest["nivel_efectividad"] = df_gest[col_mejor].str.lower().map(jerarquia)

    df_mejor = df_gest.sort_values("nivel_efectividad").groupby(col_id, as_index=False).first()
    df_cant = df_gest.groupby(col_id, as_index=False).size().rename(columns={"size": "cantidad_gestiones"})
    df_gest_final = pd.merge(df_mejor, df_cant, on=col_id, how="left")
    df_gest_final["tiene_gestion_efectiva"] = df_gest_final["nivel_efectividad"].apply(lambda x: 1 if x in [1, 2] else 0)
    df_gest_final = df_gest_final.rename(columns={col_id: "deudor"})

    df_cruce = pd.merge(df, df_gest_final, on="deudor", how="left")
    st.session_state["df_limpio"] = df_cruce

    st.success("✅ Cruce de gestiones realizado con éxito.")
    st.dataframe(df_cruce.head(10))
else:
    st.info("⬆️ Carga la base de gestiones después de los pasos previos.")

# =============================================
# 📊 PASO 5A — ANÁLISIS EMPÍRICO
# =============================================
st.title("📊 Paso 5A — Análisis Empírico de Efectividad (Producto y Mora)")

file_consolidado = st.file_uploader("📘 Cargar base consolidada (Base_Consolidada_Paso5.xlsx)", type=["xlsx"])

if file_consolidado:
    df = pd.read_excel(file_consolidado)
    df.columns = df.columns.str.strip().str.lower()

    cols_ok = ["grupop", "ciclo_mora_act", "deudor", "tiene_gestion_efectiva", "cantidad_promesas", "ultimo_pago"]
    faltantes = [c for c in cols_ok if c not in df.columns]
    if faltantes:
        st.error(f"❌ Faltan las columnas requeridas: {faltantes}")
        st.stop()

    agg = (
        df.groupby(["grupop", "ciclo_mora_act"])
        .agg(
            total_clientes=("deudor", "nunique"),
            total_contacto=("tiene_gestion_efectiva", "sum"),
            total_promesas=("cantidad_promesas", "sum"),
            total_pago_valor=("ultimo_pago", "sum"),
        )
        .reset_index()
    )

    agg["%_contacto"] = (agg["total_contacto"] / agg["total_clientes"] * 100).round(2)
    agg["promesas_promedio"] = (agg["total_promesas"] / agg["total_clientes"]).round(2)
    agg["pago_promedio"] = (agg["total_pago_valor"] / agg["total_clientes"]).round(0)

    st.dataframe(agg, use_container_width=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        agg.to_excel(writer, index=False, sheet_name="Efectividad")
    buffer.seek(0)
    b64 = base64.b64encode(buffer.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="Analisis_Efectividad_Cartera.xlsx">📥 Descargar análisis empírico en Excel</a>'
    st.markdown(href, unsafe_allow_html=True)

    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.bar(agg["grupop"], agg["%_contacto"], label="% Contacto", alpha=0.7)
    ax1.plot(agg["grupop"], agg["promesas_promedio"], color="orange", marker="o", label="Promesas promedio")
    ax2 = ax1.twinx()
    ax2.plot(agg["grupop"], agg["pago_promedio"], color="green", marker="s", label="Pago promedio ($)")
    ax1.set_xlabel("Producto (GrupoP)")
    ax1.set_ylabel("% Contacto / Promesas")
    ax2.set_ylabel("Pago promedio ($)")
    ax1.set_title("Indicadores de efectividad por producto")
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    st.pyplot(fig)

    st.success("✅ Análisis empírico completado correctamente.")
