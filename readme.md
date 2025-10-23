# ⚠️ Aviso Importante

Este repositório é parte de um **estudo experimental** sobre o uso do **Python para criação de um MCP Server universal**, capaz de servir *tools*, *resources* e *prompts* de forma declarativa via JSON.

O código e os exemplos aqui contidos **não devem ser utilizados em produção**.
Não há garantias de estabilidade, segurança, compatibilidade ou manutenção.
**O uso é por conta e risco do usuário.**

# MCP HTTP Hub

Servidor **MCP (Model Context Protocol)** em Python que atua como **ponte universal entre APIs HTTP e clientes MCP** (como ChatGPT, Copilot, ou outras aplicações que suportam o protocolo).

Permite definir *tools*, *resources* e *prompts* em arquivos JSON — sem precisar programar endpoints manualmente.
Suporta:
- Chamadas **HTTP** (GET, POST, PUT, etc.)
- Envio de **form-urlencoded** e **multipart/form-data**
- Respostas **JSON**, **texto** ou **binárias**
- Autenticação (Bearer, API Key, Basic, OAuth2 Client Credentials)
- Placeholders com variáveis (`{id}`, `{token}`, etc.)
- Filtros em respostas JSON
- Configuração via `.env`

---

## 📦 Instalação

```bash
docker-compose up -d
```

Depois, é necessário instalar as dependências, dentro do container:

```bash
docker-compose exec app bash -c 'pip install -r requirements.txt'
```

---

## 🧩 Configuração `.env`

Crie um arquivo `.env` na raiz do projeto (ou copie de `.env.example`):

```env
# Servidor MCP
HOST=0.0.0.0
PORT=8030
SERVER_NAME=MCP-HTTP-Hub

# Arquivos de definição
TOOLS_FILE=config/tools.json
PROMPTS_FILE=config/prompts.json
RESOURCES_FILE=config/resources.json

# HTTP padrão
HTTP_TIMEOUT=15
HTTP_VERIFY_SSL=false
MAX_MULTIPART_MB=25

# Logs
LOG_LEVEL=debug

# Tokens de exemplo
API_TOKEN=seu_token_aqui
MAPS_KEY=chave_googlemaps
CRM_CLIENT_ID=abc123
CRM_CLIENT_SECRET=def456
```

---

## 🚀 Execução

```bash
python mcp_server.py
```

Saída esperada:

```
DEBUG:    Carregando tools de config/tools.json
DEBUG:    Tool carregada: product-details - Obtém informações de um produto
INFO:     Started server process [53]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8030 (Press CTRL+C to quit)
```

---

## 🧠 Conceito

Cada tipo de definição é lido de um arquivo JSON:

| Tipo | Função |
|------|---------|
| **tools** | Operações acionáveis (chamadas HTTP, APIs) |
| **resources** | Endpoints consultáveis via URI (`content://...`) |
| **prompts** | Modelos de mensagens textuais (locais ou HTTP) |

---

## 🧰 Definindo Tools

Arquivo: `config/tools.json`

Cada tool é um objeto com:

| Campo | Descrição |
|--------|------------|
| `name` | Nome único da tool |
| `description` | Descrição breve |
| `args` | Parâmetros e tipos (`int`, `str`, `bool`, `float`) |
| `http` | Configuração HTTP (detalhes abaixo) |

### Exemplo 1 — GET simples

```json
[
  {
    "name": "mystore-produto",
    "description": "Busca informações de produto",
    "args": { "codigo": "str" },
    "http": {
      "method": "GET",
      "url": "https://api.my.store/products/{codigo}",
      "response": "json"
    }
  }
]
```

### Exemplo 2 — POST com `form-urlencoded`

```json
[
  {
    "name": "login",
    "description": "Autentica o usuário no serviço X",
    "args": { "username": "str", "password": "str" },
    "http": {
      "method": "POST",
      "url": "https://example.com/api/login",
      "form": {
        "user": "{username}",
        "pass": "{password}"
      },
      "response": "json"
    }
  }
]
```

### Exemplo 3 — Upload de arquivo (multipart)

```json
[
  {
    "name": "upload-avatar",
    "description": "Envia um avatar de usuário",
    "args": { "user_id": "int", "path": "str" },
    "http": {
      "method": "POST",
      "url": "https://api.example.com/users/{user_id}/avatar",
      "multipart": {
        "avatar": {
          "file": "{path}",
          "filename": "avatar-{user_id}.png",
          "content_type": "image/png"
        },
        "note": "Upload via MCP"
      },
      "response": "json"
    }
  }
]
```

