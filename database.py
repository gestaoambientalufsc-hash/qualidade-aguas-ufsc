import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "aguas_ufsc.db"

def get_conexao():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def inicializar_banco():
    conn = get_conexao()
    cursor = conn.cursor()
    
    # Tabela Pontos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pontos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT,
            local TEXT,
            latitude REAL,
            longitude REAL
        )
    ''')
    
    # Tabela Parâmetros
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parametros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            unidade TEXT,
            limite_legal REAL
        )
    ''')
    
    # Tabela Coletas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS coletas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ponto_id INTEGER,
            parametro_id INTEGER,
            data_amostra DATE,
            valor REAL,
            FOREIGN KEY(ponto_id) REFERENCES pontos(id),
            FOREIGN KEY(parametro_id) REFERENCES parametros(id)
        )
    ''')
    
    # Pré-cadastrar os 12 parâmetros caso o banco seja novo
    cursor.execute("SELECT COUNT(*) FROM parametros")
    if cursor.fetchone()[0] == 0:
        parametros_iniciais = [
            ('Carbono Orgânico Total', 'mg/L', 5.0),
            ('Coliforme Total', 'NMP/100mL', 1000.0),
            ('Coliformes Termotolerantes', 'NMP/100mL', 200.0),
            ('Condutividade Eletrolítica', 'µS/cm', 100.0),
            ('DBO', 'mg/L', 5.0),
            ('Fósforo Total', 'mg/L', 0.1),
            ('Nitrogênio Total', 'mg/L', 10.0),
            ('Oxigênio dissolvido', 'mg/L', 5.0),
            ('pH', '-', 9.0),
            ('Sólido Total Seco à 104ºC', 'mg/L', 500.0),
            ('Temperatura da Amostra', 'ºC', 30.0),
            ('Turbidez', 'UNT', 40.0)
        ]
        cursor.executemany("INSERT INTO parametros (nome, unidade, limite_legal) VALUES (?, ?, ?)", parametros_iniciais)
    
    conn.commit()
    conn.close()

# Funções auxiliares para buscar dados
def buscar_pontos():
    conn = get_conexao()
    df = pd.read_sql_query("SELECT * FROM pontos", conn)
    conn.close()
    return df

def buscar_parametros():
    conn = get_conexao()
    df = pd.read_sql_query("SELECT * FROM parametros", conn)
    conn.close()
    return df

def buscar_coletas():
    conn = get_conexao()
    query = '''
        SELECT c.id, c.data_amostra, p.codigo, p.local, par.nome AS parametro, par.unidade, c.valor, par.limite_legal 
        FROM coletas c
        JOIN pontos p ON c.ponto_id = p.id
        JOIN parametros par ON c.parametro_id = par.id
        ORDER BY c.data_amostra DESC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# Funções de inserção
def inserir_ponto(codigo, local, lat, lon):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pontos (codigo, local, latitude, longitude) VALUES (?, ?, ?, ?)", (codigo, local, lat, lon))
    conn.commit()
    conn.close()

def inserir_coleta(ponto_id, parametro_id, data, valor):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO coletas (ponto_id, parametro_id, data_amostra, valor) VALUES (?, ?, ?, ?)", (ponto_id, parametro_id, data, valor))
    conn.commit()
    conn.close()

def deletar_ponto(ponto_id):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pontos WHERE id = ?", (ponto_id,))
    conn.commit()
    conn.close()
