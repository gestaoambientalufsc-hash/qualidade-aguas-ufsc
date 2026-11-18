"""Portal público + administração de qualidade da água — UFSC.

Iniciar: streamlit run app.py
Senha administrativa padrão: 1234
"""
from __future__ import annotations

import hmac
import html
import os
import time
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
.brand {display:flex;align-items:center;gap:12px;}
.brand-icon {width:42px;height:42px;display:grid;place-items:center;background:#EAF4F4;
 border-radius:11px;color:#167D86;flex-shrink:0;}
.brand-title {font-size:15px;font-weight:700;color:#17324D;line-height:1.25;}
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
 .brand-title {font-size:13px;}
}
</style>
""", unsafe_allow_html=True)


def txt(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def titulo_secao(titulo, subtitulo=""):
    st.markdown(f'<div class="section-title">{txt(titulo)}</div>', unsafe_allow_html=True)
    if subtitulo:
        st.markdown(f'<div class="section-sub">{txt(subtitulo)}</div>', unsafe_allow_html=True)


def marca():
    return """<div class="brand"><div class="brand-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 22a8 8 0 0 0 8-8c0-5-8-12-8-12S4 9 4 14a8 8 0 0 0 8 8Z"/>
      <path d="M8 15a4 4 0 0 0 4 4"/></svg>
      </div><div><div class="brand-title">Monitoramento das Águas</div>
      <div class="brand-sub">UFSC · Gestão Ambiental</div></div></div>"""


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


def grafico_temporal(dados, parametro, config_param):
    if dados.empty:
        st.info("Ainda não existem resultados para este parâmetro no ponto selecionado.")
        return
    dados = dados.dropna(subset=["valor", "data_amostra"]).sort_values(["data_amostra", "id"]).copy()
    if dados.empty:
        st.info("Sem medições registradas para essa seleção.")
        return
    dados["dia"] = pd.to_datetime(dados["data_amostra"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dados["dia"], y=dados["valor"], mode="markers", name="Medição registrada",
        marker=dict(size=11, color=TEAL, line=dict(color="white", width=1.5)),
        hovertemplate="%{x|%d/%m/%Y}<br><b>%{y:.5f}</b><extra></extra>",
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
    fig.update_layout(
        height=315, paper_bgcolor="white", plot_bgcolor="white",
        margin=dict(l=8, r=8, t=20, b=10),
        xaxis=dict(showgrid=False, title="", tickformat="%d/%m/%y", type="date"),
        yaxis=dict(gridcolor="#EEF3F5", zeroline=False,
                   title="" if config_param["unidade"] == "-" else config_param["unidade"]),
        hovermode="closest", showlegend=False,
        font=dict(family="Montserrat", color=NAVY, size=11),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def grafico_iqa(dados, faixas):
    if dados.empty:
        st.info("Ainda não há medições de IQA informadas para este ponto.")
        return
    dados = dados.sort_values(["data_amostra", "id"]).copy()
    dados["dia"] = pd.to_datetime(dados["data_amostra"])
    fig = go.Figure()
    for _, fx in faixas.iterrows():
        fig.add_hrect(y0=float(fx["valor_min"]), y1=float(fx["valor_max"]),
                      fillcolor=fx["cor_grafico"], opacity=1, layer="below", line_width=0)
    fig.add_trace(go.Scatter(x=dados["dia"], y=dados["valor"], name="IQA informado",
                             mode="markers", marker=dict(size=11, color="#10664D"),
                             hovertemplate="%{x|%d/%m/%Y}<br>IQA: %{y:.1f}<extra></extra>"))
    fig.update_layout(height=315, plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=8, r=8, t=20, b=10),
                      xaxis=dict(showgrid=False, title="", tickformat="%d/%m/%y"),
                      yaxis=dict(range=[0, 100], gridcolor="#EEF3F5", title="IQA (0–100)"),
                      showlegend=False, font=dict(family="Montserrat", color=NAVY, size=11))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    legenda = " · ".join(f"{fx.nome}: {formatar_valor(fx.valor_min)}–{formatar_valor(fx.valor_max)}"
                        for fx in faixas.itertuples())
    st.caption(legenda)


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

    # Exibir no mapa apenas pontos com medições registradas.
    ids_com_medicao = set(resultados["ponto_id"].dropna().astype(int)) if not resultados.empty else set()
    pontos_mapa = pontos[pontos["id"].isin(ids_com_medicao)].copy()
    if pontos_mapa.empty:
        titulo_secao("Mapa dos Pontos")
        st.info("Ainda não há pontos com medições registradas.")
        return

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
    if st.session_state.get("editor_ponto_token") != token:
        st.session_state.editor_ponto_token = token
        st.session_state.editor_lat = float(ponto["latitude"]) if ponto is not None and pd.notna(ponto["latitude"]) else -27.601
        st.session_state.editor_lon = float(ponto["longitude"]) if ponto is not None and pd.notna(ponto["longitude"]) else -48.518
    st.caption("Selecione a localização no mapa; latitude e longitude são preenchidas automaticamente. Também é possível digitá-las.")
    mp = folium.Map(location=[st.session_state.editor_lat, st.session_state.editor_lon],
                    zoom_start=15, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles=f"https://tiles.stadiamaps.com/tiles/alidade_smooth/{{z}}/{{x}}/{{y}}{{r}}.png?api_key={MAP_API_KEY}",
        attr='&copy; <a href="https://stadiamaps.com/">Stadia Maps</a>, &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a>, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        name="Base"
    ).add_to(mp)
    folium.Marker([st.session_state.editor_lat, st.session_state.editor_lon], tooltip="Posição atual").add_to(mp)
    resultado = st_folium(mp, height=230, use_container_width=True, key=f"editor_ponto_mapa_{token}",
                         returned_objects=["last_clicked"])
    if resultado and resultado.get("last_clicked"):
        p = resultado["last_clicked"]
        registro = (round(float(p["lat"]), 6), round(float(p["lng"]), 6))
        if registro != st.session_state.get("editor_ponto_ultimo_clique"):
            st.session_state.editor_lat, st.session_state.editor_lon = registro
            st.session_state.editor_ponto_ultimo_clique = registro
    with st.form("form_ponto_modal"):
        c1, c2 = st.columns([1, 2])
        codigo = c1.text_input("Código *", value=str(ponto["codigo"]) if ponto is not None else "")
        local = c2.text_input("Nome do local *", value=str(ponto["local"]) if ponto is not None else "")
        c3, c4 = st.columns(2)
        lat = c3.number_input("Latitude", min_value=-90.0, max_value=90.0, step=0.000001,
                              format="%.6f", key="editor_lat")
        lon = c4.number_input("Longitude", min_value=-180.0, max_value=180.0, step=0.000001,
                              format="%.6f", key="editor_lon")
        salvar = st.form_submit_button("Salvar ponto", type="primary", use_container_width=True)
    if salvar:
        try:
            if ponto is None:
                db.inserir_ponto(codigo, local, lat, lon)
            else:
                db.atualizar_ponto(int(ponto["id"]), codigo, local, lat, lon)
            st.session_state.editor_ponto_token = ""
            st.session_state.editor_ponto_ultimo_clique = None
            st.session_state.mensagem = "Ponto salvo com sucesso."
            st.rerun()
        except ValueError as e:
            st.error(str(e))


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
    if acao1.button("+ Registrar coleta", type="primary", use_container_width=True):
        st.session_state.admin_menu = "Coletas e análises"
        st.rerun()
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
