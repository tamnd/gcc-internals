// Behaviour for every widget in this project. There is only one of these files.
//
// The markup is built in Python and arrives complete. Nothing here creates an element or
// writes a label, so there is no second renderer to drift from the first one, and a page
// with this script blocked still shows the whole widget. What this adds is the part a
// static page cannot do: selecting, filtering, and remembering where you were in the URL.
//
// It runs in two places. On the site it is a module that finds every widget on the page.
// In a notebook it is the anywidget entry point, and then it also tells Python when the
// view changed, so a widget that needs a redraw can have one.

const NEXT = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };

function cells(root) {
  return [...root.querySelectorAll("[data-cell]")].filter((c) => !c.hidden && !c.disabled);
}

function panels(root) {
  return [...root.querySelectorAll("[data-panel][role=tabpanel]")];
}

// Which view key selection writes to. The container that holds the cells says so, because
// only Python knows whether this widget calls it "at" or "name".

function selectKey(root, from) {
  const owner = (from && from.closest("[data-select]")) || root.querySelector("[data-select]");
  return owner ? owner.dataset.select : "at";
}

// Selection

function select(root, name, { focus = false } = {}) {
  const all = [...root.querySelectorAll("[data-cell]")];
  const wanted = all.find((c) => c.dataset.cell === name);
  // A filter can hide the cell the URL asked for. Landing on a hidden cell shows a panel
  // with nothing pointing at it, so fall back to the first one still on screen.
  const usable = wanted && !wanted.hidden && !wanted.disabled;
  const chosen = usable ? wanted : cells(root)[0] || wanted;
  if (!chosen) return null;

  for (const c of all) {
    const on = c === chosen;
    c.setAttribute("aria-current", on ? "true" : "false");
    if (c.hasAttribute("tabindex")) c.tabIndex = on ? 0 : -1;
  }
  const panel = chosen.dataset.panel;
  if (panel !== undefined) {
    for (const p of panels(root)) p.hidden = p.dataset.panel !== panel;
  }
  if (focus) chosen.focus();
  return chosen.dataset.cell;
}

function step(root, from, by) {
  const list = cells(root);
  const at = list.findIndex((c) => c.dataset.cell === from);
  const next = Math.min(list.length - 1, Math.max(0, (at < 0 ? 0 : at) + by));
  return list[next] ? list[next].dataset.cell : from;
}

// Filtering. The cell already carries every fact a filter needs as a data attribute, so
// this never has to ask Python what a pass was.

function applyFilters(root, view) {
  for (const cell of root.querySelectorAll(".gx-cell, .gx-insn, .gx-slot, .gx-asmline")) {
    const wrongPhase = view.phase && view.phase !== "all" && cell.dataset.phase !== view.phase;
    const unchanged = view.only === "changed" && cell.dataset.changed !== "1";
    // The flag diff filters by the level a switch first comes on at, and the same column
    // appears once per level, so this hides a whole column across every row at once.
    const wrongFirst = view.first && view.first !== "all" && cell.dataset.first !== view.first;
    // The RTX tree filters an insn chain down to the entries that become instructions,
    // which is a third of it and is what a reader means when they say "the code". The
    // assembly listing uses the same key to cut forty six lines down to the twelve that
    // are instructions, which is the same idea one stage later.
    const wrongKind = view.kind && view.kind !== "all" && cell.dataset.kind !== view.kind;
    // The register allocation widget filters a function's pseudos down to the ones that
    // got a register or the ones that did not, which on a spilling function is the only
    // way to see the second group without counting rows.
    const wrongHome = view.home && view.home !== "all" && cell.dataset.home !== view.home;
    cell.hidden = Boolean(wrongPhase || unchanged || wrongFirst || wrongKind || wrongHome);
  }
}

// The URL. One fragment per widget, joined with semicolons, so two widgets on a page do
// not fight over it.

function writeFragment(id, view) {
  const body = Object.entries(view)
    .filter(([, v]) => v !== "" && v != null)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}:${encodeURIComponent(v)}`)
    .join(",");
  const others = (location.hash || "")
    .replace(/^#/, "")
    .split(";")
    .filter((c) => c && c.split("=")[0] !== id);
  const all = body ? [...others, `${id}=${body}`] : others;
  history.replaceState(null, "", all.length ? `#${all.join(";")}` : location.pathname);
}

function readPairs(body) {
  const view = {};
  for (const part of (body || "").split(",")) {
    const at = part.indexOf(":");
    if (at > 0) view[part.slice(0, at)] = decodeURIComponent(part.slice(at + 1));
  }
  return view;
}

