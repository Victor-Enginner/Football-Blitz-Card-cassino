# Football Blitz Command Center
## Plano de validação, tarefas e sprints

> Documento de retomada para a próxima sessão.  
> Atualizado em **11/09/2026**.  
> Escopo: dashboard operacional PAPER-only para observação e análise do Football Blitz.

---

## 1. Estado atual do projeto

O projeto ativo está em:

```text
football RAG SYSTEM AGENTS\command-center
```

Não usar como alvo principal:

- a raiz `My bot Roullet`, que contém o bot Python original;
- `continue`, que é um clone do repositório Continue/IDE e não o dashboard;
- qualquer frontend temporário Vite criado durante a investigação inicial.

### Stack confirmada

- **Backend:** Python + FastAPI.
- **Persistência:** SQLite.
- **Frontend:** HTML, CSS e JavaScript vanilla servido diretamente pelo FastAPI.
- **Tempo real:** WebSocket.
- **Testes:** `pytest` e QA browser em `qa.mjs`.
- **Modo operacional:** PAPER-only; não executar apostas reais.
- **Assets:** arquivos locais servidos pela rota `/assets/{asset_name}`.

---

## 2. O que foi alterado nesta sessão

### Frontend visual

- `web/index.html` foi reconstruído para uma interface preta e vermelha inspirada nas referências enviadas.
- Foi substituído o conceito de dashboard terminal azul/ciano por uma experiência de plataforma de cassino operacional.
- Adicionados:
  - navbar horizontal;
  - marca `BLITZ SCANNER`;
  - hero de boas-vindas;
  - banner principal do Football Blitz;
  - seção **Mesas em destaque**;
  - cards de mesas com status AO VIVO;
  - Strategy Builder;
  - painel de limites e travas;
  - timeline;
  - estatísticas;
  - Game Center PAPER;
  - Copilot governado.
- IDs importantes foram preservados para não quebrar o JavaScript e o QA:
  - `state-pill`;
  - `g-balance`;
  - `btn-start`;
  - `event-form`;
  - `strategy-color`;
  - `timeline`;
  - `stats-freq`;
  - `bet-form`;
  - `copilot-form`;
  - `omniroute-pill`;
  - `g-settled-list`;
  - `sim-form`.
- Referências textuais de roleta foram removidas da página.

### Design system

`web/app.css` foi refeito com:

- fundo preto quase absoluto;
- vermelho como cor de ação;
- cards escuros com bordas suaves;
- brilho e gradientes vermelhos;
- tipografia condensada e monoespaçada para dados;
- botões com gradiente, sombra interna e efeito `:active`;
- comportamento responsivo para desktop e mobile;
- tratamento visual das artes reais do Football Blitz.

### Lógica do frontend

`web/app.js` preserva os contratos existentes e mantém:

- atualização de estado;
- limites de sessão;
- timeline;
- estatísticas;
- Game Center PAPER;
- Copilot;
- WebSocket;
- Strategy Builder;
- navegação dos cards para as áreas correspondentes.

Foi feita checagem de sintaxe com `node --check web\app.js`.

### Backend e assets

`server.py` recebeu a rota:

```text
/assets/{asset_name}
```

A rota:

- resolve o caminho real com `Path.resolve()`;
- permite somente arquivos dentro de `web\assets`;
- retorna `404` para arquivo inexistente;
- bloqueia tentativa de path traversal;
- serve as imagens sem expor arquivos arbitrários do projeto.

Assets adicionados em `web\assets`:

| Arquivo | Uso |
|---|---|
| `blitz-capa.png` | banner principal e card |
| `blitz-rodada.png` | card principal |
| `blitz-victor.png` | card com identidade do apresentador |
| `blitz-boatarade.png` | asset disponível para carrossel ou futura seção |
| `blitz-fecho.png` | asset disponível para carrossel ou futura seção |
| `blitz-logo.jfif` | logo oficial disponível |

O banner principal foi ajustado para usar a classe visual dedicada:

```html
<img class="banner-art-image" src="/assets/blitz-capa.png" alt="Football Blitz Brasil">
```

---

## 3. Validações já realizadas

Último estado validado:

```text
33 passed
```

Comando:

```powershell
cd "football RAG SYSTEM AGENTS\command-center"
python -m pytest test_command_center.py test_game.py -q
```

Também validados:

```powershell
node --check web\app.js
python -m py_compile server.py policy.py ledger.py game.py
```

Smoke test do servidor atualizado:

- `/` → HTTP 200;
- `/api/health` → HTTP 200;
- `/assets/blitz-capa.png` → HTTP 200;
- asset PNG retornado com aproximadamente 2,5 MB;
- nenhuma ocorrência de `Roleta` ou `Roulette` no HTML;
- tentativa de `/assets/..%2Fserver.py` bloqueada com HTTP 404.

### Avisos conhecidos

