import os
import json
import random
import time
import threading
import mysql.connector
import yt_dlp
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, send_from_directory, jsonify
)
import logging
import queue
import requests  # Para enviar requisições HTTP para desligar o Flask

#############################################################################
#                         CONFIGURAÇÃO DE LOG
#############################################################################

log_queue = queue.Queue()

class TkinterHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
tk_handler = TkinterHandler(log_queue)
tk_handler.setFormatter(log_formatter)
logger.addHandler(tk_handler)

#############################################################################
#                         CLASSE DE CONFIGURAÇÃO
#############################################################################

class Config:
    def __init__(self):
        self.host = ''
        self.port = 0
        self.user = ''
        self.password = ''
        self.dbname = ''
        self.ffmpeg_path = ''
        self.file_path = ''
        self.flask_port = 5000

config = Config()

#############################################################################
#                         FUNÇÕES DE CONFIGURAÇÃO
#############################################################################

CONFIG_FILE = 'config.json'

def load_db_config():
    """Carrega as configurações do banco de dados a partir do arquivo config.json."""
    if not os.path.exists(CONFIG_FILE):
        return False
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            config.host = data.get('host', '')
            config.port = data.get('port', 0)
            config.user = data.get('user', '')
            config.password = data.get('password', '')
            config.dbname = data.get('dbname', '')
            config.ffmpeg_path = data.get('ffmpeg_path', '')
            config.file_path = data.get('file_path', '')
            config.flask_port = data.get('flask_port', 5000)
        logger.info("Configurações de banco de dados carregadas do arquivo.")
        return True
    except Exception as e:
        logger.error(f"Erro ao carregar configurações do arquivo: {e}")
        return False

def save_db_config():
    """Salva as configurações do banco de dados no arquivo config.json."""
    try:
        data = {
            'host': config.host,
            'port': config.port,
            'user': config.user,
            'password': config.password,
            'dbname': config.dbname,
            'ffmpeg_path': config.ffmpeg_path,
            'file_path': config.file_path,
            'flask_port': config.flask_port
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        logger.info("Configurações de banco de dados salvas no arquivo.")
    except Exception as e:
        logger.error(f"Erro ao salvar configurações no arquivo: {e}")

def get_db_connection_dynamic():
    """Conecta ao banco de dados usando as configurações dinâmicas."""
    return mysql.connector.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.dbname
    )

def ensure_indexes():
    """Garante que todos os índices necessários existam na tabela 'config'."""
    try:
        conn = get_db_connection_dynamic()
        if not conn:
            return
        cursor = conn.cursor()

        required_indexes = {
            'PRIMARY': ['id'],
            'idx_host': ['host'],
            'idx_user': ['user']
        }
        cursor.execute("SHOW INDEX FROM config;")
        existing_indexes = {}
        for row in cursor.fetchall():
            key_name = row[2]
            column_name = row[4]
            if key_name not in existing_indexes:
                existing_indexes[key_name] = []
            existing_indexes[key_name].append(column_name)

        for index_name, columns in required_indexes.items():
            if index_name not in existing_indexes:
                if index_name == 'PRIMARY':
                    cursor.execute("ALTER TABLE config ADD PRIMARY KEY (id);")
                    logger.info("Chave primária adicionada à tabela 'config'.")
                else:
                    cols = ', '.join(columns)
                    cursor.execute(f"ALTER TABLE config ADD INDEX {index_name} ({cols});")
                    logger.info(f"Índice '{index_name}' adicionado à tabela 'config'.")
            else:
                if existing_indexes[index_name] != columns:
                    cursor.execute(f"ALTER TABLE config DROP INDEX {index_name};")
                    if index_name == 'PRIMARY':
                        cursor.execute("ALTER TABLE config ADD PRIMARY KEY (id);")
                        logger.info("Chave primária atualizada na tabela 'config'.")
                    else:
                        cols = ', '.join(columns)
                        cursor.execute(f"ALTER TABLE config ADD INDEX {index_name} ({cols});")
                        logger.info(f"Índice '{index_name}' atualizado na tabela 'config'.")

        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        logger.error(f"Erro ao garantir índices na tabela 'config': {err}")
    except Exception as e:
        logger.error(f"Erro inesperado ao garantir índices na tabela 'config': {e}")

