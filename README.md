# Painel SMT - Consulta Multiusuário

Qualquer pessoa com login no SMT abre esta página, informa seu próprio
usuário/senha e um número de WhatsApp, clica em consultar, vê uma tela de
processamento e recebe o resultado na tela **e** no WhatsApp informado —
mostrando só os dados da própria unidade (porque a visualização já é
restrita pelo próprio SMT, de acordo com o login usado).

Não há disparo automático aqui — só roda quando alguém pede.

---

## Por que Render, e não Vercel

Vercel é uma plataforma **serverless**: cada requisição roda uma função que
sobe, executa e desliga, sem disco persistente e com tempo de execução
limitado. Este painel depende de duas coisas que não cabem nesse modelo:
um navegador real controlando o login no SMT (que pode levar bem mais que o
limite de execução de uma função serverless) e, principalmente, a sessão do
WhatsApp Web que **envia** os alertas — ela precisa continuar logada entre
uma consulta e outra, o que exige disco persistente.

O Render permite subir o mesmo Dockerfile como um serviço web **contínuo**,
com disco persistente opcional. É o que esse projeto usa.

---

## Estrutura

```
smt-painel-simples/
├── app.py                 backend Flask (rotas pública e de admin)
├── smt_scraper.py          login, navegação, filtro e extração do SMT
├── whatsapp_sender.py       envio via WhatsApp Web + ligação da conta
├── templates/index.html     página (login → processando → resultado)
├── static/style.css
├── static/app.js
├── requirements.txt
├── Dockerfile
├── render.yaml               blueprint de deploy automático no Render
├── .env.example
├── .gitignore
├── .dockerignore
└── README.md
```

## Segurança - leia antes de publicar

- **Nenhuma senha de SMT é armazenada.** Cada usuário digita a própria,
  ela é usada só durante aquela consulta e descartada - não fica em
  banco, nem em log, nem em arquivo.
- A conta que **envia** os alertas pelo WhatsApp é uma só (a sua, ou uma
  conta dedicada). Ela é ligada **uma única vez** por uma rota escondida
  (`/admin/whatsapp-qr?token=...`), protegida por um token secreto - assim,
  nenhum usuário comum do painel consegue escanear esse QR Code e tomar
  conta do número que envia os alertas.
- O `ADMIN_TOKEN` deve ser um valor aleatório e forte, conhecido só por
  você. O `render.yaml` já gera esse valor automaticamente no deploy.
- Use sempre HTTPS em produção (o Render já fornece isso automaticamente
  para o domínio `*.onrender.com` ou para domínio próprio configurado).

---

## 1. Configuração local (antes de subir pro GitHub)

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

Edite o `.env` e defina um `ADMIN_TOKEN` próprio (qualquer string aleatória
longa). Não precisa colocar usuário/senha do SMT em lugar nenhum - isso
agora é digitado na tela por quem for usar.

## 2. Ligar a conta de WhatsApp que envia os alertas (uma vez só)

Rode localmente, com `WHATSAPP_HEADLESS=false` no `.env` (assim dá pra ver
o navegador abrir):

```bash
python app.py
```

Em outra aba do navegador, acesse:

```
http://localhost:5000/admin/whatsapp-qr?token=SEU_ADMIN_TOKEN
```

Isso abre o navegador automatizado no WhatsApp Web. Escaneie o QR Code com
o celular da conta que vai enviar os alertas. A sessão fica salva na pasta
`whatsapp_session/`. Depois disso, pode testar uma consulta completa pela
página principal (`http://localhost:5000`) usando seu próprio login do SMT.

## 3. GitHub

```bash
git init
git add .
git commit -m "Painel SMT multiusuário"
git remote add origin SEU_REPOSITORIO_AQUI
git push -u origin main
```

O `.gitignore` já exclui `.env` e `whatsapp_session/` - nada sensível sobe
pro repositório.

## 4. Deploy no Render

**Opção rápida (Blueprint):** no painel do Render, escolha "New" →
"Blueprint", aponte para o seu repositório no GitHub. O `render.yaml` já
configura tudo: build via Docker, disco persistente para a sessão do
WhatsApp, e gera um `ADMIN_TOKEN` aleatório sozinho (você vê o valor gerado
na aba de variáveis de ambiente do serviço, depois do primeiro deploy).

**Opção manual:** "New" → "Web Service" → conecte o repositório → ambiente
"Docker" → adicione um disco persistente apontando para
`/app/whatsapp_session` → defina `ADMIN_TOKEN` e `WHATSAPP_HEADLESS=true`
nas variáveis de ambiente.

> O plano gratuito do Render **não inclui disco persistente** - sem ele, a
> sessão do WhatsApp se perde a cada reinício/novo deploy, exigindo escanear
> o QR Code de novo toda vez. Para isso não acontecer, use um plano pago com
> disco (o plano "Starter" já resolve).

Depois do primeiro deploy, repita o passo 2 (ligar o WhatsApp) usando a URL
pública do Render em vez de `localhost`:

```
https://SEU-APP.onrender.com/admin/whatsapp-qr?token=SEU_ADMIN_TOKEN
```

Isso vai gerar uma imagem PNG do QR Code direto no navegador (mesmo sem
tela no servidor, o Chromium headless consegue tirar essa captura) -
escaneie com o celular normalmente.

## 5. Observações

- Se o SMT atualizar a versão do sistema, seletores podem mudar e quebrar
  a extração - nesse caso, reconfira o HTML atual da tela.
- Se aparecer CAPTCHA na tela de login, a consulta vai falhar para aquele
  usuário até resolver manualmente - isso é raro, mas pode acontecer.
- Confirme com a área de TI/segurança da Correios se esse tipo de automação
  de login é permitida pelas políticas internas antes de divulgar o painel
  para outros colegas.
