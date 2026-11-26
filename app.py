"""Portal público + administração de qualidade da água — UFSC.

Iniciar: streamlit run app.py
Credenciais administrativas definidas nas Secrets do Streamlit
"""
from __future__ import annotations

import hmac
import html
import os
import time
import io
import math
from pathlib import Path
from pyproj import Transformer
from datetime import date

import folium
import pandas as pd
import xlsxwriter
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

import database as db

st.set_page_config(
    page_title="Monitoramento das Águas | UFSC",
    layout="wide",
    initial_sidebar_state="collapsed",
)
try:
    db.inicializar_banco()
except db.ErroPersistencia as exc:
    st.error(str(exc))
    st.stop()

for _chave, _padrao in {
    "pagina": "publico", "autenticado": False, "admin_menu": "Visão geral",
    "falhas_login": 0, "bloqueio_ate": 0.0,
}.items():
    if _chave not in st.session_state:
        st.session_state[_chave] = _padrao

# -----------------------------------------------------------------------------
# Design system — aparência institucional, contraste e componentes compactos.
# -----------------------------------------------------------------------------
NAVY = "#17324D"
TEAL = "#2563EB"
MUTED = "#64748B"
BORDER = "#E2E8EE"
SAND = "#F5F8FA"
MAP_API_KEY = "af1b2140-1a60-4eec-9983-9406fa69f237"

# Fonte não declara o datum. Adotado provisoriamente SIRGAS 2000 / UTM 22S.
UTM_CRS = "EPSG:31982"
WGS84_CRS = "EPSG:4326"
UTM_PARA_GPS = Transformer.from_crs(UTM_CRS, WGS84_CRS, always_xy=True)
GPS_PARA_UTM = Transformer.from_crs(WGS84_CRS, UTM_CRS, always_xy=True)


def numero_pt_br(valor):
    """Aceita 744.245,94, 6944464.32 e 744245,94."""
    texto = str(valor).strip().replace(" ", "").replace("\u00a0", "")
    if not texto or texto.lower() in ("nan", "none"):
        raise ValueError("Informe as coordenadas UTM E e N.")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif texto.count(".") > 1:
        texto = texto.replace(".", "")
    try:
        return float(texto)
    except ValueError as exc:
        raise ValueError(f"Coordenada inválida: {valor}") from exc


def converter_utm(e, n):
    e, n = numero_pt_br(e), numero_pt_br(n)
    if not (100000 <= e <= 900000 and 0 <= n <= 10000000):
        raise ValueError("UTM fora do intervalo esperado: E 100.000–900.000 m; N 0–10.000.000 m.")
    lon, lat = UTM_PARA_GPS.transform(e, n)
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("A conversão UTM produziu coordenadas inválidas.")
    return lat, lon


