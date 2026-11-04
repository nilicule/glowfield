"use strict";

/* Glowfield — reverse minesweeper with fireflies.
 * Single click rules a cell out, double click places a firefly.
 */

const MAX_MISTAKES = 3;
const DOUBLE_MS = 260;
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

const $ = (sel) => document.querySelector(sel);
const boardEl = $("#board");
const fxEl = $("#fx");

/* ---------- firefly artwork ---------- */
function fireflySVG() {
  return `<svg class="ff" viewBox="0 0 40 40" aria-hidden="true">
    <circle class="halo" cx="20" cy="28" r="13"/>
    <g class="wings">
      <ellipse cx="12.5" cy="15" rx="8" ry="4.6" transform="rotate(-28 12.5 15)" fill="#cfe0ff" fill-opacity=".5" stroke="#e9f0ff" stroke-opacity=".5" stroke-width=".6"/>
      <ellipse cx="27.5" cy="15" rx="8" ry="4.6" transform="rotate(28 27.5 15)" fill="#cfe0ff" fill-opacity=".5" stroke="#e9f0ff" stroke-opacity=".5" stroke-width=".6"/>
    </g>
    <path d="M18.6 7.6c-1.2-2.4-2.6-3.6-4.3-4" stroke="#3b3340" stroke-width="1.2" fill="none" stroke-linecap="round"/>
    <path d="M21.4 7.6c1.2-2.4 2.6-3.6 4.3-4" stroke="#3b3340" stroke-width="1.2" fill="none" stroke-linecap="round"/>
    <ellipse cx="20" cy="18.5" rx="4.4" ry="7" fill="#3b3340"/>
    <circle class="glow" cx="20" cy="27.5" r="5.6"/>
    <circle cx="20" cy="10" r="3.4" fill="#4a3f4f"/>
  </svg>`;
}
const fillIcons = (root = document) =>
  root.querySelectorAll("[data-firefly]").forEach((el) => (el.innerHTML = fireflySVG()));

/* ---------- ambient sky ---------- */
function makeSky() {
  const sky = $(".sky");
  for (let i = 0; i < 18; i++) {
    const dot = document.createElement("i");
    dot.style.left = `${Math.random() * 100}%`;
    dot.style.top = `${Math.random() * 100}%`;
    dot.style.setProperty("--dur", `${8 + Math.random() * 10}s`);
    dot.style.setProperty("--delay", `${-Math.random() * 15}s`);
    dot.style.setProperty("--dx", `${(Math.random() - 0.5) * 120}px`);
    dot.style.setProperty("--dy", `${(Math.random() - 0.5) * 120}px`);
    sky.appendChild(dot);
  }
  // Grass blades along the meadow, each swaying at its own pace.
  const grass = document.querySelector(".meadow .grass");
  const ns = "http://www.w3.org/2000/svg";
  for (let x = 0; x < 1200; x += 9 + Math.random() * 14) {
    const h = 18 + Math.random() * 34, lean = (Math.random() - 0.5) * 14;
    const base = 185 + Math.random() * 30;
    const blade = document.createElementNS(ns, "path");
    blade.setAttribute("d", `M${x} ${base} q${lean / 2} ${-h / 2} ${lean} ${-h} q${2 - lean / 2} ${h / 2} 3 ${h}z`);
    blade.style.setProperty("--d", `${2.5 + Math.random() * 3}s`);
    blade.style.animationDelay = `${-Math.random() * 5}s`;
    grass.appendChild(blade);
  }
}

/* ---------- state ---------- */
const state = {
  puzzle: null,
  solution: new Set(), // "r,c" keys holding fireflies
  clues: new Map(), // "r,c" -> number
  marks: new Map(), // "r,c" -> "x" | "f"
  history: [],
  mistakes: 0,
  hints: 0,
  elapsed: 0,
  timerStart: null,
  timerId: null,
  over: false,
  tapMode: false,
};
let pending = null; // single click waiting to see if it becomes a double click

