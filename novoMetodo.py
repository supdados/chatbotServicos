from langchain.text_splitter import RecursiveCharacterTextSplitter
from google import genai
from google.genai import types
from dotenv import load_dotenv
import requests
import ollama
import html
import os
import numpy as np
import json
import faiss
import time

load_dotenv()

DATA = "servicos"

def dividirTexto(docs: list):
    divisor = RecursiveCharacterTextSplitter(
        chunk_size = 1000,
        chunk_overlap=500,
        length_function = len,
        add_start_index=True
    )
    chunks = divisor.split_documents(docs)
    return chunks

def pesquisar(embedded, embedding, newdict, index):
    matrix=np.empty((0,len(newdict['0']["embedding"])), dtype="float32")
    aux = ollama.embed(model = embedding, input=embedded)
    embed1 = np.array(aux.embeddings[0],dtype="float32").transpose()
    matrix = np.append(matrix, [embed1], axis=0)
    D, I = index.search(matrix, 10)
    
    return [D[0], I[0]]

def retirarServicos():
    url_base = os.getenv("SERVICOS_URL")
    api_key = os.getenv("SERVICOS_KEY")
    
    url = f"{url_base}/api/cms/servicos_busca/"
    
    params = {
        "page": 1,
        "items_size": 100
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {api_key}"
    }
    
    try:
        # Realizar a requisição GET
        response = requests.get(url, headers=headers, params=params)
        # Verificar status da resposta
        response.raise_for_status()
        # Retornar dados como dicionário
        servicos =  response.json()
        servicosGuardar = {}
        totalpag = servicos.get("total_pages")
        agora = 1
        ident = 0
        while agora < totalpag + 1:
            print(agora, totalpag, end="\r")
            for servico in servicos.get("results"):
                servicosGuardar[ident] = {}
                atual = servicosGuardar[ident]
                for i in servico:
                    valor = servico.get(i)
                    if i == 'jornada' and valor != []:
                        valor = sorted(valor, key= lambda d:d['ordem'])
                        for j in valor:
                            j['conteudo'] = html.unescape(j['conteudo'])
                        atual[i] = valor
                    else:
                        atual[i] = valor if "<" not in str(valor) else html.unescape(valor)
                ident +=1
            agora +=1
            params['page'] = agora
            response = requests.get(url, headers=headers, params=params)
            servicos =  response.json()
        return servicosGuardar

    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição: {e}")
        return None



client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
buscarNaBase_funcao = {
    "name":"pesquisar",
    "description":"Faz pesquisas de serviços disponíveis no site do Estado do Rio de Janeiro com base em uma pergunta ou frase do usuário simplificada.",
    "parameters": {
        "type": "object",
        "properties": { 
            "pergunta": {
                "type":'string',
                "description":'Pergunta ou frase simplificada para pesquisar no banco de dados, não altere siglas.'
                }
                },
                "required":["pergunta"],
                },
}
ferramentas = types.Tool(function_declarations=[buscarNaBase_funcao])
config = types.GenerateContentConfig(tools=[ferramentas], system_instruction="Você é um chatbot do Estado do Rio de Janeiro, seu trabalho é auxiliar os cidadãos fluminenses da melhor maneira possível. Não ajude aqueles que demandam por opiniões pessoais ou informações ilegais. Não responda a perguntas sem antes verificar a base de dados em caso de perguntas de cunho burocratico. Se a informação já esta carregada na conversa, não busque-a de novo na base de dados.  Seja o mais sucinto mas cordial nas respostas.")
chat = client.chats.create(model="gemini-2.5-flash-lite", config=config)

