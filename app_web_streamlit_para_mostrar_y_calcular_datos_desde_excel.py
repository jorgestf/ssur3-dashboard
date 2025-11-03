import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="SSUR3 – Comparables y Objetivos", layout="wide")

# =============================
# 🎯 Objetivo
# =============================
# Esta app replica el layout del cuadro que muestras: 3 bloques principales
# (Comparables Semanas, Comparable del Mes, Evolución Objetivo) y un panel de Control.
# **Funciona con tu Excel** y te deja mapear las columnas a los campos necesarios.

st.title("📈 Panel de comparables y objetivo")
st.caption("Sube tu Excel, mapea columnas y obtén el tablero con formatos y totales.")

# ---------- Utilidades de estilo ----------
@st.cache_data(show_spinner=False)
def load_excel(file: BytesIO | str, sheet_name=None) -> dict:
    xls = pd.ExcelFile(file)
    sheets = {}
    for s in xls.sheet_names:
        if (sheet_name is None) or (s == sheet_name):
            df = xls.parse(s)
            df.columns = [str(c).strip() for c in df.columns]
            sheets[s] = df
    return sheets


def fmt_money(x):
    try:
        return f"{x:,.0f} €".replace(",", ".")
    except Exception:
        return x


def fmt_pct(x):
    try:
        return f"{x*100:.2f}%" if abs(x) < 10 else f"{x:.2f}%"  # admite ya en %
    except Exception:
        return x


def to_pct(series):
    """Convierte series que vengan como 12,3% o 0,123 a float fraccional (0-1)."""
    s = series.copy()
    if s.dtype == object:
        s = s.str.replace("%", "", regex=False).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    s = pd.to_numeric(s, errors="coerce")
    # Heurística: si media > 1.5 asumimos que venía en % (ej: 12.3) y dividimos por 100
    if pd.Series(s).mean(skipna=True) and pd.Series(s).mean(skipna=True) > 1.5:
        s = s / 100.0
    return s


def heatmap_pct(df_pct: pd.DataFrame) -> pd.io.formats.style.Styler:
    def color(v):
        if pd.isna(v):
            return ""
        # v fraccional (0=0%, -0.2=-20%)
        if v >= 0.05:
            return "background-color:#d6f5d6"  # verde suave
        if v >= 0:
            return "background-color:#ecf9ec"  # verde muy suave
        if v <= -0.05:
            return "background-color:#f8d7da"  # rojo suave
        return "background-color:#fdecec"     # rojo muy suave
    return df_pct.style.applymap(color)

# ---------- Sidebar: Carga y control ----------
st.sidebar.header("⚙️ Control")
mode = st.sidebar.radio("Origen de datos", ["Subir Excel", "Ruta local"], index=0)
excel_obj = None
if mode == "Subir Excel":
    up = st.sidebar.file_uploader("Excel (.xlsx)", type=["xlsx", "xlsm", "xls"], accept_multiple_files=False)
    if up:
        excel_obj = up
else:
    path = st.sidebar.text_input("Ruta local", value="")
    if path:
        excel_obj = path

if not excel_obj:
    st.info("👈 Sube un Excel o indica la ruta para continuar.")
    st.stop()

try:
    sheets = load_excel(excel_obj)
except Exception as e:
    st.error(f"No se pudo leer el Excel: {e}")
    st.stop()

sheet = st.sidebar.selectbox("Hoja", list(sheets.keys()))
df_raw = sheets[sheet].copy()

if df_raw.empty:
    st.warning("La hoja está vacía.")
    st.stop()

# ---------- Mapeo de columnas ----------
st.sidebar.subheader("Mapeo de columnas")
cols = df_raw.columns.tolist()
col_id = st.sidebar.selectbox("Código tienda (COD_TDA)", options=cols)
col_name = st.sidebar.selectbox("Nombre tienda (NOM_TDA)", options=cols)

st.sidebar.markdown("**Comparables por semanas (4 columnas)**")
col_w41 = st.sidebar.selectbox("Semana -3", options=cols, index=min(2, len(cols)-1))
col_w42 = st.sidebar.selectbox("Semana -2", options=cols, index=min(3, len(cols)-1))
col_w43 = st.sidebar.selectbox("Semana -1", options=cols, index=min(4, len(cols)-1))
col_w44 = st.sidebar.selectbox("Semana 0", options=cols, index=min(5, len(cols)-1))

