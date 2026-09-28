# Copa AMVI

Sistema web do campeonato regional de futebol Copa AMVI, disputado por cidades do Piauí. Ele atende a dois públicos:

- **Painel administrativo**: administradores e mesários registram jogos e eventos (gols, cartões, substituições) em tempo real.
- **Portal público**: torcedores consultam resultados, classificação, estatísticas e lances ao vivo, sem login.

**Arquitetura:** o site e o painel são páginas renderizadas pelo Django (templates e formulários), com login por sessão. O tempo real usa WebSocket (Channels). Uma API REST (DRF + JWT) fica disponível para outros sistemas.

**Stack:** Python 3.12 · Django 6.1 · Django Channels · PostgreSQL · Django REST Framework · SimpleJWT · Redis (opcional)

---

## Status do projeto

### ✅ Já está pronto

- **Estrutura modular por domínio**: não existe um app monolítico. Cada contexto de negócio é um app independente dentro de `apps/`, com rotas próprias para as páginas (`urls.py`) e para a API (`api/urls.py`).
- **Configuração base** (`config/settings.py`):
  - Variáveis sensíveis lidas de `.env` via `django-environ`.
  - `AUTH_USER_MODEL = "accounts.User"`.
  - Site: templates do projeto em `templates/`, arquivos estáticos em `static/`, `django.contrib.humanize` e `messages` ativos, e URLs de login e logout definidas (`LOGIN_URL = "accounts:login"`).
  - E-mail configurado via `EMAIL_URL`: no desenvolvimento os e-mails são impressos no terminal; em produção usa SMTP. É o que a recuperação de senha vai usar.
  - Segurança para produção: `CSRF_TRUSTED_ORIGINS` e cookies seguros quando `DEBUG=False`.
  - DRF com autenticação JWT (para sistemas externos) e por sessão (para o JavaScript do próprio site), leitura pública e escrita autenticada, filtros, paginação e limite de requisições.
  - SimpleJWT: token de acesso de 30 min e refresh de 7 dias, renovado a cada uso.
  - Channels com Redis quando `REDIS_URL` está definido; senão, uma camada em memória.
  - Idiomas pt-BR (padrão) e inglês, fuso `America/Fortaleza` (Piauí) e CORS configurável.
