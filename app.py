"""Portal público + administração de qualidade da água — UFSC.

Iniciar: streamlit run app.py
Senha administrativa padrão: 1234
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
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

import database as db

st.set_page_config(
    page_title="Monitoramento das Águas | UFSC",
    layout="wide",
    initial_sidebar_state="collapsed",
)
db.inicializar_banco()

# -----------------------------------------------------------------------------
# Design system — aparência institucional, contraste e componentes compactos.
# -----------------------------------------------------------------------------
NAVY = "#17324D"
TEAL = "#167D86"
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
  padding:16px 18px; min-height:112px;}
[data-testid="stMetricLabel"] p {color:#64748B !important; font-size:.76rem !important; font-weight:600;}
[data-testid="stMetricValue"] {color:#17324D !important; font-size:1.75rem !important;}
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
 border-radius:9px !important; font-weight:600 !important; min-height:39px;
 border-color:#DCE5EA !important;}
button[kind="primary"] {background:#167D86 !important; border-color:#167D86 !important; color:white !important;}
button[kind="primary"]:hover {background:#12666E !important;}
button[kind="primaryFormSubmit"] {background:#167D86 !important; color:white !important;}
[data-baseweb="input"] > div, [data-baseweb="select"] > div,
[data-testid="stDateInput"] input, [data-testid="stTextArea"] textarea {
  border-radius:8px !important; border-color:#DCE5EA !important;}
[data-testid="stWidgetLabel"] p {font-size:.84rem !important; color:#344B5B !important; font-weight:500;}
[data-testid="stCaptionContainer"] p {color:#64748B !important; line-height:1.5;}
[data-testid="stRadio"] [role="radiogroup"] {gap:.25rem;}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  padding:.55rem .70rem; border-radius:9px; transition:background .12s;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
  background:#EAF4F4; color:#10656D; font-weight:700;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {background:#F1F6F7;}
[data-testid="stDataFrame"] {border-radius:10px; overflow:hidden;}
[data-testid="stPlotlyChart"] {border-radius:10px;}
section[data-testid="stSidebar"] [data-testid="stElementContainer"] {margin-bottom:.05rem;}
.brand {display:flex;align-items:center;gap:16px;}
.brand-logo {width:88px;height:88px;object-fit:contain;flex-shrink:0;border-radius:5px;}
.brand-icon {width:42px;height:42px;display:grid;place-items:center;background:#EAF4F4;
 border-radius:11px;color:#167D86;flex-shrink:0;}
.brand-title {font-size:20px;font-weight:700;color:#17324D;line-height:1.25;}
.brand-sub {font-size:11px;color:#64748B;margin-top:4px;}
.eyebrow {font-size:.73rem;letter-spacing:.07em;text-transform:uppercase;
 color:#167D86;font-weight:700;margin-bottom:6px;}
.lead {font-size:.88rem;color:#64748B;max-width:820px;margin:0 0 8px;}
.section-title {font-size:1.03rem;font-weight:700;color:#17324D;margin:1px 0 2px;}
.section-sub {font-size:.80rem;color:#64748B;margin:0 0 10px;}
.rule {height:1px;background:#E2E8EE;margin:12px 0;}
.status {display:inline-block;padding:5px 10px;border-radius:20px;font-size:.76rem;
 font-weight:700;border:1px solid currentColor;}
.small-note {font-size:.77rem;color:#64748B;line-height:1.6;}
.point-code {display:inline-block;background:#EAF4F4;color:#116C73;font-weight:700;
 padding:4px 8px;border-radius:6px;font-size:.75rem;}
.section-box {border:1px solid #E2E8EE;background:#FFF;border-radius:12px;padding:18px;}
[data-testid="stAlert"] {border-radius:9px;}
[class*="st-key-sticky_coleta_"] {position:sticky;bottom:8px;z-index:20;
 background:#fff;border-radius:12px;box-shadow:0 8px 30px rgba(23,50,77,.10);}
@media (max-width:700px) {
 [data-testid="stMainBlockContainer"] {padding-left:1rem;padding-right:1rem;}
 h1 {font-size:1.35rem !important;}
 [data-testid="stMetric"] {min-height:92px;padding:12px;}
 [data-testid="stMetricValue"] {font-size:1.33rem !important;}
 .brand-title {font-size:16px;}
 .brand-logo {width:68px;height:68px;}
}
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
    return (
        '<div class="brand">'
        f'<img class="brand-logo" src="{LOGO_GESTAO_AMBIENTAL}" alt="Gestão Ambiental UFSC">'
        '<div><div class="brand-title">Gestão das Águas</div>'
        '<div class="brand-sub">UFSC · Gestão Ambiental</div></div></div>'
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
        return pd.to_datetime(dia).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
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


def cartografia(pontos, foco_id=None, selecionar=True, chave="mapa_publico", altura=350):
    validos = pontos.dropna(subset=["latitude", "longitude"]).copy()
    if validos.empty:
        st.info("Os pontos ainda não possuem coordenadas válidas.")
        return None
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
        folium.CircleMarker(
            location=[float(item["latitude"]), float(item["longitude"])],
            radius=10 if item_id == foco_id else 8,
            color="#FFFFFF", weight=2, fill=True,
            fill_color=TEAL if item_id == foco_id else "#428BA2", fill_opacity=1,
            tooltip=folium.Tooltip(legenda),
            popup=folium.Popup(f"<strong>{txt(item['codigo'])}</strong><br>{txt(item['local'])}", max_width=300),
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


def _layout_eixo_coletas(fig, datas, altura=315, eixo_y=""):
    # Categoria preserva o ordenamento cronológico sem inserir dias intermediários.
    fig.update_layout(
        height=altura, paper_bgcolor="white", plot_bgcolor="white",
        margin=dict(l=8, r=8, t=20, b=12),
        xaxis=dict(type="category", categoryorder="array", categoryarray=datas,
                   tickmode="array", tickvals=datas, ticktext=datas,
                   showgrid=False, title="", automargin=True,
                   tickangle=-30 if len(datas) > 7 else 0),
        yaxis=dict(gridcolor="#EEF3F5", zeroline=False, title=eixo_y),
        hovermode="closest", showlegend=False,
        font=dict(family="Montserrat", color=NAVY, size=11),
    )


def grafico_temporal(dados, parametro, config_param):
    if dados.empty:
        st.info("Ainda não existem resultados para este parâmetro no ponto selecionado.")
        return
    dados, datas = _preparar_serie_grafico(dados)
    if dados.empty:
        st.info("Sem medições registradas para essa seleção.")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dados["data_rotulo"], y=dados["valor"], mode="lines+markers",
        name="Medições", connectgaps=False,
        line=dict(color=TEAL, width=2.5),
        marker=dict(size=11, color=TEAL, line=dict(color="white", width=1.5)),
        customdata=dados["dia"].dt.strftime("%d/%m/%Y"),
        hovertemplate="%{customdata}<br><b>%{y:.5f}</b><extra></extra>",
    ))
    if bool(config_param.get("referencia_validada", 0)):
        tipo = config_param["tipo_limite"]
        for chave, rotulo in (("limite_min", "Referência mínima"), ("limite_max", "Referência máxima")):
            if ((chave == "limite_min" and tipo in ("minimo", "intervalo")) or
                    (chave == "limite_max" and tipo in ("maximo", "intervalo"))):
                valor = config_param[chave]
                if pd.notna(valor):
                    fig.add_hline(y=float(valor), line_dash="dash", line_color="#D97736",
                                  annotation_text=rotulo, annotation_position="top left")
    unidade = "" if config_param["unidade"] == "-" else config_param["unidade"]
    _layout_eixo_coletas(fig, datas, eixo_y=unidade)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def grafico_iqa(dados, faixas):
    if dados.empty:
        st.info("Ainda não há medições de IQA informadas para este ponto.")
        return
    dados, datas = _preparar_serie_grafico(dados)
    if dados.empty:
        st.info("Ainda não há medições de IQA válidas para este ponto.")
        return

    cores, categorias = [], []
    for valor in dados["valor"]:
        faixa = classificar_iqa(valor, faixas)
        cores.append(str(faixa["cor_texto"]) if faixa is not None else "#64748B")
        categorias.append(str(faixa["nome"]) if faixa is not None else "Indefinida")

    fig = go.Figure()
    for _, fx in faixas.iterrows():
        fig.add_hrect(y0=float(fx["valor_min"]), y1=float(fx["valor_max"]),
                      fillcolor=fx["cor_grafico"], opacity=1,
                      layer="below", line_width=0)
    fig.add_trace(go.Scatter(
        x=dados["data_rotulo"], y=dados["valor"], mode="lines+markers",
        name="IQA", connectgaps=False,
        line=dict(color="#44657A", width=2.5),
        marker=dict(size=13, color=cores, line=dict(color="white", width=2)),
        customdata=list(zip(dados["data_rotulo"], categorias)),
        hovertemplate="%{customdata[0]}<br>IQA: <b>%{y:.1f}</b><br>%{customdata[1]}<extra></extra>",
    ))
    _layout_eixo_coletas(fig, datas, eixo_y="IQA (0–100)")
    fig.update_yaxes(range=[0, 100])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    # Legenda das cores dos marcadores, derivada das faixas configuradas.
    itens = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;white-space:nowrap">'
        f'<span style="width:9px;height:9px;background:{txt(fx.cor_texto)};'
        f'border-radius:50%;display:inline-block"></span>{txt(fx.nome)}</span>'
        for fx in faixas.sort_values("valor_min").itertuples()
    )
    st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:12px;'
                f'font-size:12px;color:#64748B;margin:2px 0 8px">{itens}</div>',
                unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Sessão, acesso e navegação.
# -----------------------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "pagina" not in st.session_state:
    st.session_state.pagina = "publico"
if "admin_menu" not in st.session_state:
    st.session_state.admin_menu = "Visão geral"
if "falhas_login" not in st.session_state:
    st.session_state.falhas_login = 0
if "bloqueio_ate" not in st.session_state:
    st.session_state.bloqueio_ate = 0.0


def senha_admin():
    senha = os.environ.get("ADMIN_PASSWORD", "")
    if senha:
        return senha
    try:
        senha_secret = st.secrets.get("ADMIN_PASSWORD", "")
        if senha_secret:
            return senha_secret
    except (FileNotFoundError, KeyError):
        pass
    return "1234"


def cabecalho_publico():
    # A barra superior flutuante do Streamlit não pode cobrir o botão.
    st.markdown('<div class="public-header-clearance"></div>', unsafe_allow_html=True)
    esquerda, direita = st.columns([5, 1.4], vertical_alignment="center")
    with esquerda:
        st.markdown(marca(), unsafe_allow_html=True)
    with direita:
        if st.button("Administração", key="entrar_admin", use_container_width=True):
            st.session_state.pagina = "login" if not st.session_state.autenticado else "admin"
            st.rerun()
    st.divider()


def tela_login():
    cabecalho_login = st.columns([4, 1])[0]
    with cabecalho_login:
        st.markdown(marca(), unsafe_allow_html=True)
    st.divider()
    esq, meio, dir_ = st.columns([1, 1.35, 1])
    with meio:
        with st.container(border=True):
            st.subheader("Acesso administrativo")
            senha_config = senha_admin()
            restante = max(0, int(st.session_state.bloqueio_ate - time.monotonic()))
            if restante:
                st.warning(f"Tente novamente em {restante} segundos.")
            with st.form("login_admin"):
                senha_informada = st.text_input("Senha", type="password", autocomplete="current-password")
                enviar = st.form_submit_button("Entrar", type="primary", use_container_width=True,
                                               disabled=restante > 0)
            if enviar:
                if hmac.compare_digest(senha_informada, senha_config):
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
# Painel público.
# -----------------------------------------------------------------------------
def painel_publico():
    pontos = db.buscar_pontos(ativos=True)
    parametros = db.buscar_parametros(ativos=True)
    resultados = db.buscar_coletas()
    faixas = db.buscar_faixas_iqa()

    cabecalho_publico()
    st.markdown('<div class="eyebrow">Monitoramento ambiental · Campus Florianópolis</div>', unsafe_allow_html=True)
    st.title("Qualidade da água nos córregos da UFSC")
    st.markdown('<div class="lead">Consulte os pontos de coleta e acompanhe a evolução dos indicadores.</div>', unsafe_allow_html=True)
    st.write("")

    pontos_com_dados = resultados["ponto_id"].nunique() if not resultados.empty else 0
    ultimo_dia = formatar_data(resultados["data_amostra"].max()) if not resultados.empty else "—"
    a, b, c, d = st.columns(4)
    a.metric("Pontos cadastrados", len(pontos))
    b.metric("Pontos com medições", pontos_com_dados)
    c.metric("Resultados", len(resultados))
    d.metric("Última coleta", ultimo_dia)

    st.write("")
    if pontos.empty:
        st.info("Nenhum ponto ativo cadastrado.")
        return

    # Exibir todos os pontos ativos, inclusive os recém-importados sem coletas.
    pontos_mapa = pontos.copy()

    ids = pontos_mapa["id"].astype(int).tolist()
    nomes_pontos = {int(r["id"]): rotulo_ponto(r) for _, r in pontos_mapa.iterrows()}
    if st.session_state.get("ponto_publico") not in ids:
        st.session_state.ponto_publico = ids[0]

    titulo_secao("Mapa dos Pontos")
    escolhido_mapa = cartografia(
        pontos_mapa, foco_id=st.session_state.ponto_publico,
        chave="mapa_publico", altura=430,
    )
    if escolhido_mapa is not None and escolhido_mapa != st.session_state.ponto_publico:
        st.session_state.ponto_publico = escolhido_mapa
        st.rerun()

    st.write("")
    titulo_secao("Evolução dos indicadores")
    with st.container(border=True):
        # Filtros em uma linha; somente datas e parâmetros com registros reais.
        c_ponto, c_dia, c_parametro = st.columns([1.3, 1, 1.6], gap="small")
        with c_ponto:
            st.selectbox("Ponto de coleta", ids, format_func=lambda pid: nomes_pontos[pid], key="ponto_publico")
        ponto_id = st.session_state.ponto_publico
        dados_pt = resultados[resultados["ponto_id"] == ponto_id].copy()
        dados_pt["dia_data"] = pd.to_datetime(dados_pt["data_amostra"], errors="coerce").dt.date

        # Definir as opções a partir das medições disponíveis; não gerar datas artificiais.
        datas = sorted(d for d in dados_pt["dia_data"].dropna().unique())
        opcoes_dia = [None] + datas
        with c_dia:
            dia_sel = st.selectbox("Dia da coleta", opcoes_dia,
                                   format_func=lambda d: "Todos os dias" if d is None else d.strftime("%d/%m/%Y"),
                                   key="dia_publico")
        dados_dia = dados_pt if dia_sel is None else dados_pt[dados_pt["dia_data"] == dia_sel]

        outros = parametros[~parametros["nome"].apply(somente_iqa)]
        ids_marcados = set(dados_dia["param_id"].dropna().astype(int)) if not dados_dia.empty else set()
        disponiveis = outros[outros["id"].isin(ids_marcados)]
        param_ids = disponiveis["id"].astype(int).tolist()
        with c_parametro:
            if param_ids:
                if st.session_state.get("parametro_publico") not in param_ids:
                    st.session_state.parametro_publico = param_ids[0]
                st.selectbox("Parâmetro", param_ids,
                             format_func=lambda pid: disponiveis.loc[disponiveis["id"] == pid, "nome"].iloc[0],
                             key="parametro_publico")
            else:
                st.selectbox("Parâmetro", ["Sem medições"], disabled=True, key="parametro_sem_medicoes")

        if param_ids:
            param = disponiveis.loc[disponiveis["id"] == st.session_state.parametro_publico].iloc[0]
            serie = dados_dia[dados_dia["param_id"] == st.session_state.parametro_publico]
            grafico_temporal(serie, param["nome"], param)
        else:
            st.info("Nenhum resultado de parâmetro nesta data.")

    # IQA também respeita o ponto e o dia escolhido.
    with st.container(border=True):
        titulo_secao("Histórico do IQA")
        serie_iqa = dados_dia[dados_dia["parametro"].str.startswith("IQA (", na=False)]
        grafico_iqa(serie_iqa, faixas)

    if not resultados.empty:
        exportar = resultados[resultados["ponto_id"] == st.session_state.ponto_publico].copy()
        if dia_sel is not None:
            exportar = exportar[pd.to_datetime(exportar["data_amostra"], errors="coerce").dt.date == dia_sel]
        st.download_button("Baixar histórico (CSV)",
                           exportar.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           "historico_aguas_ufsc.csv", "text/csv", type="secondary")
    st.divider()
    st.caption("UFSC · Gestão Ambiental")


# -----------------------------------------------------------------------------
# Componentes de edição administrativa — modais e confirmações.
# -----------------------------------------------------------------------------
@st.dialog("Cadastrar ou editar ponto", width="large", on_dismiss="rerun")
def formulario_ponto(ponto=None):
    token = f"ponto_{int(ponto['id'])}" if ponto is not None else "ponto_novo"
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
            st.session_state.editor_ponto_token = None
            st.session_state.mensagem = 'Ponto salvo com sucesso.'
            st.rerun()
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
        nome = n1.text_input("Nome *", value=str(param["nome"]) if param is not None else "")
        unidade = n2.text_input("Unidade *", value=str(param["unidade"]) if param is not None else "mg/L")
        tipo = st.selectbox("Tipo de referência", tipo_opcoes,
                            index=tipo_opcoes.index(tipo_atual) if tipo_atual in tipo_opcoes else 0,
                            format_func=lambda v: {"nenhum": "Sem referência", "minimo": "Mínimo",
                                                   "maximo": "Máximo", "intervalo": "Intervalo (mínimo e máximo)"}[v])
        l1, l2 = st.columns(2)
        min_atual = float(param["limite_min"]) if param is not None and pd.notna(param["limite_min"]) else None
        max_atual = float(param["limite_max"]) if param is not None and pd.notna(param["limite_max"]) else None
        minimo = l1.number_input("Valor mínimo", value=min_atual, format="%.5f", step=0.01,
                                 disabled=tipo not in ("minimo", "intervalo"))
        maximo = l2.number_input("Valor máximo", value=max_atual, format="%.5f", step=0.01,
                                 disabled=tipo not in ("maximo", "intervalo"))
        norma = st.text_input("Base normativa (norma, artigo ou resolução)",
                              value=str(param["base_normativa"]) if param is not None else "")
        aplica = st.text_input("Aplicabilidade (classe, enquadramento, condições)",
                               value=str(param["aplicabilidade"]) if param is not None else "")
        valida = st.checkbox("Referência revisada e validada para o contexto do monitoramento",
                             value=bool(param["referencia_validada"]) if param is not None else False)
        st.divider()
        compoe = st.checkbox("Este parâmetro participa da metodologia do IQA",
                             value=bool(param["compoe_iqa"]) if param is not None else False)
        i1, i2 = st.columns([1, 2])
        peso = i1.number_input("Peso do IQA (documental)", min_value=0.000001,
                               value=float(param["peso_iqa"]) if param is not None and pd.notna(param["peso_iqa"]) else None,
                               format="%.5f", disabled=not compoe)
        curva = i2.text_input("Curva/fonte do subíndice", value=str(param["curva_iqa"]) if param is not None else "",
                              disabled=not compoe)
        st.caption("Pesos e curvas são documentais: este projeto não calcula automaticamente o IQA.")
        salvar = st.button("Salvar parâmetro", type="primary", use_container_width=True,
                           key="salvar_parametro_modal")
    if salvar:
        try:
            db.salvar_parametro(None if param is None else int(param["id"]), nome, unidade, tipo,
                               minimo, maximo, norma, aplica, valida, compoe, peso, curva)
            st.session_state.mensagem = "Parâmetro salvo com sucesso."
            st.rerun()
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
        if tipo == "ponto":
            db.alterar_status_ponto(identificador, ativar)
        else:
            db.alterar_status_parametro(identificador, ativar)
        st.session_state.mensagem = "Cadastro atualizado."
        st.rerun()


@st.dialog("Confirmar exclusão da coleta", on_dismiss="rerun")
def confirmar_exclusao_amostra(amostra_id):
    st.error("Esta operação remove permanentemente a amostra e todos os valores associados. Não poderá ser desfeita.")
    confirmar = st.checkbox("Entendi que esta exclusão é permanente.")
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", use_container_width=True):
        st.rerun()
    if c2.button("Excluir coleta", type="primary", disabled=not confirmar, use_container_width=True):
        db.excluir_amostra(amostra_id)
        st.session_state.mensagem = "Coleta excluída."
        st.rerun()


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


def formulario_amostra(pontos, parametros, amostra=None, dialogo=False):
    """Formulário com atualização responsiva dos campos e conferência pré-salvamento."""
    if pontos.empty or parametros.empty:
        st.info("Cadastre ao menos um ponto e um parâmetro ativos para registrar uma coleta.")
        return
    amostra_id = int(amostra["id"]) if amostra is not None else None
    prefixo = f"edit_{amostra_id}" if amostra_id else "nova"
    ids_pt = pontos["id"].astype(int).tolist()
    mapa_pt = {int(p["id"]): f"{p['codigo']} · {p['local']}" for _, p in pontos.iterrows()}
    ponto_padrao = int(amostra["ponto_id"]) if amostra is not None else ids_pt[0]
    if ponto_padrao not in ids_pt:
        ponto_padrao = ids_pt[0]
    with st.container(border=True):
        titulo_secao("1. Identificação da amostra")
        p1, p2 = st.columns([2, 1])
        ponto = p1.selectbox("Ponto de coleta *", ids_pt, index=ids_pt.index(ponto_padrao),
                             format_func=lambda i: mapa_pt[i], key=f"{prefixo}_ponto")
        dia = p2.date_input("Data da coleta *", value=pd.to_datetime(amostra["data_amostra"]).date()
                            if amostra is not None else date.today(), max_value=date.today(),
                            format="DD/MM/YYYY", key=f"{prefixo}_data")
    duplicadas = db.buscar_duplicadas(ponto, dia, amostra_id)
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
    parametros_analise = parametros[~parametros["nome"].apply(somente_iqa)]
    valores = {}
    with st.container(border=True):
        titulo_secao("2. Resultados da análise")
        lista = list(parametros_analise.iterrows())
        for i in range(0, len(lista), 2):
            cols = st.columns(2)
            for indice_coluna, (_, par) in enumerate(lista[i:i + 2]):
                param_id = int(par["id"])
                unidade = "" if par["unidade"] == "-" else f" · {par['unidade']}"
                with cols[indice_coluna]:
                    valores[param_id] = st.number_input(
                        f"{par['nome']}{unidade}", value=valores_existentes.get(param_id),
                        key=f"{prefixo}_valor_{param_id}", format="%.5f", step=0.00001,
                        placeholder="Não analisado",
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
        st.caption(f"Ponto: {mapa_pt[ponto]} · Data: {formatar_data(dia)} · "
                   f"Resultados informados: {len(preenchidos)}")
        a, b = st.columns([3, 1], vertical_alignment="bottom")
        with a:
            st.caption("Ao salvar, os valores são gravados em uma única transação. Em edições, "
                       "os resultados anteriores desta amostra são substituídos.")
        with b:
            salvar = st.button("Salvar alterações" if amostra_id else "Salvar coleta",
                               type="primary", key=f"{prefixo}_salvar", use_container_width=True)
    if salvar:
        try:
            if duplicadas and not confirmar_mesma_data:
                raise ValueError("Confirme a existência da outra amostra antes de continuar.")
            _validar_resultados_semanticos(parametros, preenchidos)
            db.salvar_amostra(
                ponto, dia, preenchidos,
                identificador=str(amostra["identificador"] or "") if amostra is not None else "",
                observacoes=str(amostra["observacoes"] or "") if amostra is not None else "",
                permitir_mesma_data=confirmar_mesma_data, amostra_id=amostra_id,
            )
            st.session_state.mensagem = "Coleta salva com sucesso."
            # Limpa controles da nova coleta para não reutilizar resultados por acidente.
            if not amostra_id:
                for chave in list(st.session_state.keys()):
                    if chave.startswith("nova_"):
                        del st.session_state[chave]
            st.rerun()
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
        titulo_secao("Coletas recentes")
        if amostras.empty:
            st.info("Ainda não há coletas cadastradas.")
        else:
            resumo = amostras.head(8)[["data_amostra", "codigo", "local", "qtd_parametros"]].copy()
            resumo["data_amostra"] = resumo["data_amostra"].map(formatar_data)
            resumo.columns = ["Data", "Ponto", "Local", "Resultados"]
            st.dataframe(resumo, hide_index=True, use_container_width=True)
    with st.container(border=True):
        titulo_secao("Qualidade e consistência do cadastro")
        pendentes = parametros[(parametros["limite_legal"].notna()) &
                              (parametros["referencia_validada"] != 1)] if not parametros.empty else pd.DataFrame()
        if not pendentes.empty:
            st.warning(f"{len(pendentes)} parâmetros têm referência numérica legada ainda não validada. "
                       "Revise a base normativa e a aplicabilidade antes de publicar conformidade.")
        st.caption("O IQA é um resultado preenchido manualmente. O cadastro de faixas não executa o cálculo do índice.")


def admin_coletas(pontos, parametros, amostras, coletas):
    st.title("Coletas e análises")
    st.caption("Registre medições por ponto e data ou consulte e edite o histórico.")
    tab_nova, tab_historico = st.tabs(["Registrar coleta", "Histórico de coletas"])
    with tab_nova:
        formulario_amostra(pontos[pontos["ativo"] == 1], parametros[parametros["ativo"] == 1])
    with tab_historico:
        titulo_secao("Coletas registradas")
        if amostras.empty:
            st.info("Nenhuma coleta registrada.")
            return
        filtro = st.text_input("Buscar por ponto ou local", placeholder="Pesquisar...", key="busca_amostras")
        visual = amostras.copy()
        if filtro.strip():
            alvo = filtro.lower().strip()
            visual = visual[visual[["codigo", "local"]].fillna("").astype(str)
                            .apply(lambda col: col.str.lower().str.contains(alvo, regex=False)).any(axis=1)]
        tabela = visual[["id", "data_amostra", "codigo", "local", "qtd_parametros"]].copy()
        tabela["data_amostra"] = tabela["data_amostra"].map(formatar_data)
        tabela.columns = ["ID", "Data", "Código", "Local", "Resultados"]
        st.dataframe(tabela, hide_index=True, use_container_width=True)
        if visual.empty:
            return
        ids = visual["id"].astype(int).tolist()
        opcoes = {int(a["id"]): f"{formatar_data(a['data_amostra'])} · {a['codigo']} · {a['local']} · #{a['id']}"
                  for _, a in visual.iterrows()}
        escolha = st.selectbox("Selecione uma coleta para gerenciar", ids, format_func=lambda v: opcoes[v])
        c1, c2, c3 = st.columns([1, 1, 3])
        registro = amostras.loc[amostras["id"] == escolha].iloc[0]
        if c1.button("Editar coleta", use_container_width=True):
            editar_amostra_dialogo(registro, pontos, parametros)
        if c2.button("Excluir coleta", use_container_width=True):
            confirmar_exclusao_amostra(escolha)
        if not coletas.empty:
            st.download_button("Exportar medições (CSV)", coletas.to_csv(index=False, sep=";").encode("utf-8-sig"),
                               "medicoes_aguas_ufsc.csv", "text/csv")


def admin_pontos(pontos):
    st.title("Pontos de coleta")
    st.caption("Cadastre localizações geográficas, edite informações e arquive pontos inativos.")
    col_t, col_b = st.columns([3, 1], vertical_alignment="center")
    with col_t:
        titulo_secao("Pontos cadastrados", f"{len(pontos)} registros no banco de dados")
    if col_b.button("+ Novo ponto", type="primary", use_container_width=True):
        st.session_state.editor_ponto_token = None
        formulario_ponto()
    with st.expander('Importar pontos UTM (CSV)', expanded=False):
        st.caption('Formato: codigo;local;E (m);N (m) · UTM zona 22 Sul, SIRGAS 2000.')
        arquivo = st.file_uploader('Arquivo CSV', type=['csv'], key='importar_utm_csv')
        if arquivo is not None:
            try:
                dados_importar = ler_csv_utm(arquivo)
                st.dataframe(dados_importar.rename(columns={
                    'codigo':'Código', 'local':'Local', 'e':'E (m)', 'n':'N (m)',
                    'latitude':'Latitude', 'longitude':'Longitude',
                }), hide_index=True, use_container_width=True)
                st.caption(f'{len(dados_importar)} pontos no arquivo. Códigos já existentes serão ignorados.')
                confirmacao = st.checkbox('Conferi os pontos e o sistema de coordenadas',
                                           key='confirmar_importacao_utm')
                if st.button('Importar pontos', type='primary', disabled=not confirmacao,
                             key='botao_importar_utm'):
                    adicionados, ignorados = db.importar_pontos_lote(dados_importar.to_dict('records'))
                    st.session_state.mensagem = (f'{adicionados} pontos importados; '
                                                  f'{ignorados} códigos já existentes ignorados.')
                    st.rerun()
            except (ValueError, KeyError) as exc:
                st.error(str(exc))
    busca, incl = st.columns([3, 1], vertical_alignment="bottom")
    texto = busca.text_input("Pesquisar ponto", placeholder="Código ou local", label_visibility="collapsed")
    ver_inativos = incl.checkbox("Exibir arquivados", value=False)
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
    st.caption("Gerencie unidades e referências legais contextualizadas para os parâmetros monitorados.")
    col_t, col_b = st.columns([3, 1], vertical_alignment="center")
    with col_t:
        titulo_secao("Parâmetros cadastrados", "Somente referências revisadas são utilizadas na consulta pública.")
    if col_b.button("+ Novo parâmetro", type="primary", use_container_width=True):
        formulario_parametro()
    busca, inativos = st.columns([3, 1], vertical_alignment="bottom")
    termo = busca.text_input("Buscar parâmetro", placeholder="Nome do parâmetro", label_visibility="collapsed")
    ver_inativos = inativos.checkbox("Exibir arquivados")
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
        with st.form("form_faixas_iqa"):
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
                    label_visibility="collapsed", key=f"faixa_min_{r['id']}",
                )
                maximo = c3.number_input(
                    f"Máximo {r['nome']}", value=float(r["valor_max"]),
                    min_value=0.0, max_value=100.0, step=1.0,
                    label_visibility="collapsed", key=f"faixa_max_{r['id']}",
                )
                alteradas.append({"id": int(r["id"]), "min": minimo, "max": maximo})
            if st.form_submit_button("Salvar todas as faixas", type="primary"):
                try:
                    db.atualizar_faixas_iqa(alteradas)
                    st.session_state.mensagem = "Faixas do IQA atualizadas."
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


def painel_admin():
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


# Proteção de rota: jamais renderizar a administração sem autenticação.
if st.session_state.pagina == "admin" and not st.session_state.autenticado:
    st.session_state.pagina = "login"

if st.session_state.pagina == "admin" and st.session_state.autenticado:
    painel_admin()
elif st.session_state.pagina == "login":
    tela_login()
else:
    painel_publico()
