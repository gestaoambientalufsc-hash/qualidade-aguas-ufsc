import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import database as db

db.inicializar_banco()
st.set_page_config(page_title="Qualidade da Água - UFSC", layout="wide", page_icon="💧")

# --- CSS BASEADO NO SEU DESIGN ---
st.markdown("""
    <style>
    .stApp { background-color: #F4F7F6; }
    h1, h2, h3, p { color: #1E4D3B; }
    .card { background-color: #FFFFFF; border-radius: 12px; padding: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 24px; border: 1px solid #E2E8F0; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-family: sans-serif; font-size: 14px;}
    th { color: #2C6E4F; border-bottom: 2px solid #E2E8F0; text-align: left; padding: 12px; font-weight: bold;}
    td { padding: 12px; border-bottom: 1px solid #E2E8F0; color: #333; }
    tr:nth-child(even) { background-color: #F8FAFC; }
    tr:hover { background-color: #EDF2F7; }
    .stButton>button { background-color: #2C6E4F !important; color: white !important; border-radius: 20px !important; border: none !important; padding: 5px 24px !important; font-weight: bold !important; }
    .stButton>button:hover { background-color: #1E4D3B !important; }
    </style>
""", unsafe_allow_html=True)

df_pontos = db.buscar_pontos()
df_parametros = db.buscar_parametros()
df_coletas = db.buscar_coletas()

# ==========================================
# BARRA LATERAL (ADMIN ISOLADO)
# ==========================================
st.sidebar.title("💧 Menu de Navegação")
menu = st.sidebar.radio("Selecione a área:", ["🌍 Área Pública (Visualização)", "🔒 Painel Admin (Gestão)"])
st.sidebar.markdown("---")
st.sidebar.info("Monitoramento contínuo dos recursos hídricos do campus UFSC.")

