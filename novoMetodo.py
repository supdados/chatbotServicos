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
import datetime
import pymysql
import smtplib
from email.message import EmailMessage
from criarEmbeddingServicos import novo

load_dotenv()

DATA = "servicos"
USER = os.getenv("DBUSER")
PASS = os.getenv("DBPASS")
ADDR = os.getenv("DBIPV4")
BASE = os.getenv("DBBASE")

con = pymysql.connect(host=ADDR, user=USER, password=PASS, database=BASE, cursorclass=pymysql.cursors.DictCursor)
cur = con.cursor()

def pesquisar(embedded, embedding, newdict, index):
    matrix=np.empty((0,len(newdict['0']["embedding"])), dtype="float32")
    aux = ollama.embed(model = embedding, input=embedded)
    embed1 = np.array(aux.embeddings[0],dtype="float32").transpose()
    matrix = np.append(matrix, [embed1], axis=0)
    D, I = index.search(matrix, 10)
    
    return [D[0], I[0]]

def retirarServicos(verbose=False):
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
            if verbose:
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
                "description":'Pergunta ou frase reformulada para pesquisar no banco de dados, a reescrita deve traduzir a frase para termos utilizados no Rio de janeiro e não deve ser mechido nas siglas usadas pelo usuário, coloque-a também no modo imperativo.'
                }
                },
                "required":["pergunta"],
                },
}
ferramentas = types.Tool(function_declarations=[buscarNaBase_funcao])
config = types.GenerateContentConfig(tools=[ferramentas], system_instruction=f"""
    Você é um chatbot do portal de serviços do Estado do Rio de Janeiro com o nome de Edite que tem como dever encontrar os serviços que mais se adequam, quando eles existem, para as demandas dos cidadãos.
    Para esse fim você pode utilizar a função "pesquisar" quando for necessário para achar os serviços. Evite de usar essa função quando o usuário estiver pedindo informações adicionais sobre serviços já retornados.
    Não responda indagações que pessam opiniões pessoais, ajuda que não tenha haver com serviços disponíveis no portal ou pedidos que são contra a lei.
    Lembre-se também que você esta representando a esfera estadual do governo, assim atribuições de municipios não são da sua ossada.
    O dia de hoje é {datetime.datetime.today().strftime("%d/%m/%Y, %A")}.   
    O OuveRj é disponibilizado nesse endereço: https://www.rj.gov.br/ouverj/manifestacoes
""")
chat = client.chats.create(model="gemini-2.5-flash-lite", config=config)