def fazerPergunta(pergunta,servicos, index, verbose= False):
    response = chat.send_message(f"""Responda a pegunta: {pergunta}. Seguindo o Modelo:
                                 "
                                    <div>
                                    <p> Este e um modelo para a resposta.</p>
                                    <p> Multiplas linhas devem ser separados por diferentes tags p</p>
                                    <p> para dar enfaze em certas palavras usar <span style="{'{'+'font-weight:bold'+'}'}">negrito</span></p>
                                    </div>

                                    -ids:[11, 3, 44]
                                "
                                 """)
    if response.candidates[0].content.parts[0].function_call:
        print('entrei')
        a, b =pesquisar(response.candidates[0].content.parts[0].function_call.args['pergunta'], "bge-m3:latest", servicos, index=index)
        print("pergunta reformulada: ", response.candidates[0].content.parts[0].function_call.args['pergunta'])
        servicosEscolhidos = []
        for i in b:
            escolhido = servicos[str(i)].copy() 
            escolhido['id'] = str(i)
            escolhido.pop("embedding")
            servicosEscolhidos.append(escolhido)
        response = chat.send_message(f"""
                                     Com base nesses resultados da função pergunta: {servicosEscolhidos}, responda a pergunta: {pergunta}.
                                     Sua resposta deve seguir as seguintes regras:
                                        Deve conter até 3 serviços que são relacionados a pergunta.
                                        Se um serviço cumpre perfeitamente a demanda do usuário retorne apenas ele.
                                        Se nenhum atender ao usuário, retorne para ele entrar em contato com o OUVERJ.
                                        A resposta sera em duas partes. Primeiro um texto explicando a escolha dos serviços, ele DEVE estar em html. Segundo a ULTIMA LINHA da resposta deve conter: "-ids: [ARRAY DOS SERVIÇOS UTILIZADOS NA RESPOSTA]"
                                        Exemplo:
                                            "
                                            <div>
                                            <p> Este e um modelo para a resposta.</p>
                                            <p> Multiplas linhas devem ser separados por diferentes tags p</p>
                                            <p> para dar enfaze em certas palavras usar <span style="{'{'+'font-weight:bold'+'}'}">negrito</span></p>
                                            </div>

                                            -ids:[11, 3, 44]
                                            "
                                     """) 
        texto = response.text
        frases = texto.split('\n')
        ids = ''
        for i in frases:
            if "-id" in i:
                ids = i
        frases.remove(ids) 
        texto = "\n".join(frases)
        ids = ids.split(":")[1].strip()
        ids = ids[1:-1] if '[' in ids and ']' in ids else ids
        ids = ids.split(", ")
        return texto, ids
    else:
        texto = response.text
        frases = texto.split('\n')
        ids = ''
        for i in frases:
            if "-id" in i:
                ids = i
        frases.remove(ids) 
        texto = "\n".join(frases)
        ids = ids.split(":")[1].strip()
        ids = ids[1:-1] if '[' in ids and ']' in ids else ids
        ids = ids.split(", ")
        return texto, ids


def inicializarConsulta(modelo, pergunta = None, verbose = False):
    embeding = "snowflake-arctic-embed2:568m"

    doc = open("teste.json", "rb")
    newdict = json.load(doc)
    aux=np.empty((0,len(newdict[0]["embedding"])), dtype="float32")
    for i in newdict:
        aux = np.append(aux, [np.array(i["embedding"], dtype="float32")], axis=0)
    index = faiss.IndexFlatL2(aux.shape[1])
    print(aux.shape[1]) if verbose else ""
    index.add(aux)
    faiss.write_index(index, "teste.index")

    return fazerPergunta(embeding, newdict, index, pergunta,modelo, True)

def salvarServicos():
    servicos = retirarServicos()
    with open("servicosApi.json", "w", encoding='UTF-8') as fp:
        json.dump(servicos, fp, indent=4, ensure_ascii=False)

def main():
    fp = open("servicosApiEmbedding.json", 'r', encoding="utf-8")
    servicos = json.load(fp)
    fp.close()
    index = faiss.read_index('testeApiServ.index')
    while True:
        pergun = input("Você: ")
        inicio = time.time()
        resp, ids = fazerPergunta(pergun, servicos)
        fim = time.time()
        print(fim-inicio)
        print(resp)
        print(ids, end="\n\n")