---

## 📚 Definindo Resources

Arquivo: `config/resources.json`

Um *resource* é lido pelo URI `content://...`, podendo ter parâmetros:

```json
[
  {
    "uri": "content://my.store/produto/{codigo}",
    "description": "Detalhe do produto por código",
    "args": { "codigo": "str" },
    "http": {
      "method": "GET",
      "url": "https://api.my.store/products/{codigo}",
      "response": "json"
    }
  }
]
```

---

## 💬 Definindo Prompts

Arquivo: `config/prompts.json`

### Exemplo 1 — Texto estático

```json
[
  {
    "name": "saudacao",
    "description": "Mensagem de boas-vindas",
    "text": "Olá! Em que posso ajudar hoje?"
  }
]
```

### Exemplo 2 — Template com parâmetros

```json
[
  {
    "name": "pergunta",
    "description": "Gera uma pergunta com base em um tema",
    "content": "Qual a sua opinião sobre {tema}?",
    "params": ["tema"]
  }
]
```

### Exemplo 3 — Prompt dinâmico via HTTP

```json
[
  {
    "name": "noticias",
    "description": "Obtém manchetes de tecnologia",
    "http": {
      "method": "GET",
      "url": "https://api.example.com/news?topic=tech",
      "response": "json"
    },
    "render": {
      "mode": "text",
      "template": "Principais manchetes: {titles}"
    }
  }
]
```

---

## 🔐 Autenticação (`http.auth`)

A chave `auth` pode ser adicionada dentro de qualquer bloco `"http"`.
Suporta quatro tipos principais:

| Tipo | Descrição |
|------|------------|
| `bearer` | Token simples (`Authorization: Bearer ...`) |
| `api_key` | Chave em header ou query string |
| `basic` | Autenticação HTTP básica |
| `oauth2_client_credentials` | Fluxo completo OAuth2 com cache de token |

---

### 1️⃣ Bearer Token

```json
"auth": {
  "type": "bearer",
  "token_env": "API_TOKEN"
}
```

ou usando argumento:

```json
"auth": {
  "type": "bearer",
  "token_template": "{token}"
}
```

---

### 2️⃣ API Key

**Header:**
```json
"auth": {
  "type": "api_key",
  "in": "header",
  "name": "X-API-Key",
  "value_env": "API_KEY"
}
```

**Query string:**
```json
"auth": {
  "type": "api_key",
  "in": "query",
  "name": "key",
  "value_env": "MAPS_KEY"
}
```

---

### 3️⃣ Basic Auth

```json
"auth": {
  "type": "basic",
  "username_env": "BASIC_USER",
  "password_env": "BASIC_PASS"
}
```

---

### 4️⃣ OAuth2 Client Credentials

Com cache automático e refresh ao receber 401:

```json
"auth": {
  "type": "oauth2_client_credentials",
  "token_url": "https://auth.example.com/oauth/token",
  "client_id_env": "CRM_CLIENT_ID",
  "client_secret_env": "CRM_CLIENT_SECRET",
  "scope": "contacts.read",
  "audience": "https://api.crm.example.com/",
  "timeout": 10
}
```

Token é obtido, cacheado por `expires_in - 30s`, e reutilizado até expirar.

---

## ⚡️ Dicas rápidas

- **Placeholders**: `{variavel}` é substituída por valores do contexto (args + env).
- **Filtros JSON**: `"filter": {"where_contains": {"campo": "{q}"}}` filtra resultados.
- **Formulários**: `"form"` → `application/x-www-form-urlencoded`.
- **Arquivos**: `"multipart"` → `multipart/form-data`.
- **SSL self-signed**: `HTTP_VERIFY_SSL=false` ignora verificação.
- **Logs**: `LOG_LEVEL=debug` mostra detalhes de carregamento e requisições.

---

## 🧪 Testando

Liste ferramentas:

```bash
http POST http://localhost:8030/mcp \
    jsonrpc=2.0 id:=1 \
    method=tools/list
```

Chame uma tool:

```bash
http POST http://localhost:8030/mcp \
    jsonrpc=2.0 id:=2 \
    method=tools/call \
    params:='{"name":"product-details","arguments":{"codigo":"ABC123"}}'
```

Dentro do diretório `tests` há scripts bashs com exemplos de uso.

---

## 🛠️ Licença

MIT — livre para uso e modificação.