- **ASGI** (`config/asgi.py`): recebe HTTP e WebSocket. O WebSocket usa a mesma sessão de login do site. As rotas de WebSocket vêm de `apps/matches/routing.py`, que ainda está vazio.
- **Rotas**: páginas na raiz do site (`/teams/`, `/matches/`…, ainda vazias), API em `/api/v1/` com o login JWT, e troca de idioma em `/i18n/setlang/`.
- **Tradução pt-BR completa** dos modelos: nomes, campos, opções, textos de ajuda e mensagens de validação (veja [Tradução](#tradução-i18n)).
- **Documentação OpenAPI 3** com Swagger UI e ReDoc (veja [Documentação da API](#documentação-da-api-swagger)).
- **Modelagem completa dos 4 domínios**, com migrations iniciais geradas (detalhes abaixo).
- **Catálogo de eventos inicial**: a migration `matches/0002` cadastra os tipos e papéis de evento da súmula (veja [Catálogo de eventos](#catálogo-de-eventos)).

### 🚧 Ainda não implementado

O cronograma completo, com as tarefas semanais de cada dev, está em [`docs/PLANO.md`](docs/PLANO.md).

- Páginas (views, formulários e templates): login, recuperação de senha, cadastros, súmula e portal público.
- Serializers, viewsets e permissões por papel (admin / mesário). Os routers da API estão vazios.
- Camada de serviço (`apps/matches/services.py`) que, ao registrar um evento, deve:
  - atualizar o placar de `Match`;
  - recalcular a classificação em `ChampionshipTeam`, incluindo os critérios de desempate e o campo `rank`;
  - enviar o evento via WebSocket.
- Regras da escalação: no máximo 11 titulares e bloqueio de jogadores suspensos ou com inscrição encerrada.
- Controle de suspensões por cartões (usando `Championship.yellow_cards_for_suspension`).
- Consumers WebSocket para os lances ao vivo.
- Endpoints de estatísticas (artilharia, assistências, cartões).
- Registro e customização dos modelos no Django Admin (fieldsets, inlines, `list_select_related`).
- Testes automatizados.
- Dockerfile e compose de produção (o `docker-compose.yml` atual sobe só o Postgres e o Redis de desenvolvimento).

---

## Organização de pastas

```
copa-amvi/
├── manage.py
├── pyproject.toml          # metadados do projeto e configuração do ruff
├── requirements.txt        # dependências de produção
├── requirements-dev.txt    # + ferramentas de desenvolvimento (ruff)
├── docker-compose.yml      # Postgres e Redis para desenvolvimento
├── .env.example            # modelo das variáveis de ambiente
├── .editorconfig           # padrão de indentação e codificação
├── docs/
│   └── PLANO.md            # cronograma e tarefas semanais da equipe
├── config/                 # projeto Django (configuração global)
│   ├── settings.py
│   ├── urls.py             # junta as rotas do site (/) e da API (/api/v1/)
│   ├── asgi.py             # HTTP + WebSocket (Channels)
│   └── wsgi.py
├── templates/              # templates do projeto (base.html, registration/…)
├── static/                 # CSS, JS e imagens do projeto
├── locale/
│   └── pt_BR/LC_MESSAGES/  # traduções (django.po / django.mo)
└── apps/
    ├── shared/             # NÃO é um app Django: só modelos abstratos
    │   └── models.py       # TimeStampedModel (created_at / updated_at)
    ├── accounts/           # usuários e autenticação
    ├── teams/              # cidades, estádios, times, jogadores
    ├── championships/      # campeonatos, inscrições de times e jogadores
    └── matches/            # jogos, escalações, eventos e tempo real
        └── routing.py      # rotas WebSocket
```

Cada app segue a mesma estrutura:

```
apps/<app>/
├── models.py, admin.py, apps.py
├── urls.py, views.py             # páginas do site (templates)
├── forms.py                      # formulários (criar quando necessário)
├── templates/<app>/              # templates do app
├── api/
│   ├── urls.py                   # rotas da API (router DRF)
│   └── views.py, serializers.py  # (criar quando necessário)
├── migrations/
└── tests/
```

Os namespaces das rotas são `<app>` para as páginas (ex.: `{% url "teams:detail" pk %}`) e `<app>_api` para a API.

### Regras de arquitetura

- **Chaves estrangeiras entre apps** usam string no formato `"app_label.Model"`, por exemplo `"championships.ChampionshipTeam"`. Isso evita importações circulares.
- **Todas as relações** declaram `related_name`.
- **Cada app tem `label` curto** (`accounts`, `teams`, …), mas fica no pacote `apps.<nome>`.
- **Lógica de negócio que envolve vários modelos** deve ficar em `services.py` do app. Assim as views do site e os viewsets da API chamam o mesmo código, sem duplicar regras.
- **Templates de cada app** ficam em `apps/<app>/templates/<app>/`. Os de uso geral, como `base.html` e as telas de login (`registration/`), ficam em `templates/` na raiz.
- **Todo texto exibido ao usuário** é escrito em inglês e marcado para tradução: `_()` / `gettext_lazy` no Python e `{% translate %}` nos templates. Todo campo de modelo tem `verbose_name`.

---

## Modelo de dados

| App | Modelo | Descrição |
|---|---|---|
| `accounts` | `User` | Usuário customizado com `role`: `ADMIN` ou `TABLE_OFFICIAL` (mesário) |
| `teams` | `City` | Município participante (padroniza o filtro por cidade) |
| | `Stadium` | Estádio (cidade, capacidade, coordenadas) |
| | `Team` | Time (sigla, escudo, cores, cidade, estádio da casa) |
| | `Player` | Jogador (nome, apelido, nascimento, foto, posição, documento único). Não aponta para time |
| `championships` | `Championship` | Edição do campeonato: ano, status, regulamento (texto e PDF), regras de pontuação e cartões |
| | `ChampionshipTeam` | Inscrição de um time num campeonato, com grupo, classificação consolidada, cartões e posição final (`rank`) |
| | `PlayerRegistration` | Vínculo jogador ↔ time no campeonato, com número da camisa e histórico |
| `matches` | `Match` | Jogo: status ao vivo, placar consolidado, pênaltis, link de transmissão (`streaming_url`), mesários designados |
| | `Lineup` | Súmula: titular/reserva, camisa e capitão |
| | `EventType` | Catálogo de tipos de evento (gol, gol contra, cartão…) |
| | `EventRole` | Papel do jogador no evento (autor, assistência, entra, sai…) |
| | `MatchEvent` | Evento do jogo: período, minuto e acréscimo, quem registrou, cancelamento |
| | `MatchEventParticipant` | Jogadores envolvidos num evento e o papel de cada um |

### Decisões importantes

- **Jogos ligados à inscrição, não ao time**: `Match`, `Lineup` e `MatchEvent` apontam para `ChampionshipTeam`, e não para `Team`. Assim, um jogo só envolve times inscritos naquele campeonato.
- **Placar e classificação guardados prontos**: `Match.home_score/away_score` e as estatísticas de `ChampionshipTeam` ficam gravados no banco. Isso deixa as consultas públicas baratas; quem atualiza esses campos é a camada de serviço.
- **Tipos de evento como dados**: `EventType` é uma tabela, não uma lista fixa no código, para permitir novos tipos sem deploy. O campo `score_effect` diz se o evento altera o placar do próprio time ou do adversário (gol contra).
- **Eventos nunca são apagados**: uma correção marca `is_canceled` e registra quem cancelou e por quê. Isso preserva a auditoria e permite transmitir a correção ao vivo.
- **Histórico de vínculos**: um jogador que sai do time recebe `released_on`, e a inscrição não é removida.
- **Validações entre tabelas** (ex.: um jogador ativo em só um time por campeonato) estão em `clean()` dos modelos. Os serializers devem chamar essas validações.
- **Período do jogo é numérico** (1º tempo = 1 … pênaltis = 5), para a timeline ficar em ordem cronológica, incluindo a prorrogação.
- **Posição na tabela vem do serviço**: critérios como confronto direto não cabem num `ORDER BY`. Por isso o serviço aplica o regulamento completo e grava a posição final em `ChampionshipTeam.rank`, que é o que a tabela pública usa para ordenar.
- **Cidade é uma tabela** (`City`, UF padrão `PI`), não texto livre, para que grafias diferentes não quebrem os filtros.

### Catálogo de eventos

A migration `apps/matches/migrations/0002_seed_event_types_and_roles.py` cadastra os itens abaixo. O `code` é o identificador usado no código e nas consultas de estatísticas; não o altere. O nome exibido pode ser editado.

**Tipos de evento** (`EventType`)

| Código | Nome | Efeito no placar |
|---|---|---|
| `goal` | Gol | a favor do time |
| `penalty-goal` | Gol de pênalti | a favor do time |
| `own-goal` | Gol contra | a favor do adversário |
| `penalty-missed` | Pênalti perdido | — |
| `yellow-card` | Cartão amarelo | — |
| `second-yellow-card` | Segundo cartão amarelo | — (conta como amarelo e vermelho) |
| `red-card` | Cartão vermelho | — |
| `substitution` | Substituição | — |
| `shootout-goal` / `shootout-missed` | Pênalti convertido / perdido na disputa | — (vai para o placar de pênaltis) |
| `period-start` / `period-end` | Início / fim do período | — (sem time) |

**Papéis** (`EventRole`): `scorer` (autor do gol), `assist` (assistência), `own-goal-author` (autor do gol contra), `penalty-taker` (cobrador), `goalkeeper` (goleiro), `booked-player` (jogador punido), `player-in` (jogador que entra), `player-out` (jogador que sai).

O gol contra usa o papel `own-goal-author`, e não `scorer`, para nunca contar na artilharia.

---

## Como rodar

### Pré-requisitos

- Python 3.12+
- Docker (para o Postgres e o Redis de desenvolvimento). Sem Docker, instale o PostgreSQL 14+ localmente e ajuste o `DATABASE_URL`.

### Passo a passo

```bash
cd copa-amvi

# 1. Banco de dados e Redis
docker compose up -d

# 2. Ambiente virtual
python -m venv .venv
source .venv/Scripts/activate      # Windows (Git Bash)
# .venv\Scripts\Activate.ps1       # Windows (PowerShell)
# source .venv/bin/activate        # Linux / macOS

# 3. Dependências (inclui as ferramentas de desenvolvimento)
pip install -r requirements-dev.txt

# 4. Variáveis de ambiente
cp .env.example .env
# edite o .env e defina SECRET_KEY (o DATABASE_URL padrão já aponta
# para o Postgres do docker compose)

# 5. Tabelas e dados iniciais
python manage.py migrate
python manage.py createsuperuser

# 6. Servidor (ASGI via Daphne: HTTP + WebSocket)
python manage.py runserver
```

A API sobe em `http://localhost:8000/`, com a documentação em `http://localhost:8000/api/docs/`.

### Variáveis de ambiente

| Variável | Exemplo | Descrição |
|---|---|---|
| `SECRET_KEY` | — | Chave secreta do Django (obrigatória) |
| `DEBUG` | `True` | Modo debug |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hosts permitidos, separados por vírgula |
| `DATABASE_URL` | `postgres://copa_amvi:copa_amvi@localhost:5432/copa_amvi` | Conexão com o PostgreSQL |
| `DB_CONN_MAX_AGE` | `60` | Tempo (s) que conexões persistentes ficam abertas |
| `REDIS_URL` | `redis://localhost:6379/0` | Camada do Channels; vazio usa memória |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Origens externas que podem chamar a API, separadas por vírgula |
| `CSRF_TRUSTED_ORIGINS` | `https://copaamvi.com.br` | Obrigatório em produção para os formulários funcionarem com HTTPS |
| `EMAIL_URL` | `consolemail://` | Envio de e-mail. Em produção: `smtp+tls://usuario:senha@smtp.exemplo.com:587` |
| `DEFAULT_FROM_EMAIL` | `Copa AMVI <nao-responda@...>` | Remetente dos e-mails (ex.: recuperação de senha) |

Para gerar uma `SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

---

## Endpoints disponíveis

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/api/v1/auth/token/` | Login: recebe `username` e `password` e devolve `access` e `refresh` |
| `POST` | `/api/v1/auth/token/refresh/` | Renova o token de acesso |
| — | `/api/v1/accounts/` | *(router vazio)* |
| — | `/api/v1/teams/` | *(router vazio)* |
| — | `/api/v1/championships/` | *(router vazio)* |
| — | `/api/v1/matches/` | *(router vazio)* |
| — | `/admin/` | Django Admin |
| `GET` | `/api/docs/` | Documentação interativa (Swagger UI) |
| `GET` | `/api/redoc/` | Documentação em formato de leitura (ReDoc) |
| `GET` | `/api/schema/` | Schema OpenAPI 3 (YAML; `?format=json` para JSON) |

Nas requisições autenticadas, envie o cabeçalho `Authorization: Bearer <access_token>`.

---

## Documentação da API (Swagger)

A documentação é gerada automaticamente pelo [drf-spectacular](https://drf-spectacular.readthedocs.io/) a partir dos serializers e viewsets. Cada endpoint novo aparece nela sem configuração extra.

Com o servidor rodando, acesse `http://localhost:8000/api/docs/`. Para testar rotas protegidas:

1. Chame `POST /api/v1/auth/token/` com usuário e senha e copie o campo `access`.
2. Clique em **Authorize** e cole o token (sem o prefixo `Bearer`).
3. O token continua salvo mesmo ao recarregar a página.

O botão **Authorize** só aparece quando existe pelo menos um endpoint que exige JWT, ou seja, depois que os primeiros viewsets forem criados.

Para exportar o schema (por exemplo, para gerar um cliente no front-end ou validar no CI):

```bash
python manage.py spectacular --validate --file schema.yml
```

Para melhorar a documentação de um endpoint específico, use `@extend_schema` nos viewsets:

```python
from drf_spectacular.utils import extend_schema


@extend_schema(tags=["Jogos"], summary="Timeline do jogo")
def timeline(self, request, pk=None): ...
```

---

## Tradução (i18n)

O código é escrito em inglês e traduzido para pt-BR, que é o idioma padrão. O inglês fica disponível pelo seletor de idioma (`/i18n/setlang/`).

As traduções ficam em `locale/pt_BR/LC_MESSAGES/django.po`. Depois de adicionar ou alterar textos marcados com `_()` ou `{% translate %}`:

```bash
python manage.py makemessages -l pt_BR --ignore=.venv   # atualiza o django.po
# edite o django.po e preencha os msgstr vazios
python manage.py compilemessages --ignore=.venv         # gera o django.mo
```

Os dois comandos precisam do **GNU gettext** instalado:
- Linux: `apt install gettext`
- macOS: `brew install gettext`
- Windows: instalador em https://mlocati.github.io/articles/gettext-iconv-windows.html

O `django.mo` compilado fica versionado, então só quem altera traduções precisa do gettext.

---

## Comandos úteis

```bash
python manage.py check                 # valida a configuração
python manage.py makemigrations        # gera migrations após alterar modelos
python manage.py migrate               # aplica migrations
python manage.py test apps             # roda os testes

ruff check .                           # verifica estilo e erros comuns
ruff check . --fix                     # corrige o que for automático
ruff format .                          # formata o código

docker compose down                    # para o Postgres e o Redis
docker compose down -v                 # para e APAGA os dados do banco
```

Em produção, instale só o `requirements.txt`; o `requirements-dev.txt` traz ferramentas que não são necessárias no servidor.
