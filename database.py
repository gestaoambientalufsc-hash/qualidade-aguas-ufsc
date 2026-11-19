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