// What the widget was rendered with, then whatever the URL says on top of it. That order
// is what makes a link to a widget work: the page is built once with default state, and
// the fragment is the only thing that knows where the reader was pointed.

function readView(root, id) {
  const mine = (location.hash || "")
    .replace(/^#/, "")
    .split(";")
    .find((c) => c.split("=")[0] === id);
  const asked = mine ? readPairs(mine.slice(mine.indexOf("=") + 1)) : {};
  const known = readPairs(root.dataset.state);
  for (const key of Object.keys(asked)) {
    if (key in known) known[key] = asked[key];
  }
  return known;
}

// The prediction gate. The reveal stays shut until the reader commits, which is the whole
// point of the rule and the one thing the static fallback cannot enforce.

function wireGate(root, view, push) {
  const reveal = root.querySelector(".gx-reveal");
  const answer = root.querySelector(".gx-answer");
  if (!reveal || !answer) return;

  const picked = root.querySelector(`input[type=radio][value="${view.pick}"]`);
  if (picked) picked.checked = true;
  answer.hidden = !view.shown;
  reveal.disabled = !root.querySelector("input[type=radio]:checked");

  root.addEventListener("change", (e) => {
    if (e.target.matches("input[type=radio]")) {
      reveal.disabled = false;
      push({ pick: e.target.value });
    }
  });

  reveal.addEventListener("click", () => {
    const picked = root.querySelector("input[type=radio]:checked");
    answer.hidden = false;
    answer.open = true;
    reveal.setAttribute("aria-expanded", "true");
    if (picked) {
      const right = root.querySelector(`[data-why="${picked.value}"]`) === null;
      const label = picked.closest("label");
      if (label) label.classList.add(right ? "gx-right" : "gx-wrong");
      for (const why of root.querySelectorAll("[data-why]")) {
        why.hidden = why.dataset.why !== picked.value;
      }
    }
    push({ shown: "1" });
    answer.scrollIntoView({ block: "nearest" });
  });
}

// Putting it together

export function wire(root, model) {
  if (!root || root.dataset.wired === "1") return;
  root.dataset.wired = "1";

  const id = root.dataset.id || root.dataset.gx;
  const view = readView(root, id);
  const push = (change) => {
    Object.assign(view, change);
    writeFragment(id, view);
    if (model) model.set("view", { ...view });
    if (model) model.save_changes();
  };

  // Catch the controls up with whatever the URL asked for, before anything is clicked.
  applyFilters(root, view);
  for (const b of root.querySelectorAll("[data-filter]")) {
    const on = view[b.dataset.filter] === b.dataset.value;
    b.setAttribute("aria-pressed", on ? "true" : "false");
  }
  wireGate(root, view, push);
  const key = selectKey(root);
  if (view[key] !== undefined) view[key] = select(root, view[key]) ?? view[key];

  root.addEventListener("click", (e) => {
    const cell = e.target.closest("[data-cell]");
    if (cell && root.contains(cell)) {
      push({ [selectKey(root, cell)]: select(root, cell.dataset.cell) });
      return;
    }
    const filter = e.target.closest("[data-filter]");
    if (filter && root.contains(filter)) {
      const { filter: key, value } = filter.dataset;
      for (const b of root.querySelectorAll(`[data-filter="${key}"]`)) {
        b.setAttribute("aria-pressed", b === filter ? "true" : "false");
      }
      view[key] = value;
      applyFilters(root, view);
      push({ [key]: value });
      // A filter can hide the selected cell, so land on whatever is still on screen.
      const at = selectKey(root);
      push({ [at]: select(root, view[at]) });
    }
  });

  root.addEventListener("keydown", (e) => {
    const cell = e.target.closest("[data-cell]");
    if (!cell) return;
    const key = selectKey(root, cell);
    if (e.key in NEXT) {
      e.preventDefault();
      push({ [key]: select(root, step(root, cell.dataset.cell, NEXT[e.key]), { focus: true }) });
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      const list = cells(root);
      const target = (e.key === "Home" ? list[0] : list[list.length - 1]).dataset.cell;
      push({ [key]: select(root, target, { focus: true }) });
    }
  });
}

/** Every widget on a static page. Safe to call twice. */
export function attach(scope = document) {
  for (const root of scope.querySelectorAll("[data-gx]")) wire(root, null);
}

/** The anywidget entry point. */
export default {
  render({ model, el }) {
    el.innerHTML = model.get("html");
    wire(el.firstElementChild, model);
    model.on("change:html", () => {
      el.innerHTML = model.get("html");
      wire(el.firstElementChild, model);
    });
  },
};
