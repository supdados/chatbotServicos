/**
 * Script para o Chatbot de Serviços
 * Gerencia a troca de telas, envio de mensagens, exibição de respostas e coleta de feedback.
 *
 * Nota:
 * - A nova estrutura do JSON utiliza o campo "servico" no lugar de "titulo".
 * - O backend já mapeia esse campo para "titulo" na resposta. Mas, para maior robustez,
 *   o código utiliza um fallback para exibir o nome do serviço.
 */

let currentChat = {};
let conversationSaved = false; // Flag para indicar se a conversa já foi salva
let conversaId = null; // Adicione esta variável global no início do arquivo

// Seleção de elementos
const perguntaInput = document.getElementById('pergunta');
const historico = document.getElementById('historico');
const introContainer = document.getElementById('intro-container');
const chatContainer = document.getElementById('chat-container');
const btnComecar = document.getElementById('btn-comecar');
const btnEnviar = document.getElementById('btn-enviar');

document.addEventListener('DOMContentLoaded', () => {
  btnComecar.addEventListener('click', exibirChat);
  btnEnviar.addEventListener('click', enviarPergunta);
  perguntaInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') enviarPergunta();
  });

  // Novo botão "Novo Chat"
  const btnNovoChat = document.getElementById('novo-chat');
  if (btnNovoChat) {
    btnNovoChat.addEventListener('click', novoChat);
  }
});

/**
 * Exibe a interface do chat e coloca o foco no campo de entrada.
 */
function exibirChat() {
  introContainer.classList.add('hidden');
  chatContainer.classList.remove('hidden');
  perguntaInput.focus();
  // Gera um novo ID de conversa ao iniciar
  conversaId = null;
}

/**
 * Envia a pergunta para o backend, exibe o loader e armazena os dados da conversa em currentChat.
 */
async function enviarPergunta() {
  const pergunta = perguntaInput.value.trim();
  if (!pergunta) return;

  currentChat = { pergunta: pergunta };
  conversationSaved = false;
  perguntaInput.value = '';

  // Exibe a mensagem do usuário
  const mensagemPergunta = document.createElement('div');
  mensagemPergunta.className = 'mensagem pergunta fade-in';
  mensagemPergunta.textContent = pergunta;
  historico.appendChild(mensagemPergunta);
  scrollHistorico();

  await delay(300);

  // Exibe o loader
  const loaderDiv = document.createElement('div');
  loaderDiv.className = 'mensagem resposta digitando fade-in';
  const dots = document.createElement('span');
  dots.className = 'typing-dots';
  dots.textContent = 'Assistente está digitando';
  loaderDiv.appendChild(dots);
  historico.appendChild(loaderDiv);
  scrollHistorico();

  try {
    // Nova chamada adaptada para o novo backend
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        consulta: pergunta,
        conversa_id: conversaId
      })
    });

    const data = await response.json();
    
    // Atualiza o ID da conversa se recebido
    if (data.conversa_id) {
      conversaId = data.conversa_id;
    }

    loaderDiv.classList.add('fade-out');
    await delay(300);
    loaderDiv.remove();

    if (data.error) {
      mostrarErro(data.error);
    } else {
      currentChat.pergunta_formatada = data.consulta_reformulada || pergunta;
      currentChat.resposta = data.mensagem;
      currentChat.servicos = data.servicos_encontrados;
      await mostrarResposta(data);
    }
  } catch (error) {
    loaderDiv.remove();
    mostrarErro("Erro ao processar sua pergunta. Por favor, tente novamente.");
  }
}

/**
 * Exibe a resposta do backend e, ao final, injeta o container de feedback.
 * @param {Object} data - Dados retornados do backend.
 */
function extrairUrl(texto) {
  const urlMatch = texto.match(/URL: ([^\s]+)/);
  if (!urlMatch) return '#';
  let url = urlMatch[1];
  if (url.endsWith('.')) {
    url = url.slice(0, -1);
  }
  return url;
}

