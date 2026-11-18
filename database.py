import sqlite3
import pandas as pd

DB_NAME = "aguas_ufsc.db"

def get_conexao():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def inicializar_banco():
    conn = get_conexao()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pontos (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, local TEXT, latitude REAL, longitude REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS parametros (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, unidade TEXT, limite_legal REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS coletas (id INTEGER PRIMARY KEY AUTOINCREMENT, ponto_id INTEGER, parametro_id INTEGER, data_amostra DATE, valor REAL, FOREIGN KEY(ponto_id) REFERENCES pontos(id), FOREIGN KEY(parametro_id) REFERENCES parametros(id))''')
    
    # Nova tabela para as faixas dinâmicas do IQA
    cursor.execute('''CREATE TABLE IF NOT EXISTS faixas_iqa (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, valor_min REAL, valor_max REAL, cor_texto TEXT, cor_bg TEXT, cor_grafico TEXT)''')
    
    # Preencher faixas padrão caso seja a primeira vez
    cursor.execute("SELECT COUNT(*) FROM faixas_iqa")
    if cursor.fetchone()[0] == 0:
        faixas = [
            ('Péssima', 0, 20, '#E53E3E', '#FFF5F5', 'rgba(229, 62, 62, 0.08)'),
            ('Ruim', 20, 36, '#DD6B20', '#FFF5F5', 'rgba(221, 107, 32, 0.08)'),
            ('Regular', 36, 51, '#D69E2E', '#FFFFF0', 'rgba(214, 158, 46, 0.08)'),
            ('Boa', 51, 80, '#38A169', '#E6FFFA', 'rgba(56, 161, 105, 0.08)'),
            ('Ótima', 80, 100, '#2F855A', '#F0FFF4', 'rgba(47, 133, 90, 0.12)')
        ]
        cursor.executemany("INSERT INTO faixas_iqa (nome, valor_min, valor_max, cor_texto, cor_bg, cor_grafico) VALUES (?, ?, ?, ?, ?, ?)", faixas)
    
    cursor.execute("SELECT COUNT(*) FROM parametros")
    if cursor.fetchone()[0] == 0:
        parametros_iniciais = [
            ('IQA (Índice de Qualidade da Água)', '-', None),
            ('Carbono Orgânico Total', 'mg/L', None),
            ('Coliforme Total', 'NMP/100mL', None),
            ('Coliformes Termotolerantes', 'NMP/100mL', 1000.0),
            ('Condutividade Eletrolítica', 'µS/cm', None),
            ('DBO', 'mg/L', 5.0),
            ('Fósforo Total', 'mg/L', 0.05),
            ('Nitrogênio Total', 'mg/L', 10.0),
            ('Oxigênio dissolvido', 'mg/L', 5.0),
            ('pH', '-', 9.0),
            ('Sólido Total Seco à 104ºC', 'mg/L', 500.0),
            ('Temperatura da Amostra', 'ºC', 30.0),
            ('Turbidez', 'NTU', 100.0)
        ]
        cursor.executemany("INSERT INTO parametros (nome, unidade, limite_legal) VALUES (?, ?, ?)", parametros_iniciais)
    
    conn.commit()
    conn.close()

# Funções das Faixas do IQA
def buscar_faixas_iqa():
    conn = get_conexao()
    df = pd.read_sql_query("SELECT * FROM faixas_iqa ORDER BY id", conn)
    conn.close()
    return df

def atualizar_faixa_iqa(id_faixa, val_min, val_max):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("UPDATE faixas_iqa SET valor_min=?, valor_max=? WHERE id=?", (val_min, val_max, id_faixa))
    conn.commit()
    conn.close()

# Funções base existentes
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
        SELECT c.id, c.data_amostra, p.id as ponto_id, p.codigo, p.local, par.id as param_id, par.nome AS parametro, par.unidade, c.valor, par.limite_legal 
        FROM coletas c
        JOIN pontos p ON c.ponto_id = p.id
        JOIN parametros par ON c.parametro_id = par.id
        ORDER BY c.data_amostra DESC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def obter_id_ponto(local_nome):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM pontos WHERE local = ?", (local_nome,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def inserir_ponto(codigo, local, lat, lon):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pontos (codigo, local, latitude, longitude) VALUES (?, ?, ?, ?)", (codigo, local, lat, lon))
    conn.commit()
    conn.close()

def inserir_parametro(nome, unidade, limite):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO parametros (nome, unidade, limite_legal) VALUES (?, ?, ?)", (nome, unidade, limite))
    conn.commit()
    conn.close()

def inserir_coleta(ponto_id, param_id, data, valor):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO coletas (ponto_id, parametro_id, data_amostra, valor) VALUES (?, ?, ?, ?)", (ponto_id, param_id, data, valor))
    conn.commit()
    conn.close()

def atualizar_ponto(id_ponto, codigo, local, lat, lon):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("UPDATE pontos SET codigo=?, local=?, latitude=?, longitude=? WHERE id=?", (codigo, local, lat, lon, id_ponto))
    conn.commit()
    conn.close()

def atualizar_parametro(id_param, nome, unidade, limite):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("UPDATE parametros SET nome=?, unidade=?, limite_legal=? WHERE id=?", (nome, unidade, limite, id_param))
    conn.commit()
    conn.close()

def deletar_ponto(id_ponto):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pontos WHERE id = ?", (id_ponto,))
    conn.commit()
    conn.close()

def deletar_parametro(id_param):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM parametros WHERE id = ?", (id_param,))
    conn.commit()
    conn.close()
