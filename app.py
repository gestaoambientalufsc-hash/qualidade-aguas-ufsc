import streamlit as st
import pandas as pd

# Configuração da página para ocupar a tela toda
st.set_page_config(page_title="Qualidade da Água - UFSC", layout="wide")

# Cabeçalho do seu painel
st.title("Monitoramento dos Córregos da UFSC")
st.markdown("Avaliação contínua da saúde hídrica do campus Florianópolis.")

# Criando abas para separar a Área Pública do Painel Admin
aba_mapa, aba_admin = st.tabs(["Visão Geral e Mapa", "Registrar Nova Coleta"])

with aba_mapa:
    st.subheader("Análise Temporal e Mapa")
    
    # Criando colunas para colocar os filtros lado a lado
    col1, col2 = st.columns(2)
    with col1:
        ponto = st.selectbox("Selecione o Ponto:", ["Ponto 1 - Carvoeira", "Ponto 2 - Serrinha"])
    with col2:
        parametro = st.selectbox("Selecione o Parâmetro:", ["DBO", "Nitrogênio Total", "Coliformes", "IQA"])
        
    st.info(f"Aqui entrará o gráfico de linha e o mapa mostrando o {ponto}.")

with aba_admin:
    st.subheader("Inserir Resultados do LIMA")
    
    # Formulário de preenchimento manual (igual você queria)
    with st.form("form_coleta"):
        ponto_admin = st.selectbox("Ponto de Coleta", ["Ponto 1", "Ponto 2"])
        data_coleta = st.date_input("Data da Amostra")
        param_admin = st.selectbox("Parâmetro", ["DBO (mg/L)", "Fósforo Total (mg/L)"])
        valor = st.number_input("Valor Encontrado", format="%.2f")
        
        salvar = st.form_submit_button("Salvar Medição")
        
        if salvar:
            st.success(f"Dado salvo: {valor} para {param_admin} no {ponto_admin}.")
