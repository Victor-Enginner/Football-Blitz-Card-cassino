import { useState } from 'react';
import { Button, Card, OptionCard, ProgressBar } from './components/ui';

const questions = [
  { title: 'O que uma sequência de resultados revela?', options: ['O próximo resultado', 'Somente o histórico observado', 'Uma vitória garantida'], correct: 1, explanation: 'O histórico descreve o que aconteceu. Ele não garante o próximo resultado.' },
  { title: 'Ao atingir o limite definido para a sessão, o que fazer?', options: ['Aumentar o limite', 'Tentar recuperar perdas', 'Encerrar a sessão'], correct: 2, explanation: 'Respeite o limite definido antes de iniciar a sessão.' },
  { title: 'Para que serve o modo de simulação?', options: ['Estudar sem movimentar dinheiro', 'Garantir lucro futuro', 'Eliminar a aleatoriedade'], correct: 0, explanation: 'A simulação permite estudar o funcionamento sem operações com dinheiro.' },
];

export default function App() {
  const [step, setStep] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [score, setScore] = useState(0);
  const finished = step === questions.length;
  const question = questions[Math.min(step, questions.length - 1)];
  const completed = finished ? questions.length : step + Number(confirmed);
  function reset() { setStep(0); setSelected(null); setConfirmed(false); setScore(0); }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col gap-7 px-5 py-8 sm:py-12">
      <header className="flex items-center justify-between gap-4 border-b border-card-border pb-5">
        <span className="text-lg font-bold tracking-tight">REY <span className="text-accent">DO WIN</span></span>
        <span className="rounded-md border border-card-border px-2 py-1 text-xs text-muted-foreground">Quiz educativo</span>
      </header>
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-accent">Conhecimento antes da ação</p>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Entenda o jogo.<br />Reconheça seus limites.</h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">Três perguntas sobre histórico, limites e simulação.</p>
      </div>
      <section aria-label="Progresso do quiz" className="space-y-3">
        <div className="flex justify-between text-xs text-muted-foreground"><span>Seu progresso</span><span>{completed} de {questions.length}</span></div>
        <ProgressBar value={completed} max={questions.length} label="Perguntas concluídas" />
      </section>
      {finished ? <Card className="space-y-4" role="status">
        <p className="text-xs font-semibold uppercase tracking-widest text-accent">Quiz concluído</p>
        <h2 className="text-xl font-semibold">Você acertou {score} de {questions.length}</h2>
        <p className="text-sm leading-6 text-muted-foreground">Continue estudando e respeite seus limites. Nenhuma estratégia garante resultados.</p>
        <Button className="w-full" onClick={reset}>Refazer quiz</Button>
      </Card> : <Card>
        <form onSubmit={(event) => {
          event.preventDefault();
          if (selected === null) return;
          if (confirmed) { setStep(step + 1); setSelected(null); setConfirmed(false); }
          else { setConfirmed(true); if (selected === question.correct) setScore(score + 1); }
        }}>
          <fieldset className="min-w-0" disabled={confirmed}>
            <legend className="mb-5 text-lg font-semibold leading-7">{question.title}</legend>
            <div className="space-y-3">{question.options.map((option, index) =>
              <OptionCard key={`${step}-${index}`} name={`question-${step}`} value={index} checked={selected === index}
                onChange={() => setSelected(index)}>{option}</OptionCard>)}</div>
          </fieldset>
          <div role="status" className="mt-4 text-sm leading-6">
            {confirmed && <><p className={selected === question.correct ? 'text-success' : 'text-error'}>{selected === question.correct ? 'Resposta correta.' : 'Vamos revisar.'}</p><p className="text-muted-foreground">{question.explanation}</p></>}
          </div>
          <Button type="submit" disabled={selected === null} className="mt-4 w-full">{confirmed ? (step === questions.length - 1 ? 'Ver resultado' : 'Próxima pergunta') : 'Confirmar resposta'}</Button>
        </form>
      </Card>}
      {!finished && <Button variant="outline" onClick={reset}>Recomeçar</Button>}
      <footer className="mt-auto pt-2 text-center text-xs leading-5 text-muted-foreground">Conteúdo educativo · Sem apostas ou movimentação de dinheiro.</footer>
    </main>
  );
}
