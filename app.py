import json
import faiss
import signal
import sys
import uuid
from datetime import datetime
from pathlib import Path
from novoMetodo import fazerPergunta, fazerPerguntaIbm, pegarToken
import os
from dotenv import load_dotenv
import pymysql
import markdown

from flask import Flask, request, jsonify, render_template, session, Response, g

load_dotenv()
HISTORICO_DIR = Path("historico")
HISTORICO_DIR.mkdir(exist_ok=True)

MODELO = "gemma3:12b"
EMBEDDING = "bge-m3:latest"

USER = os.getenv("DBUSER")
PASS = os.getenv("DBPASS")
ADDR = os.getenv("DBIPV4")
BASE = os.getenv("DBBASE")

IBMID = os.getenv("IBMID")
IBMURL = os.getenv("IBMURL")
IBMAPI = os.getenv("IBMAPI")

fp = open("servicosApiEmbedding.json", 'r', encoding="utf-8")
SERVICOS = json.load(fp)
fp.close()
INDEX = faiss.read_index('servicosApi.index')


def gerar_id_conversa():
    """Gera um ID único para a conversa"""
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"

def salvar_conversa(conversa_id: str, dados: dict):
    """Salva ou atualiza os dados da conversa em um arquivo JSON"""
    arquivo = HISTORICO_DIR / f"conversa_{conversa_id}.json"
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_conversa(conversa_id: str) -> dict:
    """Carrega os dados de uma conversa específica"""
    arquivo = HISTORICO_DIR / f"conversa_{conversa_id}.json"
    if arquivo.exists():
        with open(arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"id": conversa_id, "interacoes": [], "timestamp_inicio": datetime.now().isoformat()}

