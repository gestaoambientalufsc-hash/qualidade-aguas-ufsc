"""Persistência SQLite do monitoramento de águas da UFSC.

Compatível com o banco anterior ``aguas_ufsc.db``: a inicialização adiciona
colunas/tabelas sem apagar registros existentes. Faça backup antes do deploy.

IMPORTANTE: referências legais importadas do esquema antigo ficam NÃO validadas.
"""
from __future__ import annotations

import math
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime

import pandas as pd

DB_NAME = os.getenv("AGUAS_DB_PATH", "aguas_ufsc.db")

# Ordem da tabela original do laboratório (novos parâmetros entram ao final).
PARAMETROS_ORDEM_LAB = (
    'Carbono Orgânico Total',
    'Coliforme Total',
    'Coliformes Termotolerantes',
    'Condutividade Eletrolítica',
    'DBO',
    'Fósforo Total',
    'Nitrogênio Total',
    'Oxigênio dissolvido',
    'pH',
    'Sólido Total Seco à 104ºC',
    'Temperatura da Amostra',
    'Turbidez',
)


@contextmanager
def conexao():
    con = sqlite3.connect(DB_NAME, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def get_conexao():
    """Interface de consulta legada; o chamador deve fechar a conexão."""
    con = sqlite3.connect(DB_NAME, timeout=20)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _colunas(con, tabela):
    return {x["name"] for x in con.execute(f"PRAGMA table_info({tabela})")}


def _adicionar_coluna(con, tabela, nome, definicao):
    if nome not in _colunas(con, tabela):
        con.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {definicao}")


def inicializar_banco():
    with conexao() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS pontos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, local TEXT,
            latitude REAL, longitude REAL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS parametros (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, unidade TEXT,
            limite_legal REAL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS coletas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ponto_id INTEGER,
            parametro_id INTEGER, data_amostra DATE, valor REAL,
            FOREIGN KEY(ponto_id) REFERENCES pontos(id),
            FOREIGN KEY(parametro_id) REFERENCES parametros(id)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS faixas_iqa (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT,
            valor_min REAL, valor_max REAL, cor_texto TEXT,
            cor_bg TEXT, cor_grafico TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS amostras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ponto_id INTEGER NOT NULL,
            data_amostra TEXT NOT NULL,
            identificador TEXT DEFAULT '',
            observacoes TEXT DEFAULT '',
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(ponto_id) REFERENCES pontos(id)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY, valor TEXT NOT NULL DEFAULT ''
        )""")
        _adicionar_coluna(con, "pontos", "ativo", "INTEGER NOT NULL DEFAULT 1")
        _adicionar_coluna(con, "parametros", "ativo", "INTEGER NOT NULL DEFAULT 1")
        _adicionar_coluna(con, "parametros", "tipo_limite", "TEXT NOT NULL DEFAULT 'nenhum'")
        _adicionar_coluna(con, "parametros", "limite_min", "REAL")
        _adicionar_coluna(con, "parametros", "limite_max", "REAL")
        _adicionar_coluna(con, "parametros", "base_normativa", "TEXT NOT NULL DEFAULT ''")
        _adicionar_coluna(con, "parametros", "aplicabilidade", "TEXT NOT NULL DEFAULT ''")
        _adicionar_coluna(con, "parametros", "referencia_validada", "INTEGER NOT NULL DEFAULT 0")
        _adicionar_coluna(con, "parametros", "compoe_iqa", "INTEGER NOT NULL DEFAULT 0")
        _adicionar_coluna(con, "parametros", "peso_iqa", "REAL")
        _adicionar_coluna(con, "parametros", "curva_iqa", "TEXT NOT NULL DEFAULT ''")
        _adicionar_coluna(con, "parametros", "ordem_exibicao", "INTEGER")
        _adicionar_coluna(con, "coletas", "amostra_id", "INTEGER REFERENCES amostras(id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_coletas_ponto_data ON coletas(ponto_id, data_amostra)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_coletas_amostra ON coletas(amostra_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_amostras_ponto_data ON amostras(ponto_id, data_amostra)")

        if con.execute("SELECT COUNT(*) FROM faixas_iqa").fetchone()[0] == 0:
            con.executemany("""INSERT INTO faixas_iqa
                (nome,valor_min,valor_max,cor_texto,cor_bg,cor_grafico)
                VALUES (?,?,?,?,?,?)""", [
                ("Péssima", 0, 20, "#C0392B", "#FFF0ED", "rgba(192,57,43,0.06)"),
                ("Ruim", 20, 36, "#C25B21", "#FFF2E9", "rgba(194,91,33,0.06)"),
                ("Regular", 36, 51, "#946200", "#FFF8E2", "rgba(148,98,0,0.06)"),
                ("Boa", 51, 80, "#187A5E", "#EAF7F1", "rgba(24,122,94,0.06)"),
                ("Ótima", 80, 100, "#10664D", "#E4F5ED", "rgba(16,102,77,0.08)"),
            ])
        if con.execute("SELECT COUNT(*) FROM parametros").fetchone()[0] == 0:
            valores = [
                ("IQA (Índice de Qualidade da Água)", "-", None),
                ("Carbono Orgânico Total", "mg/L", None),
                ("Coliforme Total", "NMP/100mL", None),
                ("Coliformes Termotolerantes", "NMP/100mL", 1000.0),
                ("Condutividade Eletrolítica", "µS/cm", None),
                ("DBO", "mg/L", 5.0),
                ("Fósforo Total", "mg/L", 0.05),
                ("Nitrogênio Total", "mg/L", 10.0),
                ("Oxigênio dissolvido", "mg/L", 5.0),
                ("pH", "-", 9.0),
                ("Sólido Total Seco à 104ºC", "mg/L", 500.0),
                ("Temperatura da Amostra", "ºC", 30.0),
                ("Turbidez", "NTU", 100.0),
            ]
            con.executemany("INSERT INTO parametros (nome,unidade,limite_legal) VALUES (?,?,?)", valores)

        # O IQA deve estar disponível no cadastro, mesmo em bancos criados
        # quando já existiam outros parâmetros ou quando foi arquivado.
        iqa = con.execute("SELECT id, ativo FROM parametros WHERE nome LIKE 'IQA (%' ORDER BY id LIMIT 1").fetchone()
        if iqa is None:
            con.execute("INSERT INTO parametros (nome, unidade, limite_legal, ativo) VALUES (?, ?, NULL, 1)",
                        ("IQA (Índice de Qualidade da Água)", "-"))
        elif not bool(iqa["ativo"]):
            con.execute("UPDATE parametros SET ativo=1 WHERE id=?", (int(iqa["id"]),))

        # Ordenação estável, sem alterar IDs, medições ou nomes já cadastrados.
        # Atribuída somente a parâmetros ainda sem ordem (migração idempotente).
        sem_ordem = con.execute(
            "SELECT id, nome FROM parametros WHERE ordem_exibicao IS NULL ORDER BY id"
        ).fetchall()
        if sem_ordem:
            fixos = {nome.casefold(): indice for indice, nome in enumerate(PARAMETROS_ORDEM_LAB, 1)}
            ja_usados = {int(r[0]) for r in con.execute(
                "SELECT ordem_exibicao FROM parametros WHERE ordem_exibicao IS NOT NULL"
                " AND ordem_exibicao > 0"
            )}
            proxima = max([12, *ja_usados]) + 1
            for item in sem_ordem:
                nome = str(item["nome"]).strip().casefold()
                if nome.startswith("iqa ("):
                    ordem = 0  # IQA é preenchido em campo independente.
                elif nome in fixos and fixos[nome] not in ja_usados:
                    ordem = fixos[nome]
                else:
                    while proxima in ja_usados:
                        proxima += 1
                    ordem = proxima
                    proxima += 1
                con.execute("UPDATE parametros SET ordem_exibicao=? WHERE id=?", (ordem, item["id"]))
                if ordem > 0:
                    ja_usados.add(ordem)

        # Migração conservadora executada uma só vez. Se o usuário depois
        # selecionar "sem referência", não devemos restaurar o limite legado.
        ja_migrado = con.execute("SELECT 1 FROM configuracoes WHERE chave='limites_legados_migrados'").fetchone()
        if not ja_migrado:
            con.execute("""UPDATE parametros SET
                tipo_limite=CASE WHEN LOWER(nome) LIKE 'oxigênio dissolvido%'
                                    THEN 'minimo' ELSE 'maximo' END,
                limite_min=CASE WHEN LOWER(nome) LIKE 'oxigênio dissolvido%'
                                    THEN limite_legal ELSE NULL END,
                limite_max=CASE WHEN LOWER(nome) LIKE 'oxigênio dissolvido%'
                                    THEN NULL ELSE limite_legal END
                WHERE limite_legal IS NOT NULL AND limite_min IS NULL
                      AND limite_max IS NULL AND tipo_limite='nenhum'
                      AND referencia_validada=0""")
            con.execute("INSERT INTO configuracoes(chave,valor) VALUES ('limites_legados_migrados','1')")

        # Agrupa medições antigas por ponto+data; esquema legado não distinguia
        # duas amostras coletadas no mesmo ponto e dia.
        grupos = con.execute("""SELECT ponto_id, data_amostra FROM coletas
            WHERE amostra_id IS NULL GROUP BY ponto_id, data_amostra""").fetchall()
        for grupo in grupos:
            ponto_id, dia = grupo["ponto_id"], str(grupo["data_amostra"])
            if not con.execute("SELECT id FROM pontos WHERE id=?", (ponto_id,)).fetchone():
                continue  # dado órfão antigo: não alterar silenciosamente
            cur = con.execute("""INSERT INTO amostras (ponto_id,data_amostra,observacoes)
                VALUES (?,?,'Importada do banco anterior')""", (ponto_id, dia))
            con.execute("""UPDATE coletas SET amostra_id=?
                WHERE ponto_id=? AND data_amostra=? AND amostra_id IS NULL""",
                (cur.lastrowid, ponto_id, dia))

        for chave, valor in {
            "iqa_metodologia": "Não informada",
            "iqa_fonte": "",
            "iqa_observacoes": "IQA informado manualmente. O sistema não calcula automaticamente o índice.",
        }.items():
            con.execute("INSERT OR IGNORE INTO configuracoes (chave,valor) VALUES (?,?)", (chave, valor))


def _df(sql, args=()):
    with conexao() as con:
        return pd.read_sql_query(sql, con, params=args)


def buscar_pontos(ativos=None):
    """Lista pontos na ordem natural do código: 1, 2, ..., 10, 11."""
    filtro = " WHERE ativo=1" if ativos is True else " WHERE ativo=0" if ativos is False else ""
    pontos = _df("SELECT * FROM pontos" + filtro)
    if pontos.empty:
        return pontos

    # Preserva códigos alfanuméricos (P1, P2, P10) e valores numéricos.
    # Apenas a ordem de apresentação muda: IDs e registros permanecem intactos.
    def chave_natural(codigo):
        partes = re.split(r"(\d+)", str(codigo).casefold())
        return tuple((1, int(p)) if p.isdigit() else (0, p) for p in partes)

    ordem = sorted(range(len(pontos)), key=lambda i: chave_natural(pontos.iloc[i]["codigo"]))
    return pontos.iloc[ordem].reset_index(drop=True)


def buscar_parametros(ativos=None):
    filtro = " WHERE ativo=1" if ativos is True else " WHERE ativo=0" if ativos is False else ""
    return _df("SELECT * FROM parametros" + filtro + " ORDER BY ordem_exibicao ASC, id ASC")


def buscar_coletas():
    return _df("""SELECT c.id, c.amostra_id, c.data_amostra,
        p.id AS ponto_id,p.codigo,p.local,par.id AS param_id,
        par.nome AS parametro,par.unidade,c.valor,par.limite_legal,
        par.tipo_limite,par.limite_min,par.limite_max,
        par.base_normativa,par.aplicabilidade,par.referencia_validada
        FROM coletas c
        JOIN pontos p ON p.id=c.ponto_id
        JOIN parametros par ON par.id=c.parametro_id
        ORDER BY c.data_amostra DESC,c.id DESC""")


def buscar_amostras():
    return _df("""SELECT a.id,a.ponto_id,a.data_amostra,a.identificador,
        a.observacoes,p.codigo,p.local,COUNT(c.id) AS qtd_parametros
        FROM amostras a JOIN pontos p ON p.id=a.ponto_id
        LEFT JOIN coletas c ON c.amostra_id=a.id
        GROUP BY a.id ORDER BY a.data_amostra DESC,a.id DESC""")


def buscar_valores_amostra(amostra_id):
    return _df("SELECT parametro_id, valor FROM coletas WHERE amostra_id=?", (int(amostra_id),))


TITULO_REFERENCIA_PADRAO = "Resolução CONAMA 357/2005 - águas doces classe 2"


def buscar_titulo_referencia():
    """Título de referência para identificação nos resumos; não valida limites."""
    with conexao() as con:
        r = con.execute("SELECT valor FROM configuracoes WHERE chave=?",
                        ("titulo_referencia_ambiental",)).fetchone()
    return str(r["valor"]) if r is not None else TITULO_REFERENCIA_PADRAO


def salvar_titulo_referencia(titulo):
    titulo = str(titulo).strip()
    if not titulo or len(titulo) > 250:
        raise ValueError("Informe um título de referência de até 250 caracteres.")
    with conexao() as con:
        con.execute("INSERT INTO configuracoes(chave, valor) VALUES (?, ?) "
                    "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                    ("titulo_referencia_ambiental", titulo))


def buscar_faixas_iqa():
    return _df("SELECT * FROM faixas_iqa ORDER BY id")


def buscar_configuracao_iqa():
    with conexao() as con:
        return {r["chave"]: r["valor"] for r in con.execute("SELECT * FROM configuracoes")}


def salvar_configuracao_iqa(metodologia, fonte, observacoes):
    with conexao() as con:
        for chave, valor in {
            "iqa_metodologia": metodologia.strip(),
            "iqa_fonte": fonte.strip(),
            "iqa_observacoes": observacoes.strip(),
        }.items():
            con.execute("INSERT OR REPLACE INTO configuracoes (chave,valor) VALUES (?,?)", (chave, valor))


def atualizar_faixas_iqa(faixas):
    """Atualiza as 5 faixas, aceitando fronteiras contíguas ou inteiros consecutivos."""
    # Preserva a ordem institucional das categorias: Péssima → Ótima.
    itens = [(int(x["id"]), float(x["min"]), float(x["max"])) for x in faixas]
    if len(itens) != 5 or any(not math.isfinite(y) for _, a, b in itens for y in (a, b)):
        raise ValueError("É necessário informar cinco faixas numéricas válidas.")
    if abs(itens[0][1]) > 1e-8 or abs(itens[-1][2] - 100) > 1e-8:
        raise ValueError("As faixas precisam cobrir todo o intervalo de 0 a 100.")
    for i, (_, a, b) in enumerate(itens):
        if a < 0 or b > 100 or a >= b:
            raise ValueError("Cada faixa deve ter mínimo menor que máximo, entre 0 e 100.")
        if i > 0:
            anterior_max = itens[i - 1][2]
            contiguo = abs(a - anterior_max) <= 1e-8
            consecutivo_inteiro = (
                abs(a - round(a)) <= 1e-8
                and abs(anterior_max - round(anterior_max)) <= 1e-8
                and abs(a - anterior_max - 1) <= 1e-8
            )
            if not (contiguo or consecutivo_inteiro):
                raise ValueError(
                    "As faixas devem ser contínuas ou usar inteiros consecutivos "
                    "(ex.: 0–25, 26–50)."
                )
    with conexao() as con:
        ids = [r["id"] for r in con.execute("SELECT id FROM faixas_iqa ORDER BY id")]
        if [x[0] for x in itens] != ids:
            raise ValueError("As categorias de IQA não correspondem às cadastradas.")
        con.executemany("UPDATE faixas_iqa SET valor_min=?, valor_max=? WHERE id=?",
                        [(a, b, id_) for id_, a, b in itens])


def _validar_ponto(codigo, local, latitude, longitude, ignorar_id=None):
    codigo, local = codigo.strip(), local.strip()
    if not codigo or not local:
        raise ValueError("Informe código e nome do local.")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Latitude ou longitude fora dos intervalos geográficos.")
    with conexao() as con:
        repetido = con.execute("SELECT id FROM pontos WHERE LOWER(codigo)=LOWER(?) AND id!=?",
                               (codigo, ignorar_id or -1)).fetchone()
        if repetido:
            raise ValueError("Já existe um ponto com esse código.")
    return codigo, local


def inserir_ponto(codigo, local, lat, lon):
    codigo, local = _validar_ponto(codigo, local, lat, lon)
    with conexao() as con:
        con.execute("INSERT INTO pontos(codigo,local,latitude,longitude) VALUES (?,?,?,?)", (codigo, local, lat, lon))


def atualizar_ponto(id_ponto, codigo, local, lat, lon):
    codigo, local = _validar_ponto(codigo, local, lat, lon, int(id_ponto))
    with conexao() as con:
        con.execute("UPDATE pontos SET codigo=?,local=?,latitude=?,longitude=? WHERE id=?",
                    (codigo, local, lat, lon, int(id_ponto)))


def importar_pontos_lote(pontos):
    """Grava em transação única e ignora códigos preexistentes, sem alterar coletas."""
    preparados = []
    codigos_csv = set()
    for indice, ponto in enumerate(pontos, start=2):
        codigo = str(ponto['codigo']).strip()
        local = str(ponto['local']).strip()
        lat, lon = float(ponto['latitude']), float(ponto['longitude'])
        if not codigo or not local or not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f'Linha {indice}: código, local ou coordenadas inválidos.')
        if codigo.casefold() in codigos_csv:
            raise ValueError(f'Código duplicado dentro do CSV: {codigo}')
        codigos_csv.add(codigo.casefold())
        preparados.append((codigo, local, lat, lon))
    adicionados = ignorados = 0
    with conexao() as con:
        existentes = {str(row[0]).casefold() for row in con.execute('SELECT codigo FROM pontos')}
        for codigo, local, lat, lon in preparados:
            if codigo.casefold() in existentes:
                ignorados += 1
                continue
            con.execute('INSERT INTO pontos (codigo,local,latitude,longitude) VALUES (?,?,?,?)',
                        (codigo, local, lat, lon))
            existentes.add(codigo.casefold())
            adicionados += 1
    return adicionados, ignorados


def alterar_status_ponto(id_ponto, ativo):
    with conexao() as con:
        con.execute("UPDATE pontos SET ativo=? WHERE id=?", (int(bool(ativo)), int(id_ponto)))


def salvar_parametro(id_param, nome, unidade, tipo, minimo, maximo,
                     norma, aplicabilidade, validada, compoe_iqa=False,
                     peso_iqa=None, curva_iqa=""):
    nome, unidade = nome.strip(), unidade.strip()
    norma, aplicabilidade = norma.strip(), aplicabilidade.strip()
    if not nome or not unidade:
        raise ValueError("Nome e unidade são obrigatórios.")
    if tipo not in ("nenhum", "minimo", "maximo", "intervalo"):
        raise ValueError("Tipo de limite inválido.")
    if tipo in ("minimo", "intervalo") and minimo is None:
        raise ValueError("Informe o limite mínimo.")
    if tipo in ("maximo", "intervalo") and maximo is None:
        raise ValueError("Informe o limite máximo.")
    minimo = None if tipo not in ("minimo", "intervalo") else float(minimo)
    maximo = None if tipo not in ("maximo", "intervalo") else float(maximo)
    if minimo is not None and not math.isfinite(minimo) or maximo is not None and not math.isfinite(maximo):
        raise ValueError("Os limites precisam ser números finitos.")
    if tipo == "intervalo" and minimo > maximo:
        raise ValueError("O limite mínimo não pode superar o máximo.")
    if validada and tipo != "nenhum" and (not norma or not aplicabilidade):
        raise ValueError("Para validar uma referência, informe base normativa e aplicabilidade.")
    if compoe_iqa and peso_iqa is not None and (not math.isfinite(float(peso_iqa)) or float(peso_iqa) <= 0):
        raise ValueError("O peso do IQA precisa ser positivo.")
    with conexao() as con:
        repetido = con.execute("SELECT id FROM parametros WHERE LOWER(nome)=LOWER(?) AND id != ?",
                               (nome, int(id_param) if id_param else -1)).fetchone()
        if repetido:
            raise ValueError("Já existe um parâmetro com esse nome.")
        valores = (nome, unidade, tipo, minimo, maximo, norma, aplicabilidade,
                   int(bool(validada)) if tipo != "nenhum" else 0,
                   int(bool(compoe_iqa)), float(peso_iqa) if compoe_iqa and peso_iqa is not None else None,
                   curva_iqa.strip())
        if id_param:
            con.execute("""UPDATE parametros SET nome=?,unidade=?,tipo_limite=?,limite_min=?,
                limite_max=?,base_normativa=?,aplicabilidade=?,referencia_validada=?,
                compoe_iqa=?,peso_iqa=?,curva_iqa=? WHERE id=?""", (*valores, int(id_param)))
        else:
            con.execute("""INSERT INTO parametros
                (nome,unidade,tipo_limite,limite_min,limite_max,base_normativa,
                aplicabilidade,referencia_validada,compoe_iqa,peso_iqa,curva_iqa,ordem_exibicao)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    *valores,
                    0 if nome.casefold().startswith("iqa (") else max(
                        12, con.execute("SELECT COALESCE(MAX(ordem_exibicao), 12) "
                                        "FROM parametros WHERE ordem_exibicao > 0").fetchone()[0]
                    ) + 1,
                ))


