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
