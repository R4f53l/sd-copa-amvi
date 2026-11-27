# Plano de implementação — Copa AMVI

Plano semanal para uma equipe de 4 desenvolvedores, alinhado às entregas da disciplina **Sistemas Distribuídos (CCMP0054)**.

| Entrega | Conteúdo | Data | Peso |
|---|---|---|---|
| II | Modelos e Admin | **01/10** | 1,0 |
| III | Visões e Formulários | **20/10** | 1,0 |
| IV | Apresentação final + deploy na nuvem com domínio | **10/12** | 7,0 |

> Plano elaborado em 28/09/2026. Atualize os checkboxes conforme as tarefas forem concluídas.
>
> **Situação revisada em 24/11/2026** com base no código da `main` (PRs #1 a #9). Itens marcados como feitos foram conferidos no código; itens parciais indicam o que falta.

---

## Decisão de arquitetura: páginas Django + API

A especificação cobra recursos que dependem de páginas renderizadas pelo próprio Django:

- **Entrega III:** "Visões e Formulários" (views, ModelForms e templates do Django).
- **Obrigatórios:** framework de mensagens, humanização (`django.contrib.humanize`), paginação e recuperação de senha por e-mail.

Por isso:

- O **site público** e o **painel do mesário** são feitos com **templates Django**, usando JavaScript só para o tempo real (WebSocket).
- A **API DRF** continua disponível e atende ao requisito desejável "fornecer API para outros sistemas", documentada com Swagger em `/api/docs/`.

Um front-end separado (React etc.) duplicaria o trabalho sem render nota.

---

## Divisão da equipe

Cada dev é responsável por uma área do sistema durante todo o projeto:

| Dev | Responsabilidade |
|---|---|
| **Dev 1** | Contas, autenticação, e-mail, internacionalização e infraestrutura (deploy, domínio, CI) |
| **Dev 2** | Cadastros (`teams`, `championships`) e classificação |
| **Dev 3** | Jogos: escalação, súmula, serviço de eventos e tempo real |
| **Dev 4** | Portal público: layout, calendário, página do jogo, estatísticas e APIs externas |

---

## Fase 1 — Entrega II: Modelos e Admin (28/09 → 01/10)

Os modelos já estão prontos. Falta registrar e customizar o admin (fieldsets e inlines são obrigatórios).

**Dev 1**
- [ ] Criar o repositório no GitHub, com proteção da branch `main` e fluxo de PR
- [x] Criar o `docker-compose` de desenvolvimento (Postgres e Redis), para todos usarem Postgres
- [x] Customizar o `UserAdmin`: fieldsets com o papel e filtro por papel (feito em 24/11; superusuários passam a ter o papel Administrador)

**Dev 2**
- [x] Admin de `City`, `Stadium`, `Team` e `Player`: `list_display`, busca e filtros
- [x] Fieldsets e prévia do escudo e da foto

**Dev 3**
- [x] Admin de `Championship` com os times inscritos (`ChampionshipTeam`) como inline e fieldsets Geral / Regulamento / Regras
- [x] Admin de `ChampionshipTeam` com as inscrições de jogadores como inline e a classificação só para leitura

**Dev 4**
- [x] Admin de `Match` com escalação (`Lineup`) e eventos (`MatchEvent`) como inlines
- [x] Admin de `MatchEvent` com os participantes como inline
- [x] Admin de `EventType` e `EventRole`
- [x] Comando `seed_demo` com cidades do PI, times e jogadores de exemplo

**Todos:** usar `list_select_related` nas listas cujo `__str__` acessa outras tabelas (`Match`, `Lineup`, `PlayerRegistration`), para evitar uma consulta por linha.

**Pronto quando:** o admin estiver navegável em português com os dados de demonstração e as validações dos modelos (`clean()`) aparecendo como erros nos formulários do admin.

---

## Fase 2 — Entrega III: Visões e Formulários (02/10 → 20/10)

### Semana 1 (02–08/10)

**Dev 1**
- [x] Login e logout por sessão, com templates. A rota de login deve se chamar `accounts:login` (já configurada em `LOGIN_URL`)
- [x] Recuperação de senha com e-mail. O envio já está configurado (`EMAIL_URL`); no desenvolvimento, o e-mail aparece no terminal
- [x] Controle de acesso das views: só admin, ou admin e mesário

**Dev 2**
- [x] Cadastros de times, jogadores, estádios e cidades com ModelForm
- [x] Listas paginadas com busca
- [x] Mensagens de sucesso e erro

**Dev 3**
- [x] Cadastro de jogos (calendário de confrontos)
- [x] Validações: times inscritos no campeonato e mandante diferente do visitante
- [x] Lista de jogos por rodada

**Dev 4**
- [x] `base.html`: layout, menu e exibição das mensagens
- [x] Ativar o `django.contrib.humanize`
- [x] Página inicial pública (concluída em 24/11: antes só redirecionava para a lista de jogos)
- [x] Lista de jogos e resultados, com filtros por rodada e cidade e paginação (filtro de cidade adicionado em 24/11)

### Semana 2 (09–15/10) — 12/10 é feriado

**Dev 1**
- [x] Cadastro de mesários pelo admin
- [x] Troca de senha
- [x] Painel do mesário com os jogos designados a ele
- [x] Testes de permissão

**Dev 2**
- [x] Cadastro de campeonatos
- [x] Inscrição de times com formset
- [x] Inscrição de jogadores, validando um time por campeonato e o número da camisa

**Dev 3**
- [x] Formulário de escalação com formset: 11 titulares, capitão único e só jogadores aptos
- [x] Súmula v1: formulário de evento com os participantes conforme o tipo
- [x] Cancelamento de evento

**Dev 4**
- [x] Página pública do jogo: escalações, local, horário, timeline e player do streaming (feito em 24/11): player do YouTube incorporado (`youtube-nocookie`); outros links viram botão
- [x] Página do time (feito em 24/11): campanha, elenco, próximos jogos, resultados e artilheiros do time
- [x] Tabela de classificação, lendo os campos atuais de `ChampionshipTeam` (feita no detalhe do campeonato; os valores dependem do `recompute_standings`, do Dev 2)

### Semana 3 (16–20/10) — fechamento

- [ ] Integração das partes e correção de bugs (todos)
- [ ] Revisão das mensagens de validação (todos)
- [ ] Congelar o código em **18/10**
- [ ] Testes finais em 19–20/10 e tag `v0.3`

---

## Fase 3 — Entrega IV: Final com deploy (21/10 → 10/12)

### S4 (21–27/10) — Serviços de domínio

**Dev 1**
- [ ] Dockerfile e compose de produção (Daphne, Postgres, Redis, Nginx)
- [ ] Settings de produção: segurança e arquivos estáticos
- [ ] **Primeiro deploy de teste na nuvem**

**Dev 2**
- [x] `recompute_standings()`: pontos, vitórias, saldo, gols pró, confronto direto e cartões (implementado em `apps/championships/services.py`; requer integração com o fluxo de encerramento do Dev 3)
- [x] Gravar a posição final em `ChampionshipTeam.rank` por grupo
- [x] Testes de classificação e suspensão adicionados (execução pendente: dependências Python não estão instaladas neste ambiente)

**Dev 3**
- [ ] `apps/matches/services.py`, com cada operação numa transação. Ao criar um evento junto com os participantes, validar aqui o papel e a presença do jogador na súmula, porque `MatchEventParticipant.clean()` só roda com o evento já salvo:
  - [ ] registrar e cancelar eventos, atualizando placar e cartões
  - [ ] avançar o período do jogo
  - [ ] encerrar o jogo e consolidar a súmula
- [ ] Testes

**Dev 4**
- [x] Consultas das estatísticas: artilharia, assistências e cartões (feito em 24/11): `apps/matches/stats.py`
- [x] Página da Central de Estatísticas (feito em 24/11): `/matches/stats/`

### S5 (28/10–03/11) — Tempo real (02/11 é feriado)

**Dev 1**
- [ ] Domínio, DNS e HTTPS (Let's Encrypt)
- [ ] E-mail SMTP real (Amazon SES, Brevo ou Gmail)

**Dev 2**
- [x] Suspensões por acúmulo de cartões (aplicadas ao recalcular classificação de jogos encerrados; liberação após cumprir suspensão ainda é administrativa)
- [x] Bloqueio de jogadores suspensos na escalação
- [x] Visualização dos jogos do mata-mata na página do campeonato

**Dev 3**
- [ ] Consumer do Channels, com um grupo por jogo
- [ ] Enviar os eventos só depois de gravados no banco (`transaction.on_commit`)

**Dev 4**
- [x] JavaScript da página do jogo: placar e timeline ao vivo, com reconexão automática (feito em 24/11): `static/js/live.js` consulta `/matches/<id>/live/` (10 s ao vivo, 60 s antes do jogo, para ao encerrar). Já tenta o WebSocket `/ws/matches/<id>/` assim que existir uma rota em `routing.py`: o consumer do Dev 3 só precisa enviar qualquer mensagem quando o jogo mudar
- [x] Seção "ao vivo agora" na página inicial (feito em 24/11): atualiza sozinha a cada 30 s (`/live-now/`)

### S6 (04–10/11) — APIs e internacionalização

**Dev 1**
- [ ] Internacionalização — **parcial**: seletor de idioma no layout ✅, modelos e telas de jogos, times, campeonatos e página inicial traduzidos ✅. Falta: as telas de senha (`apps/accounts/templates/accounts/password_*`) foram escritas com o texto-fonte em português; reescrever com texto em inglês e traduzir no `.po`, para funcionarem em inglês

**Dev 2**
- [x] Endpoints DRF só de leitura para times, campeonatos e classificação

**Dev 3**
- [ ] Endpoints DRF de jogos, eventos e estatísticas, documentados no Swagger

**Dev 4**
- [x] Clima no estádio via Open-Meteo, usando as coordenadas de `Stadium` (feito em 24/11): previsão na hora do jogo, com cache de 30 min; se a API falhar, a previsão some sem quebrar a página
- [x] Importar os municípios do PI pela API do IBGE (dados de governo) (feito em 24/11): `python manage.py import_ibge_cities [--state PI] [--update-names] [--dry-run]`

### S7 (11–17/11) — Qualidade

**Dev 1**
- [ ] CI no GitHub Actions (testes e ruff)
- [ ] Backup automático do Postgres
- [ ] Documentar o processo de migração e carga inicial (artefato obrigatório)

**Dev 2**
- [x] Time favorito salvo na sessão e destacado na tabela (inclui visitantes anônimos)

**Dev 3**
- [ ] Casos de borda: prorrogação, pênaltis, W.O. e evento cancelado durante o jogo

**Dev 4**
- [x] Ajustes para celular e responsividade (feito em 24/11): páginas públicas conferidas em 390 px de largura
- [x] Revisar o uso do humanize ("há 5 min", números formatados) (feito em 24/11): `naturalday`, `naturaltime` e `intcomma` (capacidade dos estádios)

### S8 (18–24/11) — Beta (20/11 é feriado)

- [ ] **Dev 1:** monitoramento e logs em produção
- [ ] **Dev 2:** carga dos dados reais da Copa AMVI
- [ ] **Dev 3:** simular um jogo completo, com o mesário usando o celular
- [ ] **Dev 4:** coletar feedback e ajustar a interface

### S9 (25/11–01/12) — Congelamento de funcionalidades

- [ ] Nenhuma funcionalidade nova depois de **01/12**
- [ ] Correções e testes (todos)
- [ ] Opcional (Dev 3): súmula do jogo em PDF

### S10 (02–10/12) — Apresentação

- [ ] **Dev 1:** deploy final e repositório público para a turma
- [ ] **Dev 2:** slides sobre a modelagem e as regras do campeonato
- [ ] **Dev 3:** slides sobre a arquitetura e o tempo real
- [x] **Dev 4:** roteiro da demonstração (feito em 24/11): [`docs/DEMO.md`](DEMO.md)
- [ ] **Ensaio geral em 08/12** (apresentação de 30 minutos)

---

## Requisitos da disciplina → onde são atendidos

| Requisito | Tipo | Semana |
|---|---|---|
| Grupo de 3 ou 4 integrantes | Obrigatório | ✅ |
| 7 a 10 modelos, 2 ou mais apps | Obrigatório | ✅ já atendido (14 modelos, 4 apps) |
| Customização do admin (fieldsets, inlines) | Obrigatório | Fase 1 |
| Validação de dados | Obrigatório | Modelos (feito) + S1–S2 |
| Banco de dados relacional (Postgres) | Obrigatório | ✅ |
| Mensagens, paginação e humanização | Obrigatório | Apps já ativos no settings; uso nas páginas em S1 |
| Recuperação de senha e envio de e-mail | Obrigatório | E-mail configurado; telas em S1 (console) → S5 (SMTP real) |
| Deploy na nuvem gratuita + domínio | Entrega IV | S4 (teste) → S5 (domínio) |
| Processo de migração e carga inicial | Entrega IV | Fase 1 (`seed_demo`) + S7 |
| Código-fonte compartilhado com a turma | Entrega IV | S10 |
| Sessões anônimas | Desejável | S7 |
| Consumir API REST externa | Desejável | S6 (Open-Meteo, IBGE) |
| Fornecer API para outros sistemas | Desejável | S6 (DRF + Swagger, já iniciado) |
| Internacionalização (inglês/português) | Desejável | Base e modelos prontos; templates em S6 |

---

## Riscos

1. **Entrega II em 3 dias.** Dá para cumprir porque cada dev cuida do admin de um app. Não é o momento de refatorar os modelos.
2. **Hospedagem gratuita com tempo real.** Uma máquina pequena (GCP e2-micro, gratuita permanente, ou AWS t3.micro, gratuita por 12 meses) roda Postgres, Redis e Daphne com 1 GB de RAM, mas no limite. Por isso o primeiro deploy fica na S4. Se o WebSocket não funcionar lá, a página passa a consultar o servidor a cada 10 segundos.
3. **Domínio.** A especificação pede domínio próprio. Um `.com.br` custa cerca de R$ 40 por ano; convém confirmar com o professor se um subdomínio gratuito é aceito.
4. **Feriados.** 12/10, 02/11 e 20/11 caem em semanas de desenvolvimento; as tarefas dessas semanas já estão dimensionadas com um dia a menos.
