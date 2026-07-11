"""
Painel SMT - consulta multiusuário com seleção de múltiplas unidades.
Sem envio de WhatsApp.

Rotas:
    GET  /                página principal
    POST /api/consultar   roda a consulta e retorna JSON com os objetos
"""

import os
import logging
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from smt_scraper import rodar_consulta, montar_mensagem

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("app")

app = Flask(__name__)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))
CONSULTA_HEADLESS = os.environ.get("CONSULTA_HEADLESS", "false").lower() == "true"

# Carrega a lista de unidades do arquivo unidades.txt (uma por linha).
# Se o arquivo não existir, a lista começa vazia e o usuário preenche na tela.
_UNIDADES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unidades.txt")

def _carregar_unidades():
    try:
        with open(_UNIDADES_FILE, encoding="utf-8") as f:
            unidades = []
            for linha in f:
                # Remove espaços, aspas simples/duplas e vírgulas que podem
                # aparecer se o arquivo foi copiado de uma lista Python
                nome = linha.strip().strip(',').strip().strip('"').strip("'").strip()
                if nome and not nome.startswith("#"):
                    unidades.append(nome)
            return unidades
    except FileNotFoundError:
        return []

UNIDADES_PADRAO = _carregar_unidades()
log.info("Unidades carregadas do arquivo: %d unidades", len(UNIDADES_PADRAO))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/unidades")
def api_unidades():
    """Devolve a lista de unidades padrão lida de unidades.txt."""
    return jsonify({"unidades": UNIDADES_PADRAO})


@app.route("/api/consultar", methods=["POST"])
def api_consultar():
    payload = request.get_json(silent=True) or {}
    usuario = (payload.get("usuario") or "").strip()
    senha = payload.get("senha") or ""

    # Unidades: lista enviada pelo frontend, ou vazia (busca todas)
    unidades_raw = payload.get("unidades") or []
    if isinstance(unidades_raw, str):
        unidades_raw = [u.strip() for u in unidades_raw.split(",") if u.strip()]
    unidades = [u.strip() for u in unidades_raw if u.strip()]

    if not usuario or not senha:
        return jsonify({"ok": False, "erro": "Informe usuário e senha do SMT."})

    try:
        resultado = rodar_consulta(usuario, senha, unidades=unidades, headless=CONSULTA_HEADLESS)
    except (PlaywrightTimeoutError, RuntimeError) as e:
        return jsonify({"ok": False, "erro": str(e)})
    except Exception as e:
        return jsonify({"ok": False, "erro": f"Erro inesperado: {e}"})
    finally:
        senha = None

    objetos = resultado.get("objetos", [])

    return jsonify({
        "ok": True,
        "tem_pendencia": len(objetos) > 0,
        "objetos": objetos,
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "unidades_consultadas": unidades if unidades else ["(todas)"],
        "completo": resultado.get("completo", True),
        "paginas_processadas": resultado.get("paginas_processadas"),
        "paginas_total": resultado.get("paginas_total"),
        "erro_parcial": resultado.get("erro_parcial"),
    })


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)