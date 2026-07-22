import os
import logging
import json
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, Response
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from smt_scraper import rodar_consulta_generator

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("app")

app = Flask(__name__)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))
CONSULTA_HEADLESS = os.environ.get("CONSULTA_HEADLESS", "true").lower() == "true"

_UNIDADES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unidades.txt")

def _carregar_unidades():
    try:
        with open(_UNIDADES_FILE, encoding="utf-8") as f:
            unidades = []
            for linha in f:
                nome = linha.strip().strip(',').strip().strip('"').strip("'").strip()
                if nome and not nome.startswith("#"):
                    unidades.append(nome)
            return unidades
    except FileNotFoundError:
        return []

UNIDADES_PADRAO = _carregar_unidades()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/unidades")
def api_unidades():
    return jsonify({"unidades": UNIDADES_PADRAO})

@app.route("/api/consultar_stream", methods=["POST"])
def api_consultar_stream():
    """Endpoint via SSE (Server-Sent Events) para transmitir progresso e dados em tempo real."""
    payload = request.get_json(silent=True) or {}
    usuario = (payload.get("usuario") or "").strip()
    senha = payload.get("senha") or ""

    unidades_raw = payload.get("unidades") or []
    if isinstance(unidades_raw, str):
        unidades_raw = [u.strip() for u in unidades_raw.split(",") if u.strip()]
    unidades = [u.strip() for u in unidades_raw if u.strip()]

    if not usuario or not senha:
        return jsonify({"ok": False, "erro": "Informe usuário e senha do SMT."}), 400

    def generate():
        try:
            for evento in rodar_consulta_generator(usuario, senha, unidades=unidades, headless=CONSULTA_HEADLESS):
                yield f"data: {json.dumps(evento)}\n\n"
        except Exception as e:
            err_payload = {"tipo": "erro_fatal", "mensagem": f"Erro crítico durante a execução: {str(e)}"}
            yield f"data: {json.dumps(err_payload)}\n\n"

    return Response(generate(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
