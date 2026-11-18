import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import database as db

db.inicializar_banco()
st.set_page_config(page_title="Qualidade da Água - UFSC", layout="wide")

# ==========================================
# CSS CUSTOMIZADO (Montserrat, Hierarquia e Zero Espaços Vazios)
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');
    
    * { font-family: 'Montserrat', sans-serif !important; }
    
    /* Remoção dos espaços vazios (barras vermelhas apontadas) */
    .block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; max-width: 95% !important;}
    div[data-testid="stVerticalBlock"] > div { margin-bottom: -10px !important; }
    
    .stApp { background-color: #F8F9FA; }
    
    /* Hierarquia de Fontes */
    h1 { font-size: 28px !important; font-weight: 700 !important; color: #1F2937 !important; margin-bottom: 5px !important;}
    h3 { font-size: 18px !important; font-weight: 600 !important; color: #374151 !important; margin-bottom: 0px !important;}
    p { font-size: 13px !important; color: #6B7280 !important; }
    
    /* Cards Arredondados */
    .card { 
        background-color: #FFFFFF; 
        border-radius: 16px; 
        padding: 20px; 
        box-shadow: 0 2px 10px rgba(0,0,0,0.04); 
        margin-bottom: 15px; 
        border: 1px solid #F3F4F6; 
    }
    
    /* Caixas de Métricas */
    .metric-box-green { background-color: #F0FDF4; border-radius: 12px; padding: 15px; border: 1px solid #DCFCE7; }
    .metric-box-blue { background-color: #F0F9FF; border-radius: 12px; padding: 15px; border: 1px solid #E0F2FE; }
    .metric-box-cream { background-color: #FFFBEB; border-radius: 12px; padding: 15px; border: 1px solid #FEF3C7; }
    .metric-title { font-size: 10px; text-transform: uppercase; color: #6B7280; font-weight: 600; margin-bottom: 5px;}
    .metric-value { font-size: 28px; font-weight: 500; color: #111827; margin: 0; line-height: 1;}
    
    /* Botões Claros e Legíveis (Baixo Contraste) */
    .stButton>button { 
        background-color: #F3F4F6 !important; 
        color: #1F2937 !important; 
        border-radius: 12px !important; 
        border: 1px solid #D1D5DB !important; 
        font-weight: 600 !important; 
        padding: 4px 16px !important;
        transition: all 0.2s ease;
    }
    .stButton>button:hover { background-color: #E5E7EB !important; border-color: #9CA3AF !important;}
    
    /* Inputs arredondados */
    .stSelectbox div[data-baseweb="select"], .stTextInput input, .stNumberInput input { border-radius: 10px !important; }
    
    .logo-container { display: flex; gap: 12px; margin-bottom: 20px; }
    .logo-container img { height: 40px; object-fit: contain; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# ESTADO E LOGIN
# ==========================================
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'edit_ponto' not in st.session_state: st.session_state.edit_ponto = None
if 'edit_param' not in st.session_state: st.session_state.edit_param = None
if 'edit_coleta' not in st.session_state: st.session_state.edit_coleta = None

# ==========================================
# BARRA LATERAL
# ==========================================
with st.sidebar:
    st.markdown("""<div class="logo-container"><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/UFSC_logo_2.svg/120px-UFSC_logo_2.svg.png"></div>""", unsafe_allow_html=True)
    st.markdown("<h3 style='font-size: 16px;'>Monitoramento de Qualidade de Água</h3>", unsafe_allow_html=True)
    st.markdown("<p>Gestão das Águas - DGA/DGG/GR/UFSC<br><a href='https://gestaoambiental.ufsc.br'>gestaoambiental.ufsc.br</a></p>", unsafe_allow_html=True)
    st.markdown("<hr style='border-top: 1px solid #EAEBE6;'>", unsafe_allow_html=True)
    
    if not st.session_state.autenticado:
        senha = st.text_input("Acesso Restrito", type="password", placeholder="Senha do Admin")
        if st.button("Entrar no Painel"):
            if senha == "ufsc123":
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    else:
        st.success("Administrador logado")
        if st.button("Sair do Painel"):
            st.session_state.autenticado = False
            st.rerun()

# Buscar Dados
df_pontos = db.buscar_pontos()
df_parametros = db.buscar_parametros()
df_coletas = db.buscar_coletas()

ult_coleta = df_coletas['data_amostra'].max() if not df_coletas.empty else "N/A"
if ult_coleta != "N/A":
    partes = ult_coleta.split("-")
    ult_coleta = f"{partes[2]}/{partes[1]}/{partes[0]}"

# ==========================================
# ÁREA PÚBLICA (VISUALIZAÇÃO GERAL)
# ==========================================
if not st.session_state.autenticado:
    
    st.markdown("<h1>Qualidade da Água nos Córregos da UFSC</h1>", unsafe_allow_html=True)
    st.markdown("<p style='margin-bottom: 15px;'>Histórico de coletas, comparação com a legislação ambiental e evolução do Índice de Qualidade das Águas no campus Florianópolis.</p>", unsafe_allow_html=True)
    
    # Métricas
    c_met1, c_met2, c_met3 = st.columns(3)
    with c_met1: st.markdown(f'<div class="metric-box-green"><div class="metric-title">Pontos Monitorados</div><div class="metric-value">{len(df_pontos)}</div></div>', unsafe_allow_html=True)
    with c_met2: st.markdown(f'<div class="metric-box-blue"><div class="metric-title">Análises Registradas</div><div class="metric-value">{len(df_coletas)}</div></div>', unsafe_allow_html=True)
    with c_met3: st.markdown(f'<div class="metric-box-cream"><div class="metric-title">Última Coleta</div><div class="metric-value">{ult_coleta}</div></div>', unsafe_allow_html=True)

    # Análise Temporal
    st.markdown('<div class="card" style="margin-top: 15px;">', unsafe_allow_html=True)
    col_tit, col_sel1, col_sel2 = st.columns([2, 1, 1])
    with col_tit:
        st.markdown("<h3>Análise temporal</h3>", unsafe_allow_html=True)
        st.markdown("<p>Evolução do parâmetro escolhido frente ao limite legal e o IQA.</p>", unsafe_allow_html=True)
    
    opcoes_pontos = ["Selecione o ponto..."] + df_pontos['local'].tolist() if not df_pontos.empty else ["Selecione o ponto..."]
    ponto_sel = col_sel1.selectbox("Ponto", opcoes_pontos, label_visibility="collapsed")
    
    param_lista = df_parametros[df_parametros['nome'] != 'IQA (Índice de Qualidade da Água)']['nome'].tolist()
    opcoes_param = ["Selecione o parâmetro..."] + param_lista if param_lista else ["Selecione o parâmetro..."]
    param_sel = col_sel2.selectbox("Parâmetro", opcoes_param, label_visibility="collapsed")

    if not df_coletas.empty and ponto_sel != "Selecione o ponto..." and param_sel != "Selecione o parâmetro...":
        df_graf = df_coletas[(df_coletas['local'] == ponto_sel) & (df_coletas['parametro'] == param_sel)].sort_values(by="data_amostra")
        df_iqa = df_coletas[(df_coletas['local'] == ponto_sel) & (df_coletas['parametro'] == 'IQA (Índice de Qualidade da Água)')].sort_values(by="data_amostra")
        
        g1, g2 = st.columns(2)
        with g1:
            if not df_graf.empty:
                limite = df_graf['limite_legal'].iloc[0]
                val_atual = df_graf['valor'].iloc[-1]
                st.markdown(f"<span style='font-size:10px; font-weight:600; color:#6B7280;'>{param_sel.upper()}</span><br><span style='font-size:24px;'>{val_atual}</span> <span style='font-size:12px; color:#6B7280;'>{df_graf['unidade'].iloc[0]}</span>", unsafe_allow_html=True)
                
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=df_graf["data_amostra"], y=df_graf["valor"], mode='lines+markers', line=dict(color='#3B82F6', width=2), fill='tozeroy', fillcolor='rgba(59,130,246,0.1)'))
                if pd.notnull(limite): fig1.add_hline(y=limite, line_dash="dash", line_color="#D1D5DB")
                fig1.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10, b=0, l=0, r=0), height=220, yaxis=dict(showgrid=True, gridcolor='#F3F4F6'), xaxis=dict(showgrid=False))
                st.plotly_chart(fig1, use_container_width=True)
            else: st.info("Sem dados")
        with g2:
            if not df_iqa.empty:
                st.markdown(f"<span style='font-size:10px; font-weight:600; color:#6B7280;'>ÍNDICE DE QUALIDADE (IQA)</span><br><span style='font-size:24px;'>{df_iqa['valor'].iloc[-1]}</span> <span style='font-size:12px; color:#6B7280;'>/ 100</span>", unsafe_allow_html=True)
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df_iqa["data_amostra"], y=df_iqa["valor"], mode='lines+markers', line=dict(color='#10B981', width=2), fill='tozeroy', fillcolor='rgba(16,185,129,0.1)'))
                fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10, b=0, l=0, r=0), height=220, yaxis=dict(showgrid=True, gridcolor='#F3F4F6', range=[0,100]), xaxis=dict(showgrid=False))
                st.plotly_chart(fig2, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Mapa
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3>Mapa dos pontos de coleta</h3><p>Clique no marcador azul para ver os detalhes da estação.</p>", unsafe_allow_html=True)
    mapa = folium.Map(location=[-27.601, -48.518], zoom_start=14, tiles=f"https://tiles.stadiamaps.com/tiles/alidade_smooth/{{z}}/{{x}}/{{y}}{{r}}.png?api_key=af1b2140-1a60-4eec-9983-9406fa69f237", attr="Stadia")
    for _, row in df_pontos.iterrows():
        folium.Marker([row['latitude'], row['longitude']], popup=folium.Popup(f"<div style='font-family:Montserrat; width:150px;'><b>{row['codigo']}</b><br>{row['local']}</div>", max_width=200), icon=folium.Icon(color='cadetblue')).add_to(mapa)
    st_folium(mapa, width="100%", height=350)
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# PAINEL ADMINISTRATIVO (Listas com Edição Lateral)
# ==========================================
if st.session_state.autenticado:
    st.markdown("<h1>Painel Administrativo</h1>", unsafe_allow_html=True)
    aba_coletas, aba_pontos, aba_params = st.tabs(["Registrar Coletas", "Pontos de Coleta", "Parâmetros"])
    
    # --- ABA: COLETAS ---
    with aba_coletas:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("<h3>Registrar Nova Coleta</h3>", unsafe_allow_html=True)
        
        opcoes_pt = ["Selecione o ponto..."] + df_pontos['local'].tolist()
        ponto_selecionado = st.selectbox("Escolha o local da amostra:", opcoes_pt)
        
        if ponto_selecionado != "Selecione o ponto...":
            with st.form("form_nova_coleta"):
                st.markdown(f"<p>Preencha os resultados laboratoriais para <b>{ponto_selecionado}</b> (deixe em branco os que não foram analisados).</p>", unsafe_allow_html=True)
                data_am = st.date_input("Data da Amostra")
                st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                
                # Renderiza os campos numa grade elegante
                inputs = {}
                col_i1, col_i2 = st.columns(2)
                for i, (_, row_pa) in enumerate(df_parametros.iterrows()):
                    alvo = col_i1 if i % 2 == 0 else col_i2
                    inputs[row_pa['id']] = alvo.number_input(f"{row_pa['nome']} ({row_pa['unidade']})", value=None, format="%.2f")
                
                if st.form_submit_button("Salvar Resultados"):
                    id_ponto_sel = db.obter_id_ponto(ponto_selecionado)
                    for param_id, valor_digitado in inputs.items():
                        if valor_digitado is not None:
                            db.inserir_coleta(id_ponto_sel, param_id, data_am, valor_digitado)
                    st.success("Coleta salva com sucesso!")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # --- ABA: PONTOS ---
    with aba_pontos:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        with st.form("add_ponto_novo"):
            st.markdown("<h3>Adicionar Novo Ponto</h3>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
            cod_p = c1.text_input("Código")
            loc_p = c2.text_input("Local")
            lat_p = c3.number_input("Latitude", format="%.6f", value=-27.601)
            lon_p = c4.number_input("Longitude", format="%.6f", value=-48.518)
            if st.form_submit_button("Salvar Ponto"):
                db.inserir_ponto(cod_p, loc_p, lat_p, lon_p)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("<h3>Pontos Cadastrados</h3><br>", unsafe_allow_html=True)
        # Cabeçalho da Lista
        ch1, ch2, ch3 = st.columns([1, 4, 2])
        ch1.markdown("<span style='font-size:11px; color:#6B7280; font-weight:600;'>CÓDIGO</span>", unsafe_allow_html=True)
        ch2.markdown("<span style='font-size:11px; color:#6B7280; font-weight:600;'>LOCAL</span>", unsafe_allow_html=True)
        ch3.markdown("<span style='font-size:11px; color:#6B7280; font-weight:600;'>AÇÕES</span>", unsafe_allow_html=True)
        st.markdown("<hr style='margin: 5px 0 10px 0;'>", unsafe_allow_html=True)
        
        for _, row in df_pontos.iterrows():
            if st.session_state.edit_ponto == row['id']:
                with st.form(f"edit_pt_{row['id']}"):
                    ce1, ce2, ce3, ce4 = st.columns([1, 2, 1, 1])
                    ne_cod = ce1.text_input("Código", row['codigo'])
                    ne_loc = ce2.text_input("Local", row['local'])
                    ne_lat = ce3.number_input("Lat", value=float(row['latitude']), format="%.6f")
                    ne_lon = ce4.number_input("Lon", value=float(row['longitude']), format="%.6f")
                    if st.form_submit_button("Salvar Edição"):
                        db.atualizar_ponto(row['id'], ne_cod, ne_loc, ne_lat, ne_lon)
                        st.session_state.edit_ponto = None
                        st.rerun()
            else:
                c1, c2, c3, c4 = st.columns([1, 4, 1, 1])
                c1.markdown(f"<span style='font-size:14px; font-weight:500;'>{row['codigo']}</span>", unsafe_allow_html=True)
                c2.markdown(f"<span style='font-size:14px; color:#374151;'>{row['local']}</span>", unsafe_allow_html=True)
                if c3.button("Editar", key=f"ep_{row['id']}"): 
                    st.session_state.edit_ponto = row['id']
                    st.rerun()
                if c4.button("Excluir", key=f"dp_{row['id']}"):
                    db.deletar_ponto(row['id'])
                    st.rerun()
                st.markdown("<hr style='margin: 5px 0; border-top: 1px solid #F3F4F6;'>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- ABA: PARÂMETROS ---
    with aba_params:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        with st.form("add_param_novo"):
            st.markdown("<h3>Adicionar Novo Parâmetro</h3>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns([3, 1, 2])
            p_nome = c1.text_input("Nome do Parâmetro")
            p_und = c2.text_input("Unidade")
            p_lim = c3.text_input("Limite Legal (Deixe vazio se não houver)")
            if st.form_submit_button("Salvar Parâmetro"):
                lim_val = float(p_lim.replace(",", ".")) if p_lim else None
                db.inserir_parametro(p_nome, p_und, lim_val)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("<h3>Parâmetros Cadastrados</h3><br>", unsafe_allow_html=True)
        # Cabeçalho da Lista
        ch1, ch2, ch3, ch4 = st.columns([3, 1, 2, 2])
        ch1.markdown("<span style='font-size:11px; color:#6B7280; font-weight:600;'>NOME</span>", unsafe_allow_html=True)
        ch2.markdown("<span style='font-size:11px; color:#6B7280; font-weight:600;'>UNID.</span>", unsafe_allow_html=True)
        ch3.markdown("<span style='font-size:11px; color:#6B7280; font-weight:600;'>LIMITE</span>", unsafe_allow_html=True)
        ch4.markdown("<span style='font-size:11px; color:#6B7280; font-weight:600;'>AÇÕES</span>", unsafe_allow_html=True)
        st.markdown("<hr style='margin: 5px 0 10px 0;'>", unsafe_allow_html=True)
        
        for _, row in df_parametros.iterrows():
            if st.session_state.edit_param == row['id']:
                with st.form(f"edit_pa_{row['id']}"):
                    ce1, ce2, ce3 = st.columns([3, 1, 2])
                    ne_nome = ce1.text_input("Nome", row['nome'])
                    ne_und = ce2.text_input("Unidade", row['unidade'])
                    ne_lim = ce3.text_input("Limite", str(row['limite_legal']) if pd.notnull(row['limite_legal']) else "")
                    if st.form_submit_button("Salvar Edição"):
                        lim_val = float(ne_lim.replace(",", ".")) if ne_lim.strip() else None
                        db.atualizar_parametro(row['id'], ne_nome, ne_und, lim_val)
                        st.session_state.edit_param = None
                        st.rerun()
            else:
                c1, c2, c3, c4, c5 = st.columns([3, 1, 2, 1, 1])
                c1.markdown(f"<span style='font-size:14px; font-weight:500;'>{row['nome']}</span>", unsafe_allow_html=True)
                c2.markdown(f"<span style='font-size:14px; color:#6B7280;'>{row['unidade']}</span>", unsafe_allow_html=True)
                c3.markdown(f"<span style='font-size:14px; color:#374151;'>{row['limite_legal'] if pd.notnull(row['limite_legal']) else '-'}</span>", unsafe_allow_html=True)
                if c4.button("Editar", key=f"epa_{row['id']}"): 
                    st.session_state.edit_param = row['id']
                    st.rerun()
                if c5.button("Excluir", key=f"dpa_{row['id']}"):
                    db.deletar_parametro(row['id'])
                    st.rerun()
                st.markdown("<hr style='margin: 5px 0; border-top: 1px solid #F3F4F6;'>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