def alterar_status_parametro(id_param, ativo):
    with conexao() as con:
        con.execute("UPDATE parametros SET ativo=? WHERE id=?", (int(bool(ativo)), int(id_param)))


def buscar_duplicadas(ponto_id, data_amostra, ignorar_amostra=None):
    dia = _data_iso(data_amostra)
    with conexao() as con:
        return con.execute("""SELECT COUNT(*) FROM amostras
            WHERE ponto_id=? AND data_amostra=? AND id!=?""",
            (int(ponto_id), dia, int(ignorar_amostra or -1))).fetchone()[0]


def _data_iso(dia):
    if isinstance(dia, (date, datetime)):
        return dia.isoformat()[:10]
    try:
        return date.fromisoformat(str(dia)[:10]).isoformat()
    except ValueError as exc:
        raise ValueError("Data da amostra inválida.") from exc


def _validar_valores(valores):
    saida = {}
    for param_id, valor in valores.items():
        if valor is None or str(valor).strip() == "":
            continue
        try:
            numero = float(str(valor).replace(",", "."))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Resultado inválido para o parâmetro {param_id}.") from exc
        if not math.isfinite(numero):
            raise ValueError("Não são permitidos resultados infinitos ou NaN.")
        saida[int(param_id)] = numero
    if not saida:
        raise ValueError("Preencha pelo menos um parâmetro analisado.")
    return saida