def fazerPergunta(pergunta,servicos, index, valor, idUser, idConversa):
    try:
        cur.execute("SELECT arrayServicos FROM servicosRetornados WHERE idConversa = %s AND idUsuario = %s", [idConversa, idUser])
        carregando = cur.fetchone()
        servicosJaUsados = []
        if carregando == None:
            servicosJaUsados = []
        else:
            carregando = json.loads(carregando['arrayServicos'])
            for i in carregando:
                escolhido = servicos[str(i)].copy() 
                escolhido['id'] = str(i)
                escolhido.pop("embedding")
                servicosJaUsados.append(escolhido)
    except Exception as e:
        print(e)
        return
    response = chat.send_message(f""" Decida se a pergunta "{pergunta}" tem sua resposta nos servicos ja carregados na conversa, disponiveis abaixo.
                                      serviços retornados: {servicosJaUsados}

                                      caso negativo decida se a pergunta faz referencia a alguma das competencias que a esfera Estadual de governo. Se sim pesquise,
                                      Caso contrario não pesquise.
                                      Retorne 1 frase explicativa da escolha e se necessario a chamada da função.""")
    cur.execute("INSERT INTO historico(idUsuario, idConversa, ordemMensagem, html, dono) values (%s,%s,%s,%s,%s)", (idUser, idConversa, valor, pergunta, 0))
    cur.connection.commit()
    valor+=1
    if len(response.candidates[0].content.parts) > 1:
        a, b =pesquisar(response.candidates[0].content.parts[1].function_call.args['pergunta'], "bge-m3:latest", servicos, index=index)
        servicosEscolhidos = []
        for i in b:
            escolhido = servicos[str(i)].copy() 
            escolhido['id'] = str(i)
            escolhido.pop("embedding")
            servicosEscolhidos.append(escolhido)
        response = chat.send_message(f"""
                                     Com base nesses resultados da função pergunta: {servicosEscolhidos}, responda a pergunta: {pergunta}.
                                     Sua resposta deve seguir as seguintes regras:
                                        Se nenhum serviço se encaixa na demanda do usuário, não retorne nenhum deles e explique que não encontrou nenhum que se encaixe na demanda, além de direciona-lo a entrar em contato com o OuveRJ.
                                        Se tiver serviços compativeis com a demanda do usuário, caso seja a primeria vez expressando uma demanda e que tenha serviços relevantes, retorne apenas o serviço que mais se encaixa a ela.
                                        Caso não seja a primeira demanda com retorno relevante, retorne até 3 serviços.
                                        Em nenhum caso deve-se retornar mais de 3 serviços.
                                        A resposta sera em duas partes. Primeiro um texto explicando a escolha dos serviços em HTML. Segundo a ULTIMA LINHA da resposta deve conter: "-ids: [ARRAY DOS SERVIÇOS UTILIZADOS NA RESPOSTA]", seguindo o exemplo abaixo.
                                        Não retorne os Ids dos serviços no corpo da mensgem, apenas o coloque no lugar indicado!
                                        Nessa resposta você esta probido de utilizar a função de busca.
                                        Não retorne os ids no corpo do html, apenas os coloque na parte reservada a eles da mensagem.
                                        Exemplo:
                                            "
                                            <div>
                                            <p> Este e um modelo para a resposta.</p>
                                            <p> Multiplas linhas devem ser separados por diferentes tags p</p>
                                            <p> para dar enfaze em certas palavras usar <span style="{'{'+'font-weight:bold'+'}'}">negrito</span></p>
                                            <p> NÃO RESPONDA NADA SEM SER NA FORMATAÇÃO PASSADA</p>
                                            </div>

                                            -ids:[11, 3, 44]
                                            "
                                     """) 
        texto = response.text
        frases = texto.split('\n')
        ids = ''
        array = []
        for i in frases:
            if "-id" in i:
                ids = i
            if "<" in i or len(texto) == 1:
                array.append(i)
        texto = "\n".join(array)
        ids = ids.split(":")[1].strip('\n')
        if '[' in ids and ']' in ids and "[]" not in ids:
            ids = ids[1:-1] 
            ids = ids.split(", ")
        else:
            ids = []
        print(chat.get_history(True))
        cur.execute("INSERT INTO servicosRetornados(idConversa, idUsuario, arrayServicos) values (%s,%s,%s)", ( idConversa, idUser, json.dumps(ids)))
        cur.connection.commit()
        return texto, ids, valor
    else:
        response = chat.send_message(f"""Responda a frase "{pergunta}" sem utilizar a função de pesquisa.
                                     Se a frase não for um pedido ou algo proibido pelo prompt responda cordialmente seguindo o modelo.
                                     Se a frase for uma pergunta e não for competencia da esfera Estadual, avise ao usuário.
                                     Se a frase não tiver haver com um possível serviço ou não for algo relacionado a algum serviço se recuse a responder cordialmente.
                                     Quando falando sobre serviços ja mencionados, não retorne o id deles.
                                     lembre de basear a resposta nas mensagens trocadas durante essa conversa sem transparecer para o usuário quando necessário.
                                     Nessa resposta você esta probido de utilizar a função de busca.
                                     seguindo o modelo: 
                                     "
                                        <div>
                                        <p> Este e um modelo para a resposta.</p>
                                        <p> Multiplas linhas devem ser separados por diferentes tags p</p>
                                        <p> NÃO RESPONDA NADA SEM SER NA FORMATAÇÃO PASSADA</p>
                                        <p> para dar enfaze em certas palavras usar <span style="{'{'+'font-weight:bold'+'}'}">negrito</span></p>
                                        </div>
                                     " """)
        texto = response.text.split("\n")
        array = []
        for i in texto:
            if "<" in i or len(texto) == 1:
                array.append(i)
        texto = "\n".join(array)
        ids = []
        print(chat.get_history(True))
        return texto, ids, valor

