import pandas as pd

# ==========================
# 📂 PASO 1: CARGA DE DATOS
# ==========================

# Archivos base
archivo_ene_mar = "jur_ene_marzo.xlsx"
archivo_abr_sep = "jur_abril_sep.xlsx"

# Mostrar las hojas disponibles
print("📘 Hojas en enero-marzo:")
print(pd.ExcelFile(archivo_ene_mar).sheet_names)
print("\n📗 Hojas en abril-septiembre:")
print(pd.ExcelFile(archivo_abr_sep).sheet_names)

# Cargar la primera hoja de cada uno
df_ene_mar = pd.read_excel(archivo_ene_mar, sheet_name=0)
df_abr_sep = pd.read_excel(archivo_abr_sep, sheet_name=0)

# Mostrar estructura inicial
print("\n🧩 Estructura enero-marzo:")
print(df_ene_mar.head(3))
print("\nColumnas enero-marzo:")
print(list(df_ene_mar.columns))

print("\n🧩 Estructura abril-septiembre:")
print(df_abr_sep.head(3))
print("\nColumnas abril-septiembre:")
print(list(df_abr_sep.columns))

# ==================================
# 🔍 Comparar columnas de ambos sets
# ==================================
col_diff_1 = set(df_ene_mar.columns) - set(df_abr_sep.columns)
col_diff_2 = set(df_abr_sep.columns) - set(df_ene_mar.columns)

print("\n🧾 Columnas que están en enero-marzo pero no en abril-septiembre:", col_diff_1)
print("🧾 Columnas que están en abril-septiembre pero no en enero-marzo:", col_diff_2)

# ==============================
# 🧮 Unificar estructura inicial
# ==============================
df_unificado = pd.concat([df_ene_mar, df_abr_sep], ignore_index=True, sort=False)

print("\n✅ Tamaño total del DataFrame unificado:", df_unificado.shape)
print("\nColumnas finales:")
print(list(df_unificado.columns))

# Vista previa general
print("\n🔎 Vista previa del consolidado:")
print(df_unificado.sample(5))