Os testes exibem apenas avisos de depreciação do FastAPI sobre `on_event`. Isso não bloqueia a execução atual, mas deve ser tratado em uma sprint futura com migração para lifespan handlers.

---

## 4. Pendências importantes

### Alta prioridade

- [ ] Executar o QA completo com navegador em `qa.mjs`.
- [ ] Confirmar visualmente banner e cards no navegador real/headless.
- [ ] Verificar se o recorte das imagens não esconde textos importantes das artes.
- [ ] Confirmar que o formulário manual continua presente e funcional.
- [ ] Criar teste automatizado específico para a rota de assets e path traversal.
- [ ] Confirmar funcionamento do WebSocket após iniciar uma sessão.
- [ ] Confirmar fluxo completo de evento, aposta PAPER, settle e estatísticas.

### Média prioridade

- [ ] Adicionar carrossel usando `blitz-fecho.png` e `blitz-boatarade.png`.
- [ ] Usar `blitz-logo.jfif` em uma área de identidade da mesa.
- [ ] Revisar acessibilidade: foco visível, labels, contraste, navegação por teclado e alt text.
- [ ] Revisar responsividade em 390 px, 768 px e desktop.
- [ ] Padronizar textos de “home/away”, “azul/amarelo” e terminologia do Football Blitz.
- [ ] Migrar eventos FastAPI deprecated para lifespan.

### Baixa prioridade

- [ ] Avaliar migração futura para React/Vite somente se a complexidade do frontend justificar.
- [ ] Adicionar um sistema real de componentes somente após estabilizar o HTML/CSS atual.
- [ ] Documentar configuração de MCPs somente quando houver endpoint, pacote e comando confirmados.

---

## 5. Sprints de validação

## Sprint 0 — Retomada e baseline

**Objetivo:** confirmar que a sessão começa no projeto correto e que o estado atual é reproduzível.

Tarefas:

- [ ] Abrir `football RAG SYSTEM AGENTS\command-center`.
- [ ] Conferir `README.md`, `server.py`, `web\index.html`, `web\app.css` e `web\app.js`.
- [ ] Verificar se os seis assets existem.
- [ ] Rodar os testes backend.
- [ ] Rodar `node --check`.
- [ ] Registrar qualquer diferença encontrada neste documento.

Critério de aceite:

- testes backend passando;
- arquivos principais presentes;
- assets presentes;
- servidor iniciando sem erro.

Comandos:

```powershell
cd "football RAG SYSTEM AGENTS\command-center"
python -m pytest test_command_center.py test_game.py -q
node --check web\app.js
python -m py_compile server.py policy.py ledger.py game.py
```

---

## Sprint 1 — Smoke test HTTP e segurança dos assets

**Objetivo:** garantir que o servidor entrega o dashboard e somente os assets permitidos.

Tarefas:

- [ ] Iniciar o servidor em uma porta livre.
- [ ] Testar `/`.
- [ ] Testar `/app.css`.
- [ ] Testar `/app.js`.
- [ ] Testar `/api/health`.
- [ ] Testar todos os assets Football Blitz.
- [ ] Testar arquivo inexistente.
- [ ] Testar path traversal codificado.

Critério de aceite:

- rotas públicas esperadas retornam 200;
- asset inexistente retorna 404;
- path traversal retorna 404;
- nenhum arquivo fora de `web\assets` é servido.

---

## Sprint 2 — QA funcional da dashboard

**Objetivo:** validar a jornada operacional sem execução real.

Tarefas:

- [ ] Abrir a dashboard em navegador headless.
- [ ] Confirmar presença do título e da marca Blitz Scanner.
- [ ] Confirmar ausência de `Roleta` e `Roulette`.
- [ ] Iniciar sessão PAPER.
- [ ] Confirmar atualização do estado visual.
- [ ] Enviar um evento manual.
- [ ] Criar uma aposta PAPER.
- [ ] Resolver o evento.
- [ ] Confirmar settle da aposta.
- [ ] Conferir timeline.
- [ ] Conferir estatísticas.
- [ ] Testar simulador.
- [ ] Testar Copilot governado.
- [ ] Testar Strategy Builder.

Critério de aceite:

- fluxo completo funciona sem erro no console;
- nenhum endpoint de aposta real é chamado;
- todos os IDs esperados pelo QA continuam disponíveis;
- dados atualizados aparecem na interface.

Comando esperado:

```powershell
cd "football RAG SYSTEM AGENTS\command-center"
node qa.mjs
```

---

## Sprint 3 — Validação visual e responsiva

**Objetivo:** confirmar que a direção visual preta/vermelha realmente aparece como planejada.

Tarefas:

- [ ] Conferir desktop largo.
- [ ] Conferir notebook.
- [ ] Conferir viewport mobile.
- [ ] Conferir banner principal.
- [ ] Conferir legibilidade dos textos sobre imagens.
- [ ] Conferir proporção dos cards.
- [ ] Conferir efeito pressionado dos botões.
- [ ] Conferir estados hover, active, disabled e loading.
- [ ] Conferir contraste dos textos cinza e vermelhos.
- [ ] Conferir que nenhuma imagem apresenta quebra ou caminho incorreto.

