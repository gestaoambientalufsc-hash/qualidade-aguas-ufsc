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
    
    # Pré-cadastrar os parâmetros (Incluindo IQA para ser preenchido)
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

# --- BUSCAS ---
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

def obter_id_param(nome_param):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM parametros WHERE nome = ?", (nome_param,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

# --- INSERÇÕES ---
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

# --- ATUALIZAÇÕES (EDITAR) ---
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

def atualizar_coleta(id_coleta, ponto_id, param_id, data, valor):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("UPDATE coletas SET ponto_id=?, parametro_id=?, data_amostra=?, valor=? WHERE id=?", (ponto_id, param_id, data, valor, id_coleta))
    conn.commit()
    conn.close()

# --- EXCLUSÕES ---
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

def deletar_coleta(id_coleta):
    conn = get_conexao()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM coletas WHERE id = ?", (id_coleta,))
    conn.commit()
    conn.close()