st.sidebar.markdown("**Comparable del mes**")
col_p1 = st.sidebar.selectbox("Periodo 1 (real)", options=cols)
col_p2 = st.sidebar.selectbox("Periodo 2 (comparativo)", options=cols)

st.sidebar.markdown("**Objetivo**")
col_obj = st.sidebar.selectbox("Objetivo del mes", options=cols)

# Fechas de control (solo visuales / filtros futuros)
st.sidebar.markdown("---")
week_num = st.sidebar.number_input("Semana a analizar", min_value=1, max_value=53, value=44)
month_label = st.sidebar.text_input("Mes (texto)", value="OCTUBRE")

# ---------- Preparación de datos ----------
base = df_raw[[col_id, col_name]].copy()
base = base.rename(columns={col_id: "COD_TDA", col_name: "NOM_TDA"})

# Semanas en % -> convertir a fracción
for src, dst in zip([col_w44, col_w43, col_w42, col_w41], ["W0", "W-1", "W-2", "W-3"]):
    base[dst] = to_pct(df_raw[src])

# Mes: números monetarios
p1 = pd.to_numeric(df_raw[col_p1], errors="coerce")
p2 = pd.to_numeric(df_raw[col_p2], errors="coerce")
base["PERIODO_1"] = p1
base["PERIODO_2"] = p2
base["DIF"] = base["PERIODO_1"] - base["PERIODO_2"]
base["%DIF"] = np.where(base["PERIODO_2"].eq(0), np.nan, base["DIF"] / base["PERIODO_2"])

# Objetivo
obj = pd.to_numeric(df_raw[col_obj], errors="coerce")
base["OBJETIVO"] = obj
base["DIF_OBJ_P1"] = base["OBJETIVO"] - base["PERIODO_1"]
base["%OBJ"] = np.where(base["OBJETIVO"].eq(0), np.nan, base["PERIODO_1"] / base["OBJETIVO"])

# Totales
totales = pd.DataFrame({
    "COD_TDA": ["TOTAL"],
    "NOM_TDA": ["Todas las tiendas"],
    "W0": [base["W0"].mean(skipna=True)],
    "W-1": [base["W-1"].mean(skipna=True)],
    "W-2": [base["W-2"].mean(skipna=True)],
    "W-3": [base["W-3"].mean(skipna=True)],
    "PERIODO_1": [base["PERIODO_1"].sum(skipna=True)],
    "PERIODO_2": [base["PERIODO_2"].sum(skipna=True)],
    "DIF": [(base["PERIODO_1"].sum(skipna=True) - base["PERIODO_2"].sum(skipna=True))],
    "%DIF": [
        (base["PERIODO_1"].sum(skipna=True) - base["PERIODO_2"].sum(skipna=True)) / base["PERIODO_2"].sum(skipna=True)
        if base["PERIODO_2"].sum(skipna=True) else np.nan
    ],
    "OBJETIVO": [base["OBJETIVO"].sum(skipna=True)],
    "DIF_OBJ_P1": [base["OBJETIVO"].sum(skipna=True) - base["PERIODO_1"].sum(skipna=True)],
    "%OBJ": [
        base["PERIODO_1"].sum(skipna=True) / base["OBJETIVO"].sum(skipna=True)
        if base["OBJETIVO"].sum(skipna=True) else np.nan
    ],
})

# =============================
# 📊 Layout principal
# =============================
left, mid, right = st.columns([1.2, 1.2, 0.9])

with left:
    st.subheader("COMPARABLE HISTÓRICO ÚLTIMAS SEMANAS")
    semanas = base[["COD_TDA", "NOM_TDA", "W-3", "W-2", "W-1", "W0"]].copy()
    semanas.columns = ["COD_TDA", "NOM_TDA", f"{week_num-3}", f"{week_num-2}", f"{week_num-1}", f"{week_num}"]
    sty = heatmap_pct(semanas.set_index(["COD_TDA", "NOM_TDA"]))
    sty = sty.format(lambda v: f"{v*100:.2f}%" if pd.notna(v) else "")
    st.dataframe(sty, use_container_width=True)