const key = (r, c) => `${r},${c}`;
const parseKey = (k) => k.split(",").map(Number);
const cellEl = (k) => boardEl.querySelector(`[data-key="${k}"]`);

function neighborKeys(k) {
  const [r, c] = parseKey(k);
  const out = [];
  for (let dr = -1; dr <= 1; dr++)
    for (let dc = -1; dc <= 1; dc++) {
      if (!dr && !dc) continue;
      const rr = r + dr, cc = c + dc;
      if (rr >= 0 && cc >= 0 && rr < state.puzzle.rows && cc < state.puzzle.cols) out.push(key(rr, cc));
    }
  return out;
}

/* ---------- loading ---------- */
let currentLevel = "beginner";

async function loadDifficulties() {
  const list = await (await fetch("/api/difficulties")).json();
  const levels = [{ key: "daily", label: "Daily" }, ...list];
  $("#levels").innerHTML = levels
    .map((d) => `<button class="level" data-level="${d.key}">${d.label}</button>`)
    .join("");
  $("#levels").addEventListener("click", (e) => {
    const btn = e.target.closest(".level");
    if (btn) loadPuzzle({ difficulty: btn.dataset.level });
  });
}

function setActiveLevel(level) {
  currentLevel = level;
  document.querySelectorAll(".level").forEach((b) =>
    b.setAttribute("aria-current", String(b.dataset.level === level)),
  );
}

async function loadPuzzle({ difficulty, seed } = {}) {
  let url;
  if (difficulty === "daily") url = "/api/daily";
  else {
    url = `/api/puzzle?difficulty=${encodeURIComponent(difficulty)}`;
    if (seed != null) url += `&seed=${seed}`;
  }
  const res = await fetch(url);
  if (!res.ok) return loadPuzzle({ difficulty: "beginner" });
  startPuzzle(await res.json());
}

function startPuzzle(p) {
  state.puzzle = p;
  state.solution = new Set(p.fireflies.map(([r, c]) => key(r, c)));
  state.clues = new Map(p.clues.map(([r, c, n]) => [key(r, c), n]));
  setActiveLevel(p.daily ? "daily" : p.difficulty);
  history.replaceState(null, "", p.daily ? "#daily" : `#${p.id}`);
  try { localStorage.setItem("glowfield:difficulty", p.daily ? "daily" : p.difficulty); } catch {}
  resetProgress();
}

