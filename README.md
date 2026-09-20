# Climatch — API (Back-End)

API REST responsável pelas regras de negócio do Climatch: uma aplicação para
planejar eventos ao ar livre (casamentos, corridas, churrascos, trilhas,
etc.) levando em conta a previsão do tempo. A API recebe os dados do evento,
consulta a previsão climática na [Open-Meteo](https://open-meteo.com/),
classifica as condições (favorável, moderada ou arriscada) de acordo com o
tipo de evento, gera uma recomendação e persiste tudo no PostgreSQL.

Este repositório contém apenas a **API (Back-End)**, construída em
**Python + FastAPI**. A **Interface (Front-End)** que a consome está no
repositório [`climatch-web`](https://github.com/laurabonilha/climatch-web) —
é lá também que fica o `docker-compose.yml` que orquestra os três containers
do projeto (banco de dados, API e interface).

## Sumário

- [Arquitetura](#arquitetura)
- [Funcionalidades e regras de negócio](#funcionalidades-e-regras-de-negócio)
- [Tecnologias utilizadas](#tecnologias-utilizadas)
- [API externa consumida](#api-externa-consumida)
- [Modelo de dados](#modelo-de-dados)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Como rodar o projeto](#como-rodar-o-projeto)
  - [Opção 1 — Docker Compose (recomendado)](#opção-1--docker-compose-recomendado)
  - [Opção 2 — Rodando localmente sem Docker](#opção-2--rodando-localmente-sem-docker)
- [Documentação interativa (Swagger)](#documentação-interativa-swagger)
- [Referência das rotas](#referência-das-rotas)

## Arquitetura

O projeto segue o **Cenário 1.1** do MVP: uma Interface (Front-End) que
consome esta API principal (Back-End), que por sua vez consulta uma API
externa.

```
Interface (Front-End)  <──REST/JSON──>  API (Back-End)  <──HTTPS──  API Externa
     climatch-web              climatch-api              Open-Meteo
                                     │
                                     ▼
                              PostgreSQL (climatch-db)
```

O diagrama completo de arquitetura (com a indicação dos containers Docker e
do `docker-compose.yml`) está no README da
[Interface (`climatch-web`)](https://github.com/laurabonilha/climatch-web#arquitetura),
já que é lá que os três containers são orquestrados juntos.

## Funcionalidades e regras de negócio

- **Avaliação de evento**: ao criar ou atualizar um evento, a API busca as
  coordenadas da cidade, consulta a previsão do tempo para a data informada
  e classifica o evento como `favoravel`, `moderado` ou `arriscado`,
  considerando limites de chance de chuva e vento **específicos por tipo de
  evento** (ex.: um casamento tolera menos chuva/vento que uma corrida).
  Tipos de evento reconhecidos: `casamento`, `corrida`, `piquenique`,
  `praia`, `churrasco`, `futebol`, `show_ao_ar_livre`, `festa_infantil`,
  `trilha`, `acampamento`, `feira_ao_ar_livre`, `formatura_externa`. Tipos
  não reconhecidos usam limites genéricos.
- **Melhor horário do dia**: além da avaliação geral, a API calcula qual o
  horário do dia (entre 7h e 22h) tem a menor chance de chuva, e retorna as
  condições específicas no horário informado pelo usuário, se houver.
- **Atualização (`PATCH /eventos/{id}`) com escopo restrito**: o endpoint de
  atualização foi desenhado para *refinar* um evento já existente (nome,
  horário e descrição), sempre forçando uma nova consulta de previsão —
  útil para reavaliar o clima conforme a data do evento se aproxima. Cidade,
  data e tipo do evento **não podem ser alterados** por esse endpoint (mudar
  esses dados equivaleria a outro evento; nesse caso, o evento deve ser
  removido e recriado).
- **Melhor data entre candidatas**: dado um conjunto de datas candidatas
  para o mesmo evento (cidade + tipo), a API avalia todas e aponta qual tem
  a melhor previsão.
- **Cache de previsão**: consultas de previsão diária para a mesma
  cidade/data feitas há menos de 1 hora são reaproveitadas do banco em vez
  de gerar uma nova chamada à API externa.
- **Filtros e ordenação**: as rotas de listagem aceitam filtro por cidade
  (`?cidade=`) e retornam os resultados ordenados (eventos por data,
  sugestões pela mais recente).

## Tecnologias utilizadas

- [Python 3.12](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/) — framework web e geração
  automática de documentação Swagger/OpenAPI
- [Uvicorn](https://www.uvicorn.org/) — servidor ASGI
- [SQLAlchemy](https://www.sqlalchemy.org/) — ORM
- [Pydantic](https://docs.pydantic.dev/) — validação e serialização de dados
  (inclusive a conversão de datas entre o formato brasileiro `DD-MM-AAAA`,
  usado na API, e o formato ISO usado internamente e pela Open-Meteo)
- [PostgreSQL 16](https://www.postgresql.org/) — persistência
- [httpx](https://www.python-httpx.org/) — cliente HTTP para consumir a API
  externa
- [Docker](https://www.docker.com/)

## API externa consumida

A API consulta a **[Open-Meteo](https://open-meteo.com/)** para obter dados
climáticos (`app/services/openmeteo.py`):

| Item | Detalhe |
|---|---|
| Licença | Gratuita para uso não comercial, sem necessidade de chave de API |
| Cadastro | Não é necessário criar conta nem gerar API key |
| Endpoint de geocodificação | `GET https://geocoding-api.open-meteo.com/v1/search` — converte o nome da cidade em latitude/longitude |
| Endpoint de previsão diária | `GET https://api.open-meteo.com/v1/forecast` (parâmetro `daily`) — temperatura mín/máx, chance de chuva e vento máximo do dia |
| Endpoint de previsão horária | `GET https://api.open-meteo.com/v1/forecast` (parâmetro `hourly`) — usado para o melhor horário do dia e as condições no horário do evento |

Os dados são buscados e tratados inteiramente pela API — o cliente da API
(a interface) nunca é redirecionado para a Open-Meteo.

## Modelo de dados

Três tabelas no PostgreSQL (`app/models.py`):

- **`eventos`**: nome, tipo, cidade, data, hora, descrição e o resultado da
  última avaliação climática (classificação, recomendação, melhor horário e
  condições no horário informado).
- **`sugestoes_melhor_data`**: cidade, tipo de evento, datas candidatas e o
  resultado da comparação entre elas (classificação de cada data e qual é a
  melhor).
- **`consultas_clima`**: cache de previsões diárias já consultadas (cidade +
  data), usado para evitar chamadas repetidas à API externa.

## Estrutura de pastas

```
climatch-api/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py            # rotas da API e orquestração das regras de negócio
    ├── models.py          # modelos SQLAlchemy (tabelas do PostgreSQL)
    ├── schemas.py         # schemas Pydantic (validação/serialização, incl. datas BR ↔ ISO)
    ├── database.py        # configuração da conexão com o PostgreSQL
    └── services/
        ├── openmeteo.py   # integração com a API externa (Open-Meteo)
        └── risco.py       # regras de classificação climática por tipo de evento
```

## Como rodar o projeto

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e Docker Compose (opção 1)
- [Python 3.12+](https://www.python.org/downloads/) (opção 2, para rodar a API fora do Docker)

> ⚠️ O `docker-compose.yml` que sobe esta API junto com o banco de dados e a
> interface está no repositório da
> [Interface (`climatch-web`)](https://github.com/laurabonilha/climatch-web),
> e referencia o código deste repositório em `../climatch-api`. Por isso,
> clone os dois repositórios lado a lado, na mesma pasta pai, mantendo
> exatamente esses nomes:
>
> ```
> algum-diretorio/
> ├── climatch-api/     (este repositório)
> └── climatch-web/
> ```
>
> ```bash
> git clone https://github.com/laurabonilha/climatch-api.git
> git clone https://github.com/laurabonilha/climatch-web.git
> ```

### Opção 1 — Docker Compose (recomendado)

A partir do repositório `climatch-web` (onde está o `docker-compose.yml`):

```bash
cd climatch-web
docker compose up -d --build
```

Isso sobe os três containers: `climatch-db` (PostgreSQL), `climatch-api`
(esta API) e `climatch-web` (interface). A API fica disponível em
`http://localhost:8001`.

Também é possível construir e rodar só esta API isoladamente:

```bash
cd climatch-api
docker build -t climatch-api .
docker run -p 8000:8000 --env DATABASE_URL="postgresql://climatch:climatch123@host.docker.internal:5434/climatch" climatch-api
```

(nesse caso, é preciso ter um PostgreSQL acessível no endereço informado em
`DATABASE_URL` — por exemplo, subindo só o serviço `climatch-db` do compose:
`docker compose up -d climatch-db`, a partir de `climatch-web`).

### Opção 2 — Rodando localmente sem Docker

```bash
cd climatch-api
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt

# banco de dados: suba só o climatch-db via Docker (a partir de climatch-web)
#   docker compose up -d climatch-db
# ou aponte DATABASE_URL para um PostgreSQL já existente na sua máquina

uvicorn app.main:app --reload --port 8000
```

Variável de ambiente utilizada:

| Variável | Padrão (se não definida) | Descrição |
|---|---|---|
| `DATABASE_URL` | `postgresql://climatch:climatch123@localhost:5434/climatch` | String de conexão do PostgreSQL |

A API ficará disponível em `http://localhost:8000`.

## Documentação interativa (Swagger)

A API gera documentação automaticamente com o FastAPI:

- Swagger UI: `http://localhost:8000/docs` (ou `:8001/docs` quando rodando
  via Docker Compose)
- Redoc: `http://localhost:8000/redoc`

## Referência das rotas

7 rotas ao todo, cobrindo os métodos `GET`, `POST`, `PATCH` e `DELETE`:

### Eventos

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/eventos` | Cria um evento e já retorna a avaliação climática |
| `GET` | `/eventos` | Lista eventos (aceita `?cidade=` para filtrar) |
| `PATCH` | `/eventos/{id}` | Atualiza nome/horário/descrição e reavalia o clima |
| `DELETE` | `/eventos/{id}` | Remove um evento |

### Sugestões de melhor data

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/sugestoes-data` | Compara datas candidatas para um evento e aponta a melhor |
| `GET` | `/sugestoes-data` | Lista sugestões já calculadas (aceita `?cidade=` para filtrar) |
| `DELETE` | `/sugestoes-data/{id}` | Remove uma sugestão |

Para o formato completo de request/response de cada rota, use o Swagger
(`/docs`) — ele é gerado automaticamente a partir dos schemas Pydantic e
sempre reflete o estado atual da API.