def importarPerguntasCsv():
    import pandas as pd

    # Lê o arquivo CSV
    # O separador padrão é a vírgula (,), mas no Brasil é comum usarem ponto e vírgula (;)
    try:
        df = pd.read_csv('resposta_chatbot_servicos_pontuado_06.01.2026.xlsx - Dados.csv', sep=',', encoding='utf-8')
        return df
    except UnicodeDecodeError:
        df = pd.read_csv('resposta_chatbot_servicos_pontuado_06.01.2026.xlsx - Dados.csv', sep=';', encoding='latin-1')
        return df

def perguntaSimplificada(pergunta):
    fp = open("servicosApiEmbedding.json", 'r', encoding="utf-8")
    servicos = json.load(fp)
    fp.close()
    index = faiss.read_index('servicosApi.index')
    servicosJaUsados = []
    response = chat.send_message(f""" Decida se a pergunta "{pergunta}" tem sua resposta nos servicos ja carregados na conversa, disponiveis abaixo.
                                      serviços retornados: {servicosJaUsados}

                                      caso negativo decida se a pergunta faz referencia a alguma das competencias que a esfera Estadual de governo. Se sim pesquise,
                                      Caso contrario não pesquise.
                                      Retorne 1 frase explicativa da escolha e se necessario a chamada da função.""")
    if len(response.candidates[0].content.parts) > 1:
        a, b =pesquisar(response.candidates[0].content.parts[1].function_call.args['pergunta'], "bge-m3:latest", servicos, index=index)
        servicosEscolhidos = []
        for i in b:
            escolhido = servicos[str(i)].copy() 
            escolhido['id'] = str(i)
            escolhido.pop("embedding")
            servicosEscolhidos.append(escolhido)
        response = chat.send_message(f"""
                                     Com base nesses resultados da função pergunta: {servicosEscolhidos}, responda a pergunta: {pergunta}.
                                     Sua resposta deve seguir as seguintes regras:
                                        Se nenhum serviço se encaixa na demanda do usuário, não retorne nenhum deles e explique que não encontrou nenhum que se encaixe na demanda, além de direciona-lo a entrar em contato com o OuveRJ.
                                        Se tiver serviços compativeis com a demanda do usuário, caso seja a primeria vez expressando uma demanda e que tenha serviços relevantes, retorne apenas o serviço que mais se encaixa a ela.
                                        Caso não seja a primeira demanda com retorno relevante, retorne até 3 serviços.
                                        Em nenhum caso deve-se retornar mais de 3 serviços.
                                        A resposta sera em duas partes. Primeiro um texto explicando a escolha dos serviços em HTML. Segundo a ULTIMA LINHA da resposta deve conter: "-ids: [ARRAY DOS SERVIÇOS UTILIZADOS NA RESPOSTA]", seguindo o exemplo abaixo.
                                        Não retorne os Ids dos serviços no corpo da mensgem, apenas o coloque no lugar indicado!
                                        Nessa resposta você esta probido de utilizar a função de busca.
                                        Não retorne os ids no corpo do html, apenas os coloque na parte reservada a eles da mensagem.
                                        Exemplo:
                                            "
                                            <div>
                                            <p> Este e um modelo para a resposta.</p>
                                            <p> Multiplas linhas devem ser separados por diferentes tags p</p>
                                            <p> para dar enfaze em certas palavras usar <span style="{'{'+'font-weight:bold'+'}'}">negrito</span></p>
                                            <p> NÃO RESPONDA NADA SEM SER NA FORMATAÇÃO PASSADA</p>
                                            </div>

                                            -ids:[11, 3, 44]
                                            "
                                     """) 
        texto = response.text
        frases = texto.split('\n')
        ids = ''
        array = []
        for i in frases:
            if "-id" in i:
                ids = i
            if "<" in i or len(texto) == 1:
                array.append(i)
        texto = "\n".join(array)
        ids = ids.split(":")[1].strip('\n') if ids != '' else []
        ids_nome = []
        if '[' in ids and ']' in ids and "[]" not in ids:
            ids = ids[1:-1] 
            ids = ids.split(", ")
            for j in ids:
                ids_nome.append(j + " - " + servicos[j]['titulo'])
        else:
            ids = []
        return texto, ids_nome, 
    else:
        response = chat.send_message(f"""Responda a frase "{pergunta}" sem utilizar a função de pesquisa.
                                     Se a frase não for um pedido ou algo proibido pelo prompt responda cordialmente seguindo o modelo.
                                     Se a frase for uma pergunta e não for competencia da esfera Estadual, avise ao usuário.
                                     Se a frase não tiver haver com um possível serviço ou não for algo relacionado a algum serviço se recuse a responder cordialmente.
                                     Quando falando sobre serviços ja mencionados, não retorne o id deles.
                                     lembre de basear a resposta nas mensagens trocadas durante essa conversa sem transparecer para o usuário quando necessário.
                                     Nessa resposta você esta probido de utilizar a função de busca.
                                     seguindo o modelo: 
                                     "
                                        <div>
                                        <p> Este e um modelo para a resposta.</p>
                                        <p> Multiplas linhas devem ser separados por diferentes tags p</p>
                                        <p> NÃO RESPONDA NADA SEM SER NA FORMATAÇÃO PASSADA</p>
                                        <p> para dar enfaze em certas palavras usar <span style="{'{'+'font-weight:bold'+'}'}">negrito</span></p>
                                        </div>
                                     " """)
        texto = response.text.split("\n")
        array = []
        for i in texto:
            if "<" in i or len(texto) == 1:
                array.append(i)
        texto = "\n".join(array)
        ids = []
        return texto, ids

