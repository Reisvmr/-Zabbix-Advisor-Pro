# Zabbix Advisor Pro

Ferramenta em Python para **healthcheck de ambientes Zabbix** com foco em leitura simples, recomendações práticas e arquitetura pronta para evoluir.

## O que entrega nesta versão

- Conexão com a API do Zabbix por **token**
- Dashboard web com resumo executivo
- KPIs do ambiente
- Top hosts por volume de itens
- Top templates por volume de itens
- Análise de itens **unsupported**
- Análise de itens **SNMP candidatos a modelo assíncrono**
- Recomendações automáticas e priorizadas
- Links para o frontend do Zabbix
- API REST para integração futura
- Dockerfile e docker-compose

## Arquitetura

```text
zabbix-advisor-pro/
├── app/
│   ├── clients/
│   ├── core/
│   ├── routers/
│   ├── schemas/
│   ├── services/
│   ├── static/
│   ├── templates/
│   └── main.py
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Execução local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abra:

```text
http://127.0.0.1:8000
```

## Docker

```bash
docker compose up --build
```

## Token de API

No frontend do Zabbix, gere um token e informe:

- URL base do Zabbix, por exemplo: `https://monitoramento.seudominio.com`
- Token da API
- URL do frontend, se quiser links diretos para correção

## Próximas evoluções recomendadas

- Persistência com SQLite/PostgreSQL
- Histórico de snapshots
- Comparação entre execuções
- Exportação PDF
- Coleta de métricas internas e filas via itens internos do Zabbix
- Modo multiambiente
- Módulo por proxy
- Autenticação local

## Observação

A API do Zabbix precisa estar acessível em `URL_BASE/api_jsonrpc.php`.
