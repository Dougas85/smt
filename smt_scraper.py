"""
Módulo de login, navegação e extração do Painel de Controle da Distribuição
do SMT (Correios) - versão multiusuário com múltiplas unidades.
"""

import os
import logging

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

SMT_URL = "https://smt.correios.com.br/smt"
GREEN_RGB = "rgb(89, 211, 6)"

log = logging.getLogger("smt_scraper")

DEBUG_SCREENSHOT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "debug_ultimo_erro.png"
)


def login_smt(page, usuario, senha):
    if not usuario or not senha:
        raise RuntimeError("Usuário e senha são obrigatórios.")
    log.info("Acessando %s", SMT_URL)
    page.goto(SMT_URL, wait_until="networkidle")
    page.wait_for_selector("#username", timeout=30000)
    page.fill("#username", usuario)
    page.fill("#password", senha)
    page.click("button[name='submitBtn']")
    page.wait_for_load_state("networkidle", timeout=30000)
    if page.locator("#username").count() > 0:
        raise RuntimeError("Usuário ou senha do SMT inválidos.")
    log.info("Login realizado.")


def abrir_painel_distribuicao(page):
    log.info("Abrindo menu lateral...")
    page.click("#nav-menu")
    page.wait_for_timeout(600)
    log.info("Navegando para Painel de Controle da Distribuição...")
    page.click("text=OPERAÇÃO")
    page.wait_for_timeout(500)
    page.click("text=Painel de Controle da Distribuição")
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_selector("h1:has-text('Painel de Controle da Distribuição')", timeout=30000)


def selecionar_unidades(page, unidades):
    """Seleciona as unidades no React Select multi-seleção.
    Usa Enter para confirmar cada opção em vez de clique, mais rápido e estável.
    """
    if not unidades:
        log.info("Sem filtro de unidade — buscando todas visíveis ao login.")
        return

    log.info("Selecionando %d unidades...", len(unidades))

    for idx, unidade in enumerate(unidades, 1):
        unidade = unidade.strip().strip(',').strip().strip('"').strip("'").strip()
        if not unidade:
            continue
        try:
            # Clica no controle do Select para abrir/focar
            controle = page.locator(".Select--multi .Select-control").first
            controle.click()
            page.wait_for_timeout(200)

            # Digita o nome com keyboard.type() — dispara os eventos React
            # que mostram o dropdown (fill() não dispara esses eventos)
            page.keyboard.type(unidade, delay=30)
            page.wait_for_timeout(400)

            # Aguarda a primeira opção aparecer e clica nela
            primeira_opcao = page.locator(".Select-option").first
            primeira_opcao.wait_for(state="visible", timeout=5000)
            primeira_opcao.click()
            page.wait_for_timeout(200)

            if idx % 10 == 0:
                log.info("  %d/%d unidades selecionadas...", idx, len(unidades))

        except PlaywrightTimeoutError:
            # Limpa o campo antes de continuar
            try:
                page.keyboard.press("Escape")
                page.keyboard.press("Control+a")
                page.keyboard.press("Delete")
            except Exception:
                pass
            log.warning("Unidade '%s' não encontrada — pulando.", unidade)
        except Exception as e:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            log.warning("Erro ao selecionar '%s': %s — pulando.", unidade, e)

    page.wait_for_timeout(800)
    log.info("Seleção de unidades concluída.")


def aplicar_filtro_situacao(page):
    log.info("Ajustando filtro de Situação para C e I...")
    for codigo in ["B", "R", "D", "E", "F"]:
        cb = page.locator(f"#situacao-{codigo}")
        if cb.count() > 0 and cb.is_checked():
            cb.uncheck()
    for codigo in ["C", "I"]:
        cb = page.locator(f"#situacao-{codigo}")
        if cb.count() > 0 and not cb.is_checked():
            cb.check()

    # Confirma quantas unidades estão selecionadas antes de pesquisar
    tags = page.locator(".Select--multi .Select-value, .Select--multi .Select-multi-value")
    qtd_tags = tags.count()
    log.info("Unidades no seletor antes de pesquisar: %d tags", qtd_tags)

    page.click("text=Pesquisar")
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(1500)


