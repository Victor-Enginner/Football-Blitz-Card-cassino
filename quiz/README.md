# Rey do Win — componentes base

React 18, TypeScript e Tailwind CSS 4, conforme o package.json preexistente.

```powershell
npm install
npm run dev -- --host 127.0.0.1
npm run build
```

Os componentes exportados em `src/components/ui/index.ts` são Button, Card,
ProgressBar e OptionCard. OptionCard usa radio nativo: agrupe opções com o mesmo
`name` dentro de um fieldset com legend. O navegador oferece navegação por setas.
Button aceita ref e atributos nativos; o tipo padrão é button.
ProgressBar limita valores inválidos e exige um label acessível.

## Referência e decisões

Fonte principal: Design System Rey do Win fornecido pelo usuário nesta sessão.
Referência complementar: Refero craft-details (foco, semântica e toque).

| Decisão | Fonte / função |
| --- | --- |
| Zinc #09090B, cards #18181B, borda #27272A | Paleta fornecida |
| Vermelho #DC2626 | CTA, seleção e progresso |
| Dourado #EAB308 | Destaques e foco visível |
| max-w-md, cartões 16px e botões 8px | Layout e raios fornecidos |
| Radio nativo, alvo mínimo 44px e motion-reduce | Acessibilidade / craft-details |

Os tokens vivem em `src/styles.css` usando `@theme`, o formato Tailwind 4.
Não se aplica o arquivo de configuração CommonJS de Tailwind 3 a este projeto ESM.
CameraPlainVariable consta na cadeia pedida; nenhum arquivo dessa fonte foi
fornecido ou licenciado aqui. O navegador usa a fonte de sistema disponível.

A página demonstra seleção, confirmação, progresso, resultado e reinício.
Os dados são educativos e locais. Não há chamada a LLM nem custo de API.
