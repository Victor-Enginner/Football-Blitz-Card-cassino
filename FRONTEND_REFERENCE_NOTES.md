# Command Center — referência visual e validação

## Escopo

Melhoria do HTML/CSS/JS existente em `web/`. O quiz do usuário é referência,
não o produto a reconstruir. Sem Ollama ou dependências novas neste frontend.

## Fontes fornecidas

- https://roletaquizroeo.lovable.app/ — inspecionado no navegador; conteúdo usa
  Inter, títulos 24px/600 e opções 16px/400. JetBrains Mono em textos auxiliares.
  CameraPlainVariable apareceu no selo Lovable, não no conteúdo principal.
- https://tool.smartanalise.com.br/ — inspecionado; navegação compacta, seleção
  de mesa/janela e resultados próximos. Usado como referência de densidade.
- https://app.marcodosanjos.pro/home — inspecionado; navegação persistente e cartões.
- https://app.marcodosanjos.pro/roletas — inspecionado; agrupamento de mesas.
- https://app.marcodosanjos.pro/login — referência recebida, não necessária para
  implementar autenticação nesta etapa; nenhum formulário enviado.
- https://app.marcodosanjos.pro/register — separado do link /home que veio
  concatenado na mensagem; nenhum cadastro criado.
- https://www.zonadejogo.bet.br/ — origem oficial indicada.
- https://www.zonadejogo.bet.br/play/pragmatic/football-blitz — iframe validado
  visualmente no navegador: página oficial e mesa carregaram na sessão existente.

## Decisões

Inter para o conteúdo; superfícies zinc, CTA vermelho e detalhes dourados conforme
direção fornecida pelo usuário. Título compacto e indicadores antes do jogo.
Layout amplo no desktop, empilhado no mobile. Nenhum código de aplicação,
service worker, marca ou script Cloudflare das referências foi copiado.

## Funcionalidade

- Iframe com origem fixa, carregamento solicitado pelo usuário, ampliar/reduzir,
  fechar e link externo. Sem proxy e sem remover proteções da origem.
- Conteúdo externo pode exigir cookies/login e mudar sua política de iframe.
  O evento `load` não é usado como prova de sucesso cross-origin.
- Iframe apenas exibe o site: não coleta resultados nem sincroniza dados.
- Hipótese salva em localStorage, com validação de inteiros e restauração.
  É um rascunho, não um executor de estratégias.
- Status da sessão separado de alegações de IA ativa.
- Sem loops decorativos de canvas ou painel de ajuste que sobrescreva a paleta.
- IDs e endpoints dos controles existentes preservados.

## Validação realizada

`node --check web/app.js`; página servida por FastAPI local na porta 8766;
estado, histórico, distribuição e métricas paper renderizados com dados existentes;
iframe do jogo carregado; rascunho salvo e recuperado após reload;
inspeção visual desktop e viewport estreito sem rolagem horizontal da página.
Nenhuma aposta, depósito ou alteração de conta foi executada durante a validação.
