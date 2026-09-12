# ⚽ Football Blitz Command Center

Sistema local-first de **observação, análise e governança** para o jogo
Football Blitz (Pragmatic Play). Não aposta, não clica, não automatiza nada —
é uma estação de decisão responsável: registra eventos, mede limites, testa
hipóteses em replay e bloqueia operações quando um limite é atingido.

> **Este sistema NÃO executa apostas.** Não existe rota de auto-execução,
> martingale ou recuperação de perdas — por design, testado.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI + SQLite (append-only, hash chain SHA-256) |
| RAG | TF-IDF local determinístico com provenance (fonte + linha) |
| Compressão | Engine própria estilo RTK (30–60% economia de tokens) |
| IA | **OmniRoute** (gateway local `localhost:20128`, roteamento `auto`) |
| Fallback IA | Slot genérico OpenAI-compatible (para 9route ou outro endpoint verificado) |
| Frontend | HTML/CSS/JS puro (tema terminal escuro, sem build step) |
| Provenance | Semantica 0.6.8 (instalada; integração profunda é próximo sprint) |

## Instalação

```powershell
cd "football RAG SYSTEM AGENTS/command-center"
python -m pip install fastapi uvicorn pytest
```

## Rodar

```powershell
# 1. Gateway OmniRoute (se ainda não estiver rodando)
omniroute serve --daemon --no-open

# 2. Command Center
python -m uvicorn server:app --port 8765

# 3. Abrir o dashboard
#    http://localhost:8765
```

## Testes

```powershell
python -m pytest test_command_center.py -q
```

Cobertura: invariantes do ledger (append-only, hash chain, rejeição de eventos
sem timestamp/origem inválida), travas de política (limite diário, stop-loss,
cooldown, kill switch, mesa quente), governança da IA (schema, tom, fail-closed),
compressão determinística, replay determinístico e ausência de rotas de aposta.

## Travas de segurança (todas locais e bloqueantes)

| Trava | Padrão | Efeito |
|---|---|---|
| `FB_MAX_EVENTS_PER_DAY` | 200 | bloqueia novos eventos no dia |
| `FB_STOP_LOSS` | R$ 75 | bloqueia quando PnL papel atinge o limite |
| `FB_STOP_WIN` | 0 (off) | trava de lucro opcional |
| `FB_MAX_SESSION_MINUTES` | 60 | sessão expira para MANUAL_REVIEW |
| `FB_COOLDOWN_MINUTES` | 30 | bloqueia nova sessão após parada |
| `FB_HOT_STREAK` | 10 | alerta sonoro de mesa quente (anti-tendência) |

Estados de operação: `OFFLINE → PAPER → MANUAL_REVIEW → COOLDOWN → STOPPED`.
**Não existe estado `AUTO_EXECUTION`.**

## IA Governada (Copilot)

- Só descreve dados históricos; **nunca** prevê, recomenda aposta ou promete lucro;
- Toda saída passa por: extração JSON → validação de schema → checagem de tom
  (rejeita "garantido", "entrada certa", "recuperar prejuízo"…) → citação de fontes;
- Falha fechada: se a IA ou o gateway caem, responde com estatísticas locais;
- Contexto comprimido (relatório de compressão anexado a cada resposta);
- Segredos são redigidos antes de qualquer log/retorno.

## Roteamento de IA

Primário: **OmniRoute** (`OMNIROUTE_BASE_URL`, modelo `auto` = combo virtual com
fallback entre todos os providers conectados). Fallback opcional: slot genérico
OpenAI-compatible — ative com:

```env
GENERIC_PROVIDER_ENABLED=true
GENERIC_PROVIDER_BASE_URL=https://seu-endpoint-verificado
GENERIC_PROVIDER_MODEL=modelo
GENERIC_PROVIDER_API_KEY=...
```

> 9route permanece **não verificado** (sem repositório oficial confirmado).
> Configure o slot somente após validar origem/licença/commit.

## Estrutura

```
command-center/
├── server.py          # API FastAPI + dashboard
├── ledger.py          # ledger append-only + hash chain
├── policy.py          # travas, estados, cooldown
├── rag.py             # RAG TF-IDF + provenance
├── compression.py     # compressão RTK-style
├── router.py          # OmniRoute + slot genérico (fail-closed)
├── copilot.py         # IA governada (schema + tom + redaction)
├── config.py          # env-only, sem segredos no código
├── test_command_center.py
├── data/              # command_center.db (SQLite local)
└── web/               # dashboard (index.html, app.css, app.js)
```

## O que este sistema NÃO faz

- ❌ Não aposta, não clica, não usa API do cassino;
- ❌ Não burla anti-bot, geolocalização ou termos de uso;
- ❌ Não prevê resultados (não existe isso em jogo aleatório);
- ❌ Não promete lucro nem "recupera" prejuízo.

Estatísticas aqui são descritivas: amostra, viés e incerteza estão sempre visíveis.
