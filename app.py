import json
import numpy as np
import faiss
import signal
import ollama
import sys
import time
from typing import List, Dict, Tuple
import uuid
from datetime import datetime
from pathlib import Path

# Imports do LangChain
from langchain_ollama import OllamaLLM
from langchain.tools import BaseTool
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate, ChatPromptTemplate

from flask import Flask, request, jsonify, render_template

HISTORICO_DIR = Path("historico")
HISTORICO_DIR.mkdir(exist_ok=True)

MODELO = "gemma3:12b"
EMBEDDING = "snowflake-arctic-embed2:568m"

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

def gerar_embedding(texto: str) -> np.ndarray:
    try:
        resposta = ollama.embed( EMBEDDING, texto)
        # Converte para array NumPy do tipo float32 (requisito do FAISS)
        return np.array(resposta.embeddings[0], dtype="float32")
    except Exception as e:
        print(f"Erro ao gerar embedding: {e}")
        return None

class BuscarServicoTool(BaseTool):
    name: str = "buscar_servico"
    description: str = (
        "Dada uma consulta, retorne o serviço mais adequado a partir de uma base de serviços. "
        "Cada serviço possui 'id' e 'embedding_text'. O retorno deve estar no formato: "
        "'ID: <id> - <embedding_text>'. Se nenhum serviço for adequado, responda: "
        "'Nenhum serviço relevante encontrado'."
    )
    servicos: List[Dict] = []

    def _run(self, consulta: str, **kwargs) -> str:
        base_info = ""
        for serv in self.servicos:
            base_info += f"ID: {serv.get('id')} - {serv.get('embedding_text', 'Sem descrição')}\n"
        prompt = (
            f"O usuário fez a seguinte pergunta: '{consulta}'.\n"
            "Com base na base de serviços abaixo, identifique o serviço mais adequado. "
            "Caso encontre um serviço relevante, retorne a resposta no formato:\n"
            "'ID: <id> - <embedding_text>'\n"
            "Se nenhum serviço for adequado, responda: 'Nenhum serviço relevante encontrado'.\n\n"
            "Base de Serviços:\n" + base_info
        )
        messages = [
            {"role": "system", "content": "Você é um assistente que identifica o serviço mais adequado."},
            {"role": "user", "content": prompt}
        ]
        chat_llm = OllamaLLM(model="gemma3")
        result = chat_llm.invoke(messages)
        return result.strip()

    async def _arun(self, consulta: str, **kwargs) -> str:
        raise NotImplementedError("A execução assíncrona não é suportada.")

# Carrega o JSON com os serviços e seus embeddings
json_path = "teste.json"
with open(json_path, "r", encoding="utf-8") as f:
    servicos = json.load(f)

json_path = "servicosEditados.json"
with open(json_path, "r", encoding="utf-8") as f:
    servicosEdit = json.load(f)

# Carrega o índice FAISS
faiss_index_path = "teste.index"
index = faiss.read_index(faiss_index_path)

def buscar_servico_faiss(consulta: str) -> List[str]:
    """Realiza a busca via FAISS para a consulta informada e retorna serviços próximos."""
    print("\n[FAISS] Processando consulta para busca...")
    embedding_consulta = gerar_embedding(consulta)
    if embedding_consulta is None:
        print("Erro ao gerar embedding para a consulta.")
        return []
        
    embedding_consulta = np.expand_dims(embedding_consulta, axis=0)
    k = 10
    
    distancias, indices = index.search(embedding_consulta, k)
    
    # Mostra todos os 10 resultados encontrados
    print("\n[FAISS] Top 10 resultados mais próximos:")
    retorno = []
    indices=indices[0]
    for i in range(k):
        retorno.append(servicosEdit[str(indices[i]+1)])
    
    return retorno

def agente_saudacao(texto: str) -> Tuple[bool, str]:
    """
    Agente que analisa se o texto é apenas uma saudação e retorna uma resposta apropriada.
    Retorna: (é_apenas_saudacao, resposta)
    """
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