function puzzleName() {
  const p = state.puzzle;
  if (p.daily) {
    const d = new Date(p.daily + "T12:00:00");
    return `Daily · ${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
  }
  return `${p.label} #${p.seed}`;
}

function resetProgress() {
  cancelPending();
  state.marks.clear();
  state.history = [];
  state.mistakes = 0;
  state.hints = 0;
  state.over = false;
  fxEl.innerHTML = "";
  hideMessage();
  closeModal();
  renderBoard();
  updateStatus();
  stopTimer();
  state.elapsed = 0;
  startTimer();
}

/* ---------- rendering ---------- */
function renderBoard() {
  const { rows, cols } = state.puzzle;
  boardEl.style.setProperty("--cols", cols);
  boardEl.innerHTML = "";
  for (let r = 0; r < rows; r++)
    for (let c = 0; c < cols; c++) {
      const k = key(r, c);
      const el = document.createElement("div");
      el.dataset.key = k;
      el.setAttribute("role", "gridcell");
      if (state.clues.has(k)) {
        el.className = "cell clue";
        el.textContent = state.clues.get(k);
      } else {
        el.className = "cell open";
      }
      boardEl.appendChild(el);
    }
  updateClues();
}

function renderCell(k, { arrive = false } = {}) {
  const el = cellEl(k);
  if (!el) return;
  const mark = state.marks.get(k);
  if (mark === "f") {
    el.innerHTML = fireflySVG();
    const ff = el.querySelector(".ff");
    ff.style.setProperty("--pulse-delay", `${-Math.random() * 2.6}s`);
    if (arrive) ff.classList.add("arrive");
  } else if (mark === "x") {
    el.innerHTML = `<span class="x"></span>`;
  } else {
    el.innerHTML = "";
  }
}

function updateClues() {
  for (const [k] of state.clues) {
    // Muted once it has all its fireflies (placed fireflies are always correct).
    const placed = neighborKeys(k).filter((n) => state.marks.get(n) === "f").length;
    cellEl(k).classList.toggle("done", placed === state.clues.get(k));
  }
}

function updateStatus() {
  $("#puzzle-name").textContent = puzzleName();
  const found = [...state.marks.values()].filter((m) => m === "f").length;
  $("#found").textContent = `${found} / ${state.solution.size}`;
  const lives = $("#lives");
  lives.title = `${MAX_MISTAKES - state.mistakes} of ${MAX_MISTAKES} lanterns left`;
  [...lives.children].forEach((l, i) => l.classList.toggle("out", i >= MAX_MISTAKES - state.mistakes));
  $("#undo").disabled = state.history.length === 0 || state.over;
  $("#hint").disabled = state.over;
}

/* ---------- timer ---------- */
const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
function elapsedNow() {
  return state.elapsed + (state.timerStart ? (Date.now() - state.timerStart) / 1000 : 0);
}
function startTimer() {
  if (state.timerStart || state.over) return;
  state.timerStart = Date.now();
  state.timerId = setInterval(() => ($("#timer").textContent = fmt(elapsedNow())), 250);
  $("#timer").textContent = fmt(elapsedNow());
}
function stopTimer() {
  state.elapsed = elapsedNow();
  state.timerStart = null;
  clearInterval(state.timerId);
  $("#timer").textContent = fmt(state.elapsed);
}
document.addEventListener("visibilitychange", () => (document.hidden ? stopTimer() : startTimer()));

/* ---------- messages ---------- */
function showMessage(text, kind = "") {
  const m = $("#message");
  m.hidden = false;
  m.className = `message ${kind}`;
  m.textContent = text;
  // restart the slide-in animation
  void m.offsetWidth;
}
function hideMessage() { $("#message").hidden = true; }

/* ---------- input ---------- */
boardEl.addEventListener("click", (e) => {
  const el = e.target.closest(".cell.open");
  if (!el || state.over) return;
  const k = el.dataset.key;

  if (state.tapMode) return placeFirefly(k);

  if (pending && pending.key === k) {
    // Second click on the same cell: it's a double click.
    clearTimeout(pending.timer);
    const p = pending;
    pending = null;
    if (p.type === "unx") {
      state.history.pop();
      state.marks.set(k, "x");
    }
    renderCell(k);
    placeFirefly(k);
    return;
  }

  flushPending();
  const mark = state.marks.get(k);
  if (mark === "f") return; // confirmed fireflies are locked

  if (mark === "x") {
    // Clear the X right away; a quick second click turns it into a firefly attempt.
    setMark(k, null);
    renderCell(k);
    pending = { key: k, type: "unx", timer: setTimeout(() => (pending = null), DOUBLE_MS) };
    return;
  }

  // Show the X immediately, but only judge it once we know it's not a double click.
  cellEl(k).innerHTML = `<span class="x"></span>`;
  pending = { key: k, type: "x", timer: setTimeout(() => { pending = null; ruleOut(k); }, DOUBLE_MS) };
});
boardEl.addEventListener("dblclick", (e) => e.preventDefault());

function flushPending() {
  if (!pending) return;
  clearTimeout(pending.timer);
  const p = pending;
  pending = null;
  if (p.type === "x") ruleOut(p.key);
}
function cancelPending() {
  if (pending) clearTimeout(pending.timer);
  pending = null;
}

/* ---------- moves ---------- */
function setMark(k, mark) {
  state.history.push({ key: k, prev: state.marks.get(k) ?? null });
  if (mark) state.marks.set(k, mark);
  else state.marks.delete(k);
  clearHint();
  updateClues();
  updateStatus();
}

// X marks are the player's own notes: they're never checked, so a wrong one
// isn't a mistake. It just quietly leads you astray until you notice.
function ruleOut(k) {
  if (state.over) return;
  setMark(k, "x");
  renderCell(k);
  hideMessage();
}

function placeFirefly(k) {
  if (state.over || state.marks.get(k) === "f") return;
  if (state.solution.has(k)) {
    setMark(k, "f");
    hideMessage();
    flyIn(k);
    checkWin(k);
  } else {
    flyAway(k);
    mistake("No firefly there. It flickered out and flew away.");
  }
}

function mistake(text) {
  state.mistakes++;
  updateStatus();
  const snuffed = $("#lives").children[MAX_MISTAKES - state.mistakes];
  if (snuffed) retrigger(snuffed, "snuff");
  if (state.mistakes >= MAX_MISTAKES) {
    state.over = true;
    stopTimer();
    updateStatus();
    showMessage("The fireflies scattered. That's three mistakes.", "bad");
    setTimeout(showGameOver, 1100);
  } else {
    showMessage(`${text} (${state.mistakes} of ${MAX_MISTAKES} mistakes)`, "bad");
  }
}

function undo() {
  cancelPending();
  const last = state.history.pop();
  if (!last || state.over) return;
  if (last.prev) state.marks.set(last.key, last.prev);
  else state.marks.delete(last.key);
  renderCell(last.key);
  clearHint();
  hideMessage();
  updateClues();
  updateStatus();
}

function retrigger(el, cls) {
  el.classList.remove(cls);
  void el.offsetWidth;
  el.classList.add(cls);
  el.addEventListener("animationend", () => el.classList.remove(cls), { once: true });
}

/* ---------- animations ---------- */
function makeFlyer(rect, extraClass) {
  const size = rect.width * 0.76;
  const f = document.createElement("div");
  f.className = `flyer flying ${extraClass}`;
  f.style.width = f.style.height = `${size}px`;
  f.style.left = `${rect.left + rect.width / 2 - size / 2}px`;
  f.style.top = `${rect.top + rect.height / 2 - size / 2}px`;
  f.innerHTML = fireflySVG();
  fxEl.appendChild(f);
  return f;
}

// Correct placement: the firefly drifts in along a wobbly path, lands, and glows.
function flyIn(k) {
  const el = cellEl(k);
  const finish = () => {
    if (state.marks.get(k) !== "f") return renderCell(k); // undone mid-flight
    renderCell(k, { arrive: true });
    const burst = document.createElement("span");
    burst.className = "burst";
    el.appendChild(burst);
    burst.addEventListener("animationend", () => burst.remove(), { once: true });
  };
  if (reducedMotion) return finish();

  el.innerHTML = "";
  const rect = el.getBoundingClientRect();
  const f = makeFlyer(rect, "");
  const angle = Math.random() * Math.PI * 2;
  const dist = rect.width * 2.4;
  const sx = Math.cos(angle) * dist, sy = Math.sin(angle) * dist - rect.width;
  const tilt = sx > 0 ? -20 : 20;
  f.animate(
    [
      { transform: `translate(${sx}px, ${sy}px) scale(.45) rotate(${tilt}deg)`, opacity: 0 },
      { transform: `translate(${sx * 0.55 + sy * 0.25}px, ${sy * 0.55 - sx * 0.2}px) scale(.7) rotate(${-tilt}deg)`, opacity: 1, offset: 0.35 },
      { transform: `translate(${sx * 0.15 - sy * 0.1}px, ${sy * 0.15 + sx * 0.1}px) scale(.95) rotate(${tilt / 2}deg)`, offset: 0.7 },
      { transform: "translate(0, -6px) scale(1.05) rotate(0deg)", offset: 0.88 },
      { transform: "translate(0, 0) scale(1) rotate(0deg)", opacity: 1 },
    ],
    { duration: 680, easing: "cubic-bezier(.25,.6,.35,1)" },
  ).finished.then(() => { f.remove(); finish(); });
}

// Wrong placement: the firefly appears, flickers like a dying light, then flees.
function flyAway(k) {
  const el = cellEl(k);
  retrigger(el, "wrong");
  renderCell(k);
  if (reducedMotion) return;
  const rect = el.getBoundingClientRect();
  const f = makeFlyer(rect, "fleeing");
  const dir = Math.random() < 0.5 ? -1 : 1;
  const w = rect.width;
  f.animate(
    [
      { transform: "scale(.5)", opacity: 0 },
      { transform: "scale(1)", opacity: 1, offset: 0.1 },
      { opacity: 0.2, offset: 0.17 },
      { opacity: 1, offset: 0.24 },
      { opacity: 0.15, offset: 0.31 },
      { transform: "scale(1) translate(0, 0)", opacity: 0.9, offset: 0.4 },
      { transform: `translate(${dir * w * 0.5}px, ${-w * 0.6}px) rotate(${dir * 25}deg) scale(.9)`, opacity: 0.8, offset: 0.58 },
      { transform: `translate(${-dir * w * 0.2}px, ${-w * 1.7}px) rotate(${-dir * 15}deg) scale(.7)`, opacity: 0.6, offset: 0.78 },
      { transform: `translate(${dir * w * 1.4}px, ${-w * 3.6}px) rotate(${dir * 30}deg) scale(.35)`, opacity: 0 },
    ],
    { duration: 1150, easing: "ease-in" },
  ).finished.then(() => f.remove());
}

/* ---------- win / lose ---------- */
function checkWin(lastKey) {
  for (const k of state.solution) if (state.marks.get(k) !== "f") return;
  state.over = true;
  cancelPending();
  stopTimer();
  updateStatus();
  hideMessage();
  clearHint();

  // Fill in the remaining empties, then send a glow wave out from the last firefly.
  const [lr, lc] = parseKey(lastKey);
  let i = 0;
  boardEl.querySelectorAll(".cell.open").forEach((el) => {
    const k = el.dataset.key;
    if (!state.marks.has(k)) {
      state.marks.set(k, "x");
      setTimeout(() => renderCell(k), 20 * i++);
    }
  });
  updateClues();
  setTimeout(() => {
    for (const k of state.solution) {
      const [r, c] = parseKey(k);
      const d = Math.max(Math.abs(r - lr), Math.abs(c - lc));
      setTimeout(() => retrigger(cellEl(k), "celebrate"), d * 90);
    }
  }, 700);
  setTimeout(showWin, 1700);
}

// A glass jar holding one glowing dot per firefly caught (dim ones got away).
function jarSVG(lit, total) {
  const dots = [];
  for (let i = 0; i < Math.min(total, 24); i++) {
    const x = 34 + Math.random() * 52, y = 52 + Math.random() * 62;
    const on = i < Math.round((lit / total) * Math.min(total, 24));
    dots.push(
      `<circle class="jar-dot ${on ? "" : "dim"}" cx="${x}" cy="${y}" r="${on ? 3.2 : 2.4}"
        style="--d:${1.5 + Math.random() * 2}s;--delay:${-Math.random() * 2}s;--dx:${(Math.random() - 0.5) * 14}px;--dy:${(Math.random() - 0.5) * 14}px"/>`,
    );
  }
  return `<svg viewBox="0 0 120 130">
    <rect class="jar-lid" x="36" y="14" width="48" height="12" rx="4"/>
    <path class="jar-glass" d="M40 26 h40 v8 q14 6 14 22 v52 q0 14 -14 14 h-40 q-14 0 -14 -14 v-52 q0 -16 14 -22z"/>
    ${dots.join("")}
  </svg>`;
}

function showWin() {
  openModal({
    jar: [state.solution.size, state.solution.size],
    title: "Your jar is full",
    sub: puzzleName(),
    stats: [["Time", fmt(Math.round(state.elapsed))], ["Hints", state.hints], ["Mistakes", state.mistakes]],
    actions: [{ label: "Next puzzle", cls: "primary", onClick: () => newGame() }],
  });
}

function showGameOver() {
  const found = [...state.marks.values()].filter((m) => m === "f").length;
  openModal({
    jar: [found, state.solution.size],
    title: "The lanterns went out",
    sub: `${puzzleName()}. ${found} of ${state.solution.size} fireflies caught.`,
    stats: [["Time", fmt(Math.round(state.elapsed))], ["Hints", state.hints]],
    actions: [
      { label: "Try again", cls: "ghost", onClick: () => resetProgress() },
      { label: "New puzzle", cls: "primary", onClick: () => newGame() },
    ],
  });
}

function openModal({ jar, sub, title, stats, actions }) {
  $("#modal-icon").innerHTML = jarSVG(...jar);
  $("#modal-sub").textContent = sub;
  $("#modal-title").textContent = title;
  $("#modal-stats").innerHTML = stats.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
  const box = $("#modal-actions");
  box.innerHTML = "";
  for (const a of actions) {
    const b = document.createElement("button");
    b.className = `btn ${a.cls}`;
    b.textContent = a.label;
    b.addEventListener("click", a.onClick);
    box.appendChild(b);
  }
  $("#modal").hidden = false;
  box.querySelector(".primary")?.focus();
}
function closeModal() { $("#modal").hidden = true; }

/* ---------- hints ---------- */
function clearHint() {
  boardEl.querySelectorAll(".hint-clue, .hint-cell").forEach((el) =>
    el.classList.remove("hint-clue", "hint-cell"),
  );
}

async function requestHint() {
  if (state.over) return;
  flushPending();
  const fireflies = [], empty = [];
  for (const [k, m] of state.marks) (m === "f" ? fireflies : empty).push(parseKey(k));
  const res = await fetch("/api/hint", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ difficulty: state.puzzle.difficulty, seed: state.puzzle.seed, fireflies, empty }),
  });
  const h = await res.json();
  clearHint();
  if (!h) return showMessage("Nothing left to deduce. You're nearly there!", "tip");
  state.hints++;
  h.clues.forEach(([r, c]) => cellEl(key(r, c)).classList.add("hint-clue"));
  h.cells.forEach(([r, c]) => cellEl(key(r, c)).classList.add("hint-cell"));
  showMessage(h.reason, "tip");
}

