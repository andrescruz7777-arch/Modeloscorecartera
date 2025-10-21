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
# 🤝 PASO 4 — CRUCE CON PROMESAS DE PAGO (ULTIMA PROMESA REAL)
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

    # Detectar columna de documento
    col_doc = None
    for col in df_prom.columns:
        if "identific" in col.lower() or "document" in col.lower():
            col_doc = col
            break

    if col_doc is None:
        st.error("❌ No se encontró columna de identificación del deudor en la base de promesas.")
    else:
        df_prom = df_prom.rename(columns={col_doc: "documento"})

    # Renombrar columnas relevantes
    df_prom = df_prom.rename(columns={
        "valor_acuerdo": "valor_prometido",
        "valor_cuota_prometida": "valor_cuota_prometida",
        "fecha_de_pago_prometida": "fecha_promesa",
        "estado_final": "estado_promesa"
    })

    # Convertir tipos
    df_prom["valor_prometido"] = pd.to_numeric(df_prom.get("valor_prometido", 0), errors="coerce").fillna(0)
    df_prom["valor_cuota_prometida"] = pd.to_numeric(df_prom.get("valor_cuota_prometida", 0), errors="coerce").fillna(0)
    df_prom["fecha_promesa"] = pd.to_datetime(df_prom.get("fecha_promesa"), errors="coerce")

    # ------------------------------
    # 🧮 Determinar la última promesa real por deudor
    # ------------------------------
    df_prom = df_prom.sort_values(["documento", "fecha_promesa"], ascending=[True, True])

    # Calcular cantidad total de promesas
    cantidad_promesas = df_prom.groupby("documento").size().reset_index(name="cantidad_promesas")

    # Tomar solo la última promesa (por fecha máxima)
    ultima_promesa = (
        df_prom.sort_values("fecha_promesa")
        .groupby("documento", as_index=False)
        .tail(1)
        [["documento", "fecha_promesa", "valor_cuota_prometida", "estado_promesa", "recurso"]]
    )

    # Unir ambas: cantidad total + última promesa
    resumen_promesas = ultima_promesa.merge(cantidad_promesas, on="documento", how="left")

    # Renombrar para claridad
    resumen_promesas = resumen_promesas.rename(columns={
        "valor_cuota_prometida": "valor_ultima_promesa",
        "fecha_promesa": "fecha_ultima_promesa",
        "estado_promesa": "estado_ultima_promesa"
    })

    # Normalizar RECURSO
    resumen_promesas["recurso"] = (
        resumen_promesas["recurso"]
        .astype(str)
        .str.upper()
        .str.strip()
        .replace({
            "NAN": None,
            "": None,
            "COMPRA": "COMPRA_CARTERA",
            "COMPRA CARTERA": "COMPRA_CARTERA",
            "COMPRA DE CARTERA": "COMPRA_CARTERA",
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
    for col in ["tiene_promesa", "valor_ultima_promesa", "cantidad_promesas"]:
        if col in df_cruce_promesas.columns:
            df_cruce_promesas[col] = df_cruce_promesas[col].fillna(0)
            if col in ["tiene_promesa", "cantidad_promesas"]:
                df_cruce_promesas[col] = df_cruce_promesas[col].astype(int)

    df_cruce_promesas["recurso"] = df_cruce_promesas["recurso"].fillna("SIN_DATOS")

    # ------------------------------
    # 📊 Resumen y vista previa
    # ------------------------------
    st.success("✅ Cruce con promesas realizado correctamente (última promesa real por deudor).")
    st.write(f"Total de registros jurídicos: {len(df_base):,}")
    st.write(f"Deudores con promesa registrada: {df_cruce_promesas['tiene_promesa'].sum():,}")

    st.subheader("📊 Vista previa del consolidado jurídico + pagos + promesas")
    columnas_prev = [
        "deudor", "tiene_pago", "cantidad_pagos", "total_pagado", "fecha_ultimo_pago",
        "tiene_promesa", "cantidad_promesas", "valor_ultima_promesa",
        "fecha_ultima_promesa", "estado_ultima_promesa", "recurso"
    ]
    columnas_prev = [c for c in columnas_prev if c in df_cruce_promesas.columns]
    st.dataframe(df_cruce_promesas[columnas_prev].head(20))

    # ------------------------------
    # 💾 Guardar consolidado
    # ------------------------------
    st.session_state["df_cruce_promesas"] = df_cruce_promesas

else:
    st.info("⬆️ Carga la base de promesas para realizar el cruce.")
   # =============================================
# 📞 PASO 5 — CRUCE DE GESTIONES (Contacto Solutions Jur)
# =============================================

import io
import base64

st.title("📞 Paso 5 — Cruce de Gestiones (Contacto Solutions Jur)")

file_gestion = st.file_uploader("📘 Cargar base de gestiones (gestion_sudameris.xlsx)", type=["xlsx"])

if file_gestion and "df_limpio" in st.session_state:
    df_gest = pd.read_excel(file_gestion)
    df = st.session_state["df_limpio"].copy()

    # =========================
    # 1️⃣ Normalizar nombres
    # =========================
    df_gest.columns = df_gest.columns.str.strip().str.lower()
    df.columns = df.columns.str.strip().str.lower()

    # Buscar columnas clave
    col_id = next((c for c in df_gest.columns if "identific" in c), None)
    col_mejor = next((c for c in df_gest.columns if "mejor" in c), None)
    col_accion = next((c for c in df_gest.columns if "accion" in c), None)
    col_resp = next((c for c in df_gest.columns if "respu" in c), None)

    if not col_id:
        st.error("❌ No se encontró una columna de identificación del deudor.")
        st.stop()

    # =========================
    # 2️⃣ Jerarquía de efectividad
    # =========================
    jerarquia = {
        "1. GESTION EFECTIVA SOLUCIONA MORA": 1,
        "2. GESTION EFECTIVA SIN PAGO": 2,
        "3. NO EFECTIVA MENSAJE CON TERCERO": 3,
        "4. NO EFECTIVA MENSAJE MAQUINA": 4,
        "5. NO EFECTIVA CONTACTO CON TERCERO": 5,
        "6. NO EFECTIVA": 6,
        "7. OPERATIVO": 7
    }
    df_gest["nivel_efectividad"] = df_gest[col_mejor].map(jerarquia)

    # =========================
    # 3️⃣ Seleccionar la mejor gestión
    # =========================
    df_mejor = df_gest.sort_values("nivel_efectividad").groupby(col_id, as_index=False).first()

    # =========================
    # 4️⃣ Cantidad de gestiones
    # =========================
    df_cant = df_gest.groupby(col_id, as_index=False).size().rename(columns={"size": "cantidad_gestiones"})

    # =========================
    # 5️⃣ Unir resultados
    # =========================
    df_gest_final = pd.merge(df_mejor, df_cant, on=col_id, how="left")
    df_gest_final["tiene_gestion_efectiva"] = df_gest_final["nivel_efectividad"].apply(lambda x: 1 if x in [1, 2] else 0)

    # =========================
    # 6️⃣ Seleccionar columnas útiles
    # =========================
    cols_utiles = [col_id, "cantidad_gestiones", "tiene_gestion_efectiva"]
    for c in [col_mejor, col_accion, col_resp]:
        if c: cols_utiles.append(c)

    df_gest_final = df_gest_final[cols_utiles]

    # =========================
    # 7️⃣ Cruce con base limpia
    # =========================
    df_cruce = pd.merge(df, df_gest_final, left_on="deudor", right_on=col_id, how="left")
    df_cruce["cantidad_gestiones"] = df_cruce["cantidad_gestiones"].fillna(0).astype(int)
    df_cruce["tiene_gestion_efectiva"] = df_cruce["tiene_gestion_efectiva"].fillna(0).astype(int)

    # =========================
    # 🔄 Guardar en sesión y descargar
    # =========================
    st.session_state["df_limpio"] = df_cruce

    # Mostrar vista previa
    st.success("✅ Cruce de gestiones realizado con éxito.")
    st.dataframe(df_cruce.head(10), use_container_width=True)

    # 👉 NUEVO: Descarga completa de la base consolidada
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_cruce.to_excel(writer, index=False, sheet_name="Base Consolidada")
    buffer.seek(0)
    b64 = base64.b64encode(buffer.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="Base_Consolidada_Paso5.xlsx">📥 Descargar Base Consolidada (Paso 5)</a>'
    st.markdown(href, unsafe_allow_html=True)

else:
    st.info("⬆️ Carga la base de gestiones y asegúrate de haber completado los pasos previos.")

    # =============================================
# 📊 PASO 5A — ANÁLISIS EMPÍRICO DE EFECTIVIDAD
# =============================================

st.title("📊 Paso 5A — Análisis Empírico de Efectividad (Producto y Mora)")

# Subir base consolidada directamente
file_consolidado = st.file_uploader("📘 Cargar base consolidada (Base_Consolidada_Paso5.xlsx)", type=["xlsx"])

if file_consolidado:
    df = pd.read_excel(file_consolidado)
    df.columns = df.columns.str.strip().str.lower()

    # =========================
    # Verificar columnas
    # =========================
    cols_ok = ["grupop", "ciclo_mora_act", "deudor", "tiene_gestion_efectiva", "cantidad_promesas", "ultimo_pago"]
    faltantes = [c for c in cols_ok if c not in df.columns]
    if faltantes:
        st.error(f"❌ Faltan las columnas requeridas: {faltantes}")
        st.stop()

    # =========================
    # Agrupar
    # =========================
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

    # Exportar análisis
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        agg.to_excel(writer, index=False, sheet_name="Efectividad")
    buffer.seek(0)
    b64 = base64.b64encode(buffer.read()).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="Analisis_Efectividad_Cartera.xlsx">📥 Descargar análisis empírico en Excel</a>'
    st.markdown(href, unsafe_allow_html=True)

    # Gráfico
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
else:
    st.info("⬆️ Carga la base consolidada del Paso 5 para ejecutar este análisis.")


