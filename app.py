import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import unicodedata
import io, base64

st.set_page_config(page_title="Modelo Score Cartera", layout="wide")

# =============================================
# 📂 PASO 1 — CARGA Y LIMPIEZA DE BASE JURÍDICA
# =============================================
st.title("📂 Paso 1 — Carga y Limpieza de Base Jurídica")

file_ene_mar = st.file_uploader("📘 Enero-Marzo", type=["xlsx"])
file_abr_sep = st.file_uploader("📗 Abril-Septiembre", type=["xlsx"])

if file_ene_mar and file_abr_sep:
    df1 = pd.read_excel(file_ene_mar)
    df2 = pd.read_excel(file_abr_sep)
    df = pd.concat([df1, df2], ignore_index=True)

    # Limpieza
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_").str.replace("[^a-z0-9_]", "", regex=True)

    def limpiar_texto(t):
        if pd.isna(t): return t
        t = str(t).encode("utf-8", "ignore").decode("utf-8", "ignore")
        reemplazos = {"√ë":"Ñ","√±":"ñ","√©":"é","√¡":"á","√³":"ó","√º":"ú"}
        for k,v in reemplazos.items(): t = t.replace(k,v)
        return unicodedata.normalize("NFKD", t).strip()

    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].apply(limpiar_texto)

    st.session_state["df_limpio"] = df
    st.success(f"✅ Base jurídica cargada ({len(df):,} registros)")
    st.download_button("📥 Descargar base limpia", df.to_csv(index=False).encode("utf-8"), "base_juridica_limpia.csv", "text/csv")
else:
    st.info("⬆️ Sube las dos bases para continuar.")

# =============================================
# ⚙️ PASO 2 — CONSOLIDADO OPERATIVO
# =============================================
st.title("⚙️ Paso 2 — Consolidado con Pagos, Promesas y Gestiones")

file_pagos = st.file_uploader("💰 Cargar pagos (pagos_sudameris.xlsx)", type=["xlsx"])
file_promesas = st.file_uploader("🤝 Cargar promesas (promesas_sudameris.xlsx)", type=["xlsx"])
file_gestiones = st.file_uploader("📞 Cargar gestiones (gestion_sudameris.xlsx)", type=["xlsx"])

if "df_limpio" not in st.session_state:
    st.warning("⚠️ Primero carga la base jurídica limpia (Paso 1).")