def salvarServicos(novo):
    servicos = novo
    with open("servicosApi.json", "w", encoding='UTF-8') as fp:
        json.dump(servicos, fp, indent=4, ensure_ascii=False)

def teste(verbose = False):
    fp = open("servicosApiEmbedding.json", 'r', encoding="utf-8")
    servicos = json.load(fp)
    fp.close()
    index = faiss.read_index('testeApiServ.index')
    while True:
        pergun = input("Você: ")
        inicio = time.time()
        resp, ids = fazerPergunta(pergun, servicos)
        fim = time.time()
        if (verbose):
            print(resp)
            print(ids, end="\n\n")
        return resp

def mandarEmail():
    Email = os.getenv("EMAILSMTP")
    para = os.getenv("EMAILPARA")
    password = os.getenv("PSSWDSMTP")
    host = os.getenv("HOSTSMTP")
    port = os.getenv("PORTSMTP")

    msg = EmailMessage()
    msg['Subject'] = "Arquivo com os serviços do Portal rj.gov"
    msg['From'] = Email
    msg['to'] = para
    msg.set_content("Segue json com a relação de serviços.")

    nomeArq = "servicosApi.json"
    with open(nomeArq, 'rb') as fp:
        dados = fp.read()
        
    msg.add_attachment(dados, maintype = 'application', subtype='json', filename=nomeArq)

    with smtplib.SMTP(host, port) as emailer: 
        emailer.connect(host, port)
        emailer.ehlo()
        emailer.starttls()
        emailer.login(Email, password)
        emailer.send_message(msg)
    

def atualizarJson():
    try:
        novos = retirarServicos()
        with open("servicosApi.json", 'r', encoding='utf-8') as fp:
            velhos = json.load(fp)
        nom1 = json.loads(json.dumps(velhos))
        nom2 = json.loads(json.dumps(novos))
        if nom1 != nom2 or not os.path.isfile("servicosApi.index"):
            salvarServicos(novos)
            mandarEmail()
            novo()
            print(datetime.datetime.today(), 'Salvei')
        else:
            print(datetime.datetime.today(), 'Não salvei')
    except Exception as e:
        print(datetime.datetime.today(), "tive problemas:", e)
