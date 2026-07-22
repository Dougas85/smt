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
    log.info("Login realizado com sucesso.")

def abrir_painel_distribuicao(page):
    page.click("#nav-menu")
    page.wait_for_timeout(400)
    page.click("text=OPERAÇÃO")
    page.wait_for_timeout(300)
    page.click("text=Painel de Controle da Distribuição")
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_selector("h1:has-text('Painel de Controle da Distribuição')", timeout=30000)

def selecionar_unidades(page, unidades):
    if not unidades:
        return
    for idx, unidade in enumerate(unidades, 1):
        unidade = unidade.strip().strip(',').strip().strip('"').strip("'").strip()
        if not unidade:
            continue
        try:
            controle = page.locator(".Select--multi .Select-control").first
            controle.click()
            page.wait_for_timeout(150)
            page.keyboard.type(unidade, delay=20)
            page.wait_for_timeout(300)
            primeira_opcao = page.locator(".Select-option").first
            primeira_opcao.wait_for(state="visible", timeout=4000)
            primeira_opcao.click()
        except Exception as e:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            log.warning("Unidade '%s' não selecionada: %s", unidade, e)

def aplicar_filtro_situacao(page):
    for codigo in ["B", "R", "D", "E", "F"]:
        cb = page.locator(f"#situacao-{codigo}")
        if cb.count() > 0 and cb.is_checked():
            cb.uncheck()
    for codigo in ["C", "I"]:
        cb = page.locator(f"#situacao-{codigo}")
        if cb.count() > 0 and not cb.is_checked():
            cb.check()

    page.click("text=Pesquisar")
    page.wait_for_load_state("networkidle", timeout=30000)

def rodar_consulta_generator(usuario, senha, unidades=None, headless=True):
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

            pagina_atual = 1
            total_paginas = None

            yield {"tipo": "inicio", "mensagem": "Consulta iniciada na plataforma SMT."}

            while True:
                if total_paginas is None:
                    try:
                        inp_pagina = page.locator("input[placeholder='Página']")
                        if inp_pagina.count() > 0:
                            max_attr = inp_pagina.get_attribute("max")
                            if max_attr:
                                total_paginas = int(max_attr)
                    except Exception:
                        pass

                yield {
                    "tipo": "progresso",
                    "pagina": pagina_atual,
                    "total_paginas": total_paginas or "?"
                }

                try:
                    page.wait_for_selector(".rt-tbody", timeout=20000)
                except PlaywrightTimeoutError:
                    yield {
                        "tipo": "alerta",
                        "mensagem": f"Timeout ao carregar a página {pagina_atual}. Finalizando com os dados capturados até aqui."
                    }
                    break

                linhas = page.locator(".rt-tr-group")
                total_linhas = linhas.count()
                objetos_pagina = []

                for i in range(total_linhas):
                    try:
                        linha = linhas.nth(i)
                        celulas = linha.locator(".rt-td.grid-painel")
                        if celulas.count() < 8:
                            continue

                        seq = celulas.nth(0).inner_text(timeout=2000).strip()
                        objeto_codigo = celulas.nth(1).inner_text(timeout=2000).strip().split("\n")[0]
                        situacao_texto = celulas.nth(6).inner_text(timeout=2000).strip()

                        if situacao_texto not in ("I", "C"):
                            continue

                        tempo_cel = celulas.nth(7).locator("div").first
                        if tempo_cel.count() == 0:
                            continue

                        tempo_texto = tempo_cel.inner_text(timeout=2000).strip()
                        style_attr = tempo_cel.get_attribute("style") or ""

                        if GREEN_RGB in style_attr or not tempo_texto:
                            continue

                        try:
                            unidade_texto = celulas.nth(4).inner_text(timeout=1500).strip()
                        except Exception:
                            unidade_texto = ""

                        obj_data = {
                            "seq": seq,
                            "objeto": objeto_codigo,
                            "situacao": situacao_texto,
                            "tempo": tempo_texto,
                            "unidade": unidade_texto,
                        }
                        objetos_pagina.append(obj_data)
                    except Exception:
                        continue

                if objetos_pagina:
                    yield {"tipo": "itens", "objetos": objetos_pagina}

                botao_proxima = page.locator(".Table__nextPageWrapper button")
                if botao_proxima.count() == 0 or botao_proxima.is_disabled():
                    break

                try:
                    botao_proxima.click()
                    page.wait_for_timeout(1000)
                    pagina_atual += 1
                except Exception as e:
                    yield {
                        "tipo": "alerta",
                        "mensagem": f"Interrupção na navegação para página {pagina_atual + 1}: {str(e)}"
                    }
                    break

            yield {"tipo": "fim", "status": "concluido"}

        finally:
            browser.close()