with mid:
    st.subheader("COMPARABLE HISTÓRICO DEL MES")
    mes = base[["COD_TDA", "NOM_TDA", "PERIODO_1", "PERIODO_2", "DIF", "%DIF"]].copy()
    mes.columns = ["COD_TDA", "NOM_TDA", "PERIODO 1", "PERIODO 2", "DIFERENCIA", "% DIFERENCIA"]
    st.dataframe(
        mes.style.format({
            "PERIODO 1": fmt_money,
            "PERIODO 2": fmt_money,
            "DIFERENCIA": fmt_money,
            "% DIFERENCIA": lambda v: f"{v*100:.2f}%" if pd.notna(v) else ""
        }).background_gradient(subset=["% DIFERENCIA"], cmap="RdYlGn"),
        use_container_width=True,
    )

with right:
    st.subheader("EVOLUCIÓN OBJETIVO")
    objdf = base[["COD_TDA", "NOM_TDA", "OBJETIVO", "DIF_OBJ_P1", "%OBJ"]].copy()
    objdf.columns = ["COD_TDA", "NOM_TDA", f"OBJETIVO DE {month_label}", "DIFER. CON PERIODO 1", "% OBJETIVO CONSEGUIDO"]
    st.dataframe(
        objdf.style.format({
            f"OBJETIVO DE {month_label}": fmt_money,
            "DIFER. CON PERIODO 1": fmt_money,
            "% OBJETIVO CONSEGUIDO": lambda v: f"{v*100:.2f}%" if pd.notna(v) else ""
        }).background_gradient(subset=["% OBJETIVO CONSEGUIDO"], cmap="YlGn"),
        use_container_width=True,
    )

# ---------- Totales al pie ----------
st.markdown("---")
st.subheader("Totales")

tot_sem = totales[["COD_TDA", "NOM_TDA", "W-3", "W-2", "W-1", "W0"]].copy()
tot_sem.columns = ["COD_TDA", "NOM_TDA", f"{week_num-3}", f"{week_num-2}", f"{week_num-1}", f"{week_num}"]

c1, c2, c3 = st.columns([1.2, 1.2, 0.9])
with c1:
    st.dataframe(
        tot_sem.set_index(["COD_TDA", "NOM_TDA"]).style.format(lambda v: f"{v*100:.2f}%" if pd.notna(v) else ""),
        use_container_width=True,
    )
with c2:
    mes_tot = totales[["PERIODO_1", "PERIODO_2", "DIF", "%DIF"]].copy()
    mes_tot.columns = ["PERIODO 1", "PERIODO 2", "DIFERENCIA", "% DIFERENCIA"]
    st.dataframe(
        mes_tot.style.format({
            "PERIODO 1": fmt_money,
            "PERIODO 2": fmt_money,
            "DIFERENCIA": fmt_money,
            "% DIFERENCIA": lambda v: f"{v*100:.2f}%" if pd.notna(v) else ""
        }),
        use_container_width=True,
    )
with c3:
    obj_tot = totales[["OBJETIVO", "DIF_OBJ_P1", "%OBJ"]].copy()
    obj_tot.columns = [f"OBJETIVO DE {month_label}", "DIFER. CON PERIODO 1", "% OBJETIVO CONSEGUIDO"]
    st.dataframe(
        obj_tot.style.format({
            f"OBJETIVO DE {month_label}": fmt_money,
            "DIFER. CON PERIODO 1": fmt_money,
            "% OBJETIVO CONSEGUIDO": lambda v: f"{v*100:.2f}%" if pd.notna(v) else ""
        }),
        use_container_width=True,
    )

# ---------- Descargas ----------
st.markdown("---")
colA, colB, colC = st.columns(3)
with colA:
    csv_a = semanas.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Descargar comparables semanas (CSV)", data=csv_a, file_name="comparables_semanas.csv", mime="text/csv")
with colB:
    csv_b = mes.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Descargar comparable mes (CSV)", data=csv_b, file_name="comparable_mes.csv", mime="text/csv")
with colC:
    csv_c = objdf.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Descargar evolución objetivo (CSV)", data=csv_c, file_name="evolucion_objetivo.csv", mime="text/csv")

# ---------- Notas ----------
st.caption(
    """
    **Notas**
    - Puedes mapear cualquier columna de tu Excel a los campos requeridos desde la barra lateral.
    - Las columnas de semanas deben ser porcentajes (por ejemplo: -20,5% o -0,205). La app detecta y normaliza el formato.
    - Los periodos y objetivo se interpretan como importes (número). Ajusta separadores en tu Excel si fuera necesario.
    - Si quieres bloquear el mapeo y dejar los nombres fijos (p. ej. `PERIODO 1`, `OBJETIVO`), dime los nombres reales y lo dejo codificado.
    """
)
