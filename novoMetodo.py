from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import ollama
import numpy as np
import json
import faiss
import time

DATA = "servicos"

def carregarDocumentos():
    loader = DirectoryLoader("servicos", glob='*.md')
    doc = loader.load()
    return doc

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
    matrix=np.empty((0,len(newdict[0]["embedding"])), dtype="float32")
    aux = ollama.embed(model = embedding, input=embedded)
    embed1 = np.array(aux.embeddings[0],dtype="float32").transpose()
    matrix = np.append(matrix, [embed1], axis=0)
    D, I = index.search(matrix, 10)
    
    return [D[0], I[0]]

def retirarServicos():
    doc = open("servicos-com-embeddings.json", "rb")
    servicos=json.load(doc)
    servi = {}
    for i in servicos:
        aux = i["embedding_text"].split("URL: ")
        servi[str(i["id"])] = ["ID: " + str(i["id"]) + '-' +aux[0], aux[1]]
    
    doc.close()
    doc = open("servicosEditados.json", "w", encoding='utf-8')
    json.dump(servi, doc)
    doc.close()
    return servi



def fazerPergunta(embedding, newdict,index, pergunta,modelo, verbose= False):
    model = OllamaLLM(model=modelo)
    chat_history = []
    template = "        Você é um chatbot que tem como função ajudar os cidadãos do Estado do Rio de Janeiro a entender e achar os melhores serviços para a situação sendo trazida. Seja amigavel, mas não enrole muito com a resposta.  Caso a solicitação seja relacionado a emergências de teor policial ou de saúde retorne para entrar em contato com o 190. Fora essas situações responda diretamente a pergunta do usuário."
    prompt = ChatPromptTemplate.from_messages([("system", template), MessagesPlaceholder(variable_name="chat_history"),("human", "{pergunta}")])    
    chain = prompt | model
    while True:
        aux = input("cidadão: ") if pergunta == None else pergunta
        result = chain.invoke({"pergunta":aux, "chat_history":chat_history})
        chat_history.append(HumanMessage(content=aux))
        chat_history.append(AIMessage(content=result))
        if verbose:
            print("AI: " + result)
        else:
            return(result)
        
        

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

servicos = retirarServicos()
while True:
    inicio = time.perf_counter()
    aux = inicializarConsulta("gemma3:12b", verbose=True)
    fim = time.perf_counter()
    print(fim - inicio)
    print(aux)
    for i in aux.lstrip().split("\n")[0].replace("Ids: ", "").split(";"):
        print(i)
        servico = i.lstrip().replace("Serviço: ", "")
        if servico in servicos.keys():
            print(servicos[servico])
        else:
            print("não encontrei")
    