def coletar_objetos_fora_do_verde(page):
    objetos_em_risco = []
    pagina_atual = 1
    total_paginas = None
    completo = True
    erro_parcial = None

    while True:
        log.info("Lendo página %d da tabela...", pagina_atual)

        # Tenta obter o total de páginas na primeira iteração
        if total_paginas is None:
            try:
                inp_pagina = page.locator("input[placeholder='Página']")
                if inp_pagina.count() > 0:
                    max_attr = inp_pagina.get_attribute("max")
                    if max_attr:
                        total_paginas = int(max_attr)
                        log.info("Total de páginas: %d", total_paginas)
            except Exception:
                pass

        try:
            page.wait_for_selector(".rt-tbody", timeout=45000)
        except PlaywrightTimeoutError as e:
            completo = False
            erro_parcial = (
                f"Tempo esgotado aguardando tabela na página {pagina_atual}. "
                f"Processadas: {pagina_atual - 1}"
                + (f" de {total_paginas}" if total_paginas else "") + " páginas."
            )
            log.error(erro_parcial)
            break

        try:
            page.wait_for_selector(".-loading-inner", state="hidden", timeout=10000)
        except PlaywrightTimeoutError:
            pass

        linhas = page.locator(".rt-tr-group")
        total_linhas = linhas.count()

        for i in range(total_linhas):
            try:
                linha = linhas.nth(i)
                celulas = linha.locator(".rt-td.grid-painel")
                if celulas.count() < 8:
                    continue

                seq = celulas.nth(0).inner_text(timeout=5000).strip()
                objeto_codigo = celulas.nth(1).inner_text(timeout=5000).strip().split("\n")[0]
                situacao_texto = celulas.nth(6).inner_text(timeout=5000).strip()

                if situacao_texto not in ("I", "C"):
                    continue

                tempo_cel = celulas.nth(7).locator("div").first
                if tempo_cel.count() == 0:
                    continue

                tempo_texto = tempo_cel.inner_text(timeout=5000).strip()
                if not tempo_texto:
                    continue

                style_attr = tempo_cel.get_attribute("style") or ""
                if GREEN_RGB in style_attr:
                    continue

                try:
                    unidade_texto = celulas.nth(4).inner_text(timeout=3000).strip()
                except Exception:
                    unidade_texto = ""

                objetos_em_risco.append({
                    "seq": seq,
                    "objeto": objeto_codigo,
                    "situacao": situacao_texto,
                    "tempo": tempo_texto,
                    "unidade": unidade_texto,
                })
                log.info("[%s] Seq %s | %s | %s | %s",
                          situacao_texto, seq, objeto_codigo, tempo_texto, unidade_texto)
            except PlaywrightTimeoutError:
                log.warning("Linha %d pág %d não pôde ser lida — pulando.", i, pagina_atual)
                continue

        botao_proxima = page.locator(".Table__nextPageWrapper button")
        if botao_proxima.count() == 0 or botao_proxima.is_disabled():
            break

        try:
            botao_proxima.click()
            page.wait_for_timeout(2000)
            try:
                page.wait_for_selector(".-loading-inner", state="hidden", timeout=10000)
            except PlaywrightTimeoutError:
                pass
            pagina_atual += 1
        except Exception as e:
            completo = False
            erro_parcial = (
                f"Erro ao navegar para página {pagina_atual + 1}: {e}. "
                f"Processadas: {pagina_atual}"
                + (f" de {total_paginas}" if total_paginas else "") + " páginas."
            )
            log.error(erro_parcial)
            break

    return {
        "objetos": objetos_em_risco,
        "paginas_processadas": pagina_atual,
        "paginas_total": total_paginas,
        "completo": completo,
        "erro_parcial": erro_parcial,
    }


def montar_mensagem(resultado):
    """Monta mensagem de resultado. Aceita o dict retornado por rodar_consulta."""
    objetos = resultado.get("objetos", [])
    completo = resultado.get("completo", True)
    erro_parcial = resultado.get("erro_parcial")
    paginas_processadas = resultado.get("paginas_processadas", "?")
    paginas_total = resultado.get("paginas_total", "?")

    if not objetos and completo:
        return "Nenhum objeto pendente. Tudo certo."

    linhas = []
    if not completo:
        linhas.append(
            f"⚠️ RESULTADO PARCIAL — {paginas_processadas} de {paginas_total} páginas processadas."
        )
        linhas.append("")

    if objetos:
        linhas.append(f"{len(objetos)} objeto(s) pendente(s):")
        linhas.append("")
        for obj in objetos:
            unidade = f" | {obj['unidade']}" if obj.get("unidade") else ""
            linhas.append(
                f"[{obj['situacao']}] Seq {obj['seq']} | {obj['objeto']} | {obj['tempo']}{unidade}"
            )
    else:
        linhas.append("Nenhum objeto pendente nas páginas processadas.")

    return "\n".join(linhas)


def rodar_consulta(usuario, senha, unidades=None, headless=False):
    """Faz login, seleciona unidades, filtra C e I, retorna dict com objetos
    e metadados de paginação (inclusive resultado parcial em caso de timeout)."""
    if unidades is None:
        unidades = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1366, "height": 768})
        try:
            login_smt(page, usuario, senha)
            abrir_painel_distribuicao(page)
            selecionar_unidades(page, unidades)
            aplicar_filtro_situacao(page)
            resultado = coletar_objetos_fora_do_verde(page)
            return resultado
        except Exception as e:
            try:
                page.screenshot(path=DEBUG_SCREENSHOT_PATH, full_page=True)
                log.error("Falha fatal — print salvo em %s", DEBUG_SCREENSHOT_PATH)
            except Exception:
                pass
            raise
        finally:
            browser.close()