else:
    df = st.session_state["df_limpio"].copy()
    df.columns = df.columns.str.lower().str.strip()

    # === PAGOS ===
    if file_pagos:
        df_pagos = pd.read_excel(file_pagos)
        df_pagos.columns = df_pagos.columns.str.lower().str.strip()

        col_doc = next((c for c in df_pagos.columns if "document" in c or "identific" in c), None)
        col_valor = next((c for c in df_pagos.columns if "total" in c or "valor" in c or "pago" in c), None)
        col_fecha = next((c for c in df_pagos.columns if "fecha" in c), None)

        if col_doc and col_valor:
            df_pagos = df_pagos.rename(columns={col_doc: "deudor", col_valor: "valor_pago"})
            if col_fecha:
                df_pagos = df_pagos.rename(columns={col_fecha: "fecha_pago"})
            df_pagos["valor_pago"] = pd.to_numeric(df_pagos["valor_pago"], errors="coerce")
            if "fecha_pago" in df_pagos.columns:
                df_pagos["fecha_pago"] = pd.to_datetime(df_pagos["fecha_pago"], errors="coerce")

            pagos_agg = (
                df_pagos.groupby("deudor")
                .agg(ultimo_pago=("valor_pago", "sum"),
                     cantidad_pagos=("valor_pago", "count"),
                     fecha_ultimo_pago=("fecha_pago", "max"))
                .reset_index()
            )
            df = df.merge(pagos_agg, on="deudor", how="left")
            st.success("💰 Pagos integrados correctamente.")
        else:
            st.error(f"❌ No se detectaron columnas válidas en pagos. Columnas: {list(df_pagos.columns)}")

    # === PROMESAS ===
    if file_promesas:
        prom = pd.read_excel(file_promesas)
        prom.columns = prom.columns.str.lower().str.strip()
        col_id = next((c for c in prom.columns if "identific" in c or "document" in c), None)
        if col_id:
            prom = prom.rename(columns={col_id: "deudor"})
            prom["valor_cuota_prometida"] = pd.to_numeric(prom.get("valor_cuota_prometida", 0), errors="coerce")
            prom["fecha_de_pago_prometida"] = pd.to_datetime(prom.get("fecha_de_pago_prometida"), errors="coerce")
            prom_agg = prom.groupby("deudor").agg(
                cantidad_promesas=("valor_cuota_prometida", "count"),
                valor_prometido=("valor_cuota_prometida", "sum"),
                fecha_ultima_promesa=("fecha_de_pago_prometida", "max")
            ).reset_index()
            df = df.merge(prom_agg, on="deudor", how="left")
            st.success("🤝 Promesas integradas correctamente.")
        else:
            st.error(f"❌ No se detectó columna de documento en promesas. Columnas: {list(prom.columns)}")

    # === GESTIONES ===
    if file_gestiones:
        gest = pd.read_excel(file_gestiones)
        gest.columns = gest.columns.str.lower().str.strip()
        col_id = next((c for c in gest.columns if "identific" in c), None)
        col_mejor = next((c for c in gest.columns if "mejor" in c), None)
        jerarquia = {
            "1. gestion efectiva soluciona mora": 1,
            "2. gestion efectiva sin pago": 2,
            "3. no efectiva mensaje con tercero": 3,
            "4. no efectiva mensaje maquina": 4,
            "5. no efectiva contacto con tercero": 5,
            "6. no efectiva": 6,
            "7. operativo": 7
        }
        gest["nivel_efectividad"] = gest[col_mejor].str.lower().map(jerarquia)
        gest_agg = (
            gest.sort_values("nivel_efectividad")
            .groupby(col_id, as_index=False)
            .first()[[col_id, col_mejor, "nivel_efectividad"]]
        )
        gest_agg["tiene_gestion_efectiva"] = gest_agg["nivel_efectividad"].apply(lambda x: 1 if x in [1, 2] else 0)
        gest_agg = gest_agg.rename(columns={col_id: "deudor"})
        df = df.merge(gest_agg, on="deudor", how="left")
        st.success("📞 Gestiones integradas correctamente.")

    # === LIMPIEZA FINAL + DESCARGA ===
    for c in ["ultimo_pago", "cantidad_pagos", "cantidad_promesas", "tiene_gestion_efectiva"]:
        if c in df.columns:
            df[c] = df[c].fillna(0)
    st.session_state["df_consolidado"] = df

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name="Consolidado")
    buffer.seek(0)
    b64 = base64.b64encode(buffer.read()).decode()
    st.markdown(f'<a href="data:application/octet-stream;base64,{b64}" download="Base_Consolidada.xlsx">📥 Descargar Base Consolidada</a>', unsafe_allow_html=True)

# =============================================
# 📊 PASO 3 — ANÁLISIS EMPÍRICO
# =============================================
st.title("📊 Paso 3 — Análisis Empírico de Efectividad (Producto y Mora)")

file_consol = st.file_uploader("📘 Cargar base consolidada (Base_Consolidada.xlsx)", type=["xlsx"])

if file_consol:
    df = pd.read_excel(file_consol)
    df.columns = df.columns.str.lower()

    cols_ok = ["grupop", "ciclo_mora_act", "deudor", "tiene_gestion_efectiva", "cantidad_promesas", "ultimo_pago"]
    faltantes = [c for c in cols_ok if c not in df.columns]
    if faltantes:
        st.error(f"❌ Faltan columnas requeridas: {faltantes}")
    else:
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
        agg["%_contacto"] = (agg["total_contacto"]/agg["total_clientes"]*100).round(2)
        agg["promesas_promedio"] = (agg["total_promesas"]/agg["total_clientes"]).round(2)
        agg["pago_promedio"] = (agg["total_pago_valor"]/agg["total_clientes"]).round(0)

        st.dataframe(agg, use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            agg.to_excel(writer, index=False, sheet_name="Efectividad")
        buffer.seek(0)
        b64 = base64.b64encode(buffer.read()).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="Analisis_Efectividad_Cartera.xlsx">📥 Descargar análisis empírico</a>'
        st.markdown(href, unsafe_allow_html=True)

        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax1.bar(agg["grupop"], agg["%_contacto"], label="% Contacto", alpha=0.7)
        ax1.plot(agg["grupop"], agg["promesas_promedio"], color="orange", marker="o", label="Promesas promedio")
        ax2 = ax1.twinx()
        ax2.plot(agg["grupop"], agg["pago_promedio"], color="green", marker="s", label="Pago promedio ($)")
        ax1.legend(loc="upper left")
        ax2.legend(loc="upper right")
        ax1.set_title("Indicadores de Efectividad por Producto")
        st.pyplot(fig)

        st.success("✅ Base lista para el modelo de regresión.")