/* ---------- controls ---------- */
function newGame() {
  // The daily puzzle is fixed for the day, so "new" from there means a Medium board.
  loadPuzzle({ difficulty: currentLevel === "daily" ? "medium" : currentLevel });
}

function bindControls() {
  $("#new-game").addEventListener("click", newGame);
  $("#help").addEventListener("toggle", () => {
    try { localStorage.setItem("glowfield:help", $("#help").open ? "1" : "0"); } catch {}
  });
  $("#restart").addEventListener("click", () => resetProgress());
  $("#undo").addEventListener("click", undo);
  $("#hint").addEventListener("click", requestHint);
  $("#mode").addEventListener("click", () => {
    state.tapMode = !state.tapMode;
    $("#mode").setAttribute("aria-pressed", String(state.tapMode));
    showMessage(
      state.tapMode
        ? "Firefly mode: a single tap places a firefly."
        : "Back to normal: click to rule out, double-click to place.",
      "tip",
    );
  });
  $("#modal-close").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
    if ((e.metaKey || e.ctrlKey) && e.key === "z") { e.preventDefault(); undo(); }
  });
}

/* ---------- boot ---------- */
function fromHash() {
  const h = location.hash.slice(1);
  if (h === "daily") return { difficulty: "daily" };
  const m = h.match(/^([a-z]+)-(\d+)$/);
  if (m) return { difficulty: m[1], seed: Number(m[2]) };
  return null;
}

(async function boot() {
  fillIcons();
  makeSky();
  bindControls();
  let helpVisible = true;
  let saved = "beginner";
  try {
    helpVisible = localStorage.getItem("glowfield:help") !== "0";
    saved = localStorage.getItem("glowfield:difficulty") || saved;
  } catch {}
  $("#help").open = helpVisible;
  await loadDifficulties();
  await loadPuzzle(fromHash() ?? { difficulty: saved });
  window.addEventListener("hashchange", () => {
    const target = fromHash();
    if (target && `#${state.puzzle.daily ? "daily" : state.puzzle.id}` !== location.hash) loadPuzzle(target);
  });
})();