# ==========================================
# ÁREA PÚBLICA
# ==========================================
if menu == "🌍 Área Pública (Visualização)":
    st.title("Qualidade da Água")
    st.markdown("Monitoramento de parâmetros hídricos, evolução temporal e registros.")

    # 1. Análise Temporal & IQA
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Análise Temporal e IQA")
    
    col_f1, col_f2 = st.columns(2)
    ponto_sel = col_f1.selectbox("Selecione o Ponto de Coleta", df_pontos['local'].tolist() if not df_pontos.empty else ["Nenhum"])
    
    # Filtra os parâmetros para não mostrar o IQA no dropdown principal (ele tem um gráfico próprio ao lado)
    param_lista = df_parametros[df_parametros['nome'] != 'IQA (Índice de Qualidade da Água)']['nome'].tolist()
    param_sel = col_f2.selectbox("Selecione o Parâmetro Analisado", param_lista if param_lista else ["Nenhum"])

    if not df_coletas.empty and ponto_sel != "Nenhum":
        # Gráfico 1: Parâmetro Selecionado
        df_graf = df_coletas[(df_coletas['local'] == ponto_sel) & (df_coletas['parametro'] == param_sel)].sort_values(by="data_amostra")
        # Gráfico 2: IQA Real
        df_iqa = df_coletas[(df_coletas['local'] == ponto_sel) & (df_coletas['parametro'] == 'IQA (Índice de Qualidade da Água)')].sort_values(by="data_amostra")
        
        col_g1, col_g2 = st.columns([2, 1])
        with col_g1:
            if not df_graf.empty:
                limite = df_graf['limite_legal'].iloc[0]
                unidade = df_graf['unidade'].iloc[0]
                
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=df_graf["data_amostra"], y=df_graf["valor"], mode='lines+markers+text', 
                                          name=param_sel, text=df_graf["valor"], textposition="top center",
                                          line=dict(color='#0078A8', width=1.5), marker=dict(size=8, color='#0078A8')))
                if pd.notnull(limite):
                    fig1.add_hline(y=limite, line_dash="dash", line_color="red", line_width=1.5, annotation_text=f"Limite: {limite}")
                fig1.update_layout(title=f"Evolução: {param_sel} ({unidade})", plot_bgcolor="white", yaxis=dict(showgrid=True, gridcolor='#E2E8F0'), margin=dict(t=40, b=0, l=0, r=0))
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.info(f"Sem registros de {param_sel} para este ponto.")
                
        with col_g2:
            if not df_iqa.empty:
                fig2 = px.bar(df_iqa, x="data_amostra", y="valor", title="Evolução do IQA", text="valor", color="valor", color_continuous_scale="Teal")
                fig2.update_layout(plot_bgcolor="white", margin=dict(t=40, b=0, l=0, r=0))
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("O IQA ainda não foi preenchido para este ponto nas coletas.")
    st.markdown('</div>', unsafe_allow_html=True)

    # 2. Mapa
    st.markdown('<div class="card">', unsafe_allow_html=True)
    mapa = folium.Map(location=[-27.601, -48.518], zoom_start=14)
    for _, row in df_pontos.iterrows():
        popup_html = f"""<div style="font-family: sans-serif; width: 180px; text-align:center;">
            <p style="font-size:10px; color:#2C6E4F; font-weight:bold; margin:0;">PONTO DE COLETA</p>
            <p style="font-size:14px; font-weight:bold; margin:5px 0;">{row['codigo']}</p>
            <p style="font-size:12px; margin-bottom:15px; color:#333;">{row['local']}</p></div>"""
        folium.Marker([row['latitude'], row['longitude']], popup=folium.Popup(popup_html, max_width=250), icon=folium.Icon(color='blue')).add_to(mapa)
    st_folium(mapa, width="100%", height=400)
    st.markdown('</div>', unsafe_allow_html=True)

    # 3. Registros de Coletas
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Visualização de Coletas (Histórico)")
    if not df_coletas.empty:
        for data in sorted(df_coletas['data_amostra'].unique(), reverse=True):
            with st.expander(f"📁 Coletas do dia: {data}"):
                df_dia = df_coletas[df_coletas['data_amostra'] == data]
                html_tab = "<table><tr><th>Ponto</th><th>Parâmetro</th><th>Valor</th><th>Limite Legal</th></tr>"
                for _, row in df_dia.iterrows():
                    lim = row['limite_legal'] if pd.notnull(row['limite_legal']) else "-"
                    html_tab += f"<tr><td>{row['local']}</td><td>{row['parametro']}</td><td>{row['valor']} {row['unidade']}</td><td>{lim}</td></tr>"
                html_tab += "</table>"
                st.markdown(html_tab, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# PAINEL ADMIN (SEPARADO)
# ==========================================
elif menu == "🔒 Painel Admin (Gestão)":
    st.title("Painel Administrativo")
    aba_coleta, aba_pontos, aba_params = st.tabs(["💧 Gestão de Coletas", "📍 Gestão de Pontos", "⚙️ Gestão de Parâmetros"])
    
    # ------------------ COLETA ------------------
    with aba_coleta:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("➕ Adicionar Nova Coleta")
        if df_pontos.empty or df_parametros.empty:
            st.warning("Cadastre pontos e parâmetros primeiro.")
        else:
            with st.form("form_add_coleta"):
                c1, c2 = st.columns(2)
                p_id = c1.selectbox("Ponto", df_pontos['local'].tolist())
                param_id = c1.selectbox("Parâmetro (inclui IQA)", df_parametros['nome'].tolist())
                d_amostra = c2.date_input("Data da Amostra")
                v_amostra = c2.number_input("Valor Registrado", format="%.2f")
                if st.form_submit_button("Salvar Coleta"):
                    db.inserir_coleta(db.obter_id_ponto(p_id), db.obter_id_param(param_id), d_amostra, v_amostra)
                    st.success("Coleta registrada!")
                    st.rerun()
                    
        st.markdown("---")
        st.subheader("✏️/🗑️ Editar ou Excluir Coleta Existente")
        if not df_coletas.empty:
            df_coletas['desc_coleta'] = df_coletas['data_amostra'] + " | " + df_coletas['local'] + " | " + df_coletas['parametro'] + " (" + df_coletas['valor'].astype(str) + ")"
            col_del = st.selectbox("Selecione a coleta:", df_coletas['desc_coleta'].tolist())
            id_col = df_coletas[df_coletas['desc_coleta'] == col_del]['id'].values[0]
            
            col_b1, col_b2 = st.columns(2)
            novo_val = col_b1.number_input("Corrigir Valor", value=float(df_coletas[df_coletas['id']==id_col]['valor'].values[0]))
            
            if col_b1.button("Salvar Correção (Editar)"):
                row = df_coletas[df_coletas['id']==id_col].iloc[0]
                db.atualizar_coleta(id_col, row['ponto_id'], row['param_id'], row['data_amostra'], novo_val)
                st.rerun()
            if col_b2.button("Excluir Coleta Definitivamente"):
                db.deletar_coleta(id_col)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ------------------ PONTOS ------------------
    with aba_pontos:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("➕ Adicionar Novo Ponto")
        with st.form("form_add_ponto", clear_on_submit=True):
            col_p1, col_p2 = st.columns(2)
            cod_p = col_p1.text_input("Código (Ex: PT-01)")
            loc_p = col_p2.text_input("Nome/Local")
            lat_p = col_p1.number_input("Latitude (Y) / UTM", format="%.6f", value=-27.601)
            lon_p = col_p2.number_input("Longitude (X) / UTM", format="%.6f", value=-48.518)
            if st.form_submit_button("Cadastrar Ponto"):
                db.inserir_ponto(cod_p, loc_p, lat_p, lon_p)
                st.rerun()

        st.markdown("---")
        st.subheader("✏️/🗑️ Editar ou Excluir Ponto Existente")
        if not df_pontos.empty:
            pt_edit = st.selectbox("Selecione o ponto:", df_pontos['local'].tolist())
            row_p = df_pontos[df_pontos['local'] == pt_edit].iloc[0]
            
            with st.form("form_edit_ponto"):
                c1, c2 = st.columns(2)
                e_cod = c1.text_input("Código", value=row_p['codigo'])
                e_loc = c2.text_input("Local", value=row_p['local'])
                e_lat = c1.number_input("Latitude", value=float(row_p['latitude']), format="%.6f")
                e_lon = c2.number_input("Longitude", value=float(row_p['longitude']), format="%.6f")
                if st.form_submit_button("Salvar Edição"):
                    db.atualizar_ponto(row_p['id'], e_cod, e_loc, e_lat, e_lon)
                    st.rerun()
            if st.button("Excluir Ponto Definitivamente"):
                db.deletar_ponto(row_p['id'])
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # ------------------ PARÂMETROS ------------------
    with aba_params:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("➕ Adicionar Novo Parâmetro")
        with st.form("form_add_param", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            p_nome = c1.text_input("Nome do Parâmetro")
            p_und = c2.text_input("Unidade (Ex: mg/L)")
            p_lim = c3.text_input("Limite Legal (Opcional - deixe vazio se não houver)")
            
            if st.form_submit_button("Cadastrar Parâmetro"):
                limite_formatado = float(p_lim.replace(",", ".")) if p_lim else None
                db.inserir_parametro(p_nome, p_und, limite_formatado)
                st.rerun()

        st.markdown("---")
        st.subheader("✏️/🗑️ Editar ou Excluir Parâmetro Existente")
        if not df_parametros.empty:
            pa_edit = st.selectbox("Selecione o parâmetro:", df_parametros['nome'].tolist())
            row_pa = df_parametros[df_parametros['nome'] == pa_edit].iloc[0]
            
            with st.form("form_edit_param"):
                c1, c2, c3 = st.columns(3)
                ep_nome = c1.text_input("Nome", value=row_pa['nome'])
                ep_und = c2.text_input("Unidade", value=row_pa['unidade'])
                ep_lim = c3.text_input("Limite", value=str(row_pa['limite_legal']) if pd.notnull(row_pa['limite_legal']) else "")
                
                if st.form_submit_button("Salvar Edição do Parâmetro"):
                    lim_val = float(ep_lim.replace(",", ".")) if ep_lim.strip() and ep_lim != "None" else None
                    db.atualizar_parametro(row_pa['id'], ep_nome, ep_und, lim_val)
                    st.rerun()
            if st.button("Excluir Parâmetro Definitivamente"):
                db.deletar_parametro(row_pa['id'])
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
