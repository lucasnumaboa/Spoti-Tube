# Spoti-Tube 🎵

Um gerenciador de músicas completo, com interface gráfica, integração com banco de dados e suporte a downloads de playlists.
Selecione a playlist, adicione a pasta de download e pronto!

Todos os arquivos estão prontos para uso, basta importar a tabela SQL e executar o .exe.


## Recursos
- **Gestão de Músicas**: Gerencie favoritos, playlists e arquivos.
- **Download Automatizado**: Baixe músicas de URLs usando `yt-dlp`.
- **Configuração Fácil**: Interface intuitiva para configurar o sistema.
- **Persistência de Dados**: Banco de dados MySQL para armazenamento seguro.

## Estrutura
- **Backend**: Desenvolvido com Flask.
- **Frontend**: Páginas HTML para interação via navegador.
- **Interface GUI**: Tkinter para configurações e logs.

## Pré-requisitos
- **Python 3.8+**
- Banco de dados MySQL configurado
- FFmpeg instalado para suporte ao `yt-dlp`.

## Instalação
1. Clone o repositório:
   ```bash
   git clone https://github.com/lucasnumaboa/spoti-maneiro.git
   cd spoti-maneiro


## Caminhos do projeto
spoti-maneiro/

init__.py          # Inicializador do módulo Flask
routes.py            # Rotas do Flask
db_utils.py          # Funções auxiliares para banco de dados
queue_handler.py     # Processamento de filas
download_manager.py  # Gerenciamento de downloads
playlist_manager.py  # Funções de playlists
├── static/
│   └── css/                 # Arquivos de estilo (se necessário)
├── templates/
│   ├── index.html           # Página principal
│   ├── login.html           # Página de login
│   ├── signup.html          # Página de cadastro
│   ├── downloads.html       # Gerenciamento de downloads
│   └── favorites.html       # Gerenciamento de favoritos
├── logs/
│   └── app.log              # Arquivo de logs (será criado automaticamente)
├── config.json              # Arquivo de configuração inicial
├── main.py                  # Arquivo principal do programa
├── requirements.txt         # Dependências do projeto
├── README.md                # Documentação do projeto
└── .gitignore               # Arquivos a serem ignorados no Git
