import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import database as db

# Inicializa o banco de dados
db.inicializar_banco()

# Configuração da página para ocupar a tela toda
st.set_page_config(page_title="Qualidade da Água - UFSC", layout="wide", page_icon="💧")

# Injeção de CSS para design (Fundo claro, cards pasteis, tabelas zebradas, sem botões gritantes)
st.markdown("""
    <style>
    .stApp { background-color: #FAFAFA; }
    .card {
        background-color: #F0F4F8; 
        border-radius: 10px; 
        padding: 20px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
    th { background-color: #E2E8F0; text-align: left; padding: 10px; }
    td { padding: 10px; border-bottom: 1px solid #E2E8F0; }
    tr:nth-child(even) { background-color: #F8FAFC; }
    tr:hover { background-color: #E2E8F0; }
    .icon-btn { text-decoration: none; font-size: 18px; margin-right: 10px; cursor: pointer; }
    </style>
""", unsafe_allow_html=True)

# Cabeçalho do sistema
st.title("💧 Monitoramento de Qualidade de Águas - UFSC")
st.markdown("Avaliação contínua da saúde hídrica e gestão de resíduos do campus Florianópolis.")

# Carregar dados
df_pontos = db.buscar_pontos()
df_parametros = db.buscar_parametros()
df_coletas = db.buscar_coletas()

# Criando abas
aba_publica, aba_admin = st.tabs(["Visão Geral e Mapa", "Painel Admin"])

