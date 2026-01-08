import json
import faiss
import signal
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from novoMetodo import fazerPergunta

from flask import Flask, request, jsonify, render_template

HISTORICO_DIR = Path("historico")
HISTORICO_DIR.mkdir(exist_ok=True)

MODELO = "gemma3:12b"
EMBEDDING = "bge-m3:latest"


fp = open("servicosApiEmbedding.json", 'r', encoding="utf-8")
SERVICOS = json.load(fp)
fp.close()
INDEX = faiss.read_index('testeApiServ.index')

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
def agente_resposta(consulta) -> str:
    resp, ids = fazerPergunta(consulta, SERVICOS, INDEX ) 
    return resp, ids

def signal_handler(sig, frame):
    print('\nEncerrando o programa graciosamente...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        inicio = time.perf_counter()
        data = request.json
        consulta = data.get('consulta', '')
        conversa_id = data.get('conversa_id')
        
        if not conversa_id:
            conversa_id = gerar_id_conversa()
        
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
        
        texto, ids = agente_resposta(consulta) 
        if ids != []:
            servicos_encontrados = []
            for servi in ids:
                aux = servi.lstrip()
                servico_dict = {
                    "titulo": SERVICOS[aux]["titulo"],
                    "urlServ": "https://www.rj.gov.br/servico/" + SERVICOS[aux]["slug"],
                    "descricao": SERVICOS[aux]["descricao"],
                    "orgao": SERVICOS[aux]["orgao_sigla"],
                    "url": SERVICOS[aux]["url_externo"],
                }
                servicos_encontrados.append(servico_dict)
            
            nova_interacao["servicos_encontrados"] = servicos_encontrados
            conversa["interacoes"].append(nova_interacao)
            salvar_conversa(conversa_id, conversa)
            
            return jsonify({
                'mensagem': "Encontrei os seguintes serviços que podem te ajudar:",
                'texto':texto,
                'servicos_encontrados': servicos_encontrados,
                'conversa_id': conversa_id
            })
        else:
            return jsonify({
                'texto':texto,
                'servicos_encontrados': [],
                'conversa_id': conversa_id
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

def main():
    app.run(debug=True, port=5550)

main()