import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from io import BytesIO

# ==============================
# CONFIGURACIÓN
# ==============================
st.set_page_config(page_title="COS SCORE 1.1 — Recalibrado", layout="wide")

try:
    from xgboost import XGBClassifier
    XGBoost = True
except Exception:
    XGBoost = False

# ==============================
# FUNCIONES AUXILIARES
# ==============================
def to_datetime_safe(s):
    return pd.to_datetime(s, errors='coerce')

def days_since(series):
    dt = to_datetime_safe(series)
    return (pd.Timestamp.today().normalize() - dt).dt.days

def categorizar_capital(v):
    try:
        v = float(v)
    except:
        return np.nan
    if v < 500_000:
        return "R1"
    elif v < 2_000_000:
        return "R2"
    elif v < 5_000_000:
        return "R3"
    elif v < 10_000_000:
        return "R4"
    else:
        return "R5"

def safe_cols(df, cols):
    return [c for c in cols if c in df.columns]

# ==============================
# ENTRENAMIENTO AUTOMÁTICO CON DETECCIÓN DE DESBALANCE
# ==============================
def train_binary_model(df, target_col, num_cols, cat_cols, model_kind):
    df = df[~df[target_col].isna()]
    if df.empty or df[target_col].nunique() < 2:
        return None, None, ([], [])

    num_avail = [c for c in num_cols if c in df.columns]
    cat_avail = [c for c in cat_cols if c in df.columns]
    if len(num_avail) + len(cat_avail) == 0:
        return None, None, ([], [])

    X = df[num_avail + cat_avail].copy()
    y = df[target_col].astype(int)

    # Convertir tipos
    for c in cat_avail:
        X[c] = X[c].astype(str).fillna("DESCONOCIDO")
    for c in num_avail:
        X[c] = pd.to_numeric(X[c], errors="coerce")

    # Calcular ratio de desbalance
    pos = y.sum()
    neg = len(y) - pos
    ratio = neg / max(pos, 1)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    num_proc = Pipeline([("imputer", SimpleImputer(strategy="median"))])

    try:
        onehot = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        onehot = OneHotEncoder(handle_unknown="ignore", sparse=False)

    cat_proc = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", onehot)
    ])

    prep = ColumnTransformer([
        ("num", num_proc, num_avail),
        ("cat", cat_proc, cat_avail)
    ])

    # ==============================
    # MODELO SEGÚN TIPO + AJUSTE DE DESBALANCE
    # ==============================
    if model_kind == "logit":
        model = LogisticRegression(max_iter=300, class_weight="balanced")
    elif model_kind == "rf":
        model = RandomForestClassifier(
            n_estimators=300, random_state=42,
            class_weight="balanced_subsample", n_jobs=-1
        )
    elif model_kind == "xgb":
        if XGBoost:
            model = XGBClassifier(
                n_estimators=400, max_depth=5, learning_rate=0.08,
                subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0,
                random_state=42, objective="binary:logistic",
                eval_metric="auc", tree_method="hist",
                scale_pos_weight=ratio  # ajuste automático por desbalance
            )
        else:
            model = GradientBoostingClassifier(random_state=42)
    else:
        model = GradientBoostingClassifier(random_state=42)

    clf = Pipeline([("prep", prep), ("model", model)])
    clf.fit(X_train, y_train)

    try:
        auc = roc_auc_score(y_test, clf.predict_proba(X_test)[:, 1])
    except Exception:
        auc = None

    return clf, auc, (num_avail, cat_avail)

def add_pred(df, pipe, num, cat, out):
    if pipe is None:
        df[out] = np.nan
        return df
    try:
        df[out] = pipe.predict_proba(df[safe_cols(df, num + cat)])[:, 1]
        df[out] = df[out].clip(0.05, 0.95)  # suavizado
    except:
        df[out] = np.nan
    return df

# ==============================
# INTERFAZ
# ==============================
tab1, tab2 = st.tabs(["🧠 Modelo COS SCORE 1.1", "📊 Análisis de Resultados"])

