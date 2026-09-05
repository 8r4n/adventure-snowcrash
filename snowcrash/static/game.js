(() => {
  const SESSION = "browser";
  const mapEl = document.getElementById("map");
  const asciiEl = document.getElementById("ascii-map");
  const statsEl = document.getElementById("stats");
  const invEl = document.getElementById("inventory");
  const logEl = document.getElementById("log");
  const overlay = document.getElementById("overlay");
  const legendEl = document.getElementById("legend");
  const btnAscii = document.getElementById("btn-ascii");
  const btnMute = document.getElementById("btn-mute");

  let state = null;
  let invMode = false;
  let useTiles = true;
  let tilesMeta = null;
  let lastMode = null;
  const TILE_PATH = "/static/tiles/";
  const SFX_PATH = "/static/sfx/";
  const SFX_IDS = [
    "step",
    "bump",
    "melee",
    "hurt",
    "kill",
    "pulse",
    "pickup",
    "use",
    "talk",
    "door",
    "win",
    "death",
    "click",
  ];

  const Sound = (() => {
    const STORAGE_KEY = "snowcrash_mute";
    const DEFAULT_VOL = 0.4;
    let muted = localStorage.getItem(STORAGE_KEY) === "1";
    let volume = DEFAULT_VOL;
    let unlocked = false;
    const cache = {};
    let ctx = null;

    function ensureCtx() {
      if (!ctx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (AC) ctx = new AC();
      }
      if (ctx && ctx.state === "suspended") {
        ctx.resume().catch(() => {});
      }
      return ctx;
    }

    function unlock() {
      if (unlocked) return;
      unlocked = true;
      ensureCtx();
    }

    async function load(id) {
      if (cache[id]) return cache[id];
      try {
        const res = await fetch(SFX_PATH + id + ".wav");
        if (!res.ok) return null;
        const buf = await res.arrayBuffer();
        const ac = ensureCtx();
        if (ac) {
          const decoded = await ac.decodeAudioData(buf.slice(0));
          cache[id] = { type: "buffer", data: decoded };
          return cache[id];
        }
      } catch (err) {
        console.warn("sfx load failed", id, err);
      }
      // HTMLAudioElement fallback
      const audio = new Audio(SFX_PATH + id + ".wav");
      audio.preload = "auto";
      cache[id] = { type: "html", data: audio };
      return cache[id];
    }

    function play(id) {
      if (muted || !id) return;
      unlock();
      const entry = cache[id];
      if (!entry) {
        load(id).then(() => play(id));
        return;
      }
      try {
        if (entry.type === "buffer") {
          const ac = ensureCtx();
          if (!ac) return;
          const src = ac.createBufferSource();
          src.buffer = entry.data;
          const gain = ac.createGain();
          gain.gain.value = volume;
          src.connect(gain);
          gain.connect(ac.destination);
          src.start(0);
        } else {
          const a = entry.data.cloneNode ? entry.data.cloneNode() : entry.data;
          a.volume = volume;
          a.currentTime = 0;
          a.play().catch(() => {});
        }
      } catch (err) {
        console.warn("sfx play failed", id, err);
      }
    }

    function playList(ids) {
      if (!ids || !ids.length) return;
      // stagger slightly so overlapping events stay distinct
      ids.forEach((id, i) => {
        setTimeout(() => play(id), i * 28);
      });
    }

    function setMuted(m) {
      muted = !!m;
      localStorage.setItem(STORAGE_KEY, muted ? "1" : "0");
      syncUi();
    }

    function toggleMute() {
      setMuted(!muted);
      if (!muted) play("click");
      return muted;
    }

    function syncUi() {
      if (!btnMute) return;
      btnMute.setAttribute("aria-pressed", muted ? "true" : "false");
      btnMute.textContent = muted ? "Unmute" : "Mute";
      btnMute.title = muted
        ? "Unmute sound (m)"
        : "Mute sound (m)";
    }

    function preload() {
      SFX_IDS.forEach((id) => load(id));
    }

    return {
      play,
      playList,
      toggleMute,
      setMuted,
      isMuted: () => muted,
      unlock,
      preload,
      syncUi,
    };
  })();

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

  function glyphInfo(ch) {
    const glyphs = (tilesMeta && tilesMeta.glyphs) || {};
    return glyphs[ch] || glyphs[" "] || { file: "fog.png", label: "Unknown" };
  }

  function colorizeMap(rows, visible, explored) {
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
            else if (ch === "J" || ch === "U") cls = "landmark";
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

  function renderTiles(s) {
    const w = s.width;
    const h = s.height;
    const vis = s.visible || [];
    const exp = s.explored || [];
    const parts = [
      `<div id="tile-grid" style="grid-template-columns:repeat(${w},var(--tile));grid-template-rows:repeat(${h},var(--tile))">`,
    ];
    for (let y = 0; y < h; y++) {
      const row = s.map[y] || "";
      const vrow = vis[y] || [];
      const erow = exp[y] || [];
      for (let x = 0; x < w; x++) {
        const visible = !!vrow[x];
        const explored = !!erow[x];
        const ch = visible || explored ? row[x] : " ";
        const info = glyphInfo(ch);
        const kind = visible ? "vis" : explored ? "explored" : "hidden";
        const file = info.file || "fog.png";
        const label = escapeAttr(info.label || ch);
        const escCh = escapeAttr(ch);
        parts.push(
          `<div class="cell ${kind}" data-ch="${escCh}" title="${label}" style="background-image:url('${TILE_PATH}${file}')"></div>`
        );
      }
    }
    parts.push("</div>");
    mapEl.innerHTML = parts.join("");
  }

  function buildLegend() {
    if (!legendEl || !tilesMeta) return;
    const items = tilesMeta.legend || [];
    legendEl.innerHTML = items
      .map((it) => {
        const g = escapeHtml(it.glyph === " " ? "·" : it.glyph);
        return `<div class="leg" title="${escapeAttr(it.label)}">
          <img src="${TILE_PATH}${it.file}" alt="${escapeAttr(it.label)}" width="32" height="32" />
          <span class="g">${g}</span>
          <span>${escapeHtml(it.label)}</span>
        </div>`;
      })
      .join("");
  }

  function applyViewMode() {
    if (useTiles) {
      mapEl.classList.remove("hidden");
      asciiEl.classList.add("hidden");
      btnAscii.setAttribute("aria-pressed", "false");
      btnAscii.textContent = "ASCII view";
    } else {
      mapEl.classList.add("hidden");
      asciiEl.classList.remove("hidden");
      btnAscii.setAttribute("aria-pressed", "true");
      btnAscii.textContent = "Tile view";
    }
  }

  function toggleAscii() {
    useTiles = !useTiles;
    Sound.play("click");
    applyViewMode();
    if (state) {
      if (useTiles) renderTiles(state);
      else asciiEl.innerHTML = colorizeMap(state.map, state.visible, state.explored);
    }
  }

  function handleSfx(s) {
    const events = Array.isArray(s.sfx) ? s.sfx.slice() : [];
    // Backup: mode change to dead/won if server omitted event
    if (s.mode === "dead" && lastMode !== "dead" && !events.includes("death")) {
      events.push("death");
    }
    if (s.mode === "won" && lastMode !== "won" && !events.includes("win")) {
      events.push("win");
    }
    lastMode = s.mode;
    Sound.playList(events);
  }

  function render(s) {
    handleSfx(s);
    state = s;
    if (useTiles) {
      renderTiles(s);
    } else {
      asciiEl.innerHTML = colorizeMap(s.map, s.visible, s.explored);
    }
    applyViewMode();
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
      li.addEventListener("click", () => {
        Sound.play("click");
        send("u", String(i));
      });
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

  function escapeAttr(t) {
    return escapeHtml(t).replace(/"/g, "&quot;");
  }

  async function send(action, arg) {
    Sound.unlock();
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
    Sound.unlock();
    if (ev.key === "m" || ev.key === "M") {
      ev.preventDefault();
      Sound.toggleMute();
      return;
    }
    if (ev.key === "A") {
      ev.preventDefault();
      toggleAscii();
      return;
    }
    const action = KEYMAP[ev.key];
    if (!action) {
      if (/^[0-9]$/.test(ev.key)) {
        ev.preventDefault();
        send(ev.key);
      }
      return;
    }
    ev.preventDefault();
    if (state && state.mode === "help") {
      send("escape");
      return;
    }
    send(action);
  });

  if (btnAscii) {
    btnAscii.addEventListener("click", toggleAscii);
  }
  if (btnMute) {
    btnMute.addEventListener("click", () => {
      Sound.unlock();
      Sound.toggleMute();
    });
  }
  Sound.syncUi();

  // First gesture unlocks audio (browser autoplay policy)
  ["pointerdown", "keydown", "touchstart"].forEach((evt) => {
    window.addEventListener(evt, () => Sound.unlock(), { once: true, passive: true });
  });

  async function boot() {
    Sound.preload();
    try {
      tilesMeta = await fetch(TILE_PATH + "tiles.json").then((r) => r.json());
      buildLegend();
    } catch (err) {
      console.warn("tiles.json failed, falling back to ASCII", err);
      useTiles = false;
    }
    applyViewMode();
    try {
      const s = await api("/api/new", { seed: null });
      render(s);
    } catch (err) {
      mapEl.textContent = "Failed to load game: " + err;
    }
  }

  boot();
})();