def salvar_amostra(ponto_id, data_amostra, valores, identificador="", observacoes="",
                   permitir_mesma_data=False, amostra_id=None):
    dia = _data_iso(data_amostra)
    if dia > date.today().isoformat():
        raise ValueError("A data da coleta não pode estar no futuro.")
    numeros = _validar_valores(valores)
    if not permitir_mesma_data and buscar_duplicadas(ponto_id, dia, amostra_id):
        raise ValueError("Já existe uma coleta para esse ponto nessa data. Confira antes de continuar.")
    with conexao() as con:
        if not con.execute("SELECT 1 FROM pontos WHERE id=?", (int(ponto_id),)).fetchone():
            raise ValueError("Ponto inexistente.")
        if amostra_id:
            item = con.execute("SELECT id FROM amostras WHERE id=?", (int(amostra_id),)).fetchone()
            if not item:
                raise ValueError("Coleta inexistente.")
            con.execute("""UPDATE amostras SET ponto_id=?,data_amostra=?,identificador=?,observacoes=?
                WHERE id=?""", (int(ponto_id), dia, identificador.strip(), observacoes.strip(), int(amostra_id)))
            con.execute("DELETE FROM coletas WHERE amostra_id=?", (int(amostra_id),))
            id_ = int(amostra_id)
        else:
            cur = con.execute("""INSERT INTO amostras(ponto_id,data_amostra,identificador,observacoes)
                VALUES (?,?,?,?)""", (int(ponto_id), dia, identificador.strip(), observacoes.strip()))
            id_ = cur.lastrowid
        con.executemany("""INSERT INTO coletas(amostra_id,ponto_id,parametro_id,data_amostra,valor)
            VALUES (?,?,?,?,?)""", [(id_, int(ponto_id), p, dia, val) for p, val in numeros.items()])
        return id_


