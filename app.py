import streamlit as st
import pandas as pd
import numpy as np
import unicodedata
import io
from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import LogisticRegression

# ==========================
# ⚙️ CONFIGURACIÓN
# ==========================
st.set_page_config(page_title="Sudameris Castigada — Score de Recuperación", layout="wide")
st.title("📊 Sudameris — Modelo de Probabilidad de Pago (Cartera Castigada 2025)")

st.markdown("""
Esta app unifica las bases de **Asignaciones (enero–septiembre)**, **Promesas**, **Pagos** y **Gestión**,  
para generar un **consolidado completo por cliente** y calcular la **probabilidad de pago o recuperación**.
""")

# ==========================
# 🧩 FUNCIONES AUXILIARES
# ==========================
def normalizar_columna(c):
    c = c.strip().lower()
    c = ''.join(ch for ch in unicodedata.normalize('NFD', c) if unicodedata.category(ch) != 'Mn')
    c = c.replace(" ", "_").replace("-", "_")
    return c

def cargar_y_normalizar(archivo, prefijo):
    df = pd.read_excel(archivo)
    df.columns = [normalizar_columna(c) for c in df.columns]
    df = df.add_prefix(prefijo + "_")
    for col in df.columns:
        if "deudor" in col and prefijo + "_deudor" != col:
            df.rename(columns={col: prefijo + "_deudor"}, inplace=True)
            break
    return df

# ==========================
# 📂 CARGA DE ARCHIVOS
# ==========================
st.sidebar.header("📂 Cargar archivos Excel")

asig1 = st.sidebar.file_uploader("📘 Asignaciones Enero–Marzo", type=["xlsx"])
asig2 = st.sidebar.file_uploader("📘 Asignaciones Abril–Septiembre", type=["xlsx"])
prom_file = st.sidebar.file_uploader("📙 Promesas", type=["xlsx"])
pagos_file = st.sidebar.file_uploader("📗 Pagos", type=["xlsx"])
gestion_file = st.sidebar.file_uploader("📕 Gestión", type=["xlsx"])

