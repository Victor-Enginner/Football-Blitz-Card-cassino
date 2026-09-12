// QA interativo do Command Center
export default async function run(page, ui) {
  const out = {};

  // 1. esperar WS conectar (até 8s)
  try {
    await page.waitForFunction(
      () => document.getElementById("ws-status")?.classList.contains("on"),
      { timeout: 8000 }
    );
    out.ws = "conectado";
  } catch {
    out.ws = document.getElementById("ws-status")?.textContent || "timeout";
  }

  // 2. iniciar sessão se não houver
  out.stateBefore = await page.evaluate(() => document.getElementById("state-pill")?.textContent);
  if (out.stateBefore === "OFFLINE" || !out.stateBefore) {
    await page.click("#btn-start");
    await page.waitForTimeout(1200);
    out.stateAfterStart = await page.evaluate(() => document.getElementById("state-pill")?.textContent);
  }

  // 3. registrar aposta papel pelo form
  await page.selectOption("#bet-type", "away");
  await page.fill("#bet-stake", "1.5");
  await page.click("#bet-form button[type=submit]");
  await page.waitForTimeout(1200);
  out.betBalance = await page.evaluate(() => document.getElementById("g-balance")?.textContent);
  out.betOpen = await page.evaluate(() => document.getElementById("g-open")?.textContent);

  // 4. registrar evento manual (deve settle via WS → toast GREEN/RED + som)
  await page.fill("#ev-outcome", "away");
  await page.click("#event-form button[type=submit]");
  try {
    await page.waitForFunction(
      () => document.querySelector("#toast")?.classList.contains("show"),
      { timeout: 6000 }
    );
    out.toast = await page.evaluate(() => document.getElementById("toast")?.textContent);
  } catch {
    out.toast = "toast não apareceu";
  }

  // 5. conferir timeline + stats + lista de resolvidas
  await page.waitForTimeout(1500);
  out.timelineItems = await page.evaluate(() => document.querySelectorAll("#timeline .ev").length);
  out.settledList = await page.evaluate(() => document.querySelectorAll("#g-settled-list .bet").length);
  out.pnl = await page.evaluate(() => document.getElementById("g-pnl")?.textContent);
  out.blockReasons = await page.evaluate(() => document.getElementById("block-reasons")?.hidden);

  // 6. simulador (abrir o <details> antes)
  await page.evaluate(() => { document.querySelector(".sim-box").open = true; });
  await page.click("#sim-form button[type=submit]");
  await page.waitForFunction(() => (document.getElementById("sim-out")?.textContent || "").includes("PnL"), { timeout: 10000 });
  out.sim = (await page.evaluate(() => document.getElementById("sim-out")?.textContent)).slice(0, 120);

  return out;
}
