const stateLogin = document.getElementById("stateLogin");
const stateLoading = document.getElementById("stateLoading");
const stateResult = document.getElementById("stateResult");
const errorBox = document.getElementById("errorBox");

const loginForm = document.getElementById("loginForm");
const usuarioInput = document.getElementById("usuario");
const senhaInput = document.getElementById("senha");
const unidadesInput = document.getElementById("unidades");
const loadingDetail = document.getElementById("loadingDetail");

const resultIcon = document.getElementById("resultIcon");
const resultTitle = document.getElementById("resultTitle");
const resultTimestamp = document.getElementById("resultTimestamp");
const resultUnidades = document.getElementById("resultUnidades");
const avisoParcial = document.getElementById("avisoParcial");
const manifest = document.getElementById("manifest");
const manifestRows = document.getElementById("manifestRows");
const exportarBtn = document.getElementById("exportarExcelBtn");
const novaConsultaBtn = document.getElementById("novaConsultaBtn");

let dadosAtuais = [];
let timestampAtual = "";

function mostrarEstado(estado) {
  stateLogin.hidden = estado !== "login";
  stateLoading.hidden = estado !== "loading";
  stateResult.hidden = estado !== "result";
  errorBox.hidden = true;
}

function adicionarLinhaManifest(obj) {
  const row = document.createElement("div");
  row.className = "manifest__row";
  row.innerHTML = `
    <span class="sit sit--${obj.situacao.toLowerCase()}">${obj.situacao}</span>
    <span>${obj.seq} | ${obj.objeto}</span>
    <span class="tempo">${obj.tempo}</span>
    <span class="unidade">${obj.unidade || ""}</span>
  `;
  manifestRows.appendChild(row);
  manifest.hidden = false;
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const usuario = usuarioInput.value.trim();
  const senha = senhaInput.value;
  const unidades = unidadesInput.value
    .split("\n")
    .map((u) => u.trim())
    .filter((u) => u.length > 0);

  dadosAtuais = [];
  manifestRows.innerHTML = "";
  avisoParcial.hidden = true;
  
  mostrarEstado("loading");
  loadingDetail.textContent = "Iniciando conexão com o servidor SMT...";

  try {
    const response = await fetch("/api/consultar_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario, senha, unidades }),
    });

    if (!response.ok) {
      throw new Error("Erro na comunicação com o servidor.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop(); // Mantém o fragmento restante

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const payload = JSON.parse(line.replace("data: ", ""));
          
          if (payload.tipo === "progresso") {
            loadingDetail.textContent = `Processando página ${payload.pagina} de ${payload.total_paginas}... (Itens encontrados: ${dadosAtuais.length})`;
          } else if (payload.tipo === "itens") {
            payload.objetos.forEach(obj => {
              dadosAtuais.push(obj);
              adicionarLinhaManifest(obj);
            });
          } else if (payload.tipo === "alerta") {
            avisoParcial.hidden = false;
            avisoParcial.textContent = `⚠️ ${payload.mensagem}`;
          } else if (payload.tipo === "erro_fatal") {
            throw new Error(payload.mensagem);
          }
        }
      }
    }

    // Finalização
    senhaInput.value = "";
    timestampAtual = new Date().toLocaleString("pt-BR");
    resultTimestamp.textContent = `Última consulta: ${timestampAtual}`;
    resultUnidades.textContent = `Unidades: ${unidades.length ? unidades.join(", ") : "(todas)"}`;

    if (dadosAtuais.length > 0) {
      resultIcon.textContent = "⚠️";
      resultTitle.textContent = `${dadosAtuais.length} pendência(s) encontrada(s)`;
      exportarBtn.hidden = false;
    } else {
      resultIcon.textContent = "✅";
      resultTitle.textContent = "Nenhuma pendência encontrada.";
      exportarBtn.hidden = true;
    }

    mostrarEstado("result");

  } catch (err) {
    senhaInput.value = "";
    mostrarEstado("login");
    errorBox.hidden = false;
    errorBox.textContent = err.message || "Falha na conexão durante a extração.";
  }
});
