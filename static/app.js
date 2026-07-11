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

function renderManifest(objetos) {
  manifestRows.innerHTML = "";
  objetos.forEach((obj) => {
    const row = document.createElement("div");
    row.className = "manifest__row";
    row.innerHTML = `
      <span class="sit sit--${obj.situacao.toLowerCase()}">${obj.situacao}</span>
      <span>${obj.seq} | ${obj.objeto}</span>
      <span class="tempo">${obj.tempo}</span>
      <span class="unidade">${obj.unidade || ""}</span>
    `;
    manifestRows.appendChild(row);
  });
  manifest.hidden = false;
}

function exportarExcel() {
  if (!dadosAtuais.length) return;

  const linhas = dadosAtuais.map((obj) => ({
    Situação: obj.situacao,
    Sequencial: obj.seq,
    Objeto: obj.objeto,
    Tempo: obj.tempo,
    Unidade: obj.unidade || "",
  }));

  const ws = XLSX.utils.json_to_sheet(linhas);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Pendências");

  // Largura das colunas
  ws["!cols"] = [
    { wch: 10 },
    { wch: 12 },
    { wch: 18 },
    { wch: 10 },
    { wch: 28 },
  ];

  const dataArq = timestampAtual
    .replace(/\//g, "-")
    .replace(" ", "_")
    .replace(":", "h");
  XLSX.writeFile(wb, `pendencias_smt_${dataArq}.xlsx`);
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const usuario = usuarioInput.value.trim();
  const senha = senhaInput.value;
  const unidades = unidadesInput.value
    .split("\n")
    .map((u) => u.trim())
    .filter((u) => u.length > 0);

  mostrarEstado("loading");
  loadingDetail.textContent =
    unidades.length > 0
      ? `Selecionando ${unidades.length} unidade(s) e consultando...`
      : "Consultando todas as unidades...";

  try {
    const resposta = await fetch("/api/consultar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario, senha, unidades }),
    });
    const dados = await resposta.json();

    senhaInput.value = "";

    if (!dados.ok) {
      mostrarEstado("login");
      errorBox.hidden = false;
      errorBox.textContent =
        dados.erro || "Não foi possível concluir a consulta.";
      return;
    }

    dadosAtuais = dados.objetos || [];
    timestampAtual = dados.timestamp;

    resultTimestamp.textContent = `Última consulta: ${dados.timestamp}`;
    resultUnidades.textContent = `Unidades: ${(dados.unidades_consultadas || []).join(", ")}`;
    manifest.hidden = true;
    avisoParcial.hidden = true;
    exportarBtn.hidden = true;

    // Aviso de resultado parcial
    if (!dados.completo && dados.erro_parcial) {
      avisoParcial.hidden = false;
      avisoParcial.textContent = `⚠️ Resultado parcial: ${dados.erro_parcial}`;
    }

    if (dados.tem_pendencia) {
      const qtd = dadosAtuais.length;
      resultIcon.textContent = dados.completo ? "⚠️" : "⚠️";
      resultTitle.textContent = `${qtd} pendência${qtd > 1 ? "s" : ""}${dados.completo ? "" : " (parcial)"}`;
      renderManifest(dadosAtuais);
      exportarBtn.hidden = false;
    } else {
      resultIcon.textContent = dados.completo ? "✅" : "⚠️";
      resultTitle.textContent = dados.completo
        ? "Tudo certo"
        : "Nenhuma pendência nas páginas processadas";
    }

    mostrarEstado("result");
  } catch (err) {
    senhaInput.value = "";
    mostrarEstado("login");
    errorBox.hidden = false;
    errorBox.textContent =
      "Não foi possível conversar com o servidor. Tente novamente.";
  }
});

exportarBtn.addEventListener("click", exportarExcel);

novaConsultaBtn.addEventListener("click", () => {
  usuarioInput.value = "";
  senhaInput.value = "";
  dadosAtuais = [];
  mostrarEstado("login");
});

// Carrega as unidades padrão do servidor ao abrir a página
async function carregarUnidadesPadrao() {
  try {
    const resp = await fetch("/api/unidades");
    const dados = await resp.json();
    if (dados.unidades && dados.unidades.length > 0) {
      unidadesInput.value = dados.unidades.join("\n");
    }
  } catch (e) {
    /* usuário preenche manualmente */
  }
}

carregarUnidadesPadrao();
