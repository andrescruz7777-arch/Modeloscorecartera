import streamlit as st
import pandas as pd
import numpy as np
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
# 🧠 CONFIGURACIÓN GENERAL
# ==============================
st.set_page_config(page_title="COS SCORE 1.0 — Contacto, Negociación y Pago", layout="wide")

try:
    from xgboost import XGBClassifier
    XGB_AVAILABLE = True
except Exception:
    XGB_AVAILABLE = False

# ==============================
# 📂 CARGA DEL EXCEL
# ==============================
uploaded = st.file_uploader("📂 Cargar archivo Excel", type=["xlsx"])

# ------------------------------
# 🧩 FUNCIONES AUXILIARES
# ------------------------------
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

def train_binary_model(df, target_col, num_cols, cat_cols, model_kind):
    df = df[~df[target_col].isna()]
    if df.empty or df[target_col].nunique() < 2:
        return None, None, ([], [])

    num_avail = safe_cols(df, num_cols)
    cat_avail = safe_cols(df, cat_cols)
    if len(num_avail) + len(cat_avail) == 0:
        return None, None, ([], [])

    X = df[num_avail + cat_avail]
    y = df[target_col].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    num_proc = Pipeline([("imputer", SimpleImputer(strategy="median"))])
    cat_proc = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse=False))
    ])
    prep = ColumnTransformer([("num", num_proc, num_avail), ("cat", cat_proc, cat_avail)])

    if model_kind == "logit":
        model = LogisticRegression(max_iter=200, class_weight="balanced")
    elif model_kind == "rf":
        model = RandomForestClassifier(
            n_estimators=300, min_samples_leaf=2, random_state=42,
            n_jobs=-1, class_weight="balanced_subsample"
        )
    elif model_kind == "xgb":
        model = XGBClassifier(
            n_estimators=400, max_depth=5, learning_rate=0.08,
            subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0,
            random_state=42, objective="binary:logistic", eval_metric="auc",
            tree_method="hist"
        ) if XGBoost else GradientBoostingClassifier(random_state=42)
    else:
        model = GradientBoostingClassifier(random_state=42)

    clf = Pipeline([("prep", prep), ("model", model)])
    clf.fit(X_train, y_train)
    try:
        auc = roc_auc_score(y_test, clf.predict_proba(X_test)[:, 1])
    except:
        auc = None
    return clf, auc, (num_avail, cat_avail)

def add_pred(df, pipe, num, cat, out):
    if pipe is None:
        df[out] = np.nan
        return df
    try:
        df[out] = pipe.predict_proba(df[safe_cols(df, num + cat)])[:, 1]
    except:
        df[out] = np.nan
    return df

# ==============================
# 🧠 EJECUCIÓN DEL MODELO
# ==============================
if uploaded:
    df = pd.read_excel(uploaded)
    df.columns = [str(c).strip() for c in df.columns]

    st.info(f"Base cargada con {df.shape[0]} filas y {df.shape[1]} columnas.")

    df['RANGO_CAPITAL'] = df.get('Capital Act', np.nan).apply(categorizar_capital)
    if 'FECHA_ULTIMO_CONTACTO' in df:
        df['DIAS_DESDE_ULT_CONTACTO'] = days_since(df['FECHA_ULTIMO_CONTACTO'])
    if 'FECHA_ULTIMO_PAGO' in df:
        df['DIAS_DESDE_ULT_PAGO'] = days_since(df['FECHA_ULTIMO_PAGO'])
    if 'FECHA_DE_PROMESA' in df:
        df['DIAS_DESDE_PROMESA'] = days_since(df['FECHA_DE_PROMESA'])

    for t in ['TIENE_GESTION', 'TIENE_PROMESA', 'TIENE_PAGO']:
        if t in df.columns:
            df[t] = pd.to_numeric(df[t], errors='coerce').fillna(0).astype(int)

    # -----------------
    # Modelos
    # -----------------
    num_contact = ['Dias Mora Fin', 'Capital Act', 'CANTIDAD_GESTIONES', 'DIAS_DESDE_ULT_CONTACTO']
    cat_contact = ['Producto', 'RANGO_CAPITAL', 'ETAPA JURIDICA', 'MEJOR_CONTACTO', 'Usuario Final', 'CIUDAD']

    num_neg = ['Dias Mora Fin', 'Capital Act', 'CANTIDAD_DE_PROMESAS', 'CANTIDAD_GESTIONES']
    cat_neg = ['Producto', 'RANGO_CAPITAL', 'MEJOR_GESTION', 'TIPO_DE_ACUERDO', 'Usuario Final', 'ETAPA JURIDICA']

    num_pago = ['Dias Mora Fin', 'Capital Act', 'VALOR NEGOCIADO', 'CANTIDAD_PAGOS', 'SUMA_DE_PAGOS',
                'DIAS_DESDE_ULT_PAGO', 'DIAS_DESDE_PROMESA']
    cat_pago = ['Producto', 'RANGO_CAPITAL', 'TIPO_PAGO', 'ETAPA JURIDICA']

    with st.spinner("Entrenando modelos..."):
        if 'TIENE_GESTION' in df:
            m1, auc1, f1 = train_binary_model(df, 'TIENE_GESTION', num_contact, cat_contact, 'logit')
            df = add_pred(df, m1, *f1, 'P_contacto')
        if 'TIENE_PROMESA' in df:
            num_neg2 = num_neg + (['P_contacto'] if 'P_contacto' in df else [])
            m2, auc2, f2 = train_binary_model(df, 'TIENE_PROMESA', num_neg2, cat_neg, 'rf')
            df = add_pred(df, m2, *f2, 'P_negociacion')
        if 'TIENE_PAGO' in df:
            num_pago2 = num_pago + (['P_negociacion'] if 'P_negociacion' in df else [])
            m3, auc3, f3 = train_binary_model(df, 'TIENE_PAGO', num_pago2, cat_pago, 'xgb')
            df = add_pred(df, m3, *f3, 'P_pago')

        df['SCORE_FINAL'] = (0.3*df['P_contacto'].fillna(0) +
                             0.3*df['P_negociacion'].fillna(0) +
                             0.4*df['P_pago'].fillna(0)) * 100
        df['CATEGORIA'] = pd.cut(df['SCORE_FINAL'],
                                 bins=[-1, 49.9, 79.9, 100],
                                 labels=['BAJA', 'MEDIA', 'ALTA'])
        st.success("✅ Modelo ejecutado correctamente.")

    # ==============================
    # 📈 RESULTADOS
    # ==============================
    st.subheader("📊 Vista previa de resultados")
    st.dataframe(df[['Deudor','Producto','RANGO_CAPITAL','P_contacto','P_negociacion','P_pago','SCORE_FINAL','CATEGORIA']].head(15))

    # Descargar Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Scored')
    st.download_button(
        "📥 Descargar resultados COS SCORE",
        data=output.getvalue(),
        file_name="asig_consolidada_scored.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
