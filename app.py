import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import database as db

db.inicializar_banco()
st.set_page_config(page_title="Monitoramento Qualidade de Água Córregos UFSC", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F0F4F8; }
    h1, h2, h3, p { color: #003366; }
    .card { background-color: #FFFFFF; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; border-left: 4px solid #00509E; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-family: sans-serif; font-size: 14px;}
    th { color: #003366; border-bottom: 2px solid #E2E8F0; text-align: left; padding: 10px; font-weight: bold;}
    td { padding: 10px; border-bottom: 1px solid #E2E8F0; color: #333; }
    tr:nth-child(even) { background-color: #F8FAFC; }
    tr:hover { background-color: #E2E8F0; }
    .stButton>button { background-color: #00509E !important; color: white !important; border-radius: 4px !important; border: none !important; font-weight: bold !important; width: 100%;}
    .stButton>button:hover { background-color: #003366 !important; }
    </style>
""", unsafe_allow_html=True)

if 'admin' not in st.session_state:
    st.session_state.admin = False

def alternar_admin():
    st.session_state.admin = not st.session_state.admin

st.sidebar.button("Painel Admin" if not st.session_state.admin else "Visão Pública", on_click=alternar_admin)

df_pontos = db.buscar_pontos()
df_parametros = db.buscar_parametros()
df_coletas = db.buscar_coletas()

st.title("Monitoramento Qualidade de Água Córregos UFSC")

if not st.session_state.admin:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    ponto_sel = c1.selectbox("Ponto", df_pontos['local'].tolist() if not df_pontos.empty else [""])
    param_lista = df_parametros[df_parametros['nome'] != 'IQA (Índice de Qualidade da Água)']['nome'].tolist()
    param_sel = c2.selectbox("Parâmetro", param_lista if param_lista else [""])

    if not df_coletas.empty and ponto_sel:
        df_graf = df_coletas[(df_coletas['local'] == ponto_sel) & (df_coletas['parametro'] == param_sel)].sort_values(by="data_amostra")
        df_iqa = df_coletas[(df_coletas['local'] == ponto_sel) & (df_coletas['parametro'] == 'IQA (Índice de Qualidade da Água)')].sort_values(by="data_amostra")
        
        g1, g2 = st.columns([2, 1])
        with g1:
            if not df_graf.empty:
                limite = df_graf['limite_legal'].iloc[0]
                unidade = df_graf['unidade'].iloc[0]
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(x=df_graf["data_amostra"], y=df_graf["valor"], mode='lines+markers+text', 
                                          name=param_sel, text=df_graf["valor"], textposition="top center",
                                          line=dict(color='#00509E', width=2), marker=dict(size=8, color='#00509E')))
                if pd.notnull(limite):
                    fig1.add_hline(y=limite, line_dash="dash", line_color="#FF4B4B", line_width=1.5)
                fig1.update_layout(title=f"{param_sel} ({unidade})", plot_bgcolor="white", margin=dict(t=30, b=0, l=0, r=0))
                st.plotly_chart(fig1, use_container_width=True)
        with g2:
            if not df_iqa.empty:
                fig2 = px.bar(df_iqa, x="data_amostra", y="valor", title="IQA", text="valor")
                fig2.update_traces(marker_color='#00509E')
                fig2.update_layout(plot_bgcolor="white", margin=dict(t=30, b=0, l=0, r=0))
                st.plotly_chart(fig2, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    stadia_api = "af1b2140-1a60-4eec-9983-9406fa69f237"
    url_tiles = f"https://tiles.stadiamaps.com/tiles/alidade_smooth/{{z}}/{{x}}/{{y}}{{r}}.png?api_key={stadia_api}"
    
    mapa = folium.Map(location=[-27.601, -48.518], zoom_start=14, tiles=url_tiles, attr="Stadia Maps")
    for _, row in df_pontos.iterrows():
        html = f"<div style='font-family:sans-serif; width:150px;'><b>{row['codigo']}</b><br>{row['local']}</div>"
        folium.Marker([row['latitude'], row['longitude']], popup=folium.Popup(html, max_width=200), icon=folium.Icon(color='blue')).add_to(mapa)
    st_folium(mapa, width="100%", height=400)
    st.markdown('</div>', unsafe_allow_html=True)

    if not df_coletas.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        for data in sorted(df_coletas['data_amostra'].unique(), reverse=True):
            with st.expander(str(data)):
                df_dia = df_coletas[df_coletas['data_amostra'] == data]
                html_tab = "<table><tr><th>Ponto</th><th>Parâmetro</th><th>Valor</th><th>Limite Legal</th></tr>"
                for _, row in df_dia.iterrows():
                    lim = row['limite_legal'] if pd.notnull(row['limite_legal']) else "-"
                    html_tab += f"<tr><td>{row['local']}</td><td>{row['parametro']}</td><td>{row['valor']} {row['unidade']}</td><td>{lim}</td></tr>"
                html_tab += "</table>"
                st.markdown(html_tab, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

else:
    aba_coleta, aba_pontos, aba_params = st.tabs(["Coletas", "Pontos", "Parâmetros"])
    
    with aba_coleta:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        with st.form("add_col"):
            c1, c2 = st.columns(2)
            p_id = c1.selectbox("Ponto", df_pontos['local'].tolist() if not df_pontos.empty else [])
            param_id = c1.selectbox("Parâmetro", df_parametros['nome'].tolist() if not df_parametros.empty else [])
            d_amostra = c2.date_input("Data")
            v_amostra = c2.number_input("Valor", format="%.2f")
            if st.form_submit_button("Salvar Coleta"):
                db.inserir_coleta(db.obter_id_ponto(p_id), db.obter_id_param(param_id), d_amostra, v_amostra)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        if not df_coletas.empty:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            df_coletas['desc'] = df_coletas['data_amostra'] + " | " + df_coletas['local'] + " | " + df_coletas['parametro'] + " (" + df_coletas['valor'].astype(str) + ")"
            col_del = st.selectbox("Editar/Excluir", df_coletas['desc'].tolist())
            id_col = df_coletas[df_coletas['desc'] == col_del]['id'].values[0]
            cb1, cb2 = st.columns(2)
            nv = cb1.number_input("Novo Valor", value=float(df_coletas[df_coletas['id']==id_col]['valor'].values[0]))
            if cb1.button("Editar"):
                row = df_coletas[df_coletas['id']==id_col].iloc[0]
                db.atualizar_coleta(id_col, row['ponto_id'], row['param_id'], row['data_amostra'], nv)
                st.rerun()
            if cb2.button("Excluir"):
                db.deletar_coleta(id_col)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    with aba_pontos:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        with st.form("add_pt"):
            cp1, cp2 = st.columns(2)
            cod_p = cp1.text_input("Código")
            loc_p = cp2.text_input("Local")
            lat_p = cp1.number_input("Latitude", format="%.6f", value=-27.601)
            lon_p = cp2.number_input("Longitude", format="%.6f", value=-48.518)
            if st.form_submit_button("Salvar Ponto"):
                db.inserir_ponto(cod_p, loc_p, lat_p, lon_p)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        if not df_pontos.empty:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            pt_edit = st.selectbox("Editar/Excluir Ponto", df_pontos['local'].tolist())
            row_p = df_pontos[df_pontos['local'] == pt_edit].iloc[0]
            with st.form("edit_pt"):
                cp1, cp2 = st.columns(2)
                e_cod = cp1.text_input("Código", value=row_p['codigo'])
                e_loc = cp2.text_input("Local", value=row_p['local'])
                e_lat = cp1.number_input("Latitude", value=float(row_p['latitude']), format="%.6f")
                e_lon = cp2.number_input("Longitude", value=float(row_p['longitude']), format="%.6f")
                if st.form_submit_button("Editar Ponto"):
                    db.atualizar_ponto(row_p['id'], e_cod, e_loc, e_lat, e_lon)
                    st.rerun()
            if st.button("Excluir Ponto"):
                db.deletar_ponto(row_p['id'])
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    with aba_params:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        with st.form("add_pa"):
            ca1, ca2, ca3 = st.columns(3)
            p_nome = ca1.text_input("Nome")
            p_und = ca2.text_input("Unidade")
            p_lim = ca3.text_input("Limite")
            if st.form_submit_button("Salvar Parâmetro"):
                lim_val = float(p_lim.replace(",", ".")) if p_lim else None
                db.inserir_parametro(p_nome, p_und, lim_val)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        if not df_parametros.empty:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            pa_edit = st.selectbox("Editar/Excluir Parâmetro", df_parametros['nome'].tolist())
            row_pa = df_parametros[df_parametros['nome'] == pa_edit].iloc[0]
            with st.form("edit_pa"):
                ca1, ca2, ca3 = st.columns(3)
                ep_nome = ca1.text_input("Nome", value=row_pa['nome'])
                ep_und = ca2.text_input("Unidade", value=row_pa['unidade'])
                ep_lim = ca3.text_input("Limite", value=str(row_pa['limite_legal']) if pd.notnull(row_pa['limite_legal']) else "")
                if st.form_submit_button("Editar Parâmetro"):
                    lim_val = float(ep_lim.replace(",", ".")) if ep_lim.strip() and ep_lim != "None" else None
                    db.atualizar_parametro(row_pa['id'], ep_nome, ep_und, lim_val)
                    st.rerun()
            if st.button("Excluir Parâmetro"):
                db.deletar_parametro(row_pa['id'])
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
