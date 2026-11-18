"""Persistência SQLite do monitoramento de águas da UFSC.

Compatível com o banco anterior ``aguas_ufsc.db``: a inicialização adiciona
colunas/tabelas sem apagar registros existentes. Faça backup antes do deploy.

IMPORTANTE: referências legais importadas do esquema antigo ficam NÃO validadas.
"""
from __future__ import annotations

import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime

import pandas as pd

DB_NAME = os.getenv("AGUAS_DB_PATH", "aguas_ufsc.db")


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
    filtro = " WHERE ativo=1" if ativos is True else " WHERE ativo=0" if ativos is False else ""
    return _df("SELECT * FROM pontos" + filtro + " ORDER BY codigo COLLATE NOCASE")


def buscar_parametros(ativos=None):
    filtro = " WHERE ativo=1" if ativos is True else " WHERE ativo=0" if ativos is False else ""
    return _df("SELECT * FROM parametros" + filtro + " ORDER BY nome COLLATE NOCASE")


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
    """Atualiza as 5 faixas de maneira atômica, sem lacunas ou sobreposições."""
    # Preserva a ordem institucional das categorias: Péssima → Ótima.
    itens = [(int(x["id"]), float(x["min"]), float(x["max"])) for x in faixas]
    if len(itens) != 5 or any(not math.isfinite(y) for _, a, b in itens for y in (a, b)):
        raise ValueError("É necessário informar cinco faixas numéricas válidas.")
    if abs(itens[0][1]) > 1e-8 or abs(itens[-1][2] - 100) > 1e-8:
        raise ValueError("As faixas precisam cobrir todo o intervalo de 0 a 100.")
    for i, (_, a, b) in enumerate(itens):
        if a < 0 or b > 100 or a >= b:
            raise ValueError("Cada faixa deve ter mínimo menor que máximo, entre 0 e 100.")
        if i > 0 and abs(a - itens[i - 1][2]) > 1e-8:
            raise ValueError("As faixas não podem ter lacunas ou sobreposições.")
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
                aplicabilidade,referencia_validada,compoe_iqa,peso_iqa,curva_iqa)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", valores)


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


def excluir_amostra(amostra_id):
    with conexao() as con:
        con.execute("DELETE FROM coletas WHERE amostra_id=?", (int(amostra_id),))
        con.execute("DELETE FROM amostras WHERE id=?", (int(amostra_id),))
