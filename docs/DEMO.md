# Roteiro da demonstração — Copa AMVI

Demonstração ao vivo para a apresentação final (Entrega IV, 30 minutos no total).
Cerca de **12 minutos de demonstração**; o restante fica para os slides e perguntas.

Cada passo indica o **requisito da disciplina** que ele comprova.

---

## Preparação (antes da apresentação)

No servidor de demonstração (ou localmente):

```bash
python manage.py migrate
python manage.py seed_demo                    # campeonato, times, jogadores, mesário
python manage.py import_ibge_cities           # municípios do PI (API do IBGE)
python manage.py createsuperuser              # se ainda não existir
```

Depois, no admin (`/admin/`):

1. Em **Campeonatos**, deixe a Copa AMVI 2026 como **Em andamento**.
2. Em **Jogos**, escolha o jogo agendado e:
   - mude a data para **hoje**, em um horário próximo (a previsão do tempo aparece para até 16 dias);
   - preencha o **link da transmissão** com um vídeo do YouTube que permita incorporação;
   - designe o usuário `mesario` como mesário.
3. Confira que o estádio do jogo tem **latitude e longitude** (os do `seed_demo` já têm).

Deixe abertas duas janelas do navegador:

- **Janela A (torcedor):** aba anônima na página inicial.
- **Janela B (mesário):** logada como `mesario` / `mesario123`.

---

## Roteiro

| # | Tempo | Onde | O que mostrar | Requisito |
|---|---|---|---|---|
| 1 | 1 min | A · `/` | Página inicial: campeonato em destaque, próximos jogos, últimos resultados. Trocar o idioma no menu para **English** e voltar | Projeto web Django, **internacionalização** |
| 2 | 1 min | A · Jogos | Filtros por **cidade**, rodada e situação; paginação | **Paginação**, consultas ao banco |
| 3 | 1 min | A · Times → um time | Página do time: campanha, elenco, artilheiros do time | Navegação entre módulos (apps) |
| 4 | 1 min | B · login | Entrar com usuário errado (mensagem de erro) e depois certo. Mostrar **"Esqueceu a senha?"** e o e-mail chegando (console ou SMTP) | **Autenticação**, **recuperação de senha**, **envio de e-mail** |
| 5 | 2 min | B · Súmula do jogo | Escalação: tentar 12 titulares (erro), corrigir para 11 + reservas + capitão | **Formulários**, **formsets**, **validação de dados**, **framework de mensagens** |
| 6 | 2 min | B + A lado a lado | Mudar o jogo para **"1º tempo"** e registrar um **gol** na janela B. Na janela A (súmula do mesmo jogo), o placar e o lance a lance **atualizam sozinhos** em até 10 s | Comunicação cliente–servidor, **tempo real** |
| 7 | 1 min | B | Cancelar o gol com motivo: o lance fica riscado e o placar volta | Auditoria, regras de negócio na camada de serviço |
| 8 | 1 min | A · súmula | **Player do YouTube** incorporado e **previsão do tempo** do estádio | **Consumo de API externa** (Open-Meteo) |
| 9 | 1 min | A · Estatísticas | Artilharia, assistências e disciplina atualizadas com o gol registrado | Consultas agregadas |
| 10 | 1 min | `/admin/` | Admin customizado: jogo com escalação e lances como **inlines**, **fieldsets**, filtros; usuário com papel | **Customização do Admin** |
| 11 | 30 s | `/api/docs/` | Swagger da API REST | **Fornecer API** para outros sistemas |
| 12 | 30 s | terminal ou slide | `python manage.py import_ibge_cities --dry-run` | **Dados de governo** via API (IBGE) |

Ao longo do roteiro, aponte o **humanize** ("hoje", "há 2 minutos", "4.000 lugares").

---

## Plano B

| Problema | Solução |
|---|---|
| Internet lenta ou fora do ar | A previsão do tempo some sozinha (a página não quebra). Use capturas de tela nos slides para o clima e o player |
| O vídeo não carrega | O link "Assistir no YouTube" continua disponível |
| A atualização ao vivo demora | Ela ocorre a cada 10 s com o jogo em andamento; se precisar, recarregue a janela A |
| Erro inesperado no servidor | Tenha a demonstração gravada em vídeo como reserva |

---

## Checklist final (no dia)

- [ ] Servidor no ar, com HTTPS e domínio
- [ ] Dados preparados (passos da seção "Preparação")
- [ ] Usuários `admin` e `mesario` com senhas conhecidas pelo apresentador
- [ ] E-mail de recuperação de senha testado no servidor
- [ ] Janela anônima e janela logada abertas
- [ ] Vídeo de reserva da demonstração
