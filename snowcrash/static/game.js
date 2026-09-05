(() => {
  const SESSION = "browser";
  const mapEl = document.getElementById("map");
  const statsEl = document.getElementById("stats");
  const invEl = document.getElementById("inventory");
  const logEl = document.getElementById("log");
  const overlay = document.getElementById("overlay");

  let state = null;
  let invMode = false;

  async function api(path, body) {
    const opts = body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session: SESSION, ...body }),
        }
      : {};
    const res = await fetch(path, opts);
    return res.json();
  }

  function colorizeMap(rows, visible, explored) {
    // Client receives already-fogged map; style glyphs
    return rows
      .map((row, y) => {
        let html = "";
        for (let x = 0; x < row.length; x++) {
          const ch = row[x];
          let cls = "fog";
          if (visible && visible[y] && visible[y][x]) {
            cls = "vis";
            if (ch === "@") cls = "player";
            else if (ch === "i") cls = "enemy-i";
            else if (ch === "t") cls = "enemy-t";
            else if (ch === "d") cls = "enemy-d";
            else if (ch === "&") cls = "npc";
            else if ("*!/[}%".includes(ch)) cls = "item";
          } else if (explored && explored[y] && explored[y][x]) {
            cls = "fog";
          } else {
            cls = "fog";
          }
          const esc =
            ch === "&" ? "&amp;" : ch === "<" ? "&lt;" : ch === ">" ? "&gt;" : ch;
          html += `<span class="${cls}">${esc === " " ? "&nbsp;" : esc}</span>`;
        }
        return html;
      })
      .join("\n");
  }

  function render(s) {
    state = s;
    mapEl.innerHTML = colorizeMap(s.map, s.visible, s.explored);
    const p = s.player;
    statsEl.innerHTML = `
      <div><strong>${escapeHtml(p.name)}</strong></div>
      <div class="hp">HP ${p.hp}/${p.max_hp}</div>
      <div class="focus">Focus ${p.focus}/${p.max_focus}</div>
      <div>Atk ${p.attack} · Def ${p.defense} · Hack ${p.hack}</div>
      <div>Turn ${s.turn} · Seed ${s.seed}</div>
      <div class="${p.has_payload ? "ok" : ""}">Payload-Zero: ${
        p.has_payload ? "IN SLEEVE" : "missing"
      }</div>
      <div style="margin-top:0.5rem;color:#6e7681">Quest flags: ${
        Object.keys(s.quest_flags || {}).join(", ") || "—"
      }</div>
    `;
    invEl.innerHTML = "";
    (s.inventory || []).forEach((it, i) => {
      const li = document.createElement("li");
      li.textContent = `${i}: ${it.glyph} ${it.name}`;
      if (it.equipped) li.classList.add("equipped");
      if (i === s.selected_inv) li.classList.add("sel");
      li.title = it.description;
      li.addEventListener("click", () => send("u", String(i)));
      invEl.appendChild(li);
    });
    logEl.innerHTML = (s.messages || [])
      .map((m) => `<div>${escapeHtml(m)}</div>`)
      .join("");
    logEl.scrollTop = logEl.scrollHeight;

    if (s.mode === "help") {
      overlay.classList.remove("hidden");
      overlay.innerHTML = `<pre>${escapeHtml(s.help)}\n\n[any key / Esc to close]</pre>`;
    } else if (s.mode === "dead") {
      overlay.classList.remove("hidden");
      overlay.innerHTML = `<div class="box banner">YOU DIED<br/><span style="font-size:0.85rem;color:#c9d1d9">Press <kbd>r</kbd> to restart</span></div>`;
    } else if (s.mode === "won") {
      overlay.classList.remove("hidden");
      overlay.innerHTML = `<div class="box banner">YOU WIN<br/><span style="font-size:0.85rem;color:#c9d1d9">Payload cleared. <kbd>r</kbd> restart</span></div>`;
    } else if (s.mode === "inventory") {
      invMode = true;
      overlay.classList.add("hidden");
    } else {
      invMode = false;
      overlay.classList.add("hidden");
    }
  }

  function escapeHtml(t) {
    return String(t)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  async function send(action, arg) {
    const s = await api("/api/action", { action, arg });
    render(s);
  }

  const KEYMAP = {
    ArrowUp: "up",
    ArrowDown: "down",
    ArrowLeft: "left",
    ArrowRight: "right",
    w: "w",
    a: "a",
    s: "s",
    d: "d",
    h: "h",
    j: "j",
    k: "k",
    l: "l",
    g: "g",
    f: "f",
    i: "i",
    q: "q",
    r: "r",
    u: "u",
    e: "e",
    ".": ".",
    " ": ".",
    "?": "?",
    Escape: "escape",
  };

  window.addEventListener("keydown", (ev) => {
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    const action = KEYMAP[ev.key];
    if (!action) {
      if (/^[0-9]$/.test(ev.key)) {
        ev.preventDefault();
        send(ev.key);
      }
      return;
    }
    ev.preventDefault();
    // In help overlay, any mapped key closes
    if (state && state.mode === "help") {
      send("escape");
      return;
    }
    send(action);
  });

  // Boot
  api("/api/new", { seed: null }).then(render).catch((err) => {
    mapEl.textContent = "Failed to load game: " + err;
  });
})();
