# Hermes Agent — Combo de IA governado

O [hermes-agent](https://github.com/NousResearch/hermes-agent) (MIT, Nous Research)
é o orquestrador de agentes da operação. Ele aceita **qualquer endpoint
OpenAI-compatible** — por isso apontamos para a nossa cadeia:

```
Hermes Agent (CLI 24/7 + gateway Telegram)
   │
   ▼ provider "custom" → http://localhost:20128/v1
OmniRoute (combo "auto": fallback entre todos os providers conectados)
   │ fallback
   ▼
AIsa (api.aisa.one — OpenAI-compatible, pago por uso)
   │ fallback
   ▼
Slot genérico (9route — desativado até verificação)
```

## Instalação (VPS)

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc
```

## Configuração

1. Copie `hermes.json` para `~/.hermes/config.json` (ou rode `hermes setup`
   e escolha **Custom Endpoint** → base URL `http://localhost:20128/v1`).
2. `hermes model` → selecione o modelo `auto` do OmniRoute.
3. Regras de governança já estão no `system_prompt_suffix` do config:
   - nunca recomenda aposta nem prevê resultado;
   - nunca sugere aumentar stake ou recuperar perda;
   - vocabulário neutro (spec docs/05).

## Combo 24/7

| Peça | Papel | Onde roda |
|---|---|---|
| Observer bridge | MutationObserver lê o DOM do jogo e envia eventos via WebSocket | **seu PC** (login manual) |
| Command Center API | ledger, travas, settle de apostas papel | VPS |
| Hermes Agent | análise, resumos, perguntas do Copilot | VPS (Docker) |
| OmniRoute | roteamento IA com fallback e compressão | VPS (Docker) |
| Telegram bot | notificações + comandos (/status /saldo /apostas /parar /voltar /relatorio) | via Hermes gateway ou polling próprio |

## Comandos Hermes úteis

```bash
hermes setup                  # wizard inicial
hermes model                  # trocar modelo/provider
hermes gateway setup          # Telegram/Discord 24/7 (após CLI funcionar)
hermes cron                   # agendar relatório diário 22:00
hermes chat                   # conversa direta com o analista
```

## Limites de governança

O Hermes aqui **não** tem toolset de browser/computer-use/code-execution —
config em `hermes.json` (`agent.disabled_toolsets`). Ele não pode agir no
cassino; só analisa dados que já passaram pelas travas do Command Center.