def formatar_utm(n):
    return f"{float(n):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def ler_csv_utm(uploaded):
    raw = uploaded.getvalue()
    try:
        txt_csv = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        txt_csv = raw.decode("cp1252")
    tabela = pd.read_csv(io.StringIO(txt_csv), sep=";", dtype=str, keep_default_na=False)
    tabela.columns = [col.strip().lower() for col in tabela.columns]
    aliases = {"codigo": "codigo", "código": "codigo", "ponto": "codigo",
               "local": "local", "localização": "local", "localizacao": "local",
               "e (m)": "e", "e": "e", "e_m": "e", "este": "e",
               "n (m)": "n", "n": "n", "n_m": "n", "norte": "n"}
    tabela = tabela.rename(columns={col: aliases.get(col, col) for col in tabela.columns})
    if len(set(tabela.columns)) != len(tabela.columns) or not {'codigo','local','e','n'}.issubset(tabela.columns):
        raise ValueError("CSV precisa ter colunas: codigo;local;E (m);N (m).")
    if len(tabela) > 1000:
        raise ValueError("Importe no máximo 1.000 pontos por arquivo.")
    convertidos = []
    for i, row in tabela.iterrows():
        try:
            codigo, local = str(row['codigo']).strip(), str(row['local']).strip()
            if not codigo or not local:
                raise ValueError("Código e local são obrigatórios.")
            lat, lon = converter_utm(row['e'], row['n'])
            convertidos.append({'codigo':codigo, 'local':local, 'e':numero_pt_br(row['e']),
                                'n':numero_pt_br(row['n']), 'latitude':lat, 'longitude':lon})
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Linha {i + 2}: {exc}") from exc
    return pd.DataFrame(convertidos, columns=['codigo','local','e','n','latitude','longitude'])

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');
html, body, [data-testid="stApp"], [data-testid="stSidebar"] {
  font-family: 'Montserrat', sans-serif;
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"] {background:#F6F8FA;}
[data-testid="stHeader"] {height: 2.8rem;}
[data-testid="stMainBlockContainer"] {max-width:1280px; padding-top:2.2rem; padding-bottom:3rem;}
.public-header-clearance {height:34px;}
@media (max-width:700px) {.public-header-clearance {height:38px;}}
h1,h2,h3,h4 {color:#17324D; letter-spacing:-.035em;}
h1 {font-size:1.75rem !important; font-weight:700 !important;}
h2 {font-size:1.20rem !important; font-weight:650 !important;}
h3 {font-size:1rem !important; font-weight:650 !important;}
p,li {line-height:1.55;}
[data-testid="stSidebar"] {background:#FFFFFF; border-right:1px solid #E2E8EE;}
[data-testid="stSidebarContent"] {padding-top:1.1rem;}
[data-testid="stVerticalBlockBorderWrapper"]:has(>div[data-testid="stVerticalBlock"]) {
    border-color:#E2E8EE !important; border-radius:12px !important;
}
[data-testid="stVerticalBlockBorderWrapper"] {background:#FFFFFF;}
[data-testid="stVerticalBlockBorderWrapper"] > div {gap:.65rem;}
[data-testid="stMetric"] {background:#FFFFFF; border:1px solid #E2E8EE; border-radius:12px;
  padding:16px 18px 16px 21px; min-height:112px; position:relative; overflow:hidden;}
[data-testid="stMetric"]::before {
  content:""; position:absolute; left:0; top:16px; bottom:16px; width:4px;
  border-radius:0 4px 4px 0; background:#B9D9C6;
}
[data-testid="stMetricLabel"] p {color:#64748B !important; font-size:.76rem !important; font-weight:600;}
[data-testid="stMetricValue"] {color:#17324D !important; font-size:1.75rem !important;}
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
 border-radius:9px !important; font-weight:600 !important; min-height:39px;
 border-color:#DCE5EA !important;}
button[kind="primary"] {background:#2563EB !important; border-color:#2563EB !important; color:white !important;}
button[kind="primary"]:hover {background:#1D4ED8 !important;}
button[kind="primaryFormSubmit"] {background:#2563EB !important; color:white !important;}
/* Botão de inclusão de ponto: ação leve, compacta e alinhada à direita. */
[class*="st-key-novo_ponto_admin"] button {
  background:#DBEAFE !important;
  border:1px solid #BFDBFE !important;
  color:#1D4ED8 !important;
  font-size:.79rem !important;
  font-weight:600 !important;
  min-height:34px !important;
  padding:5px 10px !important;
}
[class*="st-key-novo_ponto_admin"] button:hover {
  background:#BFDBFE !important;
  border-color:#93C5FD !important;
  color:#1E40AF !important;
}
[data-baseweb="input"] > div, [data-baseweb="select"] > div,
[data-testid="stDateInput"] input, [data-testid="stTextArea"] textarea {
  border-radius:8px !important; border-color:#DCE5EA !important;}
[data-testid="stWidgetLabel"] p {font-size:.84rem !important; color:#344B5B !important; font-weight:500;}
[data-testid="stCaptionContainer"] p {color:#64748B !important; line-height:1.5;}
[data-testid="stRadio"] [role="radiogroup"] {gap:.25rem;}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  padding:.55rem .70rem; border-radius:9px; transition:background .12s;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
  background:#EFF6FF; color:#1D4ED8; font-weight:700;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {background:#F8FAFF;}
.campaign-kpis {display:flex;align-items:center;justify-content:flex-end;gap:16px;flex-wrap:wrap;padding-bottom:11px;}
.campaign-kpis span {font-size:12px;color:#64748B;white-space:nowrap;}
.campaign-kpis strong {font-size:18px;color:#17324D;margin-right:4px;}
[data-baseweb="tag"] {background:#2563EB !important;color:white !important;border:1px solid #1D4ED8 !important;}
[data-baseweb="tag"] span, [data-baseweb="tag"] svg {color:white !important;fill:white !important;}
[data-baseweb="select"]:focus-within > div {border-color:#2563EB !important;}
[class*="st-key-entrar_admin"] button {
  width:46px !important; min-width:46px !important; height:46px !important;
  border-radius:12px !important; background:#EFF8F1 !important;
  color:#16805B !important; border:1px solid #CDE8D4 !important;
  display:flex !important; align-items:center !important; justify-content:center !important;
}
[class*="st-key-entrar_admin"] button:hover {background:#E3F2E7 !important; border-color:#A8D5B5 !important;}
[class*="st-key-entrar_admin"] {display:flex;justify-content:flex-end;}
/* Ícone próprio desenhado por máscara SVG: centralização independente do ícone Material */
[class*="st-key-entrar_admin"] button {
  position:relative !important;
  display:grid !important;
  place-items:center !important;
  padding:0 !important;
  line-height:0 !important;
  font-size:0 !important;
  overflow:hidden !important;
}
[class*="st-key-entrar_admin"] button > * {display:none !important;}
[class*="st-key-entrar_admin"] button::before {
  content:"" !important;
  display:block !important;
  width:19px !important;
  height:19px !important;
  margin:0 !important;
  padding:0 !important;
  background-color:#16805B !important;
  -webkit-mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='8' r='3.2'/%3E%3Cpath d='M5.5 20c.6-3.3 3-5 6.5-5s5.9 1.7 6.5 5'/%3E%3C/svg%3E") !important;
  mask-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='8' r='3.2'/%3E%3Cpath d='M5.5 20c.6-3.3 3-5 6.5-5s5.9 1.7 6.5 5'/%3E%3C/svg%3E") !important;
  -webkit-mask-repeat:no-repeat !important;
  mask-repeat:no-repeat !important;
  -webkit-mask-position:center !important;
  mask-position:center !important;
  -webkit-mask-size:contain !important;
  mask-size:contain !important;
  transform:none !important;
}
[data-testid="stDataFrame"] {border-radius:10px; overflow:hidden;}
[data-testid="stPlotlyChart"] {border-radius:10px;}
section[data-testid="stSidebar"] [data-testid="stElementContainer"] {margin-bottom:.05rem;}
.brand {
  display:flex; align-items:center; gap:17px; min-height:108px;
  position:relative; isolation:isolate; overflow:hidden;
  padding:10px 14px 10px 0; border-radius:10px;
  background-color:rgba(246,248,250,.72);
  background-image:
    linear-gradient(90deg, rgba(246,248,250,.96) 0%, rgba(246,248,250,.88) 46%, rgba(246,248,250,.56) 100%),
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 720 150'%3E%3Cg fill='none' stroke='%2398C5A9' stroke-width='1.2' opacity='.52'%3E%3Cpath d='M-20 100 C80 12 160 145 270 78 S470 12 740 64'/%3E%3Cpath d='M-20 116 C85 28 165 158 280 94 S485 28 740 80'/%3E%3Cpath d='M-20 78 C75 -5 155 125 260 60 S465 -4 740 46'/%3E%3Cpath d='M-20 132 C90 48 170 175 290 110 S500 48 740 96'/%3E%3C/g%3E%3C/svg%3E");
  background-repeat:no-repeat; background-size:cover, 720px 150px;
  background-position:center, right center;
}
.brand-logo {width:88px;height:88px;object-fit:contain;flex-shrink:0;border-radius:5px;}
.brand-divider {width:2px;height:76px;background:#79B391;flex-shrink:0;border-radius:2px;}
.brand-copy {display:flex;flex-direction:column;justify-content:center;min-width:0;}
.brand-kicker {font-size:11px;line-height:1.2;letter-spacing:.075em;text-transform:uppercase;
 color:#39845F;font-weight:700;margin-bottom:7px;}
.brand-icon {width:42px;height:42px;display:grid;place-items:center;background:#EFF6FF;
 border-radius:11px;color:#2563EB;flex-shrink:0;}
.brand-title {font-size:20px;font-weight:700;color:#17324D;line-height:1.25;}
.brand-sub {font-size:11px;color:#64748B;margin-top:5px;}
.public-header-rule {height:1px;background:linear-gradient(90deg,#83B99A 0%,#C7DCCF 58%,#DCE8E0 100%);
 margin:9px 0 23px;border:0;}
.eyebrow {font-size:.73rem;letter-spacing:.07em;text-transform:uppercase;
 color:#2563EB;font-weight:700;margin-bottom:6px;}
.lead {font-size:.88rem;color:#64748B;max-width:820px;margin:0 0 8px;}
.section-title {font-size:1.03rem;font-weight:700;color:#17324D;margin:1px 0 2px;}
.section-sub {font-size:.80rem;color:#64748B;margin:0 0 10px;}
.rule {height:1px;background:#E2E8EE;margin:12px 0;}
.status {display:inline-block;padding:5px 10px;border-radius:20px;font-size:.76rem;
 font-weight:700;border:1px solid currentColor;}
.small-note {font-size:.77rem;color:#64748B;line-height:1.6;}
.point-code {display:inline-block;background:#EFF6FF;color:#1D4ED8;font-weight:700;
 padding:4px 8px;border-radius:6px;font-size:.75rem;}
.section-box {border:1px solid #E2E8EE;background:#FFF;border-radius:12px;padding:18px;}
[data-testid="stAlert"] {border-radius:9px;}
[class*="st-key-sticky_coleta_"] {position:sticky;bottom:8px;z-index:20;
 background:#fff;border-radius:12px;box-shadow:0 8px 30px rgba(23,50,77,.10);}
@media (max-width:700px) {
 [data-testid="stMainBlockContainer"] {padding-left:1rem;padding-right:1rem;}
 h1 {font-size:1.35rem !important;}
 [data-testid="stMetric"] {min-height:92px;padding:12px 12px 12px 16px;}
 [data-testid="stMetricValue"] {font-size:1.33rem !important;}
 .brand {min-height:82px;gap:10px;padding-right:4px;}
 .brand-title {font-size:16px;}
 .brand-kicker {font-size:9px;margin-bottom:5px;}
 .brand-sub {font-size:10px;}
 .brand-divider {height:58px;}
 .brand-logo {width:64px;height:64px;}
}

/* Identidade visual global: azul; cores de classificação IQA ficam só nos gráficos. */
:root { --primary-color: #2563EB; }
[data-testid="stMultiSelect"] [data-baseweb="tag"],
[data-testid="stMultiSelect"] span[data-baseweb="tag"],
.stMultiSelect [data-baseweb="tag"],
[data-baseweb="select"] [data-baseweb="tag"] {
  background-color:#2563EB !important;
  border:1px solid #1D4ED8 !important;
  color:#FFFFFF !important;
  border-radius:7px !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] *,
.stMultiSelect [data-baseweb="tag"] *,
[data-baseweb="select"] [data-baseweb="tag"] * {
  color:#FFFFFF !important;
  fill:#FFFFFF !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] svg,
.stMultiSelect [data-baseweb="tag"] svg {stroke:#FFFFFF !important;}
[data-testid="stMultiSelect"] [data-baseweb="select"]:focus-within > div,
[data-testid="stSelectbox"] [data-baseweb="select"]:focus-within > div {
 border-color:#2563EB !important; box-shadow:0 0 0 1px #2563EB !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {color:#2563EB !important;}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {background:#2563EB !important;}
</style>
""", unsafe_allow_html=True)


def txt(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def titulo_secao(titulo, subtitulo=""):
    st.markdown(f'<div class="section-title">{txt(titulo)}</div>', unsafe_allow_html=True)
    if subtitulo:
        st.markdown(f'<div class="section-sub">{txt(subtitulo)}</div>', unsafe_allow_html=True)


# Logotipo incluído no próprio app.py: não depende da pasta assets.
LOGO_GESTAO_AMBIENTAL = "data:image/jpeg;base64,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"


def marca():
    """Cabeçalho institucional; mantém a logo original incorporada ao app."""
    return (
        '<div class="brand">'
        f'<img class="brand-logo" src="{LOGO_GESTAO_AMBIENTAL}" alt="Gestão Ambiental UFSC">'
        '<span class="brand-divider" aria-hidden="true"></span>'
        '<div class="brand-copy">'
        '<div class="brand-kicker">Monitoramento ambiental</div>'
        '<div class="brand-title">Gestão das Águas</div>'
        '<div class="brand-sub">UFSC · Gestão Ambiental</div>'
        '</div></div>'
    )


def cor_status(nome):
    paleta = {"Péssima": "#C0392B", "Ruim": "#C25B21", "Regular": "#946200",
              "Boa": "#187A5E", "Ótima": "#10664D"}
    return paleta.get(nome, MUTED)


def classificar_iqa(valor, faixas):
    try:
        n = float(valor)
    except (ValueError, TypeError):
        return None
    ordenadas = faixas.sort_values("valor_min").to_dict("records")
    for i, item in enumerate(ordenadas):
        minimo = float(item["valor_min"])
        maximo = float(item["valor_max"])
        proximo_min = (
            float(ordenadas[i + 1]["valor_min"])
            if i < len(ordenadas) - 1 else None
        )
        # Fronteiras coincidentes: o limite pertence à faixa seguinte.
        # Fronteiras consecutivas (25/26): 25 pertence à primeira faixa.
        inclusivo = proximo_min is None or proximo_min > maximo
        if minimo <= n < maximo or (inclusivo and n == maximo):
            return item
    return None


def formatar_valor(valor):
    if pd.isna(valor):
        return "—"
    return f"{float(valor):,.5f}".rstrip("0").rstrip(".").replace(",", " ")


def formatar_data(dia):
    try:
        data = pd.to_datetime(dia, errors="coerce")
        if pd.isna(data):
            return "—"
        return data.strftime("%d/%m/%Y")
    except (ValueError, TypeError, AttributeError):
        return "—"


def somente_iqa(nome):
    return str(nome).startswith("IQA (")


def rotulo_ponto(ponto):
    codigo = str(ponto["codigo"]).strip()
    local = str(ponto["local"]).strip()
    return local if codigo == local else f"{codigo} · {local}"


def verificar_conformidade(valor, parametro):
    """Conformidade SOMENTE com referência revisada e aplicabilidade informada."""
    tipo = parametro.get("tipo_limite", "nenhum")
    if tipo == "nenhum":
        return "Sem referência"
    if not bool(parametro.get("referencia_validada", 0)):
        return "Não avaliado"
    minimo, maximo = parametro.get("limite_min"), parametro.get("limite_max")
    if tipo == "nenhum":
        return "Sem referência"
    if tipo in ("minimo", "intervalo") and pd.isna(minimo):
        return "Não avaliado"
    if tipo in ("maximo", "intervalo") and pd.isna(maximo):
        return "Não avaliado"
    if (tipo in ("minimo", "intervalo") and float(valor) < float(minimo)) or (
            tipo in ("maximo", "intervalo") and float(valor) > float(maximo)):
        return "Fora da referência"
    return "Na referência"


def resumo_referencia(p):
    tipo = p.get("tipo_limite", "nenhum")
    if tipo == "nenhum":
        return "Sem referência"
    if not bool(p.get("referencia_validada", 0)):
        return "Não validada"
    unidade = p.get("unidade", "")
    sufixo = "" if unidade == "-" else f" {unidade}"
    if tipo == "minimo":
        return f"≥ {formatar_valor(p['limite_min'])}{sufixo}"
    if tipo == "maximo":
        return f"≤ {formatar_valor(p['limite_max'])}{sufixo}"
    if tipo == "intervalo":
        return f"{formatar_valor(p['limite_min'])} a {formatar_valor(p['limite_max'])}{sufixo}"
    return "Não se aplica"


def cartografia(pontos, foco_id=None, selecionar=True, chave="mapa_publico", altura=350,
                estilos_por_ponto=None, popup_por_ponto=None):
    validos = pontos.dropna(subset=["latitude", "longitude"]).copy()
    if validos.empty:
        st.info("Os pontos ainda não possuem coordenadas válidas.")
        return None
    estilos_por_ponto = estilos_por_ponto or {}
    popup_por_ponto = popup_por_ponto or {}
    centro = [float(validos["latitude"].mean()), float(validos["longitude"].mean())]
    m = folium.Map(location=centro, zoom_start=14 if len(validos) < 3 else 12,
                   tiles=None, control_scale=True)
    folium.TileLayer(
        tiles=f"https://tiles.stadiamaps.com/tiles/alidade_smooth/{{z}}/{{x}}/{{y}}{{r}}.png?api_key={MAP_API_KEY}",
        attr='&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>, &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a>, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        name="Base"
    ).add_to(m)
    correspondencia = {}
    for _, item in validos.iterrows():
        item_id = int(item["id"])
        legenda = rotulo_ponto(item)
        correspondencia[legenda] = item_id
        estilo = estilos_por_ponto.get(item_id, {})
        cor = estilo.get("cor", "#2563EB")
        raio = 10 if item_id == foco_id else estilo.get("raio", 8)
        borda = "#FFFFFF" if item_id != foco_id else NAVY
        popup_default = f"<strong>{txt(item['codigo'])}</strong><br>{txt(item['local'])}"
        popup_html = popup_por_ponto.get(item_id, popup_default)
        tooltip = estilo.get("tooltip", legenda)
        folium.CircleMarker(
            location=[float(item["latitude"]), float(item["longitude"])],
            radius=raio,
            color=borda, weight=2.2, fill=True,
            fill_color=cor, fill_opacity=1,
            tooltip=folium.Tooltip(tooltip),
            popup=folium.Popup(popup_html, max_width=320),
        ).add_to(m)
    if len(validos) > 1:
        m.fit_bounds(validos[["latitude", "longitude"]].astype(float).values.tolist(), padding=(30, 30))
    retorno = st_folium(m, height=altura, use_container_width=True,
                        key=chave, returned_objects=["last_object_clicked_tooltip", "last_object_clicked_count"] if selecionar else [])
    if selecionar and retorno:
        contador = retorno.get("last_object_clicked_count")
        if contador is not None and contador != st.session_state.get(f"{chave}_ultimo_contador"):
            st.session_state[f"{chave}_ultimo_contador"] = contador
            return correspondencia.get(retorno.get("last_object_clicked_tooltip"))
    return None


def _preparar_serie_grafico(dados):
    """Ordena observações reais; eixo de categorias mostra somente datas medidas."""
    serie = dados.dropna(subset=["valor", "data_amostra"]).copy()
    if serie.empty:
        return serie, []
    serie["dia"] = pd.to_datetime(serie["data_amostra"], errors="coerce")
    serie = serie.dropna(subset=["dia"]).sort_values(["dia", "id"]).copy()
    serie["data_rotulo"] = serie["dia"].dt.strftime("%d/%m/%Y")
    datas = list(dict.fromkeys(serie["data_rotulo"].tolist()))
    return serie, datas


def _layout_eixo_coletas(fig, datas, altura=320, eixo_y=""):
    """Datas categóricas: nenhum dia artificial entre as coletas.

    Deixa respiro horizontal e vertical para que bolinhas e rótulos não sejam cortados.
    """
    qt = len(datas)
    largura_x = [-0.35, max(qt - 1 + 0.35, 0.35)] if qt else [-0.5, 0.5]
    fig.update_layout(
        height=altura, paper_bgcolor="white", plot_bgcolor="white",
        margin=dict(l=14, r=28, t=35, b=34),
        xaxis=dict(type="category", categoryorder="array", categoryarray=datas,
                   tickmode="array", tickvals=datas, ticktext=datas,
                   showgrid=False, title="", automargin=True,
                   range=largura_x, ticks="", fixedrange=False,
                   tickangle=-30 if qt > 7 else 0),
        yaxis=dict(gridcolor="#EFF3F8", zeroline=False, title=eixo_y,
                   automargin=True, ticks=""),
        hovermode="closest", showlegend=False,
        hoverlabel=dict(bgcolor="white"),
        font=dict(family="Montserrat", color="#334155", size=11),
    )




def _referencias_parametro(parametro):
    """Retorna exclusivamente limites revisados e validados, sem modificar dados."""
    if not bool(parametro.get("referencia_validada", 0)):
        return []
    tipo = str(parametro.get("tipo_limite", "nenhum"))
    unidade = str(parametro.get("unidade") or "").strip()
    sufixo = "" if unidade == "-" else f" {unidade}"
    retorno = []
    for tipo_esperado, chave, nome in (
        (("minimo", "intervalo"), "limite_min", "Referência mínima"),
        (("maximo", "intervalo"), "limite_max", "Referência máxima"),
    ):
        valor = parametro.get(chave)
        if tipo in tipo_esperado and valor is not None and pd.notna(valor):
            numero = float(valor)
            if math.isfinite(numero):
                retorno.append((numero, f"{nome}: {formatar_valor(numero)}{sufixo}"))
    return retorno


def _referencias_grafico(fig, parametro, orientacao="horizontal"):
    """Linha vermelha discreta com o valor exato; apenas apresentação Plotly."""
    refs = _referencias_parametro(parametro)
    for numero, rotulo in refs:
        estilo = dict(line_color="#DC2626", line_width=1.5, line_dash="solid",
                      annotation_text=rotulo,
                      annotation_font_color="#B91C1C", annotation_font_size=12)
        if orientacao == "vertical":
            fig.add_vline(x=numero, annotation_position="top right", **estilo)
        else:
            fig.add_hline(y=numero, annotation_position="top right", **estilo)
    return [r[0] for r in refs]

def grafico_temporal(dados, parametro, config_param):
    if dados.empty:
        st.info("Não há medições registradas para este parâmetro no ponto selecionado.")
        return
    dados, datas = _preparar_serie_grafico(dados)
    if dados.empty:
        st.info("Não há resultados para essa seleção.")
        return
    valores = dados["valor"].astype(float)
    unidade = "" if config_param["unidade"] == "-" else str(config_param["unidade"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dados["data_rotulo"], y=valores,
        mode="lines+markers+text",
        name="Medições", connectgaps=False,
        line=dict(color="#2563EB", width=1.7),
        marker=dict(size=9, color="#2563EB", line=dict(color="white", width=1.5)),
        text=[formatar_valor(v) for v in valores],
        textposition="top center", textfont=dict(size=12, color="#1D4ED8"),
        cliponaxis=False,
        customdata=dados["data_rotulo"],
        hovertemplate="%{customdata}<br><b>%{y:.5f}</b> " + unidade + "<extra></extra>",
    ))
    referencias = _referencias_grafico(fig, config_param)
    _layout_eixo_coletas(fig, datas, altura=315, eixo_y=unidade)
    extremos = [float(valores.min()), float(valores.max()), *referencias]
    baixo, alto = min(extremos), max(extremos)
    margem = max((alto - baixo) * .16, max(abs(baixo), abs(alto)) * .09, .4)
    fig.update_yaxes(range=[min(0, baixo-margem) if baixo >= 0 else baixo-margem, alto+margem*1.6])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})



# Cores com maior saturação para as faixas do IQA.
# Os intervalos/limites vêm do banco; apenas a aparência é definida aqui.
IQA_CORES = {
    "Péssima": "#DC2626", "Ruim": "#EA580C", "Regular": "#D97706",
    "Boa": "#16A34A", "Ótima": "#047857",
}
IQA_FUNDOS = {
    "Péssima": "rgba(220,38,38,0.16)", "Ruim": "rgba(234,88,12,0.13)",
    "Regular": "rgba(245,158,11,0.15)", "Boa": "rgba(34,197,94,0.13)",
    "Ótima": "rgba(5,150,105,0.16)",
}


def cor_iqa(faixa):
    return IQA_CORES.get(str(faixa["nome"]), str(faixa["cor_texto"]))


def fundo_iqa(faixa):
    return IQA_FUNDOS.get(str(faixa["nome"]), str(faixa["cor_grafico"]))


def grafico_iqa(dados, faixas):
    if dados.empty:
        st.info("Ainda não há medições de IQA informadas para este ponto.")
        return
    dados, datas = _preparar_serie_grafico(dados)
    if dados.empty:
        st.info("Ainda não existem medições válidas de IQA neste ponto.")
        return
    cores, categorias = [], []
    for valor in dados["valor"]:
        faixa = classificar_iqa(valor, faixas)
        cores.append(cor_iqa(faixa) if faixa is not None else "#64748B")
        categorias.append(str(faixa["nome"]) if faixa is not None else "Indefinida")
    fig = go.Figure()
    for _, fx in faixas.iterrows():
        fig.add_hrect(y0=float(fx["valor_min"]), y1=float(fx["valor_max"]),
                      fillcolor=fundo_iqa(fx), opacity=1,
                      layer="below", line_width=0)
    fig.add_trace(go.Scatter(
        x=dados["data_rotulo"], y=dados["valor"], mode="lines+markers+text",
        name="IQA", connectgaps=False,
        line=dict(color="#475569", width=1.7),
        marker=dict(size=10, color=cores, line=dict(color="white", width=1.6)),
        text=[formatar_valor(v) for v in dados["valor"]],
        textposition="top center", textfont=dict(color="#334155", size=11),
        cliponaxis=False,
        customdata=list(zip(dados["data_rotulo"], categorias)),
        hovertemplate="%{customdata[0]}<br>IQA: <b>%{y:.2f}</b><br>%{customdata[1]}<extra></extra>",
    ))
    _layout_eixo_coletas(fig, datas, eixo_y="IQA (0–100)")
    fig.update_yaxes(range=[0, 104])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    itens = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;white-space:nowrap">'
        f'<span style="width:9px;height:9px;background:{txt(IQA_CORES.get(fx.nome, fx.cor_texto))};'
        f'border-radius:50%;display:inline-block"></span>'
        f'{txt(fx.nome)} ({txt(formatar_valor(fx.valor_min))}–{txt(formatar_valor(fx.valor_max))})</span>'
        for fx in faixas.sort_values("valor_min").itertuples()
    )
    st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:12px;'
                f'font-size:12px;color:#64748B;margin:2px 0 8px">{itens}</div>',
                unsafe_allow_html=True)



def preparar_resultados_publicos(resultados):
    dados = resultados.copy()
    if dados.empty:
        dados["dia_ts"] = pd.to_datetime(pd.Series(dtype="datetime64[ns]"))
        dados["dia"] = pd.Series(dtype="object")
        dados["data_rotulo"] = pd.Series(dtype="object")
        return dados
    dados["dia_ts"] = pd.to_datetime(dados["data_amostra"], errors="coerce")
    dados = dados.dropna(subset=["dia_ts"]).copy()
    dados["dia"] = dados["dia_ts"].dt.date
    dados["data_rotulo"] = dados["dia_ts"].dt.strftime("%d/%m/%Y")
    return dados


def obter_iqa_por_ponto(campanha_df, faixas):
    if campanha_df.empty:
        return pd.DataFrame(columns=["ponto_id", "codigo", "local", "valor", "classificacao", "cor"])
    iqa = campanha_df[campanha_df["parametro"].astype(str).str.startswith("IQA (", na=False)].copy()
    if iqa.empty:
        return pd.DataFrame(columns=["ponto_id", "codigo", "local", "valor", "classificacao", "cor"])
    resumo = (iqa.groupby(["ponto_id", "codigo", "local"], as_index=False)
                .agg(valor=("valor", "mean")))
    classes, cores = [], []
    for valor in resumo["valor"]:
        fx = classificar_iqa(valor, faixas)
        classes.append(str(fx["nome"]) if fx is not None else "Sem classificação")
        cores.append(cor_iqa(fx) if fx is not None else "#94A3B8")
    resumo["classificacao"] = classes
    resumo["cor"] = cores
    return resumo


def estilos_mapa_por_campanha(pontos, campanha_df, faixas):
    resumo_iqa = obter_iqa_por_ponto(campanha_df, faixas)
    estilos, popups = {}, {}
    lookup = {int(r["ponto_id"]): r for _, r in resumo_iqa.iterrows()}
    for _, ponto in pontos.iterrows():
        pid = int(ponto["id"])
        linha = lookup.get(pid)
        if linha is None:
            cor = "#94A3B8"
            tooltip = f"{rotulo_ponto(ponto)} · sem IQA"
            popup = f"<strong>{txt(ponto['codigo'])}</strong><br>{txt(ponto['local'])}<br><span style='color:#64748B'>Sem IQA nesta campanha</span>"
        else:
            cor = linha["cor"]
            tooltip = f"{rotulo_ponto(ponto)} · IQA {formatar_valor(linha['valor'])} · {linha['classificacao']}"
            popup = (
                f"<strong>{txt(ponto['codigo'])}</strong><br>{txt(ponto['local'])}<br>"
                f"IQA: <strong>{formatar_valor(linha['valor'])}</strong><br>"
                f"Classificação: <strong style='color:{txt(cor)}'>{txt(linha['classificacao'])}</strong>"
            )
        estilos[pid] = {"cor": cor, "tooltip": tooltip}
        popups[pid] = popup
    return estilos, popups, resumo_iqa


def grafico_distribuicao_iqa(campanha_df, faixas):
    """Resumo discreto por categoria, legível até com somente um IQA."""
    resumo = obter_iqa_por_ponto(campanha_df, faixas)
    total = len(resumo)
    if not total:
        st.caption("Nenhum IQA informado nesta campanha.")
        return
    resumo = resumo.copy()
    col_a, col_b = st.columns([1, 2])
    col_a.metric("Com IQA", total)
    if total == 1:
        registro = resumo.iloc[0]
        with col_b:
            st.markdown(
                f'<div style="font-size:13px;color:#64748B;margin-top:7px">Classificação</div>'
                f'<div style="font-size:19px;font-weight:700;color:{txt(registro["cor"])}">'
                f'{txt(registro["classificacao"])} · {formatar_valor(registro["valor"])}'
                f'</div>', unsafe_allow_html=True)
    else:
        col_b.metric("Categorias presentes", resumo["classificacao"].nunique())
    for _, fx in faixas.sort_values("valor_min", ascending=False).iterrows():
        qtd = int((resumo["classificacao"] == fx["nome"]).sum())
        if qtd == 0:
            continue
        proporcao = 100 * qtd / total
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:9px;margin:8px 0;">'
            f'<span style="width:10px;height:10px;flex-shrink:0;border-radius:50%;background:{txt(cor_iqa(fx))}"></span>'
            f'<span style="font-size:12px;color:#334155;min-width:66px">{txt(fx["nome"])}</span>'
            f'<span style="flex:1;height:7px;background:#EFF3F8;border-radius:8px;overflow:hidden">'
            f'<span style="display:block;background:{txt(cor_iqa(fx))};height:100%;width:{proporcao:.2f}%;border-radius:8px"></span></span>'
            f'<strong style="font-size:12px;color:#17324D">{qtd}</strong></div>',
            unsafe_allow_html=True)


def grafico_comparacao_parametro(campanha_df, parametro_id, parametros, pontos):
    """Comparação por marcadores azuis, sem barras enormes e com valor exato."""
    dados = campanha_df[campanha_df["param_id"] == int(parametro_id)].copy()
    if dados.empty:
        st.info("Nenhum ponto possui esse parâmetro na campanha selecionada.")
        return
    dados = (dados.groupby(["ponto_id", "codigo", "local"], as_index=False)
                  .agg(valor=("valor", "mean"), registros=("id", "count")))
    ordem = {int(pid): i for i, pid in enumerate(pontos["id"].astype(int).tolist())}
    dados["ordem"] = dados["ponto_id"].map(ordem)
    dados = dados.sort_values("ordem")
    param = parametros[parametros["id"] == int(parametro_id)].iloc[0]
    unidade = "" if str(param["unidade"]) == "-" else str(param["unidade"])
    rotulos = [f"P{row.codigo}" if str(row.codigo).isdigit() else str(row.codigo)
               for row in dados.itertuples()]
    fig = go.Figure(go.Scatter(
        x=dados["valor"], y=rotulos, mode="markers+text",
        marker=dict(size=11, color="#2563EB", line=dict(color="white", width=1.7)),
        text=[formatar_valor(v) for v in dados["valor"]],
        textposition="middle right", textfont=dict(color="#1D4ED8", size=12),
        cliponaxis=False,
        customdata=dados[["local", "registros"]].values,
        hovertemplate="<b>%{y}</b><br>%{customdata[0]}<br>Valor: <b>%{x:.5f}</b> " + unidade +
                      "<br>Medições: %{customdata[1]}<extra></extra>",
        showlegend=False,
    ))
    valores = dados["valor"].astype(float)
    referencias = _referencias_parametro(param)
    escala = [float(valores.min()), float(valores.max()), *[v for v, _ in referencias]]
    minimo, maximo = min(escala), max(escala)
    span = max(maximo - minimo, abs(minimo) * .15, abs(maximo) * .15, 1.0)
    fig.update_layout(
        height=max(220, min(1050, 125 + len(dados) * 32)),
        paper_bgcolor="white", plot_bgcolor="white",
        margin=dict(l=18, r=85, t=23, b=32),
        xaxis=dict(title=unidade, gridcolor="#EFF3F8", zeroline=False,
                   range=[minimo - .18*span, maximo + .40*span], ticks=""),
        yaxis=dict(title="", type="category", categoryorder="array",
                   categoryarray=list(reversed(rotulos)), showgrid=False, ticks=""),
        hoverlabel=dict(bgcolor="white"),
        font=dict(family="Montserrat", color="#334155", size=11),
        showlegend=False,
    )
    _referencias_grafico(fig, param, orientacao="vertical")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})



def _anotacoes_series_sem_colisao(fig, dados, codigos, *, eixo_iqa=False, limite_rotulos=22):
    """Rotula pontos coincidentes/adjacentes sem modificar as medições reais.

    Todas as curvas mantêm suas coordenadas originais: somente os rótulos são
    deslocados em pixels, com uma linha-guia até o marcador correspondente.
    """
    if dados.empty:
        return False
    usados = dados[["ponto_id", "data_rotulo", "valor"]].copy()
    usados["valor"] = usados["valor"].astype(float)
    minimo, maximo = float(usados["valor"].min()), float(usados["valor"].max())
    amplitude = max(100.0 if eixo_iqa else maximo - minimo, 1.0)
    proximidade = amplitude * (0.042 if eixo_iqa else 0.045)
    # Com muitas amostras evita poluir o gráfico: rotula apenas as colisões.
    rotular_todos = len(usados) <= limite_rotulos
    colisoes = False
    for data_rotulo, grupo in usados.groupby("data_rotulo", sort=False):
        ordenadas = grupo.sort_values(["valor", "ponto_id"]).to_dict("records")
        conjuntos = []
        atual = []
        for registro in ordenadas:
            if atual and registro["valor"] - atual[-1]["valor"] > proximidade:
                conjuntos.append(atual)
                atual = []
            atual.append(registro)
        if atual:
            conjuntos.append(atual)
        for conjunto in conjuntos:
            colisao = len(conjunto) > 1
            colisoes = colisoes or colisao
            if not rotular_todos and not colisao:
                continue
            for indice, item in enumerate(conjunto):
                codigo = codigos.get(int(item["ponto_id"]), str(item["ponto_id"]))
                # Para valores sobrepostos, identificar a série no próprio rótulo.
                legenda = (f"{codigo}: {formatar_valor(item['valor'])}" if colisao
                           else formatar_valor(item["valor"]))
                # Cada valor recebe seu próprio rótulo, afastado em posições
                # alternadas; o marcador e a linha continuam em dados exatos.
                if colisao:
                    lado = 1 if indice % 2 == 0 else -1
                    nivel = indice // 2
                    xshift = lado * (50 + 12 * (nivel % 2))
                    yshift = 26 + nivel * 25
                else:
                    xshift, yshift = 0, 17
                fig.add_annotation(
                    x=data_rotulo, y=float(item["valor"]), text=legenda,
                    xref="x", yref="y", xshift=0 if colisao else xshift,
                    yshift=0 if colisao else yshift,
                    showarrow=colisao, arrowhead=0, arrowsize=0.7,
                    arrowwidth=1, arrowcolor="#94A3B8",
                    ax=xshift if colisao else 0, ay=-yshift if colisao else 0,
                    font=dict(size=10, color="#334155"),
                    bgcolor="rgba(255,255,255,0.90)" if colisao else "rgba(255,255,255,0)",
                    borderpad=2,
                )
    return colisoes


def grafico_comparacao_iqa_multiplos(resultados, ponto_ids, pontos, faixas, foco_id=None):
    dados = resultados[resultados["parametro"].astype(str).str.startswith("IQA (", na=False)].copy()
    dados = dados[dados["ponto_id"].isin([int(x) for x in ponto_ids])]
    if dados.empty:
        st.info("Os pontos selecionados ainda não possuem IQA para comparação.")
        return
    dados = preparar_resultados_publicos(dados)
    resumo = (dados.groupby(["ponto_id", "codigo", "local", "dia", "data_rotulo"], as_index=False)
                  .agg(valor=("valor", "mean")))
    resumo = resumo.sort_values(["dia", "ponto_id"])
    datas = resumo.sort_values("dia")["data_rotulo"].drop_duplicates().tolist()
    mapa_rotulos = {int(r["id"]): rotulo_ponto(r) for _, r in pontos.iterrows()}
    codigos = {int(r["id"]): str(r["codigo"]) for _, r in pontos.iterrows()}
    paleta = ["#17324D", "#1D4ED8", "#2563EB", "#3B82F6", "#60A5FA", "#64748B"]
    formas = ["circle", "diamond", "square", "triangle-up", "x", "star"]
    estilos = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]
    fig = go.Figure()
    selecionados = [int(x) for x in ponto_ids]
    for i, pid in enumerate(selecionados):
        serie = resumo[resumo["ponto_id"] == pid]
        if serie.empty:
            continue
        cor = paleta[i % len(paleta)]
        fig.add_trace(go.Scatter(
            x=serie["data_rotulo"], y=serie["valor"], mode="lines+markers",
            name=mapa_rotulos.get(pid, str(pid)),
            line=dict(color=cor, dash=estilos[i % len(estilos)],
                      width=2.5 if foco_id is not None and pid == int(foco_id) else 1.8),
            marker=dict(size=10, symbol=formas[i % len(formas)], color=cor,
                        line=dict(color="white", width=1.2)),
            customdata=serie["data_rotulo"],
            hovertemplate="%{fullData.name}<br>%{customdata}<br>IQA: <b>%{y:.2f}</b><extra></extra>",
        ))
    for _, fx in faixas.iterrows():
        fig.add_hrect(y0=float(fx["valor_min"]), y1=float(fx["valor_max"]),
                      fillcolor=fundo_iqa(fx), opacity=1, layer="below", line_width=0)
    _layout_eixo_coletas(fig, datas, altura=400, eixo_y="IQA (0–100)")
    fig.update_yaxes(range=[0, 104])
    fig.update_layout(legend=dict(orientation="h", y=1.16, x=0),
                      showlegend=len(selecionados) > 1,
                      margin=dict(l=18, r=70, t=62, b=42),
                      hovermode="closest")
    coincidentes = _anotacoes_series_sem_colisao(fig, resumo, codigos, eixo_iqa=True)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    if coincidentes:
        st.caption("Valores iguais ou próximos: rótulos identificados pelo código do ponto, "
                   "deslocados visualmente. As curvas mantêm os valores reais.")


def grafico_temporal_parametros_multiplos(resultados, parametro_id, ponto_ids, pontos, parametros):
    """Comparativo temporal; marcadores distintos e rótulos sem sobreposição."""
    base = resultados[(resultados["param_id"] == int(parametro_id)) &
                      (resultados["ponto_id"].isin(ponto_ids))].copy()
    if base.empty:
        st.info("Não há medições para os pontos escolhidos.")
        return
    base = (base.groupby(["ponto_id", "dia", "data_rotulo"], as_index=False)
                  .agg(valor=("valor", "mean"))).sort_values("dia")
    datas = base["data_rotulo"].drop_duplicates().tolist()
    rotulos = {int(r["id"]): rotulo_ponto(r) for _, r in pontos.iterrows()}
    codigos = {int(r["id"]): str(r["codigo"]) for _, r in pontos.iterrows()}
    cor_linhas = ["#1D4ED8", "#0284C7", "#4338CA", "#0891B2", "#2563EB", "#64748B"]
    formas = ["circle", "diamond", "square", "triangle-up", "x", "star"]
    estilos = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]
    fig = go.Figure()
    for ordem, pid in enumerate(ponto_ids):
        serie = base[base["ponto_id"] == int(pid)]
        if serie.empty:
            continue
        cor = cor_linhas[ordem % len(cor_linhas)]
        fig.add_trace(go.Scatter(
            x=serie["data_rotulo"], y=serie["valor"], mode="lines+markers",
            name=rotulos.get(int(pid), str(pid)),
            line=dict(color=cor, width=2, dash=estilos[ordem % len(estilos)]),
            marker=dict(color=cor, size=10, symbol=formas[ordem % len(formas)],
                        line=dict(color="white", width=1.3)),
            cliponaxis=False,
            customdata=serie["data_rotulo"],
            hovertemplate="%{fullData.name}<br>%{customdata}<br><b>%{y:.5f}</b><extra></extra>",
        ))
    parametro_referencia = parametros.loc[parametros["id"] == int(parametro_id)].iloc[0]
    unidade = str(parametro_referencia["unidade"])
    if unidade == "-":
        unidade = ""
    _layout_eixo_coletas(fig, datas, altura=400, eixo_y=unidade)
    referencias = _referencias_grafico(fig, parametro_referencia)
    valores = base["valor"].astype(float)
    extremos = [float(valores.min()), float(valores.max()), *referencias]
    vmin, vmax = min(extremos), max(extremos)
    folga = max((vmax-vmin)*0.18, abs(vmax)*0.10, 0.3)
    fig.update_yaxes(range=[min(0, vmin-folga) if vmin >= 0 else vmin-folga,
                            vmax+folga*2.6])
    fig.update_layout(showlegend=True,
                      legend=dict(orientation="h", y=1.17, x=0),
                      margin=dict(l=18, r=70, t=62, b=42),
                      hovermode="closest")
    coincidentes = _anotacoes_series_sem_colisao(fig, base, codigos)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    if coincidentes:
        st.caption("Valores iguais ou próximos: rótulos identificados pelo código do ponto, "
                   "deslocados visualmente. As curvas mantêm os valores reais.")


def buscar_titulo_referencia_seguro():
    """Compatível com versões anteriores do database.py; somente leitura."""
    funcao = getattr(db, "buscar_titulo_referencia", None)
    if callable(funcao):
        return funcao()
    configuracoes = db.buscar_configuracao_iqa()
    return configuracoes.get(
        "titulo_referencia_ambiental",
        "Resolução CONAMA 357/2005 - águas doces classe 2",
    )


def salvar_titulo_referencia_seguro(titulo):
    """Grava só a configuração da norma, sem alterar coletas, pontos ou IQA."""
    funcao = getattr(db, "salvar_titulo_referencia", None)
    if callable(funcao):
        return funcao(titulo)
    titulo = str(titulo).strip()
    if not titulo or len(titulo) > 250:
        raise ValueError("Informe um título de referência de até 250 caracteres.")
    # Compatibilidade com a versão anterior de database.py: atualiza somente
    # uma chave da tabela 'configuracoes', que já existe no esquema original.
    with db.conexao() as con:
        con.execute(
            "INSERT INTO configuracoes(chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            ("titulo_referencia_ambiental", titulo),
        )


def credenciais_admin():
    """Lê as credenciais dos Streamlit Secrets, sem expor senha no repositório."""
    usuario = senha = ""
    try:
        usuario = st.secrets.get("ADMIN_USER", "")
        senha = st.secrets.get("ADMIN_PASSWORD", "")
    except (FileNotFoundError, KeyError):
        pass
    # Variáveis de ambiente ficam como alternativa para deploys fora do Streamlit Cloud.
    usuario = usuario or os.environ.get("ADMIN_USER", "")
    senha = senha or os.environ.get("ADMIN_PASSWORD", "")
    return str(usuario).strip(), str(senha)


def cabecalho_publico():
    # A barra superior flutuante do Streamlit não pode cobrir o botão.
    st.markdown('<div class="public-header-clearance"></div>', unsafe_allow_html=True)
    esquerda, direita = st.columns([5, 1.4], vertical_alignment="center")
    with esquerda:
        st.markdown(marca(), unsafe_allow_html=True)
    with direita:
        if st.button(" ", icon=":material/person:", help="Acesso administrativo",
                     key="entrar_admin", use_container_width=False):
            st.session_state.pagina = "login" if not st.session_state.autenticado else "admin"
            st.rerun()
    st.markdown('<div class="public-header-rule"></div>', unsafe_allow_html=True)


def tela_login():
    cabecalho_login = st.columns([4, 1])[0]
    with cabecalho_login:
        st.markdown(marca(), unsafe_allow_html=True)
    st.divider()
    esq, meio, dir_ = st.columns([1, 1.35, 1])
    with meio:
        with st.container(border=True):
            st.subheader("Acesso administrativo")
            usuario_config, senha_config = credenciais_admin()
            if not usuario_config or not senha_config:
                st.error("Configure ADMIN_USER e ADMIN_PASSWORD nos Secrets do Streamlit para habilitar o login.")
            restante = max(0, int(st.session_state.bloqueio_ate - time.monotonic()))
            if restante:
                st.warning(f"Tente novamente em {restante} segundos.")
            with st.form("login_admin"):
                usuario_informado = st.text_input("Usuário", autocomplete="username")
                senha_informada = st.text_input("Senha", type="password", autocomplete="current-password")
                enviar = st.form_submit_button("Entrar", type="primary", use_container_width=True,
                                               disabled=restante > 0 or not (usuario_config and senha_config))
            if enviar:
                if (hmac.compare_digest(usuario_informado.strip(), usuario_config)
                        and hmac.compare_digest(senha_informada, senha_config)):
                    st.session_state.autenticado = True
                    st.session_state.pagina = "admin"
                    st.session_state.falhas_login = 0
                    st.session_state.bloqueio_ate = 0.0
                    st.rerun()
                st.session_state.falhas_login += 1
                if st.session_state.falhas_login >= 5:
                    st.session_state.bloqueio_ate = time.monotonic() + 30
                    st.session_state.falhas_login = 0
                st.error("Senha incorreta.")
            if st.button("Voltar", use_container_width=True):
                st.session_state.pagina = "publico"
                st.rerun()


# -----------------------------------------------------------------------------
# Consulta consolidada por ponto/campanha + exportação de relatório.
# -----------------------------------------------------------------------------
def montar_resumo_ponto(dados_ponto, parametros, faixas):
    """Somente leitura; preserva a ordem dos parâmetros do laboratório."""
    catalogo = parametros.drop_duplicates(subset=["id"]).copy()
    existentes = dados_ponto.drop_duplicates(subset=["param_id"], keep="last")
    por_parametro = {int(r["param_id"]): r for _, r in existentes.iterrows()}
    linhas = []
    for _, par in catalogo.iterrows():
        pid = int(par["id"])
        medicao = por_parametro.get(pid)
        valor = float(medicao["valor"]) if medicao is not None and pd.notna(medicao["valor"]) else None
        if somente_iqa(par["nome"]):
            faixa = classificar_iqa(valor, faixas) if valor is not None else None
            referencia = "Escala do IQA (0–100)"
            situacao = str(faixa["nome"]) if faixa is not None else "Não informado"
            cor = str(faixa["cor_texto"]) if faixa is not None else ""
        else:
            referencia = resumo_referencia(par)
            situacao = verificar_conformidade(valor, par) if valor is not None else "Não analisado"
            cor = ""
        linhas.append({
            "ordem": int(par["ordem_exibicao"]) if pd.notna(par.get("ordem_exibicao")) else 100000+pid,
            "parametro": str(par["nome"]),
            "unidade": "—" if str(par["unidade"]) == "-" else str(par["unidade"]),
            "valor": valor,
            "resultado": formatar_valor_br_relatorio(valor),
            "referencia": referencia,
            "situacao": situacao,
            "cor_iqa": cor,
            "iqa": somente_iqa(par["nome"]),
        })
    return sorted(linhas, key=lambda r: (r["iqa"], r["ordem"], r["parametro"]))


def formatar_valor_br_relatorio(valor):
    if valor is None or pd.isna(valor):
        return "—"
    n = float(valor)
    return f"{n:,.5f}".rstrip("0").rstrip(".").replace(",", "@").replace(".", ",").replace("@", ".")


def gerar_relatorio_excel_ponto(linhas, nome_ponto, data_coleta, titulo_referencia, codigo_amostra):
    """Relatório formatado em memória, sem acessar nem alterar o SQLite."""
    arquivo = io.BytesIO()
    with xlsxwriter.Workbook(arquivo, {"in_memory": True}) as wb:
        ws = wb.add_worksheet("Análises do ponto")
        ws.hide_gridlines(2)
        ws.set_zoom(95)
        ws.set_landscape()
        ws.fit_to_pages(1, 1)
        ws.set_paper(9)
        ws.set_margins(.35, .35, .5, .5)
        ws.set_header("&CGestão Ambiental | UFSC")
        ws.set_footer("&CMonitoramento das Águas — Página &P de &N")
        for col, largura in enumerate([5, 41, 18, 16, 29, 23]):
            ws.set_column(col, col, largura)
        navy, blue, light = "#17324D", "#2563EB", "#F3F7FC"
        titulo = wb.add_format({"font_name":"Arial","font_size":18,"bold":True,"font_color":"#FFFFFF","bg_color":navy,"valign":"vcenter"})
        marca = wb.add_format({"font_name":"Arial","font_size":10,"bold":True,"font_color":"#E2E8F0","bg_color":navy})
        subtitulo = wb.add_format({"font_name":"Arial","font_size":11,"bold":True,"font_color":navy,"bg_color":"#E8F1FF","valign":"vcenter"})
        descricao = wb.add_format({"font_name":"Arial","font_size":10,"font_color":"#475569","text_wrap":True,"valign":"vcenter"})
        rotulo = wb.add_format({"font_name":"Arial","font_size":10,"bold":True,"font_color":"#64748B"})
        cab = wb.add_format({"font_name":"Arial","font_size":10,"bold":True,"font_color":"#FFFFFF","bg_color":blue,"bottom":1,"bottom_color":"#1D4ED8","valign":"vcenter"})
        body = wb.add_format({"font_name":"Arial","font_size":10,"font_color":"#23364C","valign":"vcenter"})
        alt = wb.add_format({"font_name":"Arial","font_size":10,"font_color":"#23364C","bg_color":light,"valign":"vcenter"})
        num = wb.add_format({"font_name":"Arial","font_size":10,"font_color":navy,"num_format":"#,##0.#####","valign":"vcenter"})
        num_alt = wb.add_format({"font_name":"Arial","font_size":10,"font_color":navy,"bg_color":light,"num_format":"#,##0.#####","valign":"vcenter"})
        bom = wb.add_format({"font_name":"Arial","font_size":10,"bold":True,"font_color":"#166534","bg_color":"#DCFCE7","valign":"vcenter"})
        alerta = wb.add_format({"font_name":"Arial","font_size":10,"bold":True,"font_color":"#991B1B","bg_color":"#FEE2E2","valign":"vcenter"})
        neutro = wb.add_format({"font_name":"Arial","font_size":10,"font_color":"#64748B","valign":"vcenter"})
        rodape = wb.add_format({"font_name":"Arial","font_size":9,"font_color":"#64748B","italic":True,"text_wrap":True,"valign":"vcenter"})
        ws.set_row(0, 18)
        ws.merge_range(0, 0, 0, 5, "UFSC  |  GESTÃO AMBIENTAL", marca)
        ws.set_row(1, 38)
        ws.merge_range(1, 0, 1, 5, "Resumo de análises da água", titulo)
        ws.set_row(2, 28)
        ws.merge_range(2, 0, 2, 5, nome_ponto, subtitulo)
        ws.write(4, 0, "DATA:", rotulo)
        ws.merge_range(4, 1, 4, 2, formatar_data(data_coleta), body)
        ws.write(4, 3, "AMOSTRA:", rotulo)
        ws.merge_range(4, 4, 4, 5, str(codigo_amostra), body)
        ws.set_row(5, 34)
        ws.merge_range(5, 0, 5, 5, "Referência informada: " + titulo_referencia, descricao)
        cabecalhos = ["Nº", "PARÂMETRO", "RESULTADO", "UNIDADE", "REFERÊNCIA", "SITUAÇÃO"]
        inicio = 7
        ws.set_row(inicio, 25)
        for j, titulo_col in enumerate(cabecalhos):
            ws.write(inicio, j, titulo_col, cab)
        for i, item in enumerate(linhas, 1):
            linha = inicio+i
            ws.set_row(linha, 24)
            formato = alt if i % 2 == 0 else body
            ws.write_number(linha, 0, i, formato)
            ws.write_string(linha, 1, item["parametro"], formato)
            if item["valor"] is None:
                ws.write_string(linha, 2, "—", formato)
            else:
                ws.write_number(linha, 2, float(item["valor"]), num_alt if i%2==0 else num)
            ws.write_string(linha, 3, item["unidade"], formato)
            ws.write_string(linha, 4, item["referencia"], formato)
            estado = item["situacao"]
            status_fmt = (bom if estado == "Na referência" else
                          alerta if estado == "Fora da referência" else neutro)
            ws.write_string(linha, 5, estado, status_fmt)
        final = inicio + len(linhas) + 2
        ws.set_row(final, 35)
        ws.merge_range(final, 0, final, 5,
            "* Situação é comparação numérica apenas para referências validadas e aplicáveis. "
            "O título não substitui a conferência da norma, enquadramento e condições de cada parâmetro.", rodape)
        ws.set_row(final+1, 26)
        ws.merge_range(final+1, 0, final+1, 5,
            "IQA informado manualmente. Parâmetros sem análise ou sem referência validada não recebem classificação de conformidade.", rodape)
        ws.freeze_panes(inicio+1, 2)
        ws.autofilter(inicio, 0, inicio+len(linhas), 5)
        ws.print_area(0,0,final+1,5)
    return arquivo.getvalue()


def estilo_situacao_resumo(valor):
    """Aplica cores somente à célula da situação; não modifica os dados."""
    cores = {
        "na referência": ("#DCFCE7", "#166534"),
        "fora da referência": ("#FEE2E2", "#991B1B"),
        "sem referência": ("#F1F5F9", "#64748B"),
        "não analisado": ("#F1F5F9", "#64748B"),
        "não informado": ("#F1F5F9", "#64748B"),
        "péssima": ("#FEE2E2", "#991B1B"),
        "ruim": ("#FFEDD5", "#9A3412"),
        "regular": ("#FEF3C7", "#854D0E"),
        "boa": ("#DCFCE7", "#166534"),
        "ótima": ("#D1FAE5", "#065F46"),
    }
    fundo, texto = cores.get(str(valor).strip().casefold(), ("#F1F5F9", "#475569"))
    return f"background-color: {fundo}; color: {texto}; font-weight: 600;"


def exibir_resumo_analises_ponto(campanha_df, pontos, faixas, data_campanha):
    """Tabela por ponto e campanha, com apresentação e exportação somente de leitura."""
    with st.container(border=True):
        titulo_secao("Resumo das análises do ponto",
                     "Resultados laboratoriais, referência configurada e situação por parâmetro.")
        if data_campanha is None or campanha_df.empty:
            st.info("Selecione uma campanha com medições para consultar os resultados.")
            return
        ids_campanha = [int(pid) for pid in pontos["id"].tolist()
                        if int(pid) in set(campanha_df["ponto_id"].dropna().astype(int))]
        if not ids_campanha:
            st.info("Esta campanha não possui resultados para os pontos disponíveis.")
            return
        rotulos = {int(r["id"]): rotulo_ponto(r) for _, r in pontos.iterrows()}
        if st.session_state.get("resumo_ponto_publico") not in ids_campanha:
            st.session_state.resumo_ponto_publico = ids_campanha[0]

        # Filtros no início da seção, alinhados e sem espaço vertical excessivo.
        col_ponto, col_data = st.columns([3, 1], gap="medium", vertical_alignment="bottom")
        with col_ponto:
            ponto = st.selectbox("Ponto de coleta", ids_campanha,
                                 key="resumo_ponto_publico",
                                 format_func=lambda pid: rotulos[pid])
        with col_data:
            st.markdown(
                '<div style="border:1px solid #DCE5EA;border-radius:9px;'
                'background:#FFFFFF;padding:8px 12px;margin-bottom:1px;">'
                '<div style="font-size:11px;color:#64748B;margin-bottom:2px;">'
                'Data da campanha</div>'
                f'<div style="font-size:18px;font-weight:650;color:#17324D;">'
                f'{html.escape(formatar_data(data_campanha))}</div></div>',
                unsafe_allow_html=True,
            )

        med = campanha_df[campanha_df["ponto_id"] == ponto]
        ids_amostras = med["amostra_id"].dropna().astype(int).drop_duplicates().tolist()
        if not ids_amostras:
            st.info("Nenhuma amostra vinculada a este ponto e data.")
            return
        if len(ids_amostras) > 1:
            amostra_id = st.selectbox("Amostra desta campanha", ids_amostras,
                                     format_func=lambda aid: f"Amostra #{aid}",
                                     key=f"resumo_amostra_{ponto}_{data_campanha}")
        else:
            amostra_id = ids_amostras[0]
        dados_amostra = med[med["amostra_id"] == amostra_id]
        titulo = buscar_titulo_referencia_seguro()
        st.markdown(
            '<div style="border-left:4px solid #2563EB;background:#EFF6FF;'
            'padding:12px 16px;border-radius:9px;margin:5px 0 12px;">'
            '<div style="color:#1D4ED8;font-size:11px;font-weight:700;'
            'text-transform:uppercase;letter-spacing:.055em;">Referência normativa</div>'
            f'<div style="color:#17324D;font-size:15px;font-weight:650;'
            f'margin-top:3px;">{html.escape(str(titulo))}</div></div>',
            unsafe_allow_html=True,
        )
        catalogo = db.buscar_parametros()  # inclui arquivados para preservar histórico
        linhas = montar_resumo_ponto(dados_amostra, catalogo, faixas)
        tabela = pd.DataFrame([{
            "Parâmetro": linha["parametro"],
            "Resultado": linha["resultado"],
            "Unidade": linha["unidade"],
            "Referência": linha["referencia"],
            "Situação": linha["situacao"],
        } for linha in linhas])
        tabela_estilizada = tabela.style.map(estilo_situacao_resumo, subset=["Situação"])
        st.dataframe(tabela_estilizada, hide_index=True, use_container_width=True,
                     height=min(650, 40 + 35 * len(tabela)))
        st.caption("'Na referência' ou 'Fora da referência' indica apenas comparação numérica "
                   "com limites cadastrados e validados; não substitui análise legal de enquadramento.")
        nome_arquivo = f"analises_ufsc_ponto_{ponto}_{data_campanha.isoformat()}"
        c1, c2 = st.columns([1.1, 1], gap="small")
        with c1:
            st.download_button(
                "Baixar relatório formatado (Excel)",
                data=gerar_relatorio_excel_ponto(linhas, rotulos[ponto], data_campanha,
                                                 titulo, amostra_id),
                file_name=nome_arquivo + ".xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True, type="primary")
        with c2:
            st.download_button("Baixar dados (CSV)",
                data=tabela.to_csv(index=False, sep=";").encode("utf-8-sig"),
                file_name=nome_arquivo + ".csv", mime="text/csv",
                use_container_width=True)


# -----------------------------------------------------------------------------
# Painel público.
# -----------------------------------------------------------------------------
def painel_publico():
    pontos = db.buscar_pontos(ativos=True)
    parametros = db.buscar_parametros(ativos=True)
    resultados = preparar_resultados_publicos(db.buscar_coletas())
    faixas = db.buscar_faixas_iqa()

    cabecalho_publico()
    st.title("Qualidade da água nos córregos da UFSC")
    st.markdown('<div class="lead">Veja o mapa dos pontos e acompanhe a evolução do IQA e dos parâmetros de qualidade da água por local de coleta.</div>', unsafe_allow_html=True)
    st.write("")

    campanhas = sorted(resultados["dia"].dropna().unique(), reverse=True) if not resultados.empty else []
    ultima_campanha = campanhas[0] if campanhas else None
    a, b, c, d = st.columns(4)
    a.metric("Pontos monitorados", len(pontos))
    b.metric("Campanhas de coleta", len(campanhas))
    c.metric("Pontos com análises", int(resultados["ponto_id"].nunique()) if not resultados.empty else 0)
    d.metric("Última campanha", formatar_data(ultima_campanha) if ultima_campanha else "—")

    if pontos.empty:
        st.info("Nenhum ponto ativo cadastrado.")
        return

    # Um único filtro de campanha governa o panorama e os gráficos comparativos.
    campanha_opcoes = campanhas if campanhas else [None]
    if st.session_state.get("campanha_publica") not in campanha_opcoes:
        st.session_state.campanha_publica = campanha_opcoes[0]
    st.write("")
    topo_esq, topo_dir = st.columns([1, 2.5], vertical_alignment="bottom")
    with topo_esq:
        campanha_sel = st.selectbox(
            "Campanha de coleta", campanha_opcoes, key="campanha_publica",
            format_func=lambda d: "Sem dados" if d is None else d.strftime("%d/%m/%Y"),
        )
    campanha_df = (resultados[resultados["dia"] == campanha_sel].copy()
                   if campanha_sel is not None and not resultados.empty else resultados.iloc[0:0].copy())
    resumo_iqa = obter_iqa_por_ponto(campanha_df, faixas)
    with topo_dir:
        n_pontos = int(campanha_df["ponto_id"].nunique()) if not campanha_df.empty else 0
        n_iqa = len(resumo_iqa)
        st.markdown(
            f'<div class="campaign-kpis"><span><strong>{n_pontos}</strong> pontos amostrados</span>'
            f'<span><strong>{n_iqa}</strong> com IQA</span></div>',
            unsafe_allow_html=True,
        )

    titulo_secao("Mapa dos Pontos")
    mapa_col, painel_col = st.columns([1.8, 1], gap="medium")
    pontos_mapa = pontos.copy()
    ids = pontos_mapa["id"].astype(int).tolist()
    if st.session_state.get("ponto_publico") not in ids:
        st.session_state.ponto_publico = ids[0]
    estilos, popups, resumo_iqa = estilos_mapa_por_campanha(pontos_mapa, campanha_df, faixas)
    with mapa_col:
        escolhido_mapa = cartografia(
            pontos_mapa, foco_id=st.session_state.ponto_publico,
            chave="mapa_publico", altura=405,
            estilos_por_ponto=estilos, popup_por_ponto=popups,
        )
        if escolhido_mapa is not None and escolhido_mapa != st.session_state.ponto_publico:
            st.session_state.ponto_publico = escolhido_mapa
            st.rerun()
    with painel_col:
        with st.container(border=True):
            titulo_secao("Classificação do IQA")
            grafico_distribuicao_iqa(campanha_df, faixas)
            st.caption("Cores dos pontos no mapa: classificação do IQA; cinza significa sem IQA na data.")

    # Consulta tabular completa desta data, com exportação profissional em Excel.
    st.write("")
    exibir_resumo_analises_ponto(campanha_df, pontos, faixas, campanha_sel)

    nomes_pontos = {int(r["id"]): rotulo_ponto(r) for _, r in pontos.iterrows()}
    outros_parametros = parametros[~parametros["nome"].apply(somente_iqa)]
    todas_medicoes = resultados[~resultados["parametro"].apply(somente_iqa)].copy()
    ids_parametros = outros_parametros[
        outros_parametros["id"].isin(todas_medicoes["param_id"].dropna().astype(int))
    ]["id"].astype(int).tolist() if not todas_medicoes.empty else []

    # 1 — Evolução temporal de um único ponto para o parâmetro escolhido.
    st.write("")
    with st.container(border=True):
        titulo_secao("Evolução dos parâmetros por ponto")
        if ids_parametros:
            filtro_param, filtro_ponto = st.columns([1.2, 1.8])
            with filtro_param:
                if st.session_state.get("parametro_temporal_individual") not in ids_parametros:
                    st.session_state.parametro_temporal_individual = ids_parametros[0]
                parametro_individual = st.selectbox(
                    "Parâmetro", ids_parametros,
                    format_func=lambda pid: outros_parametros.loc[
                        outros_parametros["id"] == pid, "nome"].iloc[0],
                    key="parametro_temporal_individual")
            pontos_disponiveis = set(todas_medicoes.loc[
                todas_medicoes["param_id"] == parametro_individual, "ponto_id"].dropna().astype(int))
            ids_disponiveis = [int(pid) for pid in ids if int(pid) in pontos_disponiveis]
            with filtro_ponto:
                if ids_disponiveis:
                    if st.session_state.get("ponto_parametro_individual") not in ids_disponiveis:
                        st.session_state.ponto_parametro_individual = ids_disponiveis[0]
                    ponto_individual = st.selectbox(
                        "Ponto de coleta", ids_disponiveis,
                        format_func=lambda pid: nomes_pontos[pid],
                        key="ponto_parametro_individual")
            if ids_disponiveis:
                parametro_config = parametros.loc[parametros["id"] == parametro_individual].iloc[0]
                serie = todas_medicoes[
                    (todas_medicoes["param_id"] == parametro_individual) &
                    (todas_medicoes["ponto_id"] == ponto_individual)]
                grafico_temporal(serie, parametro_config["nome"], parametro_config)
            else:
                st.info("Não há medições para esse parâmetro.")
        else:
            st.info("Ainda não há resultados de parâmetros.")

    # 2 — IQA de um único ponto.
    st.write("")
    with st.container(border=True):
        titulo_secao("Evolução do IQA por ponto")
        ids_com_iqa = resultados.loc[
            resultados["parametro"].astype(str).str.startswith("IQA (", na=False), "ponto_id"
        ].dropna().astype(int).drop_duplicates().tolist()
        ids_com_iqa = [pid for pid in ids if pid in ids_com_iqa]
        if ids_com_iqa:
            if st.session_state.get("ponto_iqa_individual") not in ids_com_iqa:
                st.session_state.ponto_iqa_individual = ids_com_iqa[0]
            st.selectbox("Ponto de coleta", ids_com_iqa,
                         format_func=lambda pid: nomes_pontos[pid], key="ponto_iqa_individual")
            dados_iqa_ponto = resultados[resultados["ponto_id"] == st.session_state.ponto_iqa_individual]
            grafico_iqa(dados_iqa_ponto[dados_iqa_ponto["parametro"].apply(somente_iqa)], faixas)
        else:
            st.info("Ainda não existem valores de IQA registrados para os pontos.")

    if not resultados.empty:
        exportar = resultados[resultados["ponto_id"] == st.session_state.get("ponto_iqa_individual", st.session_state.ponto_publico)].copy()
        st.download_button("Baixar histórico do ponto (CSV)",
                           exportar.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           "historico_aguas_ufsc.csv", "text/csv", type="secondary")
    st.divider()
    st.caption("UFSC · Gestão Ambiental")


# -----------------------------------------------------------------------------
# Componentes de edição administrativa — modais e confirmações.
# -----------------------------------------------------------------------------
def versao_formulario_admin():
    pagina = st.session_state.get("admin_menu", "Visão geral")
    return st.session_state.get("_versoes_formularios_admin", {}).get(pagina, 0)


def chave_formulario_admin(chave):
    return f"{chave}_v{versao_formulario_admin()}"


def concluir_salvamento(mensagem):
    """Reinicia os campos da página somente após a gravação bem-sucedida."""
    st.session_state.mensagem = mensagem
    st.session_state._limpar_pagina_admin = st.session_state.get("admin_menu")
    st.rerun()


def limpar_pagina_apos_salvar():
    """Executado antes de criar widgets; mantém autenticação e navegação."""
    pagina = st.session_state.pop("_limpar_pagina_admin", None)
    prefixos = {
        "Coletas e análises": ("nova_", "edit_", "historico_ponto_", "confirmar_excluir_amostra_"),
        "Pontos de coleta": ("editor_ponto_", "editor_lat", "editor_lon", "modo_coord_ponto_",
                              "e_ponto_", "n_ponto_", "lat_ponto_", "lon_ponto_", "admin_ponto_",
                              "importar_utm_csv_", "confirmar_importacao_utm_", "botao_importar_utm_"),
        "Parâmetros ambientais": ("admin_param_",),
        "Configuração do IQA": ("faixa_min_", "faixa_max_"),
        "Visão geral": ("visao_geral_ponto_",),
    }.get(pagina, ())
    if prefixos:
        for chave in list(st.session_state.keys()):
            if chave.startswith(prefixos):
                st.session_state.pop(chave, None)
    if pagina:
        # Novas identidades dos widgets impedem que o navegador restaure valores antigos.
        versoes = dict(st.session_state.get("_versoes_formularios_admin", {}))
        versoes[pagina] = versoes.get(pagina, 0) + 1
        st.session_state._versoes_formularios_admin = versoes


@st.dialog("Cadastrar ou editar ponto", width="large", on_dismiss="rerun")
def formulario_ponto(ponto=None):
    token = chave_formulario_admin(f"ponto_{int(ponto['id'])}" if ponto is not None else "ponto_novo")
    lat_ant = float(ponto['latitude']) if ponto is not None and pd.notna(ponto['latitude']) else -27.601
    lon_ant = float(ponto['longitude']) if ponto is not None and pd.notna(ponto['longitude']) else -48.518
    if st.session_state.get('editor_ponto_token') != token:
        st.session_state.editor_ponto_token = token
        st.session_state.editor_lat = lat_ant
        st.session_state.editor_lon = lon_ant
        st.session_state.editor_ponto_ultimo_clique = None
    modo = st.radio('Tipo de coordenada', ['UTM (E / N)', 'Latitude / longitude'],
                    horizontal=True, key=f'modo_coord_{token}')
    st.caption('UTM zona 22 Sul · SIRGAS 2000 (EPSG:31982). Verifique o datum do levantamento.')

    with st.form(f'form_ponto_{token}'):
        c1, c2 = st.columns([1, 2])
        codigo = c1.text_input('Código *', value=str(ponto['codigo']) if ponto is not None else '')
        local = c2.text_input('Local *', value=str(ponto['local']) if ponto is not None else '')
        c3, c4 = st.columns(2)
        if modo == 'UTM (E / N)':
            e_atual, n_atual = GPS_PARA_UTM.transform(lon_ant, lat_ant)
            e_txt = c3.text_input('E (m) *', value=formatar_utm(e_atual), key=f'e_{token}',
                                  help='Ex.: 744.245,94')
            n_txt = c4.text_input('N (m) *', value=formatar_utm(n_atual), key=f'n_{token}',
                                  help='Ex.: 6.944.464,32')
            lat = lon = None
        else:
            lat = c3.number_input('Latitude', min_value=-90.0, max_value=90.0,
                                   value=lat_ant, format='%.7f', key=f'lat_{token}')
            lon = c4.number_input('Longitude', min_value=-180.0, max_value=180.0,
                                   value=lon_ant, format='%.7f', key=f'lon_{token}')
        salvar = st.form_submit_button('Salvar ponto', type='primary', use_container_width=True)
    if salvar:
        try:
            if modo == 'UTM (E / N)':
                lat, lon = converter_utm(e_txt, n_txt)
            if ponto is None:
                db.inserir_ponto(codigo, local, lat, lon)
            else:
                db.atualizar_ponto(int(ponto['id']), codigo, local, lat, lon)
            concluir_salvamento('Ponto salvo com sucesso.')
        except (ValueError, TypeError) as exc:
            st.error(str(exc))


@st.dialog("Cadastrar ou editar parâmetro", width="large", on_dismiss="rerun")
def formulario_parametro(param=None):
    st.caption("Referências legais só são utilizadas na comparação pública após validação de norma e aplicabilidade.")
    tipo_opcoes = ["nenhum", "minimo", "maximo", "intervalo"]
    tipo_atual = str(param["tipo_limite"]) if param is not None else "nenhum"
    # Widgets reativos: dentro de st.form os campos mínimo/máximo não seriam
    # habilitados imediatamente ao escolher o tipo de referência.
    with st.container():
        n1, n2 = st.columns([2, 1])
        nome = n1.text_input("Nome *", value=str(param["nome"]) if param is not None else "", key=chave_formulario_admin("admin_param_nome"))
        unidade = n2.text_input("Unidade *", value=str(param["unidade"]) if param is not None else "mg/L", key=chave_formulario_admin("admin_param_unidade"))
        tipo = st.selectbox("Tipo de referência", tipo_opcoes,
                            index=tipo_opcoes.index(tipo_atual) if tipo_atual in tipo_opcoes else 0,
                            key=chave_formulario_admin("admin_param_tipo"),
                            format_func=lambda v: {"nenhum": "Sem referência", "minimo": "Mínimo",
                                                   "maximo": "Máximo", "intervalo": "Intervalo (mínimo e máximo)"}[v])
        l1, l2 = st.columns(2)
        min_atual = float(param["limite_min"]) if param is not None and pd.notna(param["limite_min"]) else None
        max_atual = float(param["limite_max"]) if param is not None and pd.notna(param["limite_max"]) else None
        minimo = l1.number_input("Valor mínimo", value=min_atual, format="%.5f", step=0.01,
                                 disabled=tipo not in ("minimo", "intervalo"), key=chave_formulario_admin("admin_param_minimo"))
        maximo = l2.number_input("Valor máximo", value=max_atual, format="%.5f", step=0.01,
                                 disabled=tipo not in ("maximo", "intervalo"), key=chave_formulario_admin("admin_param_maximo"))
        norma = st.text_input("Base normativa (norma, artigo ou resolução)",
                              value=str(param["base_normativa"]) if param is not None else "", key=chave_formulario_admin("admin_param_norma"))
        aplica = st.text_input("Aplicabilidade (classe, enquadramento, condições)",
                               value=str(param["aplicabilidade"]) if param is not None else "", key=chave_formulario_admin("admin_param_aplica"))
        valida = st.checkbox("Referência revisada e validada para o contexto do monitoramento",
                             value=bool(param["referencia_validada"]) if param is not None else False, key=chave_formulario_admin("admin_param_valida"))
        # Preservar os metadados antigos, sem exibir campos de metodologia do IQA.
        compoe = bool(param["compoe_iqa"]) if param is not None else False
        peso = (float(param["peso_iqa"])
                if param is not None and pd.notna(param["peso_iqa"]) else None)
        curva = str(param["curva_iqa"] or "") if param is not None else ""
        salvar = st.button("Salvar parâmetro", type="primary", use_container_width=True,
                           key=chave_formulario_admin("admin_param_salvar_modal"))
    if salvar:
        try:
            db.salvar_parametro(None if param is None else int(param["id"]), nome, unidade, tipo,
                               minimo, maximo, norma, aplica, valida, compoe, peso, curva)
            concluir_salvamento("Parâmetro salvo com sucesso.")
        except ValueError as e:
            st.error(str(e))


@st.dialog("Confirmar alteração", on_dismiss="rerun")
def confirmar_arquivamento(tipo, identificador, nome, ativar=False):
    verbo = "reativar" if ativar else "arquivar"
    st.warning(f"Deseja {verbo} '{nome}'?")
    if not ativar:
        st.caption("Arquivar oculta o cadastro de novas coletas, mas mantém todo o histórico existente.")
    x, y = st.columns(2)
    if x.button("Cancelar", use_container_width=True):
        st.rerun()
    if y.button("Confirmar", type="primary", use_container_width=True):
        try:
            if tipo == "ponto":
                db.alterar_status_ponto(identificador, ativar)
            else:
                db.alterar_status_parametro(identificador, ativar)
        except db.ErroPersistencia as exc:
            st.error(str(exc))
            return
        concluir_salvamento("Cadastro atualizado.")


@st.dialog("Confirmar exclusão da coleta", on_dismiss="rerun")
def confirmar_exclusao_amostra(amostra_id, codigo, local, data_amostra):
    st.write(f"Ponto: {codigo} · {local}")
    st.write(f"Data da coleta: {formatar_data(data_amostra)}")
    st.warning("Todos os resultados e o IQA desta coleta serão excluídos. Os demais pontos e datas serão preservados.")
    confirmar = st.checkbox("Confirmo a exclusão desta coleta.", key=f"confirmar_excluir_amostra_{amostra_id}")
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", use_container_width=True):
        st.rerun()
    if c2.button("Excluir coleta", type="primary", disabled=not confirmar, use_container_width=True):
        try:
            db.excluir_amostra(amostra_id)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
            return
        concluir_salvamento("Coleta excluída.")


def _validar_resultados_semanticos(parametros, valores):
    for _, row in parametros.iterrows():
        v = valores.get(int(row["id"]))
        if v is None:
            continue
        nome = str(row["nome"]).lower().strip()
        if nome == "ph" and not 0 <= v <= 14:
            raise ValueError("O pH deve estar entre 0 e 14.")
        if somente_iqa(row["nome"]) and not 0 <= v <= 100:
            raise ValueError("O IQA deve estar entre 0 e 100.")
        nomes_nao_negativos = ("carbono orgânico", "coliform", "condutividade", "dbo", "fósforo",
                               "nitrogênio", "oxigênio dissolvido", "sólido", "turbidez")
        if any(nome.startswith(item) for item in nomes_nao_negativos) and v < 0:
            raise ValueError(f"{row['nome']} não pode ter valor negativo.")


def _interpretar_valor_planilha(celula):
    """Converte número brasileiro; rejeita valores ambíguos e textos."""
    import re
    valor = str(celula).strip().replace("\u00a0", "").replace(" ", "")
    if valor in ("", "-", "—"):
        return None
    # Exemplos aceitos: 3,22 | 5.800,00 | 400,5 | 156 | 26.5
    if re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+(?:,\d+)?", valor):
        normalizado = valor.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[+-]?\d+(?:,\d+)?", valor):
        normalizado = valor.replace(",", ".")
    elif re.fullmatch(r"[+-]?\d+\.\d+", valor):
        normalizado = valor
    else:
        raise ValueError(f"Valor inválido: {celula}")
    numero = float(normalizado)
    if not math.isfinite(numero):
        raise ValueError("Valores infinitos ou NaN não são permitidos.")
    return numero


def _processar_coluna_laboratorio(texto_colado, parametros_analise):
    """Retorna valores e conferência. Nunca associa lista incompleta silenciosamente."""
    linhas = texto_colado.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while linhas and not linhas[-1].strip():
        linhas.pop()
    qtd = len(linhas)
    total = len(parametros_analise)
    if qtd == 0:
        return {}, [], "Cole os valores para visualizar a conferência."
    if any("\t" in linha for linha in linhas):
        return {}, [], "Copie apenas uma coluna da planilha, sem outras colunas."
    tamanhos_validos = {total}
    # A planilha padronizada original contém 12 valores. Campos novos ficam vazios.
    if total >= 12:
        tamanhos_validos.add(12)
    aviso = ""
    if qtd not in tamanhos_validos:
        aviso = (f"Foram coladas {qtd} linhas. Use 12 linhas na ordem original "
                 f"ou {total} linhas para incluir os parâmetros novos. "
                 "Para deixar um resultado sem medição, mantenha a linha vazia no local correto.")
    valores = {}
    conferencia = []
    for i, (_, par) in enumerate(parametros_analise.iterrows()):
        texto = linhas[i].strip() if i < qtd else ""
        valor = None
        status = "Sem medição"
        if texto:
            try:
                valor = _interpretar_valor_planilha(texto)
                status = "OK" if valor is not None else "Sem medição"
            except ValueError:
                status = "Inválido"
                aviso = aviso or "Corrija os valores inválidos antes de salvar."
        if valor is not None:
            valores[int(par["id"])] = valor
        conferencia.append({
            "Ordem": i + 1,
            "Parâmetro": str(par["nome"]),
            "Valor colado": texto if texto else "—",
            "Situação": status,
        })
    if not valores and not aviso:
        aviso = "Informe pelo menos um resultado válido."
    return valores, conferencia, aviso


def formulario_amostra(pontos, parametros, amostra=None, dialogo=False):
    """Formulário com atualização responsiva dos campos e conferência pré-salvamento."""
    if pontos.empty or parametros.empty:
        st.info("Cadastre ao menos um ponto e um parâmetro ativos para registrar uma coleta.")
        return
    amostra_id = int(amostra["id"]) if amostra is not None else None
    prefixo = chave_formulario_admin(f"edit_{amostra_id}" if amostra_id else "nova")
    ids_pt = pontos["id"].astype(int).tolist()
    mapa_pt = {int(p["id"]): f"{p['codigo']} · {p['local']}" for _, p in pontos.iterrows()}
    ponto_padrao = int(amostra["ponto_id"]) if amostra is not None else None
    if ponto_padrao not in ids_pt:
        ponto_padrao = None
    with st.container(border=True):
        titulo_secao("1. Identificação da amostra")
        p1, p2 = st.columns([2, 1])
        ponto = p1.selectbox("Ponto de coleta *", ids_pt,
                             index=ids_pt.index(ponto_padrao) if ponto_padrao is not None else None,
                             placeholder="Selecione o ponto de coleta",
                             format_func=lambda i: mapa_pt[i], key=f"{prefixo}_ponto")
        dia = p2.date_input("Data da coleta *", value=pd.to_datetime(amostra["data_amostra"]).date()
                            if amostra is not None else None, max_value=date.today(),
                            format="DD/MM/YYYY", key=f"{prefixo}_data")
    duplicadas = db.buscar_duplicadas(ponto, dia, amostra_id) if ponto is not None and dia is not None else 0
    if duplicadas:
        st.warning(f"Já existe(m) {duplicadas} coleta(s) nesse ponto nessa data. Confira para evitar duplicidade.")
        confirmar_mesma_data = st.checkbox("Confirmo que se trata de outra amostra ou de um registro distinto.",
                                          key=f"{prefixo}_confirmar_duplicada")
    else:
        confirmar_mesma_data = False

    valores_existentes = {}
    if amostra_id:
        valores_existentes = {int(r["parametro_id"]): float(r["valor"])
                             for _, r in db.buscar_valores_amostra(amostra_id).iterrows()}
    # O IQA tem campo próprio; não depende da listagem dos parâmetros laboratoriais.
    iqa_cadastrados = parametros[parametros["nome"].apply(somente_iqa)]
    parametros_analise = (parametros[~parametros["nome"].apply(somente_iqa)]
                          .sort_values(["ordem_exibicao", "id"]))
    valores = {}
    erro_colagem = ""
    with st.container(border=True):
        titulo_secao("2. Resultados da análise")
        modo = st.radio(
            "Modo de preenchimento", ["Colar coluna da planilha", "Preenchimento individual"],
            horizontal=True, key=f"{prefixo}_modo_preenchimento",
            index=1 if amostra_id else 0,
        )
        coluna_entrada, coluna_conferencia = st.columns([1, 1.5], gap="large")
        with coluna_entrada:
            if modo == "Colar coluna da planilha":
                st.caption("Copie a coluna de resultados do Excel. Cole 12 valores, na ordem do "
                           "laboratório, um por linha. Parâmetros futuros ficam ao final.")
                texto_colado = st.text_area(
                    "Valores da planilha", key=f"{prefixo}_coluna_planilha", height=310,
                    placeholder="3,22\n5.800,00\n3.100,00\n400,5\n...",
                )
                valores, conferencia, erro_colagem = _processar_coluna_laboratorio(
                    texto_colado, parametros_analise
                )
                # A planilha de 12 linhas só pode ser mapeada quando os 12
                # parâmetros originais estiverem ativos e na mesma sequência.
                nomes_atuais = [str(n).strip().casefold() for n in parametros_analise["nome"]]
                ordem_esperada = [nome.casefold() for nome in db.PARAMETROS_ORDEM_LAB]
                if nomes_atuais[:12] != ordem_esperada:
                    erro_colagem = ("A ordem padrão de 12 parâmetros não está completa ou "
                                     "foi alterada no cadastro. Use preenchimento individual "
                                     "até que o cadastro seja revisado.")
                if erro_colagem and texto_colado.strip():
                    st.error(erro_colagem)
                elif not texto_colado.strip():
                    st.info("Cole os valores para iniciar a conferência.")
                elif not erro_colagem:
                    st.success(f"{len(valores)} resultados reconhecidos.")
            else:
                st.caption("Preencha somente os parâmetros analisados; deixe os demais vazios.")
                for _, par in parametros_analise.iterrows():
                    param_id = int(par["id"])
                    unidade = "" if par["unidade"] == "-" else f" · {par['unidade']}"
                    valores[param_id] = st.number_input(
                        f"{par['nome']}{unidade}", value=valores_existentes.get(param_id),
                        key=f"{prefixo}_valor_{param_id}", format="%.5f", step=0.00001,
                        placeholder="Não analisado",
                    )
                conferencia = [
                    {"Ordem": i + 1, "Parâmetro": str(par["nome"]),
                     "Valor colado": (formatar_valor(valores[int(par["id"])])
                                      if valores.get(int(par["id"])) is not None else "—"),
                     "Situação": ("OK" if valores.get(int(par["id"])) is not None else "Sem medição")}
                    for i, (_, par) in enumerate(parametros_analise.iterrows())
                ]
        with coluna_conferencia:
            st.markdown("**Conferência dos resultados**")
            st.caption("Confira a ordem de cada linha antes de registrar a coleta.")
            st.dataframe(pd.DataFrame(conferencia, columns=[
                "Ordem", "Parâmetro", "Valor colado", "Situação"
            ]), hide_index=True, use_container_width=True, height=390)
            st.caption("Novos parâmetros aparecem ao final. IQA é informado separadamente.")
        confirmar_ordem = True
        if modo == "Colar coluna da planilha":
            confirmar_ordem = st.checkbox(
                "Conferi a correspondência entre valores e parâmetros",
                key=f"{prefixo}_conferir_ordem",
            )
    with st.container(border=True):
        titulo_secao("3. Índice de Qualidade da Água (IQA)")
        if not iqa_cadastrados.empty:
            par_iqa = iqa_cadastrados.iloc[0]
            id_iqa = int(par_iqa["id"])
            iqa_digitado = st.number_input(
                "Valor do IQA (0 a 100)", min_value=0.0, max_value=100.0,
                value=valores_existentes.get(id_iqa), step=0.1, format="%.2f",
                placeholder="Não informado", key=f"{prefixo}_valor_{id_iqa}",
            )
            valores[id_iqa] = iqa_digitado
        else:
            st.error("O parâmetro IQA não foi encontrado no cadastro.")
    preenchidos = {k: v for k, v in valores.items() if v is not None}
    with st.container(border=True, key=f"sticky_coleta_{prefixo}"):
        titulo_secao("4. Conferência e registro")
        st.caption(f"Ponto: {mapa_pt.get(ponto, 'Não selecionado')} · Data: {formatar_data(dia)} · "
                   f"Resultados informados: {len(preenchidos)}")
        a, b = st.columns([3, 1], vertical_alignment="bottom")
        with a:
            st.caption("Ao salvar, os valores são gravados em uma única transação. Em edições, "
                       "os resultados anteriores desta amostra são substituídos.")
        with b:
            salvar = st.button("Salvar alterações" if amostra_id else "Salvar coleta",
                               type="primary", key=f"{prefixo}_salvar", use_container_width=True,
                               disabled=ponto is None or dia is None or bool(erro_colagem) or not confirmar_ordem)
    if salvar:
        try:
            if ponto is None or dia is None:
                raise ValueError("Selecione o ponto e a data da coleta.")
            if duplicadas and not confirmar_mesma_data:
                raise ValueError("Confirme a existência da outra amostra antes de continuar.")
            _validar_resultados_semanticos(parametros, preenchidos)
            db.salvar_amostra(
                ponto, dia, preenchidos,
                identificador=str(amostra["identificador"] or "") if amostra is not None else "",
                observacoes=str(amostra["observacoes"] or "") if amostra is not None else "",
                permitir_mesma_data=confirmar_mesma_data, amostra_id=amostra_id,
            )
            concluir_salvamento("Coleta salva com sucesso.")
        except (ValueError, TypeError) as e:
            st.error(str(e))


@st.dialog("Editar coleta", width="large", on_dismiss="rerun")
def editar_amostra_dialogo(amostra, pontos, parametros):
    formulario_amostra(pontos, parametros, amostra=amostra, dialogo=True)


# -----------------------------------------------------------------------------
# Páginas administrativas.
# -----------------------------------------------------------------------------
def navegar_para_registro_coleta():
    """Callback executado antes dos widgets serem instanciados no rerun."""
    st.session_state.admin_menu = "Coletas e análises"


def admin_visao_geral(pontos, parametros, coletas, amostras):
    st.title("Visão geral")
    st.caption("Resumo dos registros disponíveis no sistema de monitoramento.")
    x1, x2, x3, x4 = st.columns(4)
    x1.metric("Pontos ativos", int((pontos["ativo"] == 1).sum()) if not pontos.empty else 0)
    x2.metric("Parâmetros ativos", int((parametros["ativo"] == 1).sum()) if not parametros.empty else 0)
    x3.metric("Coletas registradas", len(amostras))
    x4.metric("Última coleta", formatar_data(amostras["data_amostra"].max()) if not amostras.empty else "—")
    st.write("")
    acao1, acao2, _ = st.columns([1.3, 1.2, 3])
    acao1.button(
        "+ Registrar coleta",
        type="primary",
        use_container_width=True,
        on_click=navegar_para_registro_coleta,
    )
    if acao2.button("Visualizar painel público", use_container_width=True):
        st.session_state.pagina = "publico"
        st.rerun()
    st.write("")
    with st.container(border=True):
        titulo_secao("Coletas por data")
        # A árvore parte das amostras registradas, sem supor que todos os pontos
        # tenham coleta em todas as datas. Um ponto aparece uma vez por data.
        if amostras.empty:
            st.info("Ainda não há coletas cadastradas.")
        else:
            registros = amostras.copy()
            registros["dia"] = pd.to_datetime(registros["data_amostra"], errors="coerce").dt.date
            registros = registros.dropna(subset=["dia"])
            registros = registros[registros["qtd_parametros"].fillna(0) > 0]
            if registros.empty:
                st.info("Ainda não há coletas com medições registradas.")
            else:
                for dia in sorted(registros["dia"].unique(), reverse=True):
                    desta_data = registros[registros["dia"] == dia].copy()
                    pontos_data = desta_data.drop_duplicates(subset=["ponto_id"]).copy()
                    pontos_data = pontos_data.sort_values(
                        "codigo", key=lambda col: col.map(chave_ordenacao_ponto)
                    )
                    quantidade = len(pontos_data)
                    n_amostras = len(desta_data)
                    titulo_data = (
                        f"{dia.strftime('%d/%m/%Y')}  ·  {quantidade} "
                        f"{'ponto' if quantidade == 1 else 'pontos'}"
                    )
                    with st.expander(titulo_data, expanded=False):
                        for _, ponto in pontos_data.iterrows():
                            codigo = str(ponto["codigo"])
                            local = str(ponto["local"])
                            total_ponto = int(desta_data.loc[
                                desta_data["ponto_id"] == ponto["ponto_id"], "qtd_parametros"
                            ].sum())
                            linha1, linha2 = st.columns([5, 1], vertical_alignment="center")
                            linha1.markdown(
                                f'<div style="padding:6px 0;font-size:13px">'
                                f'<strong style="color:#1D4ED8">{txt(codigo)}</strong> · {txt(local)}</div>',
                                unsafe_allow_html=True,
                            )
                            linha2.caption(f"{total_ponto} resultados")
                        # Um seletor permite abrir os resultados sem usar expanders aninhados.
                        ids_data = pontos_data["ponto_id"].astype(int).tolist()
                        nomes_data = {int(row["ponto_id"]): rotulo_ponto(row)
                                      for _, row in pontos_data.iterrows()}
                        escolhido = st.selectbox(
                            "Ver resultados de um ponto", ids_data, index=None,
                            placeholder="Selecione um ponto",
                            format_func=lambda pid: nomes_data[pid],
                            key=chave_formulario_admin(f"visao_geral_ponto_{dia.isoformat()}"),
                        )
                        if escolhido is not None:
                            amostras_ponto = desta_data[desta_data["ponto_id"] == escolhido]
                            for _, amostra in amostras_ponto.iterrows():
                                resultados_amostra = coletas[
                                    coletas["amostra_id"] == int(amostra["id"])
                                ].dropna(subset=["valor"])
                                if resultados_amostra.empty:
                                    continue
                                if len(amostras_ponto) > 1:
                                    st.caption(f"Amostra #{int(amostra['id'])}")
                                tabela = resultados_amostra[["parametro", "valor", "unidade"]].copy()
                                tabela["valor"] = tabela["valor"].map(formatar_valor)
                                tabela["unidade"] = tabela["unidade"].replace("-", "")
                                tabela.columns = ["Parâmetro", "Valor", "Unidade"]
                                st.dataframe(tabela, hide_index=True, use_container_width=True)
    with st.container(border=True):
        titulo_secao("Qualidade e consistência do cadastro")
        pendentes = parametros[(parametros["limite_legal"].notna()) &
                              (parametros["referencia_validada"] != 1)] if not parametros.empty else pd.DataFrame()
        if not pendentes.empty:
            st.warning(f"{len(pendentes)} parâmetros têm referência numérica legada ainda não validada. "
                       "Revise a base normativa e a aplicabilidade antes de publicar conformidade.")
        st.caption("O IQA é um resultado preenchido manualmente. O cadastro de faixas não executa o cálculo do índice.")


@st.dialog("Editar resultado", width="small", on_dismiss="rerun")
def editar_resultado_individual(resultado):
    """Edita somente o resultado selecionado, preservando as outras medições."""
    st.markdown(f"**{txt(resultado['parametro'])}**", unsafe_allow_html=True)
    st.caption(f"{formatar_data(resultado['data_amostra'])} · "
               f"{resultado['codigo']} · {resultado['local']}")
    unidade = str(resultado.get("unidade") or "")
    if unidade == "-":
        unidade = ""
    with st.form(chave_formulario_admin(f"form_editar_medicao_{int(resultado['id'])}")):
        valor = st.number_input(
            f"Valor medido{(' (' + unidade + ')') if unidade else ''}",
            value=float(resultado["valor"]), step=0.00001, format="%.5f",
        )
        confirmar = st.form_submit_button("Salvar valor", type="primary", use_container_width=True)
    if confirmar:
        try:
            if not pd.notna(valor):
                raise ValueError("Informe um valor válido.")
            parametro_atual = db.buscar_parametros()
            selecionado = parametro_atual[parametro_atual["id"] == int(resultado["param_id"])]
            if not selecionado.empty:
                _validar_resultados_semanticos(selecionado, {int(resultado["param_id"]): valor})
            db.atualizar_valor_coleta(int(resultado["id"]), valor)
            concluir_salvamento("Resultado atualizado com sucesso.")
        except (ValueError, TypeError) as e:
            st.error(str(e))


@st.dialog("Editar data da coleta", width="small", on_dismiss="rerun")
def editar_data_amostra_dialogo(amostra_id, data_amostra, codigo, local):
    """Altera somente a data da amostra, preservando todas as medições e o IQA."""
    st.caption(f"{codigo} · {local}")
    with st.form(chave_formulario_admin(f"form_editar_data_amostra_{int(amostra_id)}")):
        nova_data = st.date_input(
            "Data da coleta",
            value=pd.to_datetime(data_amostra).date(),
            max_value=date.today(),
            format="DD/MM/YYYY",
        )
        salvar = st.form_submit_button(
            "Salvar data", type="primary", use_container_width=True,
        )
    if salvar:
        try:
            db.atualizar_data_amostra(int(amostra_id), nova_data)
            concluir_salvamento("Data da coleta atualizada com sucesso.")
        except (ValueError, TypeError) as exc:
            st.error(str(exc))


@st.dialog("IQA da coleta", width="small", on_dismiss="rerun")
def editar_iqa_amostra(amostra_id, data_amostra, codigo, local, valor_atual=None):
    """Permite incluir IQA ausente ou atualizar o resultado já registrado."""
    st.caption(f"{formatar_data(data_amostra)} · {codigo} · {local}")
    with st.form(chave_formulario_admin(f"form_iqa_amostra_{int(amostra_id)}")):
        iqa = st.number_input(
            "Valor do IQA (0 a 100)", min_value=0.0, max_value=100.0,
            value=float(valor_atual) if valor_atual is not None else None,
            step=0.1, format="%.2f", placeholder="Informe o IQA",
        )
        salvar = st.form_submit_button(
            "Salvar IQA", type="primary", use_container_width=True,
        )
    if salvar:
        try:
            if iqa is None:
                raise ValueError("Informe o valor do IQA antes de salvar.")
            db.salvar_iqa_amostra(amostra_id, iqa)
            concluir_salvamento("IQA salvo com sucesso.")
        except (ValueError, TypeError) as exc:
            st.error(str(exc))


def chave_ordenacao_ponto(codigo):
    import re
    partes = re.split(r"(\d+)", str(codigo).casefold())
    return tuple((1, int(p)) if p.isdigit() else (0, p) for p in partes)


def admin_coletas(pontos, parametros, amostras, coletas):
    st.title("Coletas e análises")
    tab_nova, tab_historico = st.tabs(["Registrar coleta", "Histórico de coletas"])
    with tab_nova:
        formulario_amostra(pontos[pontos["ativo"] == 1], parametros[parametros["ativo"] == 1])
    with tab_historico:
        if amostras.empty or coletas.empty:
            st.info("Ainda não existem medições registradas.")
            return

        # Amostras sem resultados não aparecem no histórico de análises.
        dados = coletas.dropna(subset=["amostra_id", "valor", "data_amostra"]).copy()
        if dados.empty:
            st.info("Ainda não existem medições registradas.")
            return
        dados["amostra_id"] = dados["amostra_id"].astype(int)
        dados["dia"] = pd.to_datetime(dados["data_amostra"], errors="coerce").dt.date
        dados = dados.dropna(subset=["dia"])
        if dados.empty:
            st.info("Nenhuma data de coleta válida foi encontrada.")
            return

        # Cada data mostra apenas os pontos efetivamente amostrados naquele dia.
        # As datas mais recentes aparecem primeiro.
        for dia in sorted(dados["dia"].unique(), reverse=True):
            dados_dia = dados[dados["dia"] == dia]
            pontos_dia = dados_dia[["ponto_id", "codigo", "local"]].drop_duplicates("ponto_id")
            # Ordenação natural de códigos (1, 2, ..., 10).
            pontos_dia = pontos_dia.sort_values("codigo", key=lambda col: col.map(chave_ordenacao_ponto))
            identificadores = pontos_dia["ponto_id"].astype(int).tolist()
            rotulos = {int(r["ponto_id"]): rotulo_ponto(r) for _, r in pontos_dia.iterrows()}
            n_pontos = len(identificadores)
            with st.expander(f"{dia.strftime('%d/%m/%Y')}  ·  {n_pontos} {'ponto' if n_pontos == 1 else 'pontos'}"):
                # O seletor funciona como menu suspenso. Evita expanders aninhados,
                # não suportados por algumas versões do Streamlit.
                escolhido = st.selectbox(
                    "Ponto de coleta", options=identificadores,
                    index=None, placeholder="Selecione um ponto desta data",
                    format_func=lambda pid: rotulos[pid],
                    key=chave_formulario_admin(f"historico_ponto_{dia.isoformat()}"),
                )
                if escolhido is None:
                    continue
                resultados_pt = dados_dia[dados_dia["ponto_id"] == escolhido]
                amostras_pt = resultados_pt["amostra_id"].drop_duplicates().tolist()
                for id_amostra in amostras_pt:
                    resultados_amostra = resultados_pt[resultados_pt["amostra_id"] == id_amostra]
                    if len(amostras_pt) > 1:
                        st.caption(f"Amostra #{id_amostra}")
                    with st.container(border=True):
                        amostra_info = amostras.loc[
                            amostras["id"].astype(int) == int(id_amostra)
                        ].iloc[0]
                        linha_data = st.columns([4, 1.1, 1.4], vertical_alignment="center")
                        linha_data[0].caption(
                            f"Data da coleta: {formatar_data(amostra_info['data_amostra'])}"
                        )
                        if linha_data[1].button(
                            "Editar data",
                            key=f"editar_data_amostra_{int(id_amostra)}",
                            use_container_width=True,
                        ):
                            editar_data_amostra_dialogo(
                                int(id_amostra), amostra_info["data_amostra"],
                                str(amostra_info["codigo"]), str(amostra_info["local"]),
                            )
                        if linha_data[2].button(
                            "Excluir coleta",
                            key=chave_formulario_admin(f"excluir_amostra_{int(id_amostra)}"),
                            use_container_width=True,
                        ):
                            confirmar_exclusao_amostra(
                                int(id_amostra), str(amostra_info["codigo"]),
                                str(amostra_info["local"]), amostra_info["data_amostra"],
                            )
                        cab = st.columns([4, 1.8, 1.1], vertical_alignment="center")
                        cab[0].caption("PARÂMETRO")
                        cab[1].caption("VALOR")
                        cab[2].caption("AÇÃO")
                        # IQA faz parte do histórico, mas também pode ser inserido
                        # posteriormente, mesmo quando não constava na coleta original.
                        iqa_existente = resultados_amostra[
                            resultados_amostra["parametro"].apply(somente_iqa)
                        ]
                        outros_resultados = resultados_amostra[
                            ~resultados_amostra["parametro"].apply(somente_iqa)
                        ]
                        for _, medicao in outros_resultados.sort_values("parametro").iterrows():
                            c1, c2, c3 = st.columns([4, 1.8, 1.1], vertical_alignment="center")
                            c1.write(medicao["parametro"])
                            unidade = str(medicao.get("unidade") or "")
                            sufixo = "" if unidade == "-" else f" {unidade}"
                            c2.write(f"{formatar_valor(medicao['valor'])}{sufixo}")
                            if c3.button("Editar", key=f"editar_valor_{int(medicao['id'])}",
                                         use_container_width=True):
                                editar_resultado_individual(medicao.to_dict())
                        coluna_nome, coluna_valor, coluna_acao = st.columns(
                            [4, 1.8, 1.1], vertical_alignment="center"
                        )
                        coluna_nome.write("**IQA (Índice de Qualidade da Água)**")
                        valor_iqa = (float(iqa_existente.iloc[0]["valor"])
                                     if not iqa_existente.empty else None)
                        coluna_valor.write(formatar_valor(valor_iqa) if valor_iqa is not None else "Não informado")
                        rotulo_acao = "Editar IQA" if valor_iqa is not None else "Inserir IQA"
                        if coluna_acao.button(
                            rotulo_acao, key=f"gerenciar_iqa_{int(id_amostra)}",
                            use_container_width=True,
                        ):
                            referencia = resultados_amostra.iloc[0]
                            editar_iqa_amostra(
                                int(id_amostra), referencia["data_amostra"],
                                referencia["codigo"], referencia["local"], valor_iqa,
                            )


def admin_pontos(pontos):
    st.title("Pontos de coleta")
    col_t, col_b = st.columns([5.5, 1], vertical_alignment="center")
    with col_t:
        titulo_secao("Pontos cadastrados", f"{len(pontos)} registros no banco de dados")
    if col_b.button("+ Novo ponto", type="secondary", use_container_width=True, key="novo_ponto_admin"):
        st.session_state.editor_ponto_token = None
        formulario_ponto()
    with st.expander('Importar pontos UTM (CSV)', expanded=False):
        st.caption('Formato: codigo;local;E (m);N (m) · UTM zona 22 Sul, SIRGAS 2000.')
        versao = versao_formulario_admin()
        arquivo = st.file_uploader('Arquivo CSV', type=['csv'], key=f'importar_utm_csv_{versao}')
        if arquivo is not None:
            try:
                dados_importar = ler_csv_utm(arquivo)
                st.dataframe(dados_importar.rename(columns={
                    'codigo':'Código', 'local':'Local', 'e':'E (m)', 'n':'N (m)',
                    'latitude':'Latitude', 'longitude':'Longitude',
                }), hide_index=True, use_container_width=True)
                st.caption(f'{len(dados_importar)} pontos no arquivo. Códigos já existentes serão ignorados.')
                confirmacao = st.checkbox('Conferi os pontos e o sistema de coordenadas',
                                           key=f'confirmar_importacao_utm_{versao}')
                if st.button('Importar pontos', type='primary', disabled=not confirmacao,
                             key=f'botao_importar_utm_{versao}'):
                    adicionados, ignorados = db.importar_pontos_lote(dados_importar.to_dict('records'))
                    concluir_salvamento(f'{adicionados} pontos importados; '
                                         f'{ignorados} códigos já existentes ignorados.')
            except (ValueError, KeyError) as exc:
                st.error(str(exc))
    busca, incl = st.columns([3, 1], vertical_alignment="bottom")
    texto = busca.text_input("Pesquisar ponto", placeholder="Código ou local", label_visibility="collapsed", key=chave_formulario_admin("admin_ponto_busca"))
    ver_inativos = incl.checkbox("Exibir arquivados", value=False, key=chave_formulario_admin("admin_ponto_inativos"))
    exibidos = pontos.copy()
    if not ver_inativos:
        exibidos = exibidos[exibidos["ativo"] == 1]
    if texto.strip():
        exibidos = exibidos[exibidos["codigo"].str.contains(texto, case=False, na=False, regex=False) |
                            exibidos["local"].str.contains(texto, case=False, na=False, regex=False)]
    if exibidos.empty:
        st.info("Não foram encontrados pontos com esses filtros.")
        return
    with st.container(border=True):
        h1, h2, h3, h4 = st.columns([1, 4, 1, 2])
        h1.caption("CÓDIGO")
        h2.caption("LOCAL")
        h3.caption("ESTADO")
        h4.caption("AÇÕES")
        st.divider()
        for _, r in exibidos.iterrows():
            a, b, c, d = st.columns([1, 4, 1, 2], vertical_alignment="center")
            a.markdown(f'**{txt(r["codigo"])}**', unsafe_allow_html=True)
            b.write(r["local"])
            c.caption("Ativo" if bool(r["ativo"]) else "Arquivado")
            e1, e2 = d.columns(2)
            if e1.button("Editar", key=f"editar_ponto_{r['id']}", use_container_width=True):
                st.session_state.editor_ponto_token = None
                formulario_ponto(r)
            if e2.button("Reativar" if not bool(r["ativo"]) else "Arquivar",
                         key=f"arquivar_ponto_{r['id']}", use_container_width=True):
                confirmar_arquivamento("ponto", int(r["id"]), str(r["local"]), not bool(r["ativo"]))
            st.divider()


def admin_parametros(parametros):
    st.title("Parâmetros ambientais")
    with st.expander("Título da referência normativa do relatório", expanded=False):
        st.caption("Este título identifica a norma nos resumos e nas exportações. "
                   "Os limites de cada parâmetro continuam sendo configurados e validados individualmente.")
        with st.form(chave_formulario_admin("form_titulo_referencia_normativa")):
            titulo_atual = buscar_titulo_referencia_seguro()
            titulo_novo = st.text_input("Referência para os relatórios", value=titulo_atual,
                                       max_chars=250, key=chave_formulario_admin("admin_param_titulo"))
            if st.form_submit_button("Salvar título da referência", type="primary"):
                try:
                    salvar_titulo_referencia_seguro(titulo_novo)
                    concluir_salvamento("Título salvo com sucesso.")
                except ValueError as exc:
                    st.error(str(exc))
    col_t, col_b = st.columns([3, 1], vertical_alignment="center")
    with col_t:
        titulo_secao("Parâmetros cadastrados")
    if col_b.button("+ Novo parâmetro", type="primary", use_container_width=True):
        formulario_parametro()
    busca, inativos = st.columns([3, 1], vertical_alignment="bottom")
    termo = busca.text_input("Buscar parâmetro", placeholder="Nome do parâmetro", label_visibility="collapsed", key=chave_formulario_admin("admin_param_busca"))
    ver_inativos = inativos.checkbox("Exibir arquivados", key=chave_formulario_admin("admin_param_inativos"))
    exibidos = parametros.copy()
    if not ver_inativos:
        exibidos = exibidos[exibidos["ativo"] == 1]
    if termo.strip():
        exibidos = exibidos[exibidos["nome"].str.contains(termo, case=False, na=False, regex=False)]
    if exibidos.empty:
        st.info("Nenhum parâmetro encontrado.")
        return
    with st.container(border=True):
        cab = st.columns([3, 1.1, 2.2, 1.2, 2])
        for col, rot in zip(cab, ["PARÂMETRO", "UNIDADE", "REFERÊNCIA", "VALIDAÇÃO", "AÇÕES"]):
            col.caption(rot)
        st.divider()
        for _, r in exibidos.iterrows():
            a, b, c, d, e = st.columns([3, 1.1, 2.2, 1.2, 2], vertical_alignment="center")
            a.write(r["nome"])
            b.caption(r["unidade"])
            c.caption(resumo_referencia(r))
            d.caption("Revisada" if bool(r["referencia_validada"]) else "Pendente")
            q1, q2 = e.columns(2)
            if q1.button("Editar", key=f"editar_param_{r['id']}", use_container_width=True):
                formulario_parametro(r)
            if q2.button("Reativar" if not bool(r["ativo"]) else "Arquivar",
                         key=f"arquivar_param_{r['id']}", use_container_width=True):
                confirmar_arquivamento("parametro", int(r["id"]), str(r["nome"]), not bool(r["ativo"]))
            st.divider()
    st.info("Valores importados do antigo campo 'limite_legal' permanecem pendentes até revisão da norma, "
            "classe do corpo hídrico e demais condições de aplicabilidade.")


def admin_iqa(faixas, config, parametros):
    st.title("Configuração do IQA")
    with st.container(border=True):
        titulo_secao("Faixas de qualidade")
        with st.form(chave_formulario_admin("form_faixas_iqa")):
            hdr = st.columns([2, 1, 1])
            for col, texto_ in zip(hdr, ["CATEGORIA", "MÍNIMO", "MÁXIMO"]):
                col.caption(texto_)
            alteradas = []
            for _, r in faixas.iterrows():
                c1, c2, c3 = st.columns([2, 1, 1], vertical_alignment="center")
                c1.markdown(
                    f'<span class="status" style="color:{txt(r["cor_texto"])};'
                    f'background:{txt(r["cor_bg"])}">{txt(r["nome"])}</span>',
                    unsafe_allow_html=True,
                )
                minimo = c2.number_input(
                    f"Mínimo {r['nome']}", value=float(r["valor_min"]),
                    min_value=0.0, max_value=100.0, step=1.0,
                    label_visibility="collapsed", key=chave_formulario_admin(f"faixa_min_{r['id']}"),
                )
                maximo = c3.number_input(
                    f"Máximo {r['nome']}", value=float(r["valor_max"]),
                    min_value=0.0, max_value=100.0, step=1.0,
                    label_visibility="collapsed", key=chave_formulario_admin(f"faixa_max_{r['id']}"),
                )
                alteradas.append({"id": int(r["id"]), "min": minimo, "max": maximo})
            if st.form_submit_button("Salvar todas as faixas", type="primary"):
                try:
                    db.atualizar_faixas_iqa(alteradas)
                    concluir_salvamento("Faixas do IQA atualizadas.")
                except ValueError as e:
                    st.error(str(e))


def painel_admin():
    limpar_pagina_apos_salvar()
    with st.sidebar:
        try:
            st.download_button("Baixar backup do banco", data=db.baixar_backup(),
                               file_name="aguas_ufsc.db", mime="application/octet-stream")
        except db.ErroPersistencia as exc:
            st.error(str(exc))
    pontos = db.buscar_pontos()
    parametros = db.buscar_parametros()
    coletas = db.buscar_coletas()
    amostras = db.buscar_amostras()
    faixas = db.buscar_faixas_iqa()
    config = db.buscar_configuracao_iqa()
    opcoes = ["Visão geral", "Coletas e análises", "Pontos de coleta", "Parâmetros ambientais", "Configuração do IQA"]
    with st.sidebar:
        st.markdown(marca(), unsafe_allow_html=True)
        st.divider()
        st.caption("MENU ADMINISTRATIVO")
        st.radio("Navegação", opcoes, label_visibility="collapsed", key="admin_menu")
        st.divider()
        if st.button("Ver painel público", use_container_width=True):
            st.session_state.pagina = "publico"
            st.rerun()
        if st.button("Sair da administração", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.pagina = "publico"
            st.rerun()
        st.caption("UFSC · Gestão Ambiental")
    if "mensagem" in st.session_state:
        st.toast(st.session_state.pop("mensagem"))
    menu = st.session_state.admin_menu
    if menu == opcoes[0]:
        admin_visao_geral(pontos, parametros, coletas, amostras)
    elif menu == opcoes[1]:
        admin_coletas(pontos, parametros, amostras, coletas)
    elif menu == opcoes[2]:
        admin_pontos(pontos)
    elif menu == opcoes[3]:
        admin_parametros(parametros)
    elif menu == opcoes[4]:
        admin_iqa(faixas, config, parametros)


# Inicialize a sessão antes de acessar suas propriedades. No Streamlit,
# cada navegador/sessão começa com um estado independente.
VALORES_INICIAIS_SESSAO = {
    "pagina": "publico",
    "autenticado": False,
    "admin_menu": "Visão geral",
    "falhas_login": 0,
    "bloqueio_ate": 0.0,
}
for chave, padrao in VALORES_INICIAIS_SESSAO.items():
    if chave not in st.session_state:
        st.session_state[chave] = padrao


# Proteção de rota: jamais renderizar a administração sem autenticação.
if st.session_state.pagina == "admin" and not st.session_state.autenticado:
    st.session_state.pagina = "login"

if st.session_state.pagina == "admin" and st.session_state.autenticado:
    painel_admin()
elif st.session_state.pagina == "login":
    tela_login()
else:
    painel_publico()
