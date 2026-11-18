import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import database as db

db.inicializar_banco()
st.set_page_config(page_title="Qualidade da Água - UFSC", layout="wide")

# ==========================================
# CONFIGURAÇÃO DINÂMICA DAS FAIXAS DO IQA
# ==========================================
# Você pode alterar os valores de "min" e "max" aqui. 
# O gráfico e as etiquetas se ajustarão sozinhos!
IQA_FAIXAS = {
    "Péssima": {"min": 0,  "max": 20,  "cor_texto": "#E53E3E", "cor_bg": "#FFF5F5", "cor_grafico": "rgba(229, 62, 62, 0.08)"},
    "Ruim":    {"min": 20, "max": 36,  "cor_texto": "#DD6B20", "cor_bg": "#FFF5F5", "cor_grafico": "rgba(221, 107, 32, 0.08)"},
    "Regular": {"min": 36, "max": 51,  "cor_texto": "#D69E2E", "cor_bg": "#FFFFF0", "cor_grafico": "rgba(214, 158, 46, 0.08)"},
    "Boa":     {"min": 51, "max": 80,  "cor_texto": "#38A169", "cor_bg": "#E6FFFA", "cor_grafico": "rgba(56, 161, 105, 0.08)"},
    "Ótima":   {"min": 80, "max": 100, "cor_texto": "#2F855A", "cor_bg": "#F0FFF4", "cor_grafico": "rgba(47, 133, 90, 0.12)"}
}

def classificar_iqa(valor):
    for nome, config in IQA_FAIXAS.items():
        if config["min"] <= valor <= config["max"]:
            return nome, config["cor_texto"], config["cor_bg"]
    return "Indefinido", "#718096", "#EDF2F7" # Caso o valor fuja da escala 0-100

# ==========================================
# CSS CUSTOMIZADO
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');
    
    * { font-family: 'Montserrat', sans-serif !important; }
    
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; max-width: 95% !important;}
    .stApp { background-color: #FAFAFA; }
    
    h1 { font-size: 26px !important; font-weight: 700 !important; color: #2D3748 !important; margin-bottom: 5px !important;}
    h3 { font-size: 17px !important; font-weight: 600 !important; color: #4A5568 !important; margin-bottom: 0px !important;}
    p { font-size: 14px !important; color: #718096 !important; }
    
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF; 
        border-radius: 16px !important; 
        padding: 10px; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.03); 
        border: 1px solid #EDF2F7 !important; 
    }
    
    .metric-box-green { background-color: #E8F5E9; border-radius: 12px; padding: 20px; border: 1px solid #C8E6C9; }
    .metric-box-blue { background-color: #E3F2FD; border-radius: 12px; padding: 20px; border: 1px solid #BBDEFB; }
    .metric-box-cream { background-color: #FFF9C4; border-radius: 12px; padding: 20px; border: 1px solid #FFF59D; }
    .metric-title { font-size: 11px; text-transform: uppercase; color: #4A5568; font-weight: 600; margin-bottom: 8px;}
    .metric-value { font-size: 32px; font-weight: 600; color: #2D3748; margin: 0; line-height: 1;}
    
    .iqa-badge {
        font-size: 11px; font-weight: 600; padding: 4px 10px; 
        border-radius: 12px; border: 1px solid; display: inline-block;
    }

    .stButton>button { 
        background-color: #F7FAFC !important; 
        color: #4A5568 !important; 
        border-radius: 8px !important; 
        border: 1px solid #E2E8F0 !important; 
        font-weight: 500 !important; 
        padding: 4px 12px !important;
        transition: all 0.2s ease;
    }
    .stButton>button:hover { background-color: #EDF2F7 !important; border-color: #CBD5E0 !important;}
    
    .stSelectbox div[data-baseweb="select"], .stTextInput input, .stNumberInput input, .stDateInput input { 
        border-radius: 8px !important; border: 1px solid #E2E8F0;
    }
    
    .logo-container { display: flex; gap: 12px; margin-bottom: 20px; }
    .logo-container img { height: 45px; object-fit: contain; }
    .row-divider { border-bottom: 1px solid #EDF2F7; margin-top: 8px; margin-bottom: 8px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# ESTADO E LOGIN
# ==========================================
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'edit_ponto' not in st.session_state: st.session_state.edit_ponto = None
if 'edit_param' not in st.session_state: st.session_state.edit_param = None
if 'edit_coleta' not in st.session_state: st.session_state.edit_coleta = None

# Buscar Dados
df_pontos = db.buscar_pontos()
df_parametros = db.buscar_parametros()
df_coletas = db.buscar_coletas()

ult_coleta = df_coletas['data_amostra'].max() if not df_coletas.empty else "N/A"
if ult_coleta != "N/A":
    partes = ult_coleta.split("-")
    ult_coleta = f"{partes[2]}/{partes[1]}/{partes[0]}"

# ==========================================
# BARRA LATERAL
# ==========================================
with st.sidebar:
    st.markdown("""<div class="logo-container"><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/UFSC_logo_2.svg/120px-UFSC_logo_2.svg.png"></div>""", unsafe_allow_html=True)
    st.markdown("<h3 style='font-size: 15px;'>Monitoramento de Qualidade de Água</h3>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 12px;'>Gestão das Águas - DGA/UFSC<br><a href='https://gestaoambiental.ufsc.br' style='color:#718096; text-decoration:none;'>gestaoambiental.ufsc.br</a></p>", unsafe_allow_html=True)
    st.markdown("<hr style='border-top: 1px solid #EDF2F7;'>", unsafe_allow_html=True)
    
    if not st.session_state.autenticado:
        senha = st.text_input("Acesso Restrito", type="password", placeholder="Senha do Admin")
        if st.button("Entrar no Painel"):
            if senha == "ufsc123":
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    else:
        menu_admin = st.radio("Menu Administrativo", ["Registrar Coleta", "Gerenciar Pontos", "Gerenciar Parâmetros"])
        st.markdown("<hr style='border-top: 1px solid #EDF2F7;'>", unsafe_allow_html=True)
        st.success("Administrador logado")
        if st.button("Sair do Painel"):
            st.session_state.autenticado = False
            st.rerun()

# ==========================================
# ÁREA PÚBLICA (VISUALIZAÇÃO GERAL)
# ==========================================
if not st.session_state.autenticado:
    
    st.markdown("<h1>Monitoramento Qualidade de Água Córregos UFSC</h1>", unsafe_allow_html=True)
    st.markdown("<p style='margin-bottom: 25px;'>Histórico de coletas, comparação com a legislação ambiental e evolução do Índice de Qualidade das Águas no campus Florianópolis.</p>", unsafe_allow_html=True)
    
    c_met1, c_met2, c_met3 = st.columns(3)
    with c_met1: st.markdown(f'<div class="metric-box-green"><div class="metric-title">Pontos Monitorados</div><div class="metric-value">{len(df_pontos)}</div></div>', unsafe_allow_html=True)
    with c_met2: st.markdown(f'<div class="metric-box-blue"><div class="metric-title">Análises Registradas</div><div class="metric-value">{len(df_coletas)}</div></div>', unsafe_allow_html=True)
    with c_met3: st.markdown(f'<div class="metric-box-cream"><div class="metric-title">Última Coleta</div><div class="metric-value">{ult_coleta}</div></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Análise Temporal
    with st.container(border=True):
        col_tit, col_sel1, col_sel2 = st.columns([2, 1, 1])
        with col_tit:
            st.markdown("<h3>Análise temporal</h3>", unsafe_allow_html=True)
            st.markdown("<p>Evolução do parâmetro escolhido frente ao limite legal e o IQA do ponto.</p>", unsafe_allow_html=True)
        
        opcoes_pontos = ["Selecione o ponto..."] + df_pontos['local'].tolist() if not df_pontos.empty else ["Selecione o ponto..."]
        ponto_sel = col_sel1.selectbox("Ponto", opcoes_pontos, label_visibility="collapsed")
        
        param_lista = df_parametros[df_parametros['nome'] != 'IQA (Índice de Qualidade da Água)']['nome'].tolist()
        opcoes_param = ["Selecione o parâmetro..."] + param_lista if param_lista else ["Selecione o parâmetro..."]
        param_sel = col_sel2.selectbox("Parâmetro", opcoes_param, label_visibility="collapsed")

        if not df_coletas.empty and ponto_sel != "Selecione o ponto..." and param_sel != "Selecione o parâmetro...":
            df_graf = df_coletas[(df_coletas['local'] == ponto_sel) & (df_coletas['parametro'] == param_sel)].sort_values(by="data_amostra").copy()
            df_iqa = df_coletas[(df_coletas['local'] == ponto_sel) & (df_coletas['parametro'] == 'IQA (Índice de Qualidade da Água)')].sort_values(by="data_amostra").copy()
            
            if not df_graf.empty: df_graf['data_str'] = pd.to_datetime(df_graf['data_amostra']).dt.strftime('%d/%m/%Y')
            if not df_iqa.empty: df_iqa['data_str'] = pd.to_datetime(df_iqa['data_amostra']).dt.strftime('%d/%m/%Y')

            g1, g2 = st.columns(2)
            with g1:
                if not df_graf.empty:
                    limite = df_graf['limite_legal'].iloc[0]
                    val_atual = df_graf['valor'].iloc[-1]
                    st.markdown(f"<span style='font-size:11px; font-weight:600; color:#A0AEC0; text-transform:uppercase;'>{param_sel}</span><br><span style='font-size:26px; font-weight:600; color:#2D3748;'>{val_atual}</span> <span style='font-size:13px; color:#A0AEC0;'>{df_graf['unidade'].iloc[0]}</span>", unsafe_allow_html=True)
                    
                    fig1 = go.Figure()
                    fig1.add_trace(go.Scatter(
                        x=df_graf["data_str"], y=df_graf["valor"], mode='lines+markers', line_shape='spline',
                        marker=dict(size=8, color='#2B6CB0', line=dict(width=2, color='white')),
                        line=dict(color='#4299E1', width=2.5), fill='tozeroy', fillcolor='rgba(66,153,225,0.08)'
                    ))
                    if pd.notnull(limite): fig1.add_hline(y=limite, line_dash="dash", line_color="#A0AEC0", annotation_text="Limite")
                    fig1.update_layout(
                        plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=20, b=10, l=0, r=0), height=240, 
                        yaxis=dict(showgrid=True, gridcolor='#F7FAFC', zeroline=False), xaxis=dict(showgrid=False, type='category')
                    )
                    st.plotly_chart(fig1, use_container_width=True)
                else: st.info("Sem dados para este parâmetro.")
            
            with g2:
                if not df_iqa.empty:
                    iqa_atual = df_iqa['valor'].iloc[-1]
                    status_nome, status_cor, status_bg = classificar_iqa(iqa_atual)
                    
                    # Cabeçalho do IQA com Badge lado a lado
                    st.markdown(f"""
                        <div style="display:flex; justify-content:space-between; align-items:flex-end;">
                            <div>
                                <span style='font-size:11px; font-weight:600; color:#A0AEC0;'>ÍNDICE DE QUALIDADE DAS ÁGUAS</span><br>
                                <span style='font-size:26px; font-weight:600; color:#2D3748;'>{iqa_atual}</span> <span style='font-size:13px; color:#A0AEC0;'>/ 100</span>
                            </div>
                            <span class='iqa-badge' style='background-color:{status_bg}; color:{status_cor}; border-color:{status_cor};'>{status_nome}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    fig2 = go.Figure()
                    
                    # LER AS FAIXAS DINAMICAMENTE DO DICIONÁRIO IQA_FAIXAS PARA PINTAR O FUNDO
                    for nome, config in IQA_FAIXAS.items():
                        fig2.add_hrect(
                            y0=config["min"], y1=config["max"], 
                            fillcolor=config["cor_grafico"], 
                            opacity=1, layer="below", line_width=0
                        )
                    
                    fig2.add_trace(go.Scatter(
                        x=df_iqa["data_str"], y=df_iqa["valor"], mode='lines+markers', line_shape='spline',
                        marker=dict(size=8, color='#276749', line=dict(width=2, color='white')),
                        line=dict(color='#38A169', width=2.5)
                    ))
                    fig2.update_layout(
                        plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=20, b=5, l=0, r=0), height=240, 
                        yaxis=dict(showgrid=True, gridcolor='#F7FAFC', range=[0,100], zeroline=False), xaxis=dict(showgrid=False, type='category')
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    # Legenda de Cores IQA minimalista (Renderizada baseada nas cores configuradas no dict)
                    legend_html = '<div style="display:flex; gap:12px; font-size:10px; color:#A0AEC0; font-weight:500; margin-top:-10px; margin-bottom: 5px;">'
                    for nome, config in reversed(IQA_FAIXAS.items()): # Reversed para mostrar de Ótima até Péssima
                        legend_html += f'<span style="display:flex; align-items:center; gap:4px;"><div style="width:7px; height:7px; border-radius:50%; background:{config["cor_texto"]};"></div> {nome}</span>'
                    legend_html += '</div>'
                    
                    st.markdown(legend_html, unsafe_allow_html=True)
                else: st.info("Sem dados de IQA para este ponto.")
        else:
            st.markdown("<div style='text-align: center; padding: 40px 20px; color: #A0AEC0; font-size: 14px;'>Selecione um ponto e um parâmetro nos menus acima para visualizar o histórico.</div>", unsafe_allow_html=True)

    # Mapa
    with st.container(border=True):
        st.markdown("<h3>Mapa dos pontos de coleta</h3><p>Passe o mouse sobre os pontos para visualizar o código e o local.</p>", unsafe_allow_html=True)
        
        if not df_pontos.empty:
            url_stadia = "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}.png?api_key=af1b2140-1a60-4eec-9983-9406fa69f237"
            
            if hasattr(go, 'Scattermap'):
                map_trace = go.Scattermap(
                    lat=df_pontos['latitude'].astype(float), lon=df_pontos['longitude'].astype(float),
                    mode='markers', marker=dict(size=14, color='#4299E1', opacity=0.9),
                    text=df_pontos['codigo'] + " - " + df_pontos['local'], hoverinfo='text'
                )
                map_layout = dict(
                    map=dict(style="white-bg", layers=[dict(below="traces", sourcetype="raster", source=[url_stadia])], center=dict(lat=-27.601, lon=-48.518), zoom=13.5),
                    margin=dict(r=0, t=0, l=0, b=0), height=400, paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF"
                )
            else:
                map_trace = go.Scattermapbox(
                    lat=df_pontos['latitude'].astype(float), lon=df_pontos['longitude'].astype(float),
                    mode='markers', marker=dict(size=14, color='#4299E1', opacity=0.9),
                    text=df_pontos['codigo'] + " - " + df_pontos['local'], hoverinfo='text'
                )
                map_layout = dict(
                    mapbox=dict(style="white-bg", layers=[dict(below="traces", sourcetype="raster", source=[url_stadia])], center=dict(lat=-27.601, lon=-48.518), zoom=13.5),
                    margin=dict(r=0, t=0, l=0, b=0), height=400, paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF"
                )

            fig_map = go.Figure(map_trace)
            fig_map.update_layout(**map_layout)
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.info("Nenhum ponto de coleta cadastrado.")

# ==========================================
# PAINEL ADMINISTRATIVO
# ==========================================
if st.session_state.autenticado:
    st.markdown("<h1>Painel Administrativo</h1>", unsafe_allow_html=True)
    
    if menu_admin == "Registrar Coleta":
        with st.container(border=True):
            st.markdown("<h3>Registrar Nova Coleta</h3><br>", unsafe_allow_html=True)
            
            opcoes_pt = ["Selecione o ponto..."] + df_pontos['local'].tolist()
            ponto_selecionado = st.selectbox("Escolha o local da amostra:", opcoes_pt)
            
            if ponto_selecionado != "Selecione o ponto...":
                with st.form("form_nova_coleta"):
                    st.markdown(f"<p>Preencha os resultados laboratoriais para <b>{ponto_selecionado}</b> (deixe em branco os que não foram analisados).</p>", unsafe_allow_html=True)
                    data_am = st.date_input("Data da Amostra")
                    st.markdown("<hr style='margin: 20px 0; border-top: 1px solid #EDF2F7;'>", unsafe_allow_html=True)
                    
                    inputs = {}
                    col_i1, col_i2 = st.columns(2)
                    for i, (_, row_pa) in enumerate(df_parametros.iterrows()):
                        alvo = col_i1 if i % 2 == 0 else col_i2
                        inputs[row_pa['id']] = alvo.number_input(f"{row_pa['nome']} ({row_pa['unidade']})", value=None, format="%.2f")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("Salvar Resultados"):
                        id_ponto_sel = db.obter_id_ponto(ponto_selecionado)
                        for param_id, valor_digitado in inputs.items():
                            if valor_digitado is not None:
                                db.inserir_coleta(id_ponto_sel, param_id, data_am, valor_digitado)
                        st.success("Coleta salva com sucesso!")
                        st.rerun()

    elif menu_admin == "Gerenciar Pontos":
        with st.container(border=True):
            with st.form("add_ponto_novo"):
                st.markdown("<h3>Adicionar Novo Ponto</h3><br>", unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
                cod_p = c1.text_input("Código")
                loc_p = c2.text_input("Local")
                lat_p = c3.number_input("Latitude", format="%.6f", value=-27.601)
                lon_p = c4.number_input("Longitude", format="%.6f", value=-48.518)
                if st.form_submit_button("Salvar Ponto"):
                    db.inserir_ponto(cod_p, loc_p, lat_p, lon_p)
                    st.rerun()
        
        with st.container(border=True):
            st.markdown("<h3>Pontos Cadastrados</h3><br>", unsafe_allow_html=True)
            ch1, ch2, ch3 = st.columns([1, 4, 2])
            ch1.markdown("<span style='font-size:12px; color:#A0AEC0; font-weight:600;'>CÓDIGO</span>", unsafe_allow_html=True)
            ch2.markdown("<span style='font-size:12px; color:#A0AEC0; font-weight:600;'>LOCAL</span>", unsafe_allow_html=True)
            ch3.markdown("<span style='font-size:12px; color:#A0AEC0; font-weight:600;'>AÇÕES</span>", unsafe_allow_html=True)
            st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)
            
            for index, row in df_pontos.iterrows():
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
                    c1.markdown(f"<span style='font-size:14px; font-weight:500; color:#2D3748;'>{row['codigo']}</span>", unsafe_allow_html=True)
                    c2.markdown(f"<span style='font-size:14px; color:#4A5568;'>{row['local']}</span>", unsafe_allow_html=True)
                    if c3.button("Editar", icon=":material/edit:", key=f"ep_{row['id']}", help="Editar Ponto"): 
                        st.session_state.edit_ponto = row['id']
                        st.rerun()
                    if c4.button("Excluir", icon=":material/delete:", key=f"dp_{row['id']}", help="Excluir Ponto"):
                        db.deletar_ponto(row['id'])
                        st.rerun()
                    st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)

    elif menu_admin == "Gerenciar Parâmetros":
        with st.container(border=True):
            with st.form("add_param_novo"):
                st.markdown("<h3>Adicionar Novo Parâmetro</h3><br>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns([3, 1, 2])
                p_nome = c1.text_input("Nome do Parâmetro")
                p_und = c2.text_input("Unidade")
                p_lim = c3.text_input("Limite Legal (Deixe vazio se não houver)")
                if st.form_submit_button("Salvar Parâmetro"):
                    lim_val = float(p_lim.replace(",", ".")) if p_lim else None
                    db.inserir_parametro(p_nome, p_und, lim_val)
                    st.rerun()

        with st.container(border=True):
            st.markdown("<h3>Parâmetros Cadastrados</h3><br>", unsafe_allow_html=True)
            ch1, ch2, ch3, ch4 = st.columns([3, 1, 2, 2])
            ch1.markdown("<span style='font-size:12px; color:#A0AEC0; font-weight:600;'>NOME</span>", unsafe_allow_html=True)
            ch2.markdown("<span style='font-size:12px; color:#A0AEC0; font-weight:600;'>UNID.</span>", unsafe_allow_html=True)
            ch3.markdown("<span style='font-size:12px; color:#A0AEC0; font-weight:600;'>LIMITE</span>", unsafe_allow_html=True)
            ch4.markdown("<span style='font-size:12px; color:#A0AEC0; font-weight:600;'>AÇÕES</span>", unsafe_allow_html=True)
            st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)
            
            for index, row in df_parametros.iterrows():
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
                    c1.markdown(f"<span style='font-size:14px; font-weight:500; color:#2D3748;'>{row['nome']}</span>", unsafe_allow_html=True)
                    c2.markdown(f"<span style='font-size:14px; color:#718096;'>{row['unidade']}</span>", unsafe_allow_html=True)
                    c3.markdown(f"<span style='font-size:14px; color:#4A5568;'>{row['limite_legal'] if pd.notnull(row['limite_legal']) else '-'}</span>", unsafe_allow_html=True)
                    if c4.button("Editar", icon=":material/edit:", key=f"epa_{row['id']}", help="Editar Parâmetro"): 
                        st.session_state.edit_param = row['id']
                        st.rerun()
                    if c5.button("Excluir", icon=":material/delete:", key=f"dpa_{row['id']}", help="Excluir Parâmetro"):
                        db.deletar_parametro(row['id'])
                        st.rerun()
                    st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)