async function mostrarResposta(data) {
  const respostaDiv = document.createElement('div');
  respostaDiv.className = 'mensagem resposta fade-in';

  // Se houver serviços encontrados
  console.log(data)
  if (data.servicos_encontrados && data.servicos_encontrados.length > 0) {
    let htmlContent = '<div class="detalhes-servico">';
    
    if (data.mensagem) {
      htmlContent += `<p class="secao-header">${data.mensagem}</p>`;
      htmlContent += `<p class="descricao-escolha">${data.texto}</p>`
    }

    // Processa o primeiro serviço (principal)
    const primeiroServico = data.servicos_encontrados[0];
    if (primeiroServico) {
      htmlContent += `
        <div class="servico-item servico-principal">
          <h3>${primeiroServico['titulo']}</h3>
          <p class="orgao-text">Órgão: ${primeiroServico['descricao']}</p>
          <p class="descricao-text">${primeiroServico['orgao']}</p>
          <button class="botao-acesso" onclick="registrarCliqueServico('${primeiroServico['titulo']}'); window.open('${primeiroServico['urlServ']}', '_blank', 'noopener,noreferrer')">
            Acessar informações do serviço
          </button>
        </div>
      `;
    }

    // Se houver serviços adicionais
    if (data.servicos_encontrados.length > 1) {
      htmlContent += '<div class="servicos-relacionados">';
      htmlContent += '<h4 class="secao-header">Serviços que podem estar relacionados:</h4>';
      htmlContent += '<div class="servicos-secundarios-grid">';

      // Processa os serviços relacionados (2º e 3º)
      for (let i = 1; i < data.servicos_encontrados.length; i++) {
        const servicoRelacionado = data.servicos_encontrados[i];
        if (servicoRelacionado) {

          htmlContent += `
            <div class="servico-item servico-secundario">
              <h3>${servicoRelacionado['titulo']}</h3>
              <p class="orgao-text">Órgão: ${servicoRelacionado['orgao']}</p>
              <p class="descricao-text">${servicoRelacionado['descricao']}</p>
              <button class="botao-acesso botao-secundario" onclick="registrarCliqueServico('${servicoRelacionado['titulo']}'); window.open('${servicoRelacionado['urlServ']}', '_blank', 'noopener,noreferrer')">
                Acessar informações do serviço
              </button>
            </div>
          `;
        }
      }

      htmlContent += '</div>'; // Fecha servicos-secundarios-grid
      htmlContent += '</div>'; // Fecha servicos-relacionados
    }

    htmlContent += '</div>'; // Fecha detalhes-servico
    respostaDiv.innerHTML = htmlContent;
  } else {
    // Se não houver serviços, apenas mostra a mensagem
    respostaDiv.innerHTML = `
      <div class="detalhes-servico">
        
        <p class="descricao-escolha">${data.texto}</p>
      </div>
    `;
  }

  historico.appendChild(respostaDiv);
  scrollHistorico();
  adicionarFeedback(respostaDiv);
}

/**
 * Adiciona os botões de feedback (👍 e 👎) ao container informado.
 * O sistema não envia feedback automaticamente; se o usuário não votar, o feedback permanecerá como null.
 * @param {HTMLElement} parent - Container onde os botões serão inseridos.
 */
function adicionarFeedback(parent) {
  const feedbackContainer = document.createElement('div');
  feedbackContainer.className = 'feedback-container';
  feedbackContainer.innerHTML = `
    <button class="btn-feedback" data-feedback="like" aria-label="Gostei da resposta">
      <img src="/static/icons/like.svg" alt="Like" width="28" height="28">
    </button>
    <button class="btn-feedback" data-feedback="dislike" aria-label="Não gostei da resposta">
      <img src="/static/icons/dislike.svg" alt="Dislike" width="28" height="28">
    </button>
    <span class="feedback-message"></span>
  `;
  parent.appendChild(feedbackContainer);

  feedbackContainer.querySelectorAll('.btn-feedback').forEach(btn => {
    btn.addEventListener('click', () => {
      const clickedFeedback = btn.getAttribute('data-feedback');
      
      // Adiciona classe 'selected' ao botão clicado e 'hidden' ao outro
      feedbackContainer.querySelectorAll('.btn-feedback').forEach(b => {
        if (b === btn) {
          b.classList.add('selected');
        } else {
          b.classList.add('hidden');
        }
      });

      // Desabilita os botões e salva o feedback
      feedbackContainer.querySelectorAll('.btn-feedback').forEach(b => b.disabled = true);
      salvarConversa(clickedFeedback, feedbackContainer);
    });
  });
}