def initialize_config_table():
    """Cria a tabela de configuração se não existir e adiciona campos faltantes."""
    try:
        conn = get_db_connection_dynamic()
        if not conn:
            return
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                id INT AUTO_INCREMENT PRIMARY KEY,
                host VARCHAR(255),
                port INT,
                user VARCHAR(255),
                password VARCHAR(255),
                dbname VARCHAR(255),
                ffmpeg_path VARCHAR(255),
                file_path VARCHAR(255),
                flask_port INT
            )
        """)
        conn.commit()
        logger.info("Tabela 'config' inicializada com sucesso.")

        required_fields = {
            'host': 'VARCHAR(255)',
            'port': 'INT',
            'user': 'VARCHAR(255)',
            'password': 'VARCHAR(255)',
            'dbname': 'VARCHAR(255)',
            'ffmpeg_path': 'VARCHAR(255)',
            'file_path': 'VARCHAR(255)',
            'flask_port': 'INT'
        }

        cursor.execute("DESCRIBE config")
        existing_fields = {row[0] for row in cursor.fetchall()}

        for field, field_type in required_fields.items():
            if field not in existing_fields:
                alter_sql = f"ALTER TABLE config ADD COLUMN {field} {field_type}"
                cursor.execute(alter_sql)
                conn.commit()
                logger.info(f"Campo '{field}' adicionado à tabela 'config'.")

        cursor.close()
        conn.close()
        ensure_indexes()
    except mysql.connector.Error as err:
        logger.error(f"Erro ao inicializar a tabela de configuração: {err}")
    except Exception as e:
        logger.error(f"Erro inesperado ao inicializar a tabela de configuração: {e}")

def get_config_from_db():
    """Recupera a configuração do banco de dados."""
    try:
        conn = get_db_connection_dynamic()
        if not conn:
            return False
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM config LIMIT 1")
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            config.host = row['host']
            config.port = row['port']
            config.user = row['user']
            config.password = row['password']
            config.dbname = row['dbname']
            config.ffmpeg_path = row['ffmpeg_path']
            config.file_path = row['file_path']
            config.flask_port = row['flask_port']
            logger.info("Configurações carregadas do banco de dados.")
            return True
        else:
            logger.info("Nenhuma configuração encontrada no banco de dados.")
            return False
    except mysql.connector.Error as err:
        logger.error(f"Erro ao obter configurações do banco de dados: {err}")
        return False
    except Exception as e:
        logger.error(f"Erro inesperado ao obter configurações do banco de dados: {e}")
        return False

def save_config_to_db():
    """Salva a configuração no banco de dados."""
    try:
        conn = get_db_connection_dynamic()
        if not conn:
            return
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM config")
        (count,) = cursor.fetchone()
        if count == 0:
            cursor.execute("""
                INSERT INTO config 
                (host, port, user, password, dbname, ffmpeg_path, file_path, flask_port) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                config.host,
                config.port,
                config.user,
                config.password,
                config.dbname,
                config.ffmpeg_path,
                config.file_path,
                config.flask_port
            ))
            logger.info("Nova configuração inserida no banco de dados.")
        else:
            cursor.execute("""
                UPDATE config SET 
                host=%s, port=%s, user=%s, password=%s, dbname=%s, 
                ffmpeg_path=%s, file_path=%s, flask_port=%s WHERE id=1
            """, (
                config.host,
                config.port,
                config.user,
                config.password,
                config.dbname,
                config.ffmpeg_path,
                config.file_path,
                config.flask_port
            ))
            logger.info("Configuração existente atualizada no banco de dados.")
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        logger.error(f"Erro ao salvar configurações no banco de dados: {err}")
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar configurações no banco de dados: {e}")

#############################################################################
#                             INTERFACE TKINTER
#############################################################################

class ConfigApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Configurações do Sistema")
        self.create_widgets()
        self.flask_thread = None
        self.flask_running = False

        if load_db_config():
            self.execute_flask()

    def create_widgets(self):
        sql_frame = ttk.LabelFrame(self.root, text="Configuração SQL")
        sql_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ttk.Label(sql_frame, text="Host:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.host_entry = ttk.Entry(sql_frame, width=30)
        self.host_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(sql_frame, text="Porta:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.port_entry = ttk.Entry(sql_frame, width=30)
        self.port_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(sql_frame, text="Usuário:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.user_entry = ttk.Entry(sql_frame, width=30)
        self.user_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(sql_frame, text="Senha:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.password_entry = ttk.Entry(sql_frame, width=30, show="*")
        self.password_entry.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(sql_frame, text="Nome do Banco:").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.dbname_entry = ttk.Entry(sql_frame, width=30)
        self.dbname_entry.grid(row=4, column=1, padx=5, pady=5)

        other_frame = ttk.LabelFrame(self.root, text="Outras Configurações")
        other_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        ttk.Label(other_frame, text="Caminho do FFmpeg:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.ffmpeg_entry = ttk.Entry(other_frame, width=50)
        self.ffmpeg_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(other_frame, text="Caminho dos Arquivos:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.file_path_entry = ttk.Entry(other_frame, width=50)
        self.file_path_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(other_frame, text="Porta do Flask:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.flask_port_entry = ttk.Entry(other_frame, width=30)
        self.flask_port_entry.grid(row=2, column=1, padx=5, pady=5)

        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")

        self.save_button = ttk.Button(button_frame, text="Salvar", command=self.save_config)
        self.save_button.grid(row=0, column=0, padx=5, pady=5)

        self.execute_button = ttk.Button(button_frame, text="Executar", command=self.execute_flask)
        self.execute_button.grid(row=0, column=1, padx=5, pady=5)

        self.stop_button = ttk.Button(button_frame, text="Parar Serviço", command=self.stop_flask)
        self.stop_button.grid(row=0, column=2, padx=5, pady=5)

        log_frame = ttk.LabelFrame(self.root, text="Logs")
        log_frame.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")

        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=15)
        self.log_text.pack(fill='both', expand=True)

        self.root.grid_rowconfigure(3, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.load_existing_config()
        self.update_logs()

    def load_existing_config(self):
        if load_db_config():
            self.host_entry.insert(0, config.host)
            self.port_entry.insert(0, str(config.port))
            self.user_entry.insert(0, config.user)
            self.password_entry.insert(0, config.password)
            self.dbname_entry.insert(0, config.dbname)
            self.ffmpeg_entry.insert(0, config.ffmpeg_path)
            self.file_path_entry.insert(0, config.file_path)
            self.flask_port_entry.insert(0, str(config.flask_port))
        else:
            logger.info("Por favor, insira as configurações iniciais.")

    def save_config(self):
        try:
            config.host = self.host_entry.get().strip()
            config.port = int(self.port_entry.get().strip())
            config.user = self.user_entry.get().strip()
            config.password = self.password_entry.get().strip()
            config.dbname = self.dbname_entry.get().strip()
            config.ffmpeg_path = self.ffmpeg_entry.get().strip()
            config.file_path = self.file_path_entry.get().strip()
            config.flask_port = int(self.flask_port_entry.get().strip())

            if not all([config.host, config.port, config.user, config.dbname, config.ffmpeg_path, config.file_path, config.flask_port]):
                raise ValueError("Todos os campos devem ser preenchidos.")

            save_db_config()

            try:
                conn = get_db_connection_dynamic()
                conn.close()
                logger.info("Conexão com o banco de dados bem-sucedida.")
            except mysql.connector.Error as err:
                logger.error(f"Erro ao conectar ao banco de dados com as novas configurações: {err}")
                messagebox.showerror("Erro de Conexão", f"Falha ao conectar ao banco de dados: {err}")
                return

            initialize_config_table()
            messagebox.showinfo("Sucesso", "Configurações salvas e tabela 'config' inicializada com sucesso!")
        except ValueError as ve:
            logger.error(f"Validação de dados falhou: {ve}")
            messagebox.showerror("Erro de Convalidação", str(ve))
        except mysql.connector.Error as err:
            logger.error(f"Erro ao salvar configurações no banco de dados: {err}")
            messagebox.showerror("Erro de Banco de Dados", f"Falha ao salvar configurações no banco de dados: {err}")
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")
            messagebox.showerror("Erro", f"Falha ao salvar configurações: {e}")

    def execute_flask(self):
        if self.flask_running:
            messagebox.showwarning("Atenção", "O servidor Flask já está em execução.")
            return

        if not load_db_config():
            messagebox.showerror("Erro", "Por favor, salve as configurações antes de executar o Flask.")
            return

        initialize_config_table()
        self.flask_thread = threading.Thread(target=run_flask_app, daemon=True)
        self.flask_thread.start()
        self.flask_running = True
        logger.info("Servidor Flask iniciado.")

    def stop_flask(self):
        if not self.flask_running:
            messagebox.showwarning("Atenção", "O servidor Flask não está em execução.")
            return
        try:
            shutdown_url = f"http://localhost:{config.flask_port}/shutdown"
            response = requests.post(shutdown_url)
            if response.status_code == 200:
                logger.info("Solicitação de desligamento do Flask enviada com sucesso.")
                self.flask_running = False
                messagebox.showinfo("Sucesso", "Servidor Flask desligado com sucesso.")
            else:
                logger.error(f"Falha ao desligar o Flask: {response.text}")
                messagebox.showerror("Erro", f"Falha ao desligar o Flask: {response.text}")
        except requests.exceptions.ConnectionError:
            logger.error("Não foi possível conectar ao servidor Flask para desligar.")
            messagebox.showerror("Erro", "Não foi possível conectar ao servidor Flask para desligar.")
        except Exception as e:
            logger.error(f"Erro ao tentar desligar o Flask: {e}")
            messagebox.showerror("Erro", f"Erro ao tentar desligar o Flask: {e}")

    def update_logs(self):
        while not log_queue.empty():
            try:
                record = log_queue.get_nowait()
                self.log_text.configure(state='normal')
                self.log_text.insert(tk.END, record + '\n')
                self.log_text.configure(state='disabled')
                self.log_text.yview(tk.END)
            except queue.Empty:
                pass
        self.root.after(100, self.update_logs)

#############################################################################
#                           FUNÇÕES ADICIONAIS
#############################################################################

def run_flask_app():
    try:
        t = threading.Thread(target=processar_fila_loop, daemon=True)
        t.start()
        app.run(debug=False, host='0.0.0.0', port=config.flask_port)
        logger.info("Servidor Flask foi desligado.")
    except Exception as e:
        logger.error(f"Erro ao executar o servidor Flask: {e}")

#############################################################################
#                          CONFIGURAÇÃO FLASK
#############################################################################

app = Flask(__name__)
app.secret_key = 'CHAVE_SECRETA_QUALQUER'

def get_db_connection():
    try:
        return get_db_connection_dynamic()
    except mysql.connector.Error as err:
        logger.error(f"Erro ao conectar ao banco de dados: {err}")
        return None

#############################################################################
#                  FUNÇÕES AUXILIARES DE BANCO (TABELA usuario)
#############################################################################

def get_usuario_info(usuario):
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT usuario, senha, diretorio FROM usuario WHERE usuario = %s", (usuario,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception as e:
        logger.error(f"Erro ao obter informações do usuário: {e}")
        return None

def get_diretorio_do_usuario(usuario):
    info = get_usuario_info(usuario)
    if info:
        return info['diretorio']
    return None

#############################################################################
#                  FUNÇÕES AUXILIARES DE BANCO (TABELA fila)
#############################################################################

def ja_tem_baixando():
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fila WHERE status = 'baixando'")
        (count,) = cursor.fetchone()
        cursor.close()
        conn.close()
        return (count > 0)
    except Exception as e:
        logger.error(f"Erro ao verificar status 'baixando' na fila: {e}")
        return False

def pegar_proximo_em_fila():
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor(dictionary=True)
        sql = """SELECT id, usuario, caminho 
                 FROM fila
                 WHERE status = 'em fila'
                 ORDER BY id ASC
                 LIMIT 1"""
        cursor.execute(sql)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return (row['id'], row['usuario'], row['caminho'])
        return None
    except Exception as e:
        logger.error(f"Erro ao pegar próximo em fila: {e}")
        return None

def atualizar_status_fila(id_registro, novo_status):
    try:
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()
        sql = "UPDATE fila SET status = %s WHERE id = %s"
        cursor.execute(sql, (novo_status, id_registro))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao atualizar status da fila: {e}")

def listar_fila(usuario):
    try:
        conn = get_db_connection()
        if not conn:
            return []
        cursor = conn.cursor(dictionary=True)
        sql = "SELECT id, usuario, caminho, status FROM fila WHERE usuario = %s"
        cursor.execute(sql, (usuario,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Erro ao listar fila: {e}")
        return []

def inserir_fila(usuario, caminho):
    try:
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()
        sql = "INSERT INTO fila (usuario, caminho, status) VALUES (%s, %s, %s)"
        cursor.execute(sql, (usuario, caminho, "em fila"))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Item inserido na fila para o usuário '{usuario}'.")
    except Exception as e:
        logger.error(f"Erro ao inserir na fila: {e}")

#############################################################################
#                  FUNÇÕES AUXILIARES DE BANCO (TABELA favorites)
#############################################################################

def adicionar_favorito(usuario, musica):
    try:
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()
        sql = "INSERT INTO favorites (usuario, musica) VALUES (%s, %s)"
        cursor.execute(sql, (usuario, musica))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Música '{musica}' adicionada aos favoritos do usuário '{usuario}'.")
    except mysql.connector.IntegrityError:
        logger.warning(f"Música '{musica}' já está nos favoritos do usuário '{usuario}'.")
    except Exception as e:
        logger.error(f"Erro ao adicionar favorito: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def remover_favorito(usuario, musica):
    try:
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()
        sql = "DELETE FROM favorites WHERE usuario = %s AND musica = %s"
        cursor.execute(sql, (usuario, musica))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Música '{musica}' removida dos favoritos do usuário '{usuario}'.")
    except Exception as e:
        logger.error(f"Erro ao remover favorito: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def esta_favorito(usuario, musica):
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        sql = "SELECT COUNT(*) FROM favorites WHERE usuario = %s AND musica = %s"
        cursor.execute(sql, (usuario, musica))
        (count,) = cursor.fetchone()
        cursor.close()
        conn.close()
        return count > 0
    except Exception as e:
        logger.error(f"Erro ao verificar favorito: {e}")
        return False

def listar_favoritos(usuario):
    try:
        conn = get_db_connection()
        if not conn:
            return []
        cursor = conn.cursor()
        sql = "SELECT musica FROM favorites WHERE usuario = %s"
        cursor.execute(sql, (usuario,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Erro ao listar favoritos: {e}")
        return []

#############################################################################
#                  FUNÇÕES AUXILIARES DE BANCO (PLAYLISTS)
#############################################################################

def criar_playlist(usuario, nome_playlist):
    """
    Cria uma nova playlist para o usuário, caso ainda não exista com esse nome.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        # Verifica se já existe
        cursor.execute("SELECT COUNT(*) FROM playlist WHERE usuario=%s AND nome=%s",
                       (usuario, nome_playlist))
        (count,) = cursor.fetchone()
        if count == 0:
            cursor.execute("INSERT INTO playlist (usuario, nome) VALUES (%s, %s)",
                           (usuario, nome_playlist))
            conn.commit()
            logger.info(f"Playlist '{nome_playlist}' criada para '{usuario}'.")
        else:
            logger.info(f"Playlist '{nome_playlist}' já existe para '{usuario}'.")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erro ao criar playlist: {e}")
        return False

def get_playlist_id(usuario, nome_playlist):
    """ Retorna o ID da playlist, ou None se não encontrar. """
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM playlist WHERE usuario=%s AND nome=%s",
                       (usuario, nome_playlist))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return row[0]
        return None
    except Exception as e:
        logger.error(f"Erro ao obter ID da playlist: {e}")
        return None

def adicionar_musica_playlist(playlist_id, musica):
    """
    Adiciona a música na tabela playlist_musica, se não estiver presente.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()
        # Verifica se já existe
        cursor.execute(
            "SELECT COUNT(*) FROM playlist_musica WHERE playlist_id=%s AND musica=%s",
            (playlist_id, musica)
        )
        (count,) = cursor.fetchone()
        if count == 0:
            cursor.execute(
                "INSERT INTO playlist_musica (playlist_id, musica) VALUES (%s, %s)",
                (playlist_id, musica)
            )
            conn.commit()
            logger.info(f"Música '{musica}' adicionada na playlist (ID={playlist_id}).")
        else:
            logger.info(f"Música '{musica}' já existe na playlist (ID={playlist_id}).")
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao adicionar música na playlist: {e}")

def remover_musica_playlist(playlist_id, musica):
    """
    Remove a música da tabela playlist_musica.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM playlist_musica WHERE playlist_id=%s AND musica=%s",
            (playlist_id, musica)
        )
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Música '{musica}' removida da playlist (ID={playlist_id}).")
    except Exception as e:
        logger.error(f"Erro ao remover música da playlist: {e}")

def listar_playlists_do_usuario(usuario):
    """
    Retorna uma lista de dicionários: [ {'id': 1, 'nome': 'Rock'}, ... ]
    """
    try:
        conn = get_db_connection()
        if not conn:
            return []
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, nome FROM playlist WHERE usuario=%s", (usuario,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Erro ao listar playlists do usuário: {e}")
        return []

def listar_musicas_da_playlist(playlist_id):
    """
    Retorna todas as músicas vinculadas a uma playlist.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return []
        cursor = conn.cursor()
        cursor.execute("SELECT musica FROM playlist_musica WHERE playlist_id=%s", (playlist_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Erro ao listar músicas da playlist: {e}")
        return []

#############################################################################
#                      FUNÇÃO DE DOWNLOAD (yt-dlp)
#############################################################################

def baixar_videos_para_mp3(playlist_url, pasta_destino):
    try:
        if not os.path.exists(pasta_destino):
            os.makedirs(pasta_destino)

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(pasta_destino, '%(title)s.%(ext)s'),
            'writethumbnail': True,
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                },
                {
                    'key': 'FFmpegThumbnailsConvertor',
                    'format': 'jpg'
                },
            ],
            'ffmpeg_location': config.ffmpeg_path,
            'quiet': False,
            'ignoreerrors': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([playlist_url])
        logger.info(f"Download concluído para URL: {playlist_url}")
    except Exception as e:
        logger.error(f"Erro ao baixar vídeos: {e}")
        raise e

#############################################################################
#                     LOOP EM BACKGROUND: PROCESSAR FILA
#############################################################################

def processar_fila_loop():
    while True:
        try:
            conn = get_db_connection()
            if not conn:
                logger.error("Conexão com o banco de dados falhou. Retentando em 10 segundos.")
                time.sleep(10)
                continue
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, usuario, caminho FROM fila WHERE status = 'em fila'")
            registros_em_fila = cursor.fetchall()
            cursor.close()
            conn.close()

            if registros_em_fila:
                logger.info(f"{len(registros_em_fila)} item(ns) em fila. Iniciando processamento...")
                threads = []

                for registro in registros_em_fila:
                    id_reg = registro['id']
                    usuario = registro['usuario']
                    caminho = registro['caminho']
                    pasta_destino = get_diretorio_do_usuario(usuario)
                    if not pasta_destino:
                        logger.error(f"Não encontrei 'diretorio' para usuario '{usuario}'.")
                        atualizar_status_fila(id_reg, 'Erro')
                        continue

                    thread = threading.Thread(target=processar_download, args=(id_reg, caminho, usuario, pasta_destino))
                    threads.append(thread)
                    thread.start()

                for thread in threads:
                    thread.join()

        except Exception as e:
            logger.error(f"Erro no loop de processamento: {e}")

        time.sleep(10)

def processar_download(id_reg, caminho, usuario, pasta_destino):
    try:
        logger.info(f"Iniciando download para usuário '{usuario}' com URL: {caminho}")
        atualizar_status_fila(id_reg, 'baixando')
        baixar_videos_para_mp3(caminho, pasta_destino)
        atualizar_status_fila(id_reg, 'Baixado')
        logger.info(f"Download concluído para ID {id_reg}.")
    except Exception as e:
        logger.error(f"Falha no download para ID {id_reg}: {e}")
        atualizar_status_fila(id_reg, 'Erro')

#############################################################################
#                  ROTAS PARA FAVORITOS
#############################################################################

@app.route('/play_music/<musica>')
def play_music(musica):
    if 'usuario' not in session:
        return jsonify({'status': 'error', 'message': 'Usuário não está logado.'}), 401

    diretorio_usuario = session.get('diretorio')
    if not diretorio_usuario:
        return jsonify({'status': 'error', 'message': 'Diretório não definido.'}), 400

    musica_path = os.path.join(diretorio_usuario, musica)
    if not os.path.isfile(musica_path):
        return jsonify({'status': 'error', 'message': 'Arquivo não encontrado.'}), 404

    return send_from_directory(diretorio_usuario, musica)

@app.route('/toggle_favorite', methods=['POST'])
def toggle_favorite():
    if 'usuario' not in session:
        return jsonify({'status': 'error', 'message': 'Usuário não está logado.'}), 401

    data = request.get_json()
    musica = data.get('musica')
    if not musica:
        return jsonify({'status': 'error', 'message': 'Música não especificada.'}), 400

    usuario = session['usuario']
    if esta_favorito(usuario, musica):
        remover_favorito(usuario, musica)
        return jsonify({'status': 'removed', 'message': 'Favorito removido.'})
    else:
        adicionar_favorito(usuario, musica)
        return jsonify({'status': 'added', 'message': 'Favorito adicionado.'})

@app.route('/favorites')
def favorites():
    if 'usuario' not in session:
        flash('Você precisa estar logado.', 'error')
        return redirect(url_for('login'))

    usuario_logado = session['usuario']
    favoritos = listar_favoritos(usuario_logado)
    return render_template('favorites.html', favoritos=favoritos, usuario=usuario_logado)

#############################################################################
#                  ROTAS PARA PLAYLISTS
#############################################################################

@app.route('/create_playlist', methods=['POST'])
def create_playlist_route():
    """
    Recebe JSON com: { 'playlistName': 'Rock' }
    Cria uma nova playlist para o usuário logado, se não existir.
    """
    if 'usuario' not in session:
        return jsonify({'status': 'error', 'message': 'Usuário não está logado.'}), 401
    data = request.get_json()
    playlist_name = data.get('playlistName')
    if not playlist_name:
        return jsonify({'status': 'error', 'message': 'Nome da playlist não informado.'}), 400

    usuario = session['usuario']
    ok = criar_playlist(usuario, playlist_name)
    if ok:
        return jsonify({'status': 'success', 'message': f"Playlist '{playlist_name}' criada/atualizada."})
    else:
        return jsonify({'status': 'error', 'message': 'Não foi possível criar a playlist.'}), 500

@app.route('/add_to_playlist', methods=['POST'])
def add_to_playlist():
    """
    Recebe JSON com: { 'playlistName': 'Rock', 'musica': 'test.mp3' }
    Adiciona a música à playlist do usuário, criando a playlist se não existir.
    """
    if 'usuario' not in session:
        return jsonify({'status': 'error', 'message': 'Usuário não está logado.'}), 401
    data = request.get_json()
    playlist_name = data.get('playlistName')
    musica = data.get('musica')

    if not playlist_name or not musica:
        return jsonify({'status': 'error', 'message': 'Dados insuficientes (playlistName, musica).'}), 400

    usuario = session['usuario']
    # Se a playlist não existir, cria
    criar_playlist(usuario, playlist_name)
    # Agora obtém ID
    p_id = get_playlist_id(usuario, playlist_name)
    if p_id:
        adicionar_musica_playlist(p_id, musica)
        return jsonify({'status': 'success', 'message': f"Música '{musica}' adicionada na playlist '{playlist_name}'."})
    else:
        return jsonify({'status': 'error', 'message': 'Não foi possível adicionar a música na playlist.'}), 500

@app.route('/user_playlists', methods=['GET'])
def user_playlists():
    """
    Retorna as playlists do usuário logado em JSON.
    """
    if 'usuario' not in session:
        return jsonify([])  # Ou retornar erro
    usuario = session['usuario']
    playlists = listar_playlists_do_usuario(usuario)  # [{'id':1,'nome':'Rock'}...]
    return jsonify(playlists)

@app.route('/get_playlist_songs/<int:playlist_id>', methods=['GET'])
def get_playlist_songs(playlist_id):
    """
    Retorna as músicas de uma playlist específica.
    """
    if 'usuario' not in session:
        return jsonify([])
    songs = listar_musicas_da_playlist(playlist_id)
    return jsonify(songs)

#############################################################################
#                  ROTAS PARA PESQUISA E SUGESTÕES
#############################################################################

@app.route('/search_suggestions', methods=['GET'])
def search_suggestions():
    if 'usuario' not in session:
        return jsonify([])
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])

    usuario = session['usuario']
    diretorio_usuario = session['diretorio']
    try:
        all_musicas = [
            f for f in os.listdir(diretorio_usuario)
            if f.lower().endswith(('.mp3', '.wav', '.ogg'))
        ]
    except FileNotFoundError:
        all_musicas = []
    matching_musicas = [m for m in all_musicas if query in m.lower()]
    return jsonify(matching_musicas[:10])

@app.route('/search')
def search():
    if 'usuario' not in session:
        flash('Você precisa estar logado.', 'error')
        return redirect(url_for('login'))
    query = request.args.get('query', '').strip().lower()
    if not query:
        flash('Por favor, insira um termo de pesquisa.', 'warning')
        return redirect(url_for('index'))

    usuario = session['usuario']
    diretorio_usuario = session['diretorio']
    try:
        all_musicas = [
            f for f in os.listdir(diretorio_usuario)
            if f.lower().endswith(('.mp3', '.wav', '.ogg'))
        ]
    except FileNotFoundError:
        all_musicas = []

    matching_musicas = [m for m in all_musicas if query in m.lower()]
    matching_musicas.sort()
    favoritos = listar_favoritos(usuario)

    return render_template(
        'search.html',
        query=query,
        matching_musicas=matching_musicas,
        usuario=usuario,
        favoritos=favoritos
    )

#############################################################################
#                       ROTAS FLASK (LOGIN, SIGNUP, ETC.)
#############################################################################

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        info = get_usuario_info(usuario)
        if info and info['senha'] == senha:
            session['usuario'] = usuario
            session['diretorio'] = info['diretorio']
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos!', 'error')
            return redirect(url_for('login'))
    else:
        return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        info = get_usuario_info(usuario)
        if info:
            flash('Usuário já existe. Escolha outro nome.', 'error')
            return redirect(url_for('signup'))

        diretorio_usuario = os.path.join(config.file_path, usuario)
        if not os.path.exists(config.file_path):
            os.makedirs(config.file_path)
        if not os.path.exists(diretorio_usuario):
            os.makedirs(diretorio_usuario)

        try:
            conn = get_db_connection()
            if not conn:
                flash('Erro ao conectar ao banco de dados.', 'error')
                return redirect(url_for('signup'))
            cursor = conn.cursor()
            sql = "INSERT INTO usuario (usuario, senha, diretorio) VALUES (%s, %s, %s)"
            cursor.execute(sql, (usuario, senha, diretorio_usuario))
            conn.commit()
            cursor.close()
            conn.close()
            logger.info(f"Usuário '{usuario}' criado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao criar usuário: {e}")
            flash('Erro ao criar usuário.', 'error')
            return redirect(url_for('signup'))

        flash('Usuário criado com sucesso! Faça login.', 'success')
        return redirect(url_for('login'))
    else:
        return render_template('signup.html')

@app.route('/index', defaults={'musica_selecionada': None})
@app.route('/index/<path:musica_selecionada>')
def index(musica_selecionada):
    if 'usuario' not in session:
        flash('Você precisa estar logado.', 'error')
        return redirect(url_for('login'))

    diretorio_usuario = session['diretorio']
    usuario_logado = session['usuario']
    if not os.path.exists(diretorio_usuario):
        os.makedirs(diretorio_usuario)

    try:
        musicas = [
            f for f in os.listdir(diretorio_usuario)
            if f.lower().endswith(('.mp3', '.wav', '.ogg'))
        ]
    except FileNotFoundError:
        musicas = []
    musicas.sort()
    favoritos = listar_favoritos(usuario_logado)

    if musica_selecionada not in musicas:
        musica_selecionada = None

    prev_file = None
    next_file = None
    if musica_selecionada:
        idx = musicas.index(musica_selecionada)
        if idx > 0:
            prev_file = musicas[idx - 1]
        if idx < len(musicas) - 1:
            next_file = musicas[idx + 1]

    cover_exists = False
    cover_filename = None
    if musica_selecionada:
        nome_sem_ext, _ = os.path.splitext(musica_selecionada)
        capa_jpg_jpg = f"{nome_sem_ext}.jpg.jpg"
        capa_jpg = f"{nome_sem_ext}.jpg"
        caminho_jpg_jpg = os.path.join(diretorio_usuario, capa_jpg_jpg)
        caminho_jpg = os.path.join(diretorio_usuario, capa_jpg)
        if os.path.exists(caminho_jpg_jpg):
            cover_filename = capa_jpg_jpg
            cover_exists = True
        elif os.path.exists(caminho_jpg):
            cover_filename = capa_jpg
            cover_exists = True

    return render_template(
        'index.html',
        usuario=usuario_logado,
        musicas=musicas,
        musica_selecionada=musica_selecionada,
        prev_file=prev_file,
        next_file=next_file,
        cover_exists=cover_exists,
        cover_filename=cover_filename,
        favoritos=favoritos
    )

@app.route('/edit_playlist', methods=['POST'])
def edit_playlist():
    if 'usuario' not in session:
        return jsonify({'status': 'error', 'message': 'Usuário não está logado.'}), 401

    data = request.get_json()
    playlist_id = data.get('playlist_id')
    new_name = data.get('new_name')

    if not playlist_id or not new_name:
        return jsonify({'status': 'error', 'message': 'Dados insuficientes.'}), 400

    usuario = session['usuario']

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'error', 'message': 'Erro de conexão com o banco.'}), 500
        cursor = conn.cursor()

        # Verificar se a playlist pertence ao usuário
        cursor.execute("SELECT usuario FROM playlist WHERE id = %s", (playlist_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'status': 'error', 'message': 'Playlist não encontrada.'}), 404
        if result[0] != usuario:
            return jsonify({'status': 'error', 'message': 'Permissão negada.'}), 403

        # Atualizar o nome da playlist
        cursor.execute("UPDATE playlist SET nome = %s WHERE id = %s", (new_name, playlist_id))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Playlist ID {playlist_id} renomeada para '{new_name}' pelo usuário '{usuario}'.")
        return jsonify({'status': 'success', 'message': 'Playlist atualizada com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao editar playlist: {e}")
        return jsonify({'status': 'error', 'message': 'Erro ao editar playlist.'}), 500

@app.route('/delete_playlist', methods=['POST'])
def delete_playlist():
    if 'usuario' not in session:
        return jsonify({'status': 'error', 'message': 'Usuário não está logado.'}), 401

    data = request.get_json()
    playlist_id = data.get('playlist_id')

    if not playlist_id:
        return jsonify({'status': 'error', 'message': 'Dados insuficientes.'}), 400

    usuario = session['usuario']

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'error', 'message': 'Erro de conexão com o banco.'}), 500
        cursor = conn.cursor()

        # Verificar se a playlist pertence ao usuário
        cursor.execute("SELECT usuario FROM playlist WHERE id = %s", (playlist_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'status': 'error', 'message': 'Playlist não encontrada.'}), 404
        if result[0] != usuario:
            return jsonify({'status': 'error', 'message': 'Permissão negada.'}), 403

        # Excluir relações na tabela playlist_musica
        cursor.execute("DELETE FROM playlist_musica WHERE playlist_id = %s", (playlist_id,))
        # Excluir a playlist
        cursor.execute("DELETE FROM playlist WHERE id = %s", (playlist_id,))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Playlist ID {playlist_id} excluída pelo usuário '{usuario}'.")
        return jsonify({'status': 'success', 'message': 'Playlist excluída com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao excluir playlist: {e}")
        return jsonify({'status': 'error', 'message': 'Erro ao excluir playlist.'}), 500

#############################################################################
#                  ROTAS PARA EXCLUSÃO DE MÚSICAS
#############################################################################

@app.route('/delete_music', methods=['POST'])
def delete_music():
    if 'usuario' not in session:
        return jsonify({'status': 'error', 'message': 'Usuário não está logado.'}), 401

    data = request.get_json()
    musica = data.get('musica')

    if not musica:
        return jsonify({'status': 'error', 'message': 'Música não especificada.'}), 400

    usuario = session['usuario']
    diretorio_usuario = session.get('diretorio')
    if not diretorio_usuario:
        return jsonify({'status': 'error', 'message': 'Diretório do usuário não encontrado.'}), 400

    music_path = os.path.join(diretorio_usuario, musica)

    if not os.path.exists(music_path):
        return jsonify({'status': 'error', 'message': 'Arquivo de música não encontrado.'}), 404

    try:
        os.remove(music_path)
        logger.info(f"Música '{musica}' excluída do diretório de '{usuario}'.")
    except Exception as e:
        logger.error(f"Erro ao excluir a música '{musica}': {e}")
        return jsonify({'status': 'error', 'message': 'Erro ao excluir a música.'}), 500

    # Remover da tabela favorites
    remover_favorito(usuario, musica)

    # Remover de playlists
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM playlist_musica WHERE musica = %s AND playlist_id IN (SELECT id FROM playlist WHERE usuario = %s)", (musica, usuario))
            conn.commit()
            cursor.close()
            conn.close()
            logger.info(f"Música '{musica}' removida das playlists do usuário '{usuario}'.")
    except Exception as e:
        logger.error(f"Erro ao remover música das playlists: {e}")

    return jsonify({'status': 'success', 'message': 'Música excluída com sucesso.'})

#############################################################################
#                  NOVA ROTA PARA REMOVER MÚSICAS DA LISTA
#############################################################################

@app.route('/remove_music_from_list', methods=['POST'])
def remove_music_from_list():
    if 'usuario' not in session:
        return jsonify({'status': 'error', 'message': 'Usuário não está logado.'}), 401

    data = request.get_json()
    musica = data.get('musica')

    if not musica:
        return jsonify({'status': 'error', 'message': 'Música não especificada.'}), 400

    usuario = session['usuario']

    try:
        # Remover da tabela favorites
        remover_favorito(usuario, musica)

        # Remover da tabela playlist_musica
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'error', 'message': 'Erro de conexão com o banco.'}), 500
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM playlist_musica 
            WHERE musica = %s AND playlist_id IN (
                SELECT id FROM playlist WHERE usuario = %s
            )
        """, (musica, usuario))
        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Música '{musica}' removida das listas do usuário '{usuario}'.")
        return jsonify({'status': 'success', 'message': 'Música removida das listas com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao remover música das listas: {e}")
        return jsonify({'status': 'error', 'message': 'Erro ao remover música das listas.'}), 500

#############################################################################
#                  ROTAS PARA DOWNLOADS
#############################################################################

@app.route('/play/<path:nome_arquivo>')
def play_musica(nome_arquivo):
    if 'usuario' not in session:
        flash('Você precisa estar logado.', 'error')
        return redirect(url_for('login'))
    diretorio_usuario = session['diretorio']
    return send_from_directory(diretorio_usuario, nome_arquivo)

@app.route('/cover/<path:cover_name>')
def get_cover(cover_name):
    if 'usuario' not in session:
        flash('Você precisa estar logado.', 'error')
        return redirect(url_for('login'))
    diretorio_usuario = session['diretorio']
    try:
        return send_from_directory(diretorio_usuario, cover_name)
    except FileNotFoundError:
        flash('Arquivo de capa não encontrado.', 'error')
        referer = request.headers.get("Referer")
        if referer and 'favorites' in referer:
            return redirect(url_for('favorites'))
        else:
            return redirect(url_for('index'))

@app.route('/random_track')
def random_track():
    if 'usuario' not in session:
        flash('Você precisa estar logado.', 'error')
        return redirect(url_for('login'))

    diretorio_usuario = session['diretorio']
    try:
        musicas = [
            f for f in os.listdir(diretorio_usuario)
            if f.lower().endswith(('.mp3', '.wav', '.ogg'))
        ]
    except FileNotFoundError:
        musicas = []
    if not musicas:
        flash('Nenhuma música na pasta!', 'error')
        return redirect(url_for('index'))

    sorteada = random.choice(musicas)
    return redirect(url_for('index', musica_selecionada=sorteada))

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

@app.route('/downloads', methods=['GET', 'POST'])
def downloads():
    if 'usuario' not in session:
        flash('Você precisa estar logado.', 'error')
        return redirect(url_for('login'))

    usuario_logado = session['usuario']
    if request.method == 'POST':
        caminho_digitado = request.form.get('caminho')
        if caminho_digitado:
            inserir_fila(usuario_logado, caminho_digitado)
            flash('Item adicionado à fila!', 'success')
        return redirect(url_for('downloads'))
    else:
        items = listar_fila(usuario_logado)
        return render_template('downloads.html', items=items)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    logger.info("Servidor Flask está desligando...")
    os._exit(0)

#############################################################################
#                            MAIN
#############################################################################

def main():
    if not load_db_config():
        logger.info("Nenhuma configuração encontrada. Abrindo interface para inserir configurações.")
    else:
        logger.info("Configurações carregadas com sucesso.")

    root = tk.Tk()
    app_interface = ConfigApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