def atualizar_data_amostra(amostra_id, nova_data):
    """Atualiza a data de uma amostra e de todas as medições vinculadas, sem alterar valores."""
    dia = _data_iso(nova_data)
    if dia > date.today().isoformat():
        raise ValueError("A data da coleta não pode estar no futuro.")

    with conexao() as con:
        amostra = con.execute(
            "SELECT id, ponto_id FROM amostras WHERE id=?",
            (int(amostra_id),),
        ).fetchone()
        if amostra is None:
            raise ValueError("A coleta selecionada não existe.")

        duplicadas = con.execute(
            """SELECT COUNT(*) FROM amostras
               WHERE ponto_id=? AND data_amostra=? AND id!=?""",
            (int(amostra["ponto_id"]), dia, int(amostra_id)),
        ).fetchone()[0]
        if duplicadas:
            raise ValueError(
                "Já existe outra coleta para esse ponto na data informada. "
                "Escolha outra data para evitar juntar registros diferentes."
            )

        con.execute(
            "UPDATE amostras SET data_amostra=? WHERE id=?",
            (dia, int(amostra_id)),
        )
        con.execute(
            "UPDATE coletas SET data_amostra=? WHERE amostra_id=?",
            (dia, int(amostra_id)),
        )


def salvar_iqa_amostra(amostra_id, novo_valor):
    """Insere ou atualiza o IQA de uma amostra sem alterar os demais resultados.

    Utiliza uma única transação e impede a criação de um segundo IQA na mesma amostra.
    """
    try:
        numero = float(novo_valor)
    except (ValueError, TypeError) as exc:
        raise ValueError("Informe um valor numérico para o IQA.") from exc
    if not math.isfinite(numero) or not 0 <= numero <= 100:
        raise ValueError("O IQA deve estar entre 0 e 100.")

    with conexao() as con:
        amostra = con.execute(
            "SELECT id, ponto_id, data_amostra FROM amostras WHERE id=?",
            (int(amostra_id),),
        ).fetchone()
        if amostra is None:
            raise ValueError("A coleta selecionada não existe.")
        parametro = con.execute(
            "SELECT id FROM parametros WHERE nome LIKE 'IQA (%' ORDER BY id LIMIT 1"
        ).fetchone()
        if parametro is None:
            raise ValueError("O parâmetro IQA não está cadastrado.")
        pid = int(parametro["id"])
        existente = con.execute(
            "SELECT id FROM coletas WHERE amostra_id=? AND parametro_id=? ORDER BY id LIMIT 1",
            (int(amostra_id), pid),
        ).fetchone()
        if existente is not None:
            con.execute(
                "UPDATE coletas SET valor=? WHERE id=?",
                (numero, int(existente["id"])),
            )
        else:
            con.execute(
                """INSERT INTO coletas(amostra_id, ponto_id, parametro_id, data_amostra, valor)
                   VALUES (?, ?, ?, ?, ?)""",
                (int(amostra_id), int(amostra["ponto_id"]), pid,
                 str(amostra["data_amostra"]), numero),
            )


def atualizar_valor_coleta(coleta_id, novo_valor):
    """Edita um único parâmetro medido sem modificar outras coletas ou parâmetros."""
    numero = float(novo_valor)
    if not math.isfinite(numero):
        raise ValueError("O resultado deve ser um número finito.")
    with conexao() as con:
        cur = con.execute("UPDATE coletas SET valor=? WHERE id=?", (numero, int(coleta_id)))
        if cur.rowcount != 1:
            raise ValueError("Resultado não encontrado para edição.")


def excluir_amostra(amostra_id):
    with conexao() as con:
        con.execute("DELETE FROM coletas WHERE amostra_id=?", (int(amostra_id),))
        con.execute("DELETE FROM amostras WHERE id=?", (int(amostra_id),))