/**
 * Envia (ou atualiza) a conversa para o backend com o feedback informado.
 * Se feedbackValue for null, isso indica que o usuário não votou.
 * @param {string|null} feedbackValue - "like", "dislike" ou null.
 * @param {HTMLElement} [feedbackContainer] - Container onde os botões de feedback estão (opcional).
 */
function salvarConversa(feedbackValue, feedbackContainer = null) {
  conversationSaved = true;
  currentChat.feedback = feedbackValue;
  currentChat.timestamp = new Date().toISOString();
  
  fetch('/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conversa_id: conversaId,
      feedback: feedbackValue
    })
  })
  .then(response => response.json())
  .then(data => {
    if (feedbackContainer) {
      const messageSpan = feedbackContainer.querySelector('.feedback-message');
      if (data.status === "ok") {
        messageSpan.textContent = "Obrigado pelo feedback!";
        messageSpan.classList.add('visible'); // Adiciona classe para mostrar a mensagem
      } else {
        messageSpan.textContent = "Erro ao enviar feedback.";
        messageSpan.classList.add('visible');
      }
    }
  })
  .catch(error => {
    console.error("Erro no feedback:", error);
    if (feedbackContainer) {
      const messageSpan = feedbackContainer.querySelector('.feedback-message');
      messageSpan.textContent = "Erro ao enviar feedback.";
      messageSpan.classList.add('visible');
    }
  });
}

/**
 * Limpa o histórico e inicia um novo chat.
 * Se houver uma conversa atual não salva, ela será enviada com feedback null.
 */
function novoChat() {
  // Se houver conversa atual com resposta e ainda não salva, envia com feedback null
  if (currentChat && currentChat.resposta && !conversationSaved) {
    salvarConversa(null);
  }
  // Limpa o histórico e reinicia a conversa
  historico.innerHTML = '';
  currentChat = {};
  conversationSaved = false;
  conversaId = null; // Reseta o ID da conversa
  perguntaInput.value = '';
  perguntaInput.focus();
}

/**
 * Exibe uma mensagem de erro no histórico.
 * @param {string} mensagem - Mensagem de erro a ser exibida.
 */
function mostrarErro(mensagem) {
  const erroDiv = document.createElement('div');
  erroDiv.className = 'mensagem resposta fade-in';
  erroDiv.textContent = `❌ Erro: ${mensagem}`;
  historico.appendChild(erroDiv);
  scrollHistorico();
}

/**
 * Simula o efeito de digitação.
 * @param {HTMLElement} element - Elemento onde o texto será exibido.
 * @param {string} text - Texto a ser digitado.
 * @param {number} speed - Velocidade da digitação (ms).
 * @returns {Promise}
 */
function typeText(element, text, speed = 10) {
  return new Promise(resolve => {
    element.textContent = '';
    let i = 0;
    const interval = setInterval(() => {
      element.textContent += text[i];
      i++;
      if (i >= text.length) {
        clearInterval(interval);
        resolve();
      }
    }, speed);
  });
}

/**
 * Cria um delay (Promise) de tempo definido.
 * @param {number} ms - Milissegundos de delay.
 * @returns {Promise}
 */
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Garante que o histórico role até a última mensagem.
 */
function scrollHistorico() {
  historico.scrollTop = historico.scrollHeight;
}

/**
 * Registra cliques nos serviços.
 * @param {string} servicoDescricao - Descrição do serviço clicado.
 */
function registrarCliqueServico(servicoDescricao) {
  if (!conversaId) return;
  
  fetch('/servico_clicado', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conversa_id: conversaId,
      servico: servicoDescricao
    })
  }).catch(error => console.error('Erro ao registrar clique:', error));
}

/**
 * Ao sair da página, se a conversa ainda não tiver sido salva (ou seja, o usuário não votou),
 * envia o registro com feedback null.
 */
window.addEventListener("beforeunload", (event) => {
  if (!conversationSaved && currentChat && currentChat.resposta) {
    const url = '/feedback';
    currentChat.feedback = null;
    currentChat.timestamp = new Date().toISOString();
    const data = JSON.stringify(currentChat);
    if (navigator.sendBeacon) {
      const blob = new Blob([data], {type: 'application/json'});
      navigator.sendBeacon(url, blob);
    } else {
      fetch(url, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: data });
    }
  }
});