Critério de aceite:

- layout sem overflow horizontal inesperado;
- cards legíveis;
- botões claramente clicáveis;
- nenhuma arte do Football Blitz aparece quebrada;
- aparência consistente com as referências pretas/vermelhas.

---

## Sprint 4 — Segurança, governança e confiabilidade

**Objetivo:** validar que a evolução visual não alterou as proteções do sistema.

Tarefas:

- [ ] Confirmar que o modo continua PAPER-only.
- [ ] Confirmar limites, cooldown, stop-loss, stop-win e kill switch.
- [ ] Confirmar ledger append-only e hash chain.
- [ ] Confirmar que não há rota de execução real.
- [ ] Confirmar que segredos continuam apenas no servidor/env.
- [ ] Confirmar que `/assets` não permite traversal.
- [ ] Verificar headers HTTP básicos.
- [ ] Verificar origem/autenticação do WebSocket conforme o escopo atual.
- [ ] Rodar auditoria de dependências quando houver manifesto de dependências no frontend.

Critério de aceite:

- nenhum teste de governança regrediu;
- nenhuma nova superfície executa aposta real;
- nenhuma chave ou segredo foi adicionado ao frontend;
- entradas de asset continuam limitadas ao diretório seguro.

---

## Sprint 5 — Polimento e próxima evolução

**Objetivo:** transformar o protótipo visual validado em uma base de produto sustentável.

Tarefas:

- [ ] Criar teste dedicado para `/assets/{asset_name}`.
- [ ] Criar snapshots ou screenshots de referência para o layout.
- [ ] Adicionar carrossel de artes oficiais.
- [ ] Melhorar feedback de carregamento e erro.
- [ ] Melhorar acessibilidade.
- [ ] Migrar FastAPI `on_event` para lifespan.
- [ ] Definir se o frontend continuará vanilla ou será migrado.
- [ ] Só então avaliar DialKit, shadcn, React Bits, 21st.dev ou outros MCPs.

Critério de aceite:

- regressões visuais detectáveis;
- cobertura dos fluxos críticos;
- decisão documentada sobre a futura stack frontend;
- dependências externas confirmadas antes da instalação.

---

## 6. Checklist rápido para amanhã

1. Abrir a pasta correta:

   ```powershell
   cd "C:\Users\Victor Ads\Desktop\My bot Roullet\football RAG SYSTEM AGENTS\command-center"
   ```

2. Rodar baseline:

   ```powershell
   python -m pytest test_command_center.py test_game.py -q
   node --check web\app.js
   ```

3. Iniciar o servidor:

   ```powershell
   python -m uvicorn server:app --port 8766
   ```

4. Abrir:

   ```text
   http://localhost:8766/
   ```

5. Validar primeiro:

   - banner;
   - três cards;
   - formulário manual;
   - Strategy Builder;
   - Game Center;
   - Copilot;
   - WebSocket;
   - fluxo PAPER.

6. Rodar o QA:

   ```powershell
   node qa.mjs
   ```

7. Registrar neste documento qualquer falha encontrada, mantendo a seção **Pendências importantes** atualizada.

---

## 7. Decisões e limites do projeto

- O sistema é para observação, análise, simulação e governança.
- O modo PAPER é obrigatório nesta fase.
- Não adicionar execução de apostas reais.
- Não colocar tokens, chaves de LLM ou credenciais no frontend.
- Não instalar MCP, pacote ou dependência apenas por nome parecido.
- Confirmar mantenedor, pacote, versão e licença antes de adicionar dependências.
- O clone `continue` não faz parte do produto Football Blitz.
- A ausência de Git local no `command-center` impede comparar automaticamente o “antes/depois”; este documento registra o estado observável e a memória consolidada da sessão.

---

## 8. Registro de alterações para futuras sessões

### Arquivos principais tocados

- `web\index.html`
- `web\app.css`
- `web\app.js`
- `server.py`

### Arquivos adicionados

- `web\assets\blitz-boatarade.png`
- `web\assets\blitz-capa.png`
- `web\assets\blitz-fecho.png`
- `web\assets\blitz-logo.jfif`
- `web\assets\blitz-rodada.png`
- `web\assets\blitz-victor.png`
- `document.md`

### Arquivos de referência preservados

- `README.md`
- `qa.mjs`
- `test_command_center.py`
- `test_game.py`
- `policy.py`
- `ledger.py`
- `game.py`
- `copilot.py`
- `rag.py`
- `realtime.py`

---

## 9. Próximo marco

O próximo marco não é adicionar mais bibliotecas. É concluir:

1. QA funcional completo;
2. validação visual em navegador;
3. teste dedicado da rota de assets;
4. confirmação de que o modo PAPER e as proteções continuam intactos;
5. somente depois decidir a próxima evolução tecnológica.