with tab1:
    uploaded = st.file_uploader("📂 Cargar archivo Excel", type=["xlsx"])

    if uploaded:
        df = pd.read_excel(uploaded)
        df.columns = [str(c).strip() for c in df.columns]

        st.info(f"Base cargada con {df.shape[0]} filas y {df.shape[1]} columnas.")

        # Rango de capital
        if 'Capital Act' in df.columns:
            df['RANGO_CAPITAL'] = df['Capital Act'].apply(categorizar_capital)
        else:
            df['RANGO_CAPITAL'] = np.nan

        # Variables temporales
        if 'FECHA_ULTIMO_CONTACTO' in df:
            df['DIAS_DESDE_ULT_CONTACTO'] = days_since(df['FECHA_ULTIMO_CONTACTO'])
        if 'FECHA_ULTIMO_PAGO' in df:
            df['DIAS_DESDE_ULT_PAGO'] = days_since(df['FECHA_ULTIMO_PAGO'])
        if 'FECHA_DE_PROMESA' in df:
            df['DIAS_DESDE_PROMESA'] = days_since(df['FECHA_DE_PROMESA'])

        # Targets binarios
        for t in ['TIENE_GESTION', 'TIENE_PROMESA', 'TIENE_PAGO']:
            if t in df.columns:
                df[t] = pd.to_numeric(df[t], errors='coerce').fillna(0).astype(int)

        num_contact = ['Dias Mora Fin', 'Capital Act', 'CANTIDAD_GESTIONES', 'DIAS_DESDE_ULT_CONTACTO']
        cat_contact = ['Producto', 'RANGO_CAPITAL', 'ETAPA JURIDICA', 'MEJOR_CONTACTO', 'Usuario Final', 'CIUDAD']

        num_neg = ['Dias Mora Fin', 'Capital Act', 'CANTIDAD_DE_PROMESAS', 'CANTIDAD_GESTIONES']
        cat_neg = ['Producto', 'RANGO_CAPITAL', 'MEJOR_GESTION', 'TIPO_DE_ACUERDO', 'Usuario Final', 'ETAPA JURIDICA']

        num_pago = ['Dias Mora Fin', 'Capital Act', 'VALOR NEGOCIADO', 'CANTIDAD_PAGOS', 'SUMA_DE_PAGOS',
                    'DIAS_DESDE_ULT_PAGO', 'DIAS_DESDE_PROMESA']
        cat_pago = ['Producto', 'RANGO_CAPITAL', 'TIPO_PAGO', 'ETAPA JURIDICA']

        with st.spinner("Entrenando modelos y calculando probabilidades..."):
            aucs = {}

            if 'TIENE_GESTION' in df:
                m1, auc1, f1 = train_binary_model(df, 'TIENE_GESTION', num_contact, cat_contact, 'logit')
                aucs['Contacto'] = auc1
                df = add_pred(df, m1, *f1, 'P_contacto')
            if 'TIENE_PROMESA' in df:
                num_neg2 = num_neg + (['P_contacto'] if 'P_contacto' in df else [])
                m2, auc2, f2 = train_binary_model(df, 'TIENE_PROMESA', num_neg2, cat_neg, 'rf')
                aucs['Negociacion'] = auc2
                df = add_pred(df, m2, *f2, 'P_negociacion')
            if 'TIENE_PAGO' in df:
                num_pago2 = num_pago + (['P_negociacion'] if 'P_negociacion' in df else [])
                m3, auc3, f3 = train_binary_model(df, 'TIENE_PAGO', num_pago2, cat_pago, 'xgb')
                aucs['Pago'] = auc3
                df = add_pred(df, m3, *f3, 'P_pago')

            df['SCORE_FINAL'] = (0.35*df['P_contacto'].fillna(0) +
                                 0.45*df['P_negociacion'].fillna(0) +
                                 0.20*df['P_pago'].fillna(0)) * 100

            df['CATEGORIA'] = pd.cut(df['SCORE_FINAL'],
                                     bins=[-1, 49.9, 79.9, 100],
                                     labels=['BAJA', 'MEDIA', 'ALTA'])
            st.success("✅ Modelo recalibrado ejecutado correctamente.")

        st.subheader("Vista previa de resultados")
        cols_show = ['Deudor','Producto','RANGO_CAPITAL','P_contacto','P_negociacion','P_pago','SCORE_FINAL','CATEGORIA']
        st.dataframe(df[safe_cols(df, cols_show)].head(15))

        st.subheader("Métricas AUC (calidad del modelo)")
        for k, v in aucs.items():
            st.write(f"- {k}: **{v:.3f}**" if v is not None else f"- {k}: sin datos suficientes")

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Scored')
        st.download_button(
            "📥 Descargar resultados recalibrados",
            data=output.getvalue(),
            file_name="asig_consolidada_score_1_1.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.session_state["df_resultado"] = df

with tab2:
    if "df_resultado" not in st.session_state:
        st.warning("⚠️ Primero ejecuta el modelo en la pestaña anterior.")
    else:
        df = st.session_state["df_resultado"]
        st.subheader("Distribución de cada submodelo")

        for col in ['P_contacto', 'P_negociacion', 'P_pago']:
            fig, ax = plt.subplots()
            ax.hist(df[col], bins=20, color="skyblue", edgecolor="gray")
            ax.set_title(f"Distribución de {col}")
            st.pyplot(fig)

        st.subheader("Promedio de Score por Categoría")
        prom = df.groupby("CATEGORIA")["SCORE_FINAL"].mean()
        st.bar_chart(prom)

        if "TIENE_PAGO" in df.columns:
            st.subheader("Comparación: SCORE vs TIENE_PAGO")
            comp = df.groupby("TIENE_PAGO")["SCORE_FINAL"].mean().rename({0:"Sin pago", 1:"Con pago"})
            st.bar_chart(comp)