prompt = f"""Analise CUIDADOSAMENTE o texto do usuário e determine se é APENAS uma saudação ou cumprimento.

REGRAS IMPORTANTES:
1. Considere como saudação APENAS expressões de cumprimento como: oi, olá, bom dia, boa tarde, boa noite, e suas variações
2. Uma saudação pode incluir "tudo bem?", "como vai?", ou expressões similares de cortesia
3. Qualquer menção a serviços, perguntas específicas, ou palavras não relacionadas a cumprimentos deve ser considerada como NÃO saudação

Exemplos de APENAS saudações:
- "oi"
- "olá, tudo bem?"
- "bom dia!"
- "boa tarde, como vai?"
- "oi, tudo bom?"

Exemplos de NÃO saudações:
- "oi, preciso de ajuda com IPVA"
- "bom dia, como faço para renovar CNH"
- "empresa"
- "quero saber sobre multas"
- "preciso de informação"
- "ajuda"
- "serviços"

Se for APENAS uma saudação: responda de forma educada e explique que este é um chat de serviços do Governo do RJ.
Se NÃO for apenas uma saudação (contiver qualquer outro conteúdo): responda exatamente '[CONTINUAR]'.

"""
def signal_handler(sig, frame):
    print('\nEncerrando o programa graciosamente...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def create_app():
    app = Flask(__name__)
    app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
    def get_db():
        con = pymysql.connect(host=ADDR, user=USER, password=PASS, database=BASE, cursorclass=pymysql.cursors.DictCursor)
        cur = con.cursor()
        if 'db' not in g:
            g.db = cur
        return g.db

    @app.route("/chat2")
    def chat2():
        return render_template("chat2.html")

    @app.route('/')
    def home():
        session['USER'] = str(uuid.uuid1())
        session['CHAT'] = str(uuid.uuid1())
        session['DATA'] = str(datetime.today().date())
        session['token'] = pegarToken(IBMAPI)
        session['ordem'] = 0
        return render_template('chat.html')
    
    @app.route('/escrever', methods=['POST'])
    def escrever():
        data = request.json
        html = data.get("html")
        cur = get_db()
        cur.execute("INSERT INTO historico (idUsuario, idConversa, ordemMensagem, html, dono) values (%s,%s,%s,%s,%s)", (session['USER'], session['CHAT'], session['ordem'], html, 1))
        cur.connection.commit()
        session['ordem'] +=1
        return Response(status=200)
   

    @app.route('/chat', methods=['POST'])
    def chat():
        try:
            data = request.json
            consulta = data.get('consulta', '')
            if not session['CHAT']:
                session['CHAT'] = uuid.uuid1()
                conversa_id = session['CHAT']
            else:
                conversa_id = session['CHAT']
            
            conversa = carregar_conversa(conversa_id)
            
            # Continua com o fluxo normal de busca de serviços
            nova_interacao = {
                "timestamp": datetime.now().isoformat(),
                "pergunta_original": consulta,
                "pergunta_reformulada": None,
                "servicos_encontrados": [],
                "servicos_clicados": [],
                "feedback": None,
                "tipo": "consulta"
            }
            
            texto, referencias, thread = fazerPerguntaIbm(session['token'],IBMURL,  consulta, session['thread'] if 'thread' in session else '') 
            texto = markdown.markdown(texto)
            if 'thread' not in session:
                session['thread'] = thread
            if referencias != []:
                servicos_encontrados = []
                for servi in referencias:
                    servico_dict = {
                        "titulo": servi["title"],
                        "urlServ": "https://www.rj.gov.br/servico/" + servi["url"],
                        "descricao": servi["body"],
                    }
                    servicos_encontrados.append(servico_dict)
                
                nova_interacao["servicos_encontrados"] = servicos_encontrados
                conversa["interacoes"].append(nova_interacao)
                salvar_conversa(conversa_id, conversa)

                
                return jsonify({
                    'mensagem': "Encontrei os seguintes serviços que podem te ajudar:",
                    'texto':texto,
                    'servicos_encontrados': servicos_encontrados,
                    'conversa_id': conversa_id,
                    'ordem':session['ordem']
                })
            else:
                return jsonify({
                    'texto':texto,
                    'servicos_encontrados': [],
                    'conversa_id': conversa_id,
                    'ordem':session['ordem']
                })
            
        except Exception as e:
            return jsonify({
                'mensagem': "Desculpe, ocorreu um erro ao processar sua solicitação. Por favor, tente novamente.",
                'servicos_encontrados': [],
                'error': str(e)
            }), 500

    @app.route('/servico_clicado', methods=['POST'])
    def registrar_clique():
        try:
            data = request.json
            conversa_id = data.get('conversa_id')
            servico_descricao = data.get('servico')
            
            if not conversa_id or not servico_descricao:
                return jsonify({'error': 'Dados incompletos'}), 400
                
            conversa = carregar_conversa(conversa_id)
            if not conversa["interacoes"]:
                return jsonify({'error': 'Conversa não encontrada'}), 404
                
            # Apenas adiciona o serviço clicado ao array de servicos_clicados
            ultima_interacao = conversa["interacoes"][-1]
            ultima_interacao["servicos_clicados"].append({
                "servico": servico_descricao,
                "timestamp": datetime.now().isoformat()
            })
            
            salvar_conversa(conversa_id, conversa)
            return jsonify({'status': 'ok'})
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/feedback', methods=['POST'])
    def feedback():
        try:
            data = request.json
            conversa_id = data.get('conversa_id')
            feedback_valor = data.get('feedback')  # 'like', 'dislike' ou None
            
            if not conversa_id:
                return jsonify({'error': 'ID da conversa não fornecido'}), 400
                
            conversa = carregar_conversa(conversa_id)
            if not conversa["interacoes"]:
                return jsonify({'error': 'Conversa não encontrada'}), 404
                
            # Atualiza o feedback da última interação
            ultima_interacao = conversa["interacoes"][-1]
            ultima_interacao["feedback"] = feedback_valor
            ultima_interacao["feedback_timestamp"] = datetime.now().isoformat()
            
            salvar_conversa(conversa_id, conversa)
            return jsonify({'status': 'ok'})
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return app