if asig1 and asig2 and prom_file and pagos_file and gestion_file:
    st.success("✅ Todos los archivos cargados correctamente")

    # ==========================
    # 🔧 CARGAR Y NORMALIZAR BASES
    # ==========================
    asig_ene_mar = cargar_y_normalizar(asig1, "asignaciones")
    asig_abr_sep = cargar_y_normalizar(asig2, "asignaciones")

    # Alinear y unir asignaciones
    columnas_comunes = list(set(asig_ene_mar.columns).intersection(set(asig_abr_sep.columns)))
    asignaciones = pd.concat([asig_ene_mar[columnas_comunes], asig_abr_sep[columnas_comunes]], ignore_index=True)
    asignaciones.drop_duplicates(subset=["asignaciones_deudor"], keep="last", inplace=True)
    asignaciones.rename(columns={"asignaciones_deudor": "deudor"}, inplace=True)
    asignaciones["deudor"] = asignaciones["deudor"].astype(str).str.strip()

    # Cargar las demás bases
    prom = cargar_y_normalizar(prom_file, "promesas")
    pagos = cargar_y_normalizar(pagos_file, "pagos")
    gest = cargar_y_normalizar(gestion_file, "gestion")

    # Normalizar llaves
    for df in [prom, pagos, gest]:
        colnames = [c for c in df.columns if "deudor" in c]
        if colnames:
            df.rename(columns={colnames[0]: "deudor"}, inplace=True)
        df["deudor"] = df["deudor"].astype(str).str.strip()

    # ==========================
    # 🔗 AGRUPAR Y UNIR TODO
    # ==========================
    prom_grouped = prom.groupby("deudor").agg("first").reset_index()
    pagos_grouped = pagos.groupby("deudor").agg("first").reset_index()
    gest_grouped = gest.groupby("deudor").agg("first").reset_index()

    df_final = asignaciones.merge(prom_grouped, on="deudor", how="left")
    df_final = df_final.merge(pagos_grouped, on="deudor", how="left")
    df_final = df_final.merge(gest_grouped, on="deudor", how="left")

    st.subheader("📋 Vista previa del consolidado (primeros 10 clientes)")
    st.dataframe(df_final.head(10), use_container_width=True)

    # ==========================
    # 🤖 MODELO DE SCORE
    # ==========================
    st.markdown("---")
    st.subheader("🧮 Cálculo de Probabilidad de Pago / Score de Recuperación")

    if st.button("Calcular probabilidad de pago para toda la base"):
        with st.spinner("Calculando, por favor espera..."):
            df_modelo = df_final.copy()

            # Variables derivadas
            def safe_days_diff(fecha):
                try:
                    return (pd.Timestamp.today() - pd.to_datetime(fecha)).days
                except:
                    return np.nan

            df_modelo["dias_desde_ultimo_pago"] = df_modelo["pagos_fecha_de_pago"].apply(safe_days_diff) if "pagos_fecha_de_pago" in df_modelo else 0
            df_modelo["dias_desde_ultima_gestion"] = df_modelo["gestion_fecha_gestion"].apply(safe_days_diff) if "gestion_fecha_gestion" in df_modelo else 0

            df_modelo["ratio_pago_saldo"] = pd.to_numeric(df_modelo.get("pagos_total_de_pago"), errors='coerce') / pd.to_numeric(df_modelo.get("asignaciones_saldo_act"), errors='coerce')
            df_modelo["efectividad_promesas"] = pd.to_numeric(df_modelo.get("promesas_valor_de_pago"), errors='coerce') / pd.to_numeric(df_modelo.get("promesas_valor_acuerdo"), errors='coerce')

            df_modelo = df_modelo.fillna(0)

            # Variables numéricas
            features = [
                "asignaciones_dias_mora_fin",
                "asignaciones_capital_act",
                "pagos_total_de_pago",
                "promesas_valor_acuerdo",
                "dias_desde_ultimo_pago",
                "dias_desde_ultima_gestion",
                "ratio_pago_saldo",
                "efectividad_promesas"
            ]
            for f in features:
                if f not in df_modelo.columns:
                    df_modelo[f] = 0
                df_modelo[f] = pd.to_numeric(df_modelo[f], errors='coerce')

            X = df_modelo[features].fillna(0)
            scaler = MinMaxScaler()
            X_scaled = scaler.fit_transform(X)

            # Modelo logístico base (sintético)
            y = (X_scaled[:, 0]*-0.3 + X_scaled[:, 2]*0.6 + X_scaled[:, 3]*0.4 + X_scaled[:, 6]*0.5) > 0.5
            y = y.astype(int)
            model = LogisticRegression()
            model.fit(X_scaled, y)
            prob_pago = model.predict_proba(X_scaled)[:, 1]

            df_modelo["probabilidad_pago"] = np.round(prob_pago, 4)
            df_modelo["score_recuperacion"] = np.round(df_modelo["probabilidad_pago"] * 100, 2)

            def segmentar(p):
                if p >= 0.8: return "Alta"
                elif p >= 0.6: return "Media"
                else: return "Baja"

            df_modelo["segmento_recuperacion"] = df_modelo["probabilidad_pago"].apply(segmentar)

            st.success("✅ Score calculado correctamente")
            st.dataframe(df_modelo[["deudor", "probabilidad_pago", "score_recuperacion", "segmento_recuperacion"]].head(20))

            # Descarga Excel
            excel_buffer = io.BytesIO()
            df_modelo.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)
            st.download_button(
                label="⬇️ Descargar base completa con Score de Recuperación",
                data=excel_buffer,
                file_name="sudameris_score_recuperacion.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

else:
    st.info("Carga los 5 archivos (Asignaciones enero–marzo, abril–septiembre, Promesas, Pagos y Gestión) para iniciar.")
