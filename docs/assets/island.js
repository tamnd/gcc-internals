// The runtime starts when the reader says so, and not before.
//
// Everything a marimo island needs to come alive is sitting in a <template> in the page.
// A script inside a template is inert, so nothing has been fetched and nothing has run.
// Moving those nodes into <head> is what starts the download, so that is what the button
// does. Before it is pressed the page costs what the HTML costs.

(function () {
  "use strict";

  function start(button) {
    var island = button.closest(".island");
    var template = island.querySelector("template.island-head");
    if (!template) {
      return;
    }

    island.classList.add("is-starting");
    button.replaceWith(status(island));
    document.head.appendChild(template.content.cloneNode(true));
    template.remove();
  }

  function status(island) {
    var line = document.createElement("span");
    line.className = "island-status";
    line.setAttribute("role", "status");
    line.textContent = "Starting Python. The first time takes a few seconds.";

    // Marimo swaps the static output for live cells as it hydrates, so the first change
    // under .island-cells is the runtime arriving. Nothing else tells us.
    var cells = island.querySelector(".island-cells");
    var watcher = new MutationObserver(function () {
      watcher.disconnect();
      island.classList.remove("is-starting");
      island.classList.add("is-live");
      line.textContent = "Python is running here now. Every cell below is live.";
    });
    watcher.observe(cells, { childList: true, subtree: true });

    return line;
  }

  // Two theme systems on one page. Material puts its scheme on the body as a data
  // attribute, marimo is Tailwind and wants a "dark" class on the root element. Without
  // this the cells come up as a white card in the middle of a dark page.
  //
  // That gets most of the way, and then there is one stubborn corner. Marimo renders its
  // input controls into a shadow root, and the wrapper inside pins color-scheme to light.
  // Its text colours are light-dark() pairs, so they resolve to the light half and every
  // label comes out near black on a near black page. A shadow root is closed to page CSS,
  // so the only way in is to hand it a stylesheet, which is what this does.
  //
  // The second line repairs a button. Marimo's island bundle asks for its background with
  // a Tailwind name its own theme does not define, so the background comes out transparent
  // and the dark text meant to sit on it lands on the page instead. The colours it wanted
  // are right there in its own variables, so we just use them.
  var scheme = new CSSStyleSheet();

  var repair =
    ".marimo button.bg-secondary { background-color: var(--secondary);" +
    " color: var(--secondary-foreground); border-color: var(--input); }";

  function lend(element) {
    var root = element.shadowRoot;
    if (root && root.adoptedStyleSheets.indexOf(scheme) === -1) {
      root.adoptedStyleSheets = root.adoptedStyleSheets.concat(scheme);
    }
  }

  function paint() {
    var slate = document.body.getAttribute("data-md-color-scheme") === "slate";
    document.documentElement.classList.toggle("dark", slate);
    scheme.replaceSync(
      ".marimo { color-scheme: " + (slate ? "dark" : "light") + "; }\n" + repair
    );
    document.querySelectorAll(".island *").forEach(lend);
  }

  // Cells appear as the runtime hydrates and again whenever a cell reruns, and each new
  // control brings a new shadow root that has not been given the sheet yet.
  var pending = 0;
  function repaint() {
    clearTimeout(pending);
    pending = setTimeout(paint, 50);
  }

  paint();
  new MutationObserver(paint).observe(document.body, {
    attributes: true,
    attributeFilter: ["data-md-color-scheme"],
  });
  new MutationObserver(repaint).observe(document.body, { childList: true, subtree: true });

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-island-start]");
    if (button) {
      start(button);
    }
  });
})();
