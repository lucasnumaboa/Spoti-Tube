# Spoti-Tube 🎵

Um gerenciador de músicas completo, com interface gráfica, integração com banco de dados e suporte a downloads de playlists.
Selecione a playlist, adicione a pasta de download e pronto!

Todos os arquivos estão prontos para uso, basta importar a tabela SQL e executar o .exe.

- Instale os requisitos do Python
- Instale o FFmpeg
- Instale o MYsql caso não tenha e importe o banco (banco-spoti-tube.sql)
- Depois de seguir os passos acima basta executar a aplicação
- Caso queira testar sem instalar os requisitos basta importar o banco SQL e executar o .exe

demo: [https://spotmanero.manerostream.com.br]
login: demo
senha: demo

## Recursos
- **Gestão de Músicas**: Gerencie favoritos, playlists e arquivos.
- **Download Automatizado**: Baixe músicas de URLs usando `yt-dlp`.
- **Configuração Fácil**: Interface intuitiva para configurar o sistema.
- **Persistência de Dados**: Banco de dados MySQL para armazenamento seguro.

Login:
![Login](imagens/Login.JPG)

Tela inicial:
![Tela inicial](imagens/tela-inicial.jpg)

Tela de Download da playlist:
![Download](imagens/download.jpg)

## Estrutura
- **Backend**: Desenvolvido com Flask.
- **Frontend**: Páginas HTML para interação via navegador.
- **Interface GUI**: Tkinter para configurações e logs.

## Pré-requisitos
- **Python 3.8+**
- Banco de dados MySQL configurado
- FFmpeg instalado para suporte ao `yt-dlp`.

- Link para FFmpeg:
https://www.ffmpeg.org/download.html

Baixe e aponte o caminho da pasta no tkinter

## Instalação
1. Clone o repositório:
   ```bash
   git clone https://github.com/lucasnumaboa/spoti-tube.git
   cd spoti-tube
