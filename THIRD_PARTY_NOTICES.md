# THIRD_PARTY_NOTICES

Dependências efetivamente incorporadas neste sprint:

| Projeto/Pacote | Versão | Licença | Uso | Commit/Tag |
|---|---|---|---|---|
| omniroute (npm) | 3.8.50 | MIT | gateway de IA local (roteamento, fallback, compressão no gateway) | v3.8.50 |
| semantica (PyPI) | 0.6.8 | MIT | instalada para provenance/context graph (integração profunda pendente) | v0.6.8 |
| FastAPI | 0.136.3 | MIT | API backend | — |
| uvicorn | 0.49.0 | BSD-3 | servidor ASGI | — |
| pydantic | 2.13.4 | MIT | validação de entrada | — |
| pytest | 9.1.1 | MIT | testes | — |
| sqlite3 (stdlib Python 3.14.5) | — | PSF | storage append-only | — |

## Observações

- **OmniRoute:** instalado via npm (trusted publisher `diegosouza.pw`), MIT.
  Existe também uma instalação pré-existente do usuário em `D:\OMNIROUTER`
  (v3.8.48, código-fonte no local). O gateway roda **apenas em loopback**
  (127.0.0.1:20128). Nenhum código do OmniRoute foi copiado — apenas chamadas
  HTTP para a API OpenAI-compatible.
- **Semantica:** instalada com `--no-deps` (gensim não tem wheel para Python 3.14).
  Nenhum código copiado ainda; integração de contexto/provenance planejada para
  sprint futuro. MIT confirmado no repositório `semantica-agi/semantica`.
- **9route:** NÃO incorporado. Sem repositório oficial verificável — permanece
  como investigação (docs/06-reference-registry.md do pacote de specs). O slot
  genérico `GENERIC_PROVIDER_*` permite plugá-lo quando/verificado.
- Todo o restante do código do Command Center é autoral, escrito neste sprint.
