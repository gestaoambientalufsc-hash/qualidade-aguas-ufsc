import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import database as db

db.inicializar_banco()
st.set_page_config(page_title="Monitoramento Qualidade de Água Córregos UFSC", layout="wide")

# ==========================================
# CSS CUSTOMIZADO (Design Fiel à Inspiração)
# ==========================================
st.markdown("""
    <style>
    /* Reset e Fontes */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif !important; }
    
    /* Fundo da aplicação */
    .stApp { background-color: #F8F9F5; }
    h1, h2, h3, p, span { color: #111827; }
    
    /* Cards Principais */
    .card { 
        background-color: #FFFFFF; 
        border-radius: 20px; 
        padding: 30px; 
        box-shadow: 0 4px 20px rgba(0,0,0,0.03); 
        margin-bottom: 24px; 
        border: 1px solid #EAEBE6; 
    }
    
    /* Cards de Métricas (Inspirados na Imagem) */
    .metric-box-green { background-color: #F0FDF4; border-radius: 12px; padding: 20px; border: 1px solid #DCFCE7; }
    .metric-box-blue { background-color: #F0F9FF; border-radius: 12px; padding: 20px; border: 1px solid #E0F2FE; }
    .metric-box-cream { background-color: #FFFBEB; border-radius: 12px; padding: 20px; border: 1px solid #FEF3C7; }
    .metric-title { font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; color: #6B7280; font-weight: 600; margin-bottom: 8px;}
    .metric-value { font-size: 32px; font-weight: 400; color: #111827; margin: 0; line-height: 1.2;}
    
    /* Tabelas e Botões */
    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 13px;}
    th { color: #9CA3AF; border-bottom: 1px solid #EAEBE6; text-align: left; padding: 12px; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px;}
    td { padding: 14px 12px; border-bottom: 1px solid #EAEBE6; color: #374151; }
    tr:hover { background-color: #F9FAFB; }
    
    /* Estilo dos botões nativos do Streamlit */
    .stButton>button { 
        background-color: #111827 !important; 
        color: white !important; 
        border-radius: 30px !important; 
        border: none !important; 
        font-weight: 500 !important; 
        padding: 6px 20px !important;
        transition: 0.3s;
    }
    .stButton>button:hover { background-color: #374151 !important; }
    
    /* Logos na Sidebar */
    .logo-container { display: flex; gap: 12px; margin-bottom: 30px; flex-wrap: wrap; }
    .logo-container img { height: 45px; object-fit: contain; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# GERENCIAMENTO DE ESTADO (LOGIN)
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# ==========================================
# BARRA LATERAL (Institucional e Login)
# ==========================================
with st.sidebar:
    st.markdown("""
        <div class="logo-container">
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/UFSC_logo_2.svg/120px-UFSC_logo_2.svg.png">
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<h3 style='font-size: 20px;'>Painel interativo de dados de monitoramento do consumo de água da UFSC</h3>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 13px; color: #6B7280; line-height: 1.5;'>Gestão das Águas - Departamento de Gestão Ambiental - DGA/DGG/GR/UFSC<br><a href='https://gestaoambiental.ufsc.br' style='color: #6366F1; text-decoration: none;'>https://gestaoambiental.ufsc.br</a></p>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 13px; color: #6B7280;'>Projeto desenvolvido em Python 3.10</p>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 13px; color: #6B7280;'>Contato: <a href='mailto:gestaodasaguas@contato.ufsc.br' style='color: #6366F1; text-decoration: none;'>gestaodasaguas@contato.ufsc.br</a></p>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 13px; color: #6B7280;'>Desenvolvido por: <a href='mailto:seu.email@ufsc.br' style='color: #6366F1; text-decoration: none;'>seu.email@ufsc.br</a></p>", unsafe_allow_html=True)
    
    st.markdown("<br><hr style='border-top: 1px solid #EAEBE6;'><br>", unsafe_allow_html=True)
    
    if not st.session_state.autenticado:
        st.markdown("<p style='font-size: 13px; font-weight: 600; color: #374151;'>Acesso Administrativo</p>", unsafe_allow_html=True)
        senha = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="Digite a senha")
        if st.button("Entrar no Painel Admin"):
            if senha == "ufsc123": # Mude a senha se desejar
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    else:
        st.success("Logado como Administrador")
        if st.button("Sair do Painel Admin"):
            st.session_state.autenticado = False
            st.rerun()