# ==========================================
# ÁREA PÚBLICA (VISUALIZAÇÃO)
# ==========================================
with aba_publica:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Análise Temporal")
    
    col1, col2 = st.columns(2)
    with col1:
        if not df_pontos.empty:
            ponto_selecionado = st.selectbox("Selecione o Ponto:", df_pontos['local'].tolist())
        else:
            ponto_selecionado = st.selectbox("Selecione o Ponto:", ["Nenhum ponto cadastrado"])
            
    with col2:
        parametro_selecionado = st.selectbox("Selecione o Parâmetro:", df_parametros['nome'].tolist())

    # Gráficos
    if not df_coletas.empty and ponto_selecionado != "Nenhum ponto cadastrado":
        # Filtrar dados para o gráfico
        df_grafico = df_coletas[(df_coletas['local'] == ponto_selecionado) & (df_coletas['parametro'] == parametro_selecionado)]
        
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            if not df_grafico.empty:
                limite = df_grafico['limite_legal'].iloc[0]
                unidade = df_grafico['unidade'].iloc[0]
                
                fig1 = px.line(df_grafico, x="data_amostra", y="valor", markers=True, 
                               title=f"Evolução: {parametro_selecionado} ({unidade})",
                               labels={"valor": "Valor", "data_amostra": "Data da Coleta"})
                # Linha do Limite Legal
                if pd.notnull(limite):
                    fig1.add_hline(y=limite, line_dash="dash", line_color="red", annotation_text=f"Limite Legal ({limite})")
                
                fig1.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.info("Sem dados suficientes para este parâmetro neste ponto.")
                
        with col_graf2:
            # Gráfico de IQA Simulado (Pode ser adaptado com seu cálculo real depois)
            df_iqa_mock = pd.DataFrame({
                "Data": ["2026-09-01", "2026-10-01", "2026-11-01"],
                "IQA": [65, 72, 80]
            })
            fig2 = px.bar(df_iqa_mock, x="Data", y="IQA", title=f"Evolução do IQA - {ponto_selecionado}", color="IQA", color_continuous_scale="Viridis")
            fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Mapa Interativo
    st.subheader("Mapa de Pontos de Coleta")
    mapa_ufsc = folium.Map(location=[-27.601, -48.518], zoom_start=14) # Coordenadas padrão UFSC Trindade
    
    for _, row in df_pontos.iterrows():
        html_popup = f"""
        <div style="font-family: Arial; width: 150px;">
            <b>{row['codigo']}</b><br>
            {row['local']}<br><br>
            <a href="#" style="background-color:#E2E8F0; padding:5px 10px; border-radius:5px; text-decoration:none; color:black; font-size:12px;">Ver Ponto</a>
        </div>
        """
        folium.Marker(
            [row['latitude'], row['longitude']],
            popup=folium.Popup(html_popup, max_width=200),
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(mapa_ufsc)
        
    st_folium(mapa_ufsc, width=1200, height=400)

    # Registros de Coletas (Árvore Colapsável por Data)
    st.subheader("Registros Históricos")
    if not df_coletas.empty:
        datas_unicas = df_coletas['data_amostra'].unique()
        for data in sorted(datas_unicas, reverse=True):
            with st.expander(f"📁 Coletas do dia: {data}"):
                df_dia = df_coletas[df_coletas['data_amostra'] == data]
                
                # Gerando a tabela zebrada via HTML
                tabela_html = "<table><tr><th>Ponto</th><th>Parâmetro</th><th>Valor Encontrado</th><th>Limite Legal</th></tr>"
                for _, row in df_dia.iterrows():
                    cor_alerta = "color: red; font-weight: bold;" if (pd.notnull(row['limite_legal']) and row['valor'] > row['limite_legal']) else ""
                    tabela_html += f"""
                        <tr>
                            <td>{row['local']}</td>
                            <td>{row['parametro']}</td>
                            <td style="{cor_alerta}">{row['valor']} {row['unidade']}</td>
                            <td>{row['limite_legal']}</td>
                        </tr>
                    """
                tabela_html += "</table>"
                st.markdown(tabela_html, unsafe_allow_html=True)


# ==========================================
# ÁREA ADMIN (INSERÇÃO DE DADOS)
# ==========================================
with aba_admin:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    admin_menu = st.radio("Selecione a ação:", ["Registrar Nova Coleta", "Gerenciar Pontos", "Gerenciar Parâmetros"], horizontal=True)
    
    if admin_menu == "Registrar Nova Coleta":
        st.subheader("Inserir Resultados do Laboratório")
        if df_pontos.empty:
            st.warning("Cadastre primeiro um Ponto de Coleta.")
        else:
            with st.form("form_coleta", clear_on_submit=True):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    dic_pontos = dict(zip(df_pontos['local'], df_pontos['id']))
                    ponto_form = st.selectbox("Ponto de Coleta", list(dic_pontos.keys()))
                    data_form = st.date_input("Data da Amostra")
                with col_f2:
                    dic_params = dict(zip(df_parametros['nome'], df_parametros['id']))
                    param_form = st.selectbox("Parâmetro Analisado", list(dic_params.keys()))
                    valor_form = st.number_input("Valor Encontrado (Use ponto para decimais)", format="%.2f")
                
                salvar = st.form_submit_button("Salvar Medição")
                if salvar:
                    db.inserir_coleta(dic_pontos[ponto_form], dic_params[param_form], data_form, valor_form)
                    st.success(f"Dado salvo com sucesso! {param_form}: {valor_form} no ponto {ponto_form}.")
                    st.rerun()
                    
    elif admin_menu == "Gerenciar Pontos":
        st.subheader("Pontos de Coleta Cadastrados")
        
        # Formulário para novo ponto
        with st.expander("➕ Adicionar Novo Ponto"):
            with st.form("novo_ponto"):
                codigo = st.text_input("Código (Ex: PTO-01)")
                local = st.text_input("Nome do Local (Ex: Wetland Corporate Park)")
                col_lat, col_lon = st.columns(2)
                lat = col_lat.number_input("Latitude", format="%.6f", value=-27.601000)
                lon = col_lon.number_input("Longitude", format="%.6f", value=-48.518000)
                submit_ponto = st.form_submit_button("Cadastrar")
                if submit_ponto:
                    db.inserir_ponto(codigo, local, lat, lon)
                    st.success("Ponto cadastrado!")
                    st.rerun()

        # Tabela HTML Customizada com ícones (sem botões gritantes)
        if not df_pontos.empty:
            tabela_pontos = "<table><tr><th>Código</th><th>Local</th><th>Latitude</th><th>Longitude</th><th>Ações</th></tr>"
            for _, row in df_pontos.iterrows():
                # No Streamlit puro, usar links ou botões dentro de HTML é restrito, 
                # mas representamos os ícones discretos como pedido.
                tabela_pontos += f"""
                    <tr>
                        <td>{row['codigo']}</td>
                        <td>{row['local']}</td>
                        <td>{row['latitude']}</td>
                        <td>{row['longitude']}</td>
                        <td>
                            <span class="icon-btn" title="Editar">✏️</span>
                            <span class="icon-btn" title="Excluir">🗑️</span>
                        </td>
                    </tr>
                """
            tabela_pontos += "</table>"
            st.markdown(tabela_pontos, unsafe_allow_html=True)
            
            # Deletar via Selectbox para contornar limitação do HTML
            del_id = st.selectbox("Selecione um ponto para excluir:", df_pontos['id'].tolist(), format_func=lambda x: df_pontos[df_pontos['id']==x]['local'].values[0])
            if st.button("🗑️ Confirmar Exclusão"):
                db.deletar_ponto(del_id)
                st.rerun()
                
    elif admin_menu == "Gerenciar Parâmetros":
        st.subheader("Limites Legais (CONAMA/ABNT)")
        st.info("Os 12 parâmetros solicitados já foram pré-cadastrados. Nesta tela, você pode editar os limites no futuro.")
        st.dataframe(df_parametros[['nome', 'unidade', 'limite_legal']], use_container_width=True, hide_index=True)

    st.markdown('</div>', unsafe_allow_html=True)