Texto do usuário: '{texto}'
"""
    
    messages = [
        {"role": "system", "content": "Você é um assistente especializado em análise precisa de saudações, sendo extremamente rigoroso para evitar falsos positivos."},
        {"role": "user", "content": prompt}
    ]
    
    chat_llm = OllamaLLM(model=MODELO)  # Reduzido temperature para maior precisão
    resposta = chat_llm.invoke(messages).strip()
    
    # Se a resposta for [CONTINUAR], significa que não é apenas uma saudação
    if resposta == "[CONTINUAR]":
        return False, ""
    
    return True, resposta

def agente_resposta(consulta, servicos) -> str:
    model = OllamaLLM(model=MODELO)
    template = """
    Você é um atendente do orgão responsável por auxiliar os cidadãos do Estado do Rio de Janeiro à encontrar os serviços que mais se encaixam em suas demandas.
    
    Se for uma demanda ilegal ou que foge das atribuições do Estado do Rio de Janeiro ou se nenhum serviço for interessante o suficiente.
    retorne algo neste estilo:
        Ids: 
        Texto: Não posso auxiliar com essas demandas, por favor tente reescrever sua pergunta para que eu possa ajudar.

    os serviços disponíveis são: {servicos}

    aqui está a consulta: {consulta}
    
    retorne a resposta com a seguinte formatação:
        Ids: (Ids dos servicos que mais se encaixam na consulta caso existam separados por ;)
        Texto: (Um texto que correlaciona os serviços mais relacionados com a consulta, esse texto deve ter uma breve explicação dos serviços escolhidos e não devem apresentar os IDs destes.)
    """
    prompt = ChatPromptTemplate.from_template(template)    
    chain = prompt | model
    resp =  chain.invoke({"servicos":servicos, "consulta":consulta})
    separador = resp.split("\n")
    separador = list(filter(lambda x: x !='', separador))
    print(separador)
    ids = separador[0].replace("Ids: ","").split(";")
    texto = separador[1].replace("Texto: ", "")
    print(ids)
    return ids, texto

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
        
        # Verifica se é apenas uma saudação usando o novo agente
        e_saudacao, resposta_saudacao = agente_saudacao(consulta)
        
        if e_saudacao:
            nova_interacao = {
                "timestamp": datetime.now().isoformat(),
                "pergunta_original": consulta,
                "tipo": "saudacao",
                "resposta": resposta_saudacao
            }
            conversa["interacoes"].append(nova_interacao)
            salvar_conversa(conversa_id, conversa)
            
            fim = time.perf_counter()
            print(fim-inicio)
            return jsonify({
                'mensagem': resposta_saudacao,
                'servicos_encontrados': [],
                'conversa_id': conversa_id
            })

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
        
        # Busca inicial via FAISS
        resultados_faiss = buscar_servico_faiss(consulta)
        ids, texto = agente_resposta(consulta, resultados_faiss) 
        if ids != ['']:
            servicos_encontrados = []
            for servi in ids:
                aux = servi.lstrip()
                servico_dict = {
                    "descricao": servicos[int(aux)-1]["embedding_text"],
                }
                servicos_encontrados.append(servico_dict)
            
            nova_interacao["servicos_encontrados"] = servicos_encontrados
            conversa["interacoes"].append(nova_interacao)
            salvar_conversa(conversa_id, conversa)
            
            return jsonify({
                'mensagem': "Encontrei os seguintes serviços que podem te ajudar:",
                'texto':texto,
                'servicos_encontrados': [s["descricao"] for s in servicos_encontrados],
                'conversa_id': conversa_id
            })
        else:
            print(texto)
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

if __name__ == '__main__':
    app.run(debug=True, port=5550)

print("Chat iniciado. Digite 'exit' para sair.\n")

while True:
    consulta = input("Você: ")
    if consulta.lower() == "exit":
        print("Encerrando o chat. Até mais!")
        break

    # --- Passo 1: Busca inicial via FAISS com a consulta original ---
    servicos_encontrados = buscar_servico_faiss(consulta)
    
    if servicos_encontrados:
        print("\n[Resultado Final] Serviço(s) identificado(s) via busca FAISS inicial:")
        for i, servico in enumerate(servicos_encontrados, 1):
            print(f"{i}. {servico}")
        print("\n---------------------------------\n")
        continue