# Carregar dados
df_pontos = db.buscar_pontos()
df_parametros = db.buscar_parametros()
df_coletas = db.buscar_coletas()

qtd_pontos = len(df_pontos)
qtd_analises = len(df_coletas)
ult_coleta = df_coletas['data_amostra'].max() if not df_coletas.empty else "N/A"
if ult_coleta != "N/A":
    partes = ult_coleta.split("-")
    ult_coleta = f"{partes[2]}/{partes[1]}/{partes[0]}"

# ==========================================
# ÁREA PÚBLICA (VISUALIZAÇÃO GERAL)
# ==========================================
if not st.session_state.autenticado:
    
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<h1 style='font-family: serif; font-size: 36px; margin-bottom: 5px; font-weight: 400;'>Qualidade da Água nos Córregos da UFSC</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #6B7280; font-size: 14px; margin-bottom: 30px;'>Histórico de coletas, comparação com a legislação ambiental e evolução do Índice de Qualidade das Águas no campus Florianópolis.</p>", unsafe_allow_html=True)
    
    c_met1, c_met2, c_met3 = st.columns(3)
    with c_met1:
        st.markdown(f'<div class="metric-box-green"><div class="metric-title">Pontos Monitorados</div><div class="metric-value">{qtd_pontos}</div></div>', unsafe_allow_html=True)
    with c_met2:
        st.markdown(f'<div class="metric-box-blue"><div class="metric-title">Análises Registradas</div><div class="metric-value">{qtd_analises}</div></div>', unsafe_allow_html=True)
    with c_met3:
        st.markdown(f'<div class="metric-box-cream"><div class="metric-title">Última Coleta</div><div class="metric-value">{ult_coleta}</div></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Análise Temporal (Com Gráficos de Área)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    col_tit, col_sel1, col_sel2 = st.columns([2, 1, 1])
    with col_tit:
        st.markdown("<h3 style='margin: 0;'>Análise temporal</h3>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 13px; color: #6B7280;'>Evolução do parâmetro escolhido frente ao limite legal e o IQA.</p>", unsafe_allow_html=True)
    
    ponto_sel = col_sel1.selectbox("Ponto", df_pontos['local'].tolist() if not df_pontos.empty else [""], label_visibility="collapsed")
    param_lista = df_parametros[df_parametros['nome'] != 'IQA (Índice de Qualidade da Água)']['nome'].tolist()
    param_sel = col_sel2.selectbox("Parâmetro", param_lista if param_lista else [""], label_visibility="collapsed")

    if not df_coletas.empty and ponto_sel:
        df_graf = df_coletas[(df_coletas['local'] == ponto_sel) & (df_coletas['parametro'] == param_sel)].sort_values(by="data_amostra")
        df_iqa = df_coletas[(df_coletas['local'] == ponto_sel) & (df_coletas['parametro'] == 'IQA (Índice de Qualidade da Água)')].sort_values(by="data_amostra")
        
        g1, g2 = st.columns(2)
        with g1:
            if not df_graf.empty:
                limite = df_graf['limite_legal'].iloc[0]
                unidade = df_graf['unidade'].iloc[0]
                val_atual = df_graf['valor'].iloc[-1]
                
                st.markdown(f"<span style='font-size:10px; text-transform:uppercase; color:#9CA3AF; font-weight:600; letter-spacing: 1px;'>{param_sel}</span><br><span style='font-size:28px; font-weight:400;'>{val_atual}</span> <span style='color:#6B7280; font-size:13px;'>{unidade}</span>", unsafe_allow_html=True)
                
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=df_graf["data_amostra"], y=df_graf["valor"], mode='lines+markers', name=param_sel, 
                                          line=dict(color='#3B82F6', width=2), marker=dict(size=5, color='#3B82F6'),
                                          fill='tozeroy', fillcolor='rgba(59, 130, 246, 0.08)')) # Efeito de Sombra
                if pd.notnull(limite):
                    fig1.add_hline(y=limite, line_dash="dash", line_color="#D1D5DB", line_width=1)
                fig1.update_layout(plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", margin=dict(t=15, b=10, l=0, r=0), height=250,
                                   yaxis=dict(showgrid=True, gridcolor='#F3F4F6'), xaxis=dict(showgrid=False))
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.info("Sem dados")
                
        with g2:
            if not df_iqa.empty:
                val_iqa = df_iqa['valor'].iloc[-1]
                st.markdown(f"<span style='font-size:10px; text-transform:uppercase; color:#9CA3AF; font-weight:600; letter-spacing: 1px;'>Índice de Qualidade das Águas</span><br><span style='font-size:28px; font-weight:400;'>{val_iqa}</span> <span style='color:#6B7280; font-size:13px;'>/ 100</span>", unsafe_allow_html=True)
                
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df_iqa["data_amostra"], y=df_iqa["valor"], mode='lines+markers', name="IQA", 
                                          line=dict(color='#10B981', width=2), marker=dict(size=5, color='#10B981'),
                                          fill='tozeroy', fillcolor='rgba(16, 185, 129, 0.08)')) # Efeito de Sombra Verde
                fig2.update_layout(plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", margin=dict(t=15, b=10, l=0, r=0), height=250,
                                   yaxis=dict(showgrid=True, gridcolor='#F3F4F6', range=[0, 100]), xaxis=dict(showgrid=False))
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Sem dados de IQA")
    st.markdown('</div>', unsafe_allow_html=True)

    # Mapa Stadia Maps
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3 style='margin: 0;'>Mapa dos pontos de coleta</h3>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 13px; color: #6B7280;'>Cada marcador azul é uma estação de monitoramento. Clique para abrir os detalhes.</p>", unsafe_allow_html=True)
    
    stadia_api = "af1b2140-1a60-4eec-9983-9406fa69f237"
    url_tiles = f"https://tiles.stadiamaps.com/tiles/alidade_smooth/{{z}}/{{x}}/{{y}}{{r}}.png?api_key={stadia_api}"
    
    mapa = folium.Map(location=[-27.601, -48.518], zoom_start=14, tiles=url_tiles, attr="Stadia Maps")
    for _, row in df_pontos.iterrows():
        html = f"<div style='font-family:sans-serif; width:150px;'><b>{row['codigo']}</b><br>{row['local']}</div>"
        folium.Marker([row['latitude'], row['longitude']], popup=folium.Popup(html, max_width=200), icon=folium.Icon(color='cadetblue')).add_to(mapa)
    st_folium(mapa, width="100%", height=400)
    st.markdown('</div>', unsafe_allow_html=True)

    # Registros
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3 style='margin: 0;'>Registros de coletas</h3>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 13px; color: #6B7280;'>Análises agrupadas por data.</p>", unsafe_allow_html=True)
    
    if not df_coletas.empty:
        for data in sorted(df_coletas['data_amostra'].unique(), reverse=True):
            partes = data.split("-")
            data_br = f"{partes[2]}/{partes[1]}/{partes[0]}"
            with st.expander(f"Coletas do dia: {data_br}"):
                df_dia = df_coletas[df_coletas['data_amostra'] == data]
                html_tab = "<table><tr><th>Ponto</th><th>Parâmetro</th><th>Valor</th><th>Limite Legal</th></tr>"
                for _, row in df_dia.iterrows():
                    lim = row['limite_legal'] if pd.notnull(row['limite_legal']) else "-"
                    html_tab += f"<tr><td>{row['local']}</td><td>{row['parametro']}</td><td>{row['valor']} {row['unidade']}</td><td>{lim}</td></tr>"
                html_tab += "</table>"
                st.markdown(html_tab, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# ÁREA RESTRITA (PAINEL ADMIN)
# ==========================================
if st.session_state.autenticado:
    st.markdown("<h2 style='margin-bottom: 30px;'>Painel Administrativo</h2>", unsafe_allow_html=True)
    
    # Métricas no Admin (Igual a Imagem 4)
    c_m1, c_m2, c_m3 = st.columns(3)
    with c_m1:
        st.markdown(f'<div class="metric-box-green"><div class="metric-value">{qtd_pontos}</div><div class="metric-title" style="margin-top:5px;">Pontos de coleta</div></div>', unsafe_allow_html=True)
    with c_m2:
        st.markdown(f'<div class="metric-box-blue"><div class="metric-value">{len(df_parametros)}</div><div class="metric-title" style="margin-top:5px;">Parâmetros</div></div>', unsafe_allow_html=True)
    with c_m3:
        st.markdown(f'<div class="metric-box-cream"><div class="metric-value">{qtd_analises}</div><div class="metric-title" style="margin-top:5px;">Coletas registradas</div></div>', unsafe_allow_html=True)
    
    st.write("")
    aba_pontos, aba_params, aba_coletas = st.tabs(["Pontos de coleta", "Parâmetros", "Coletas registradas"])
    
    # --- PONTOS ---
    with aba_pontos:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        with st.form("add_pt"):
            st.markdown("<h4 style='margin-top:0;'>Novo ponto</h4>", unsafe_allow_html=True)
            cp1, cp2 = st.columns(2)
            cod_p = cp1.text_input("CÓDIGO (Ex: P01)")
            loc_p = cp2.text_input("LOCAL")
            lat_p = cp1.number_input("LATITUDE", format="%.6f", value=-27.601)
            lon_p = cp2.number_input("LONGITUDE", format="%.6f", value=-48.518)
            if st.form_submit_button("Registrar ponto"):
                db.inserir_ponto(cod_p, loc_p, lat_p, lon_p)
                st.rerun()
        
        st.markdown("<br>", unsafe_allow_html=True)
        if not df_pontos.empty:
            pt_edit = st.selectbox("Selecione um ponto para Modificar ou Excluir:", df_pontos['local'].tolist())
            row_p = df_pontos[df_pontos['local'] == pt_edit].iloc[0]
            with st.form("edit_pt"):
                cp1, cp2 = st.columns(2)
                e_cod = cp1.text_input("Código", value=row_p['codigo'])
                e_loc = cp2.text_input("Local", value=row_p['local'])
                e_lat = cp1.number_input("Latitude", value=float(row_p['latitude']), format="%.6f")
                e_lon = cp2.number_input("Longitude", value=float(row_p['longitude']), format="%.6f")
                if st.form_submit_button("Salvar Alterações"):
                    db.atualizar_ponto(row_p['id'], e_cod, e_loc, e_lat, e_lon)
                    st.rerun()
            if st.button("Excluir Ponto Definitivamente"):
                db.deletar_ponto(row_p['id'])
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # --- PARÂMETROS ---
    with aba_params:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        with st.form("add_pa"):
            st.markdown("<h4 style='margin-top:0;'>Novo parâmetro</h4>", unsafe_allow_html=True)
            ca1, ca2, ca3 = st.columns(3)
            p_nome = ca1.text_input("PARÂMETRO")
            p_und = ca2.text_input("UNIDADE (Ex: mg/L)")
            p_lim = ca3.text_input("LIMITE LEGAL (Vazio se não houver)")
            if st.form_submit_button("Cadastrar parâmetro"):
                lim_val = float(p_lim.replace(",", ".")) if p_lim else None
                db.inserir_parametro(p_nome, p_und, lim_val)
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if not df_parametros.empty:
            pa_edit = st.selectbox("Selecione um parâmetro para Modificar ou Excluir:", df_parametros['nome'].tolist())
            row_pa = df_parametros[df_parametros['nome'] == pa_edit].iloc[0]
            with st.form("edit_pa"):
                ca1, ca2, ca3 = st.columns(3)
                ep_nome = ca1.text_input("Nome", value=row_pa['nome'])
                ep_und = ca2.text_input("Unidade", value=row_pa['unidade'])
                ep_lim = ca3.text_input("Limite", value=str(row_pa['limite_legal']) if pd.notnull(row_pa['limite_legal']) else "")
                if st.form_submit_button("Salvar Alterações"):
                    lim_val = float(ep_lim.replace(",", ".")) if ep_lim.strip() and ep_lim != "None" else None
                    db.atualizar_parametro(row_pa['id'], ep_nome, ep_und, lim_val)
                    st.rerun()
            if st.button("Excluir Parâmetro Definitivamente"):
                db.deletar_parametro(row_pa['id'])
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # --- COLETAS ---
    with aba_coletas:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("<h4 style='margin-top:0;'>Nova coleta (Inserção em Lote)</h4>", unsafe_allow_html=True)
        
        if df_pontos.empty or df_parametros.empty:
            st.warning("Cadastre pontos e parâmetros primeiro.")
        else:
            with st.form("form_lote"):
                c_head1, c_head2 = st.columns(2)
                ponto_selecionado = c_head1.selectbox("PONTO DE COLETA", df_pontos['local'].tolist())
                data_amostra = c_head2.date_input("DATA DA AMOSTRA")
                
                st.markdown("<p style='font-size:13px; color:#6B7280; margin-top:10px;'>Preencha os valores encontrados (deixe em branco os que não foram analisados):</p>", unsafe_allow_html=True)
                
                valores_inputs = {}
                for _, row_pa in df_parametros.iterrows():
                    valores_inputs[row_pa['id']] = st.number_input(f"{row_pa['nome']} ({row_pa['unidade']})", value=None, format="%.2f")
                
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("Registrar coleta"):
                    id_ponto_sel = db.obter_id_ponto(ponto_selecionado)
                    coletas_inseridas = 0
                    for param_id, valor_digitado in valores_inputs.items():
                        if valor_digitado is not None:
                            db.inserir_coleta(id_ponto_sel, param_id, data_amostra, valor_digitado)
                            coletas_inseridas += 1
                    st.success(f"Sucesso! {coletas_inseridas} parâmetros registrados.")
                    st.rerun()
                    
        st.markdown("<br>", unsafe_allow_html=True)
        if not df_coletas.empty:
            df_coletas['desc'] = df_coletas['data_amostra'] + " | " + df_coletas['local'] + " | " + df_coletas['parametro'] + " (" + df_coletas['valor'].astype(str) + ")"
            col_del = st.selectbox("Modificar ou Excluir uma Coleta Específica:", df_coletas['desc'].tolist())
            id_col = df_coletas[df_coletas['desc'] == col_del]['id'].values[0]
            cb1, cb2 = st.columns(2)
            nv = cb1.number_input("Corrigir Valor", value=float(df_coletas[df_coletas['id']==id_col]['valor'].values[0]))
            if cb1.button("Editar Coleta"):
                row_c = df_coletas[df_coletas['id']==id_col].iloc[0]
                db.atualizar_coleta(id_col, row_c['ponto_id'], row_c['param_id'], row_c['data_amostra'], nv)
                st.rerun()
            if cb2.button("Excluir Coleta"):
                db.deletar_coleta(id_col)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
