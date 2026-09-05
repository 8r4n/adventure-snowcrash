(() => {
  const SESSION = "browser";
  const fpvEl = document.getElementById("fpv");
  const minimapEl = document.getElementById("minimap");
  const statsEl = document.getElementById("stats");
  const invEl = document.getElementById("inventory");
  const logEl = document.getElementById("log");
  const overlay = document.getElementById("overlay");
  const legendEl = document.getElementById("legend");
  const btnMute = document.getElementById("btn-mute");
  const perspectiveEl = document.getElementById("perspective");
  const compassEl = document.getElementById("compass");
  const cutsceneEl = document.getElementById("cutscene");
  const cutTitleEl = document.getElementById("cut-title");
  const cutFramesEl = document.getElementById("cut-frames");
  const fpvStatus = document.getElementById("fpv-status");
  const introEl = document.getElementById("intro");
  const introCanvas = document.getElementById("intro-canvas");
  const introChapterEl = document.getElementById("intro-chapter");
  const btnSkipIntro = document.getElementById("btn-skip-intro");
  const btnReplayIntro = document.getElementById("btn-replay-intro");
  const appEl = document.getElementById("app");

  let state = null;
  let invMode = false;
  let lastMode = null;
  let cutscenePlaying = false;
  let gameplayReady = false;
  let introActive = false;

  const SFX_PATH = "/static/sfx/";
  const CUT_PATH = "/static/cutscenes/";
  const SFX_IDS = [
    "step", "bump", "melee", "hurt", "kill", "pulse", "pickup",
    "use", "talk", "door", "win", "death", "click",
  ];
  const FACING_NAMES = ["N", "E", "S", "W"];
  const FACING_GLYPH = ["^", ">", "v", "<"];
  const WALL_CHARS = "#~";
  const FPV_COLS = 88;
  const FPV_ROWS = 32;
  const MINI_R = 10; // radar radius in map cells
  const SHADE = " .:-=+*#%@";

  // ---- Sound ----
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
      if (ctx && ctx.state === "suspended") ctx.resume().catch(() => {});
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
          cache[id] = { type: "buffer", data: await ac.decodeAudioData(buf.slice(0)) };
          return cache[id];
        }
      } catch (err) {
        console.warn("sfx load failed", id, err);
      }
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
      ids.forEach((id, i) => setTimeout(() => play(id), i * 28));
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
      btnMute.title = muted ? "Unmute sound (m)" : "Mute sound (m)";
    }
    function preload() {
      SFX_IDS.forEach((id) => load(id));
    }
    return { play, playList, toggleMute, setMuted, isMuted: () => muted, unlock, preload, syncUi };
  })();

  // ---- Cutscenes (jack-in intensives) ----
  const CutscenePlayer = (() => {
    const cache = {};
    let timer = null;
    let queue = [];

    function setPerspective(intensive, title) {
      if (!perspectiveEl) return;
      if (intensive) {
        perspectiveEl.classList.add("first");
        perspectiveEl.textContent = title || "1ST PERSON — JACK-IN";
      } else {
        perspectiveEl.classList.add("first");
        perspectiveEl.textContent = "1ST PERSON — VIDEO→ASCII";
      }
    }

    async function load(id) {
      if (cache[id]) return cache[id];
      const res = await fetch(CUT_PATH + id + ".json");
      if (!res.ok) throw new Error("cutscene missing: " + id);
      cache[id] = await res.json();
      return cache[id];
    }

    function hide() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      cutscenePlaying = false;
      if (cutsceneEl) cutsceneEl.classList.add("hidden");
      setPerspective(false);
    }

    function finishOne() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      if (queue.length) {
        playNext();
        return;
      }
      hide();
    }

    function playPack(pack) {
      cutscenePlaying = true;
      const title = pack.title || ("1ST PERSON — " + (pack.id || "").toUpperCase());
      setPerspective(true, title);
      if (cutTitleEl) cutTitleEl.textContent = title;
      if (cutsceneEl) cutsceneEl.classList.remove("hidden");
      const frames = pack.frames || [];
      if (!frames.length) {
        finishOne();
        return;
      }
      let i = 0;
      if (cutFramesEl) cutFramesEl.textContent = frames[0];
      const fps = pack.fps || 10;
      timer = setInterval(() => {
        i += 1;
        if (i >= frames.length) {
          finishOne();
          return;
        }
        if (cutFramesEl) cutFramesEl.textContent = frames[i];
      }, Math.max(40, Math.floor(1000 / fps)));
    }

    async function playNext() {
      const id = queue.shift();
      if (!id) {
        finishOne();
        return;
      }
      try {
        playPack(await load(id));
      } catch (err) {
        console.warn("cutscene failed", id, err);
        playNext();
      }
    }

    function enqueue(ids) {
      const list = (ids || []).filter(Boolean);
      if (!list.length) return;
      queue.push(...list);
      if (!cutscenePlaying) playNext();
    }

    function skip() {
      if (!cutscenePlaying) return false;
      Sound.play("click");
      finishOne();
      return true;
    }

    return {
      enqueue,
      skip,
      isPlaying: () => cutscenePlaying,
      setPerspective,
      load,
    };
  })();


  // ---- Opening cinematic (high-fidelity colored ASCII video) ----
  const INTRO_VIDEO = "/static/cutscenes/intro/montage.mp4";
  const INTRO_CHAPTERS = [
    {
      at: 0,
      html:
        '<p class="intro-kicker">METAVERSE LAYER · VIDEO→ASCII</p>' +
        '<h1 class="intro-title">SNOWCRASH</h1>' +
        '<p class="intro-sub">Fractured LA</p>',
    },
    {
      at: 5.2,
      html:
        '<p class="intro-kicker">COURIER DOSSIER</p>' +
        '<h1 class="intro-title" style="letter-spacing:0.22em;font-size:clamp(1.4rem,4vw,2.2rem)">RIN VALE</h1>' +
        '<p class="intro-body">Freelance Metaverse courier and street hacker. ' +
        "You ride the neon seams between meatspace and the Layer — paid to move what shouldn't move.</p>",
    },
    {
      at: 10.8,
      html:
        '<p class="intro-kicker">BRIEFING</p>' +
        '<h1 class="intro-title" style="letter-spacing:0.18em;font-size:clamp(1.2rem,3.5vw,1.9rem)">THE STREETS</h1>' +
        '<p class="intro-body">Fractured LA is a grid of jackpoints, uplink nodes, and hostile avatars. ' +
        "Tonight's run: recover a linguistic weapon before it rewrites the Layer.</p>",
    },
    {
      at: 16.2,
      html:
        '<p class="intro-kicker">THREAT VECTOR</p>' +
        '<h1 class="intro-title" style="letter-spacing:0.16em;font-size:clamp(1.2rem,3.5vw,1.9rem)">PAYLOAD-ZERO</h1>' +
        '<p class="intro-body">A viral utterance sealed in a courier sleeve. ' +
        "Infected avatars hunt it. Security drones triangulate it. Deliver it to a Metaverse uplink — or burn with it.</p>",
    },
    {
      at: 21.5,
      html:
        '<p class="intro-kicker">JACK IN</p>' +
        '<h1 class="intro-title">SNOWCRASH</h1>' +
        '<p class="intro-sub">Enter the streets</p>' +
        '<p class="intro-body">WASD move · Q/E turn · recover Payload-Zero · punch the uplink.</p>',
    },
  ];

  const IntroPlayer = (() => {
    let ascii = null;
    let chapterTimer = null;
    let chapterIdx = -1;
    let finishing = false;
    let resolveDone = null;

    function setChapter(i) {
      if (!introChapterEl || i === chapterIdx || i < 0 || i >= INTRO_CHAPTERS.length) return;
      chapterIdx = i;
      introChapterEl.classList.remove("swap");
      // force reflow for animation restart
      void introChapterEl.offsetWidth;
      introChapterEl.innerHTML = INTRO_CHAPTERS[i].html;
      introChapterEl.classList.add("swap");
    }

    function tickChapters() {
      if (!ascii || !ascii.video) return;
      const t = ascii.video.currentTime || 0;
      let idx = 0;
      for (let i = 0; i < INTRO_CHAPTERS.length; i++) {
        if (t >= INTRO_CHAPTERS[i].at) idx = i;
      }
      setChapter(idx);
    }

    function showUi(show) {
      if (introEl) {
        if (show) introEl.classList.remove("hidden");
        else introEl.classList.add("hidden");
      }
      document.body.classList.toggle("intro-active", !!show);
      if (appEl) {
        if (show) appEl.classList.add("app-hidden");
        else appEl.classList.remove("app-hidden");
      }
    }

    function ensureAscii() {
      if (ascii || !introCanvas || typeof VideoAsciiCanvas === "undefined") return ascii;
      const cols = Math.min(200, Math.max(120, Math.floor(window.innerWidth / 7)));
      ascii = new VideoAsciiCanvas(introCanvas, {
        cols,
        brightness: 1.2,
        contrast: 1.15,
        autoColor: true,
        bg: "#05080c",
      });
      return ascii;
    }

    function finish() {
      if (finishing) return;
      finishing = true;
      introActive = false;
      if (chapterTimer) {
        clearInterval(chapterTimer);
        chapterTimer = null;
      }
      if (ascii) ascii.stop();
      showUi(false);
      const done = resolveDone;
      resolveDone = null;
      finishing = false;
      if (done) done();
    }

    async function play() {
      introActive = true;
      finishing = false;
      chapterIdx = -1;
      showUi(true);
      setChapter(0);

      const engine = ensureAscii();
      if (!engine) {
        console.warn("VideoAsciiCanvas missing — skipping intro");
        finish();
        return;
      }

      try {
        await engine.load(INTRO_VIDEO);
      } catch (err) {
        console.warn("intro video load failed", err);
        finish();
        return;
      }

      return new Promise((resolve) => {
        resolveDone = resolve;
        chapterTimer = setInterval(tickChapters, 200);
        engine.play({
          onEnded: () => finish(),
        });
        // Resize on window changes while intro runs
        const onResize = () => {
          if (!introActive || !ascii) return;
          const cols = Math.min(200, Math.max(120, Math.floor(window.innerWidth / 7)));
          ascii.setCols(cols);
        };
        window.addEventListener("resize", onResize);
        const prev = resolveDone;
        resolveDone = () => {
          window.removeEventListener("resize", onResize);
          if (prev) prev();
        };
      });
    }

    function skip() {
      if (!introActive) return false;
      finish();
      return true;
    }

    return {
      play,
      skip,
      isActive: () => introActive,
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

  function escapeHtml(t) {
    return String(t)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function mapAt(s, x, y) {
    if (y < 0 || x < 0 || y >= s.height || x >= s.width) return "#";
    const row = s.map[y] || "";
    return row[x] || "#";
  }

  function isWall(ch) {
    return ch === "#" || ch === "~" || ch === " ";
  }

  function entityAt(s, x, y) {
    const ch = mapAt(s, x, y);
    if ("itd&*!/[}%JU@".includes(ch) && ch !== "." && ch !== "=" && ch !== "," && ch !== "+") {
      // Prefer entity-like glyphs from the rendered overlay map
      if ("itd&@".includes(ch) || "*!/[}%".includes(ch) || ch === "J" || ch === "U") return ch;
    }
    return null;
  }

  // ---- Live FPV raycaster (video→ASCII Metaverse layer) ----
  function renderFpv(s) {
    if (!fpvEl || !s) return;
    const px = s.player.x + 0.5;
    const py = s.player.y + 0.5;
    const facing = (s.player.facing || 0) % 4;
    const ang = (facing * Math.PI) / 2; // 0=N -> -PI/2 in screen space? 
    // Map: 0=N (0,-1), 1=E (1,0), 2=S (0,1), 3=W (-1,0)
    // Screen angle: 0 = +X east conventionally; use dir from facing
    const dirX = [0, 1, 0, -1][facing];
    const dirY = [-1, 0, 1, 0][facing];
    // camera plane (perpendicular)
    const planeX = -dirY * 0.66;
    const planeY = dirX * 0.66;

    const cols = FPV_COLS;
    const rows = FPV_ROWS;
    const depths = new Array(cols);
    const hits = new Array(cols);
    const sides = new Array(cols);
    const hitCh = new Array(cols);

    for (let col = 0; col < cols; col++) {
      const camX = (2 * col) / cols - 1;
      const rayDirX = dirX + planeX * camX;
      const rayDirY = dirY + planeY * camX;
      let mapX = Math.floor(px);
      let mapY = Math.floor(py);
      const deltaDistX = rayDirX === 0 ? 1e30 : Math.abs(1 / rayDirX);
      const deltaDistY = rayDirY === 0 ? 1e30 : Math.abs(1 / rayDirY);
      let stepX, stepY, sideDistX, sideDistY;
      if (rayDirX < 0) {
        stepX = -1;
        sideDistX = (px - mapX) * deltaDistX;
      } else {
        stepX = 1;
        sideDistX = (mapX + 1 - px) * deltaDistX;
      }
      if (rayDirY < 0) {
        stepY = -1;
        sideDistY = (py - mapY) * deltaDistY;
      } else {
        stepY = 1;
        sideDistY = (mapY + 1 - py) * deltaDistY;
      }
      let hit = 0;
      let side = 0;
      let ch = "#";
      for (let i = 0; i < 48 && !hit; i++) {
        if (sideDistX < sideDistY) {
          sideDistX += deltaDistX;
          mapX += stepX;
          side = 0;
        } else {
          sideDistY += deltaDistY;
          mapY += stepY;
          side = 1;
        }
        ch = mapAt(s, mapX, mapY);
        if (isWall(ch) || ch === "+") hit = 1;
      }
      let perp;
      if (side === 0) perp = (mapX - px + (1 - stepX) / 2) / rayDirX;
      else perp = (mapY - py + (1 - stepY) / 2) / rayDirY;
      if (!isFinite(perp) || perp < 0.05) perp = 0.05;
      depths[col] = perp;
      sides[col] = side;
      hitCh[col] = ch;
      hits[col] = hit;
    }

    // Build ASCII framebuffer
    const lines = [];
    const mid = rows / 2;
    for (let y = 0; y < rows; y++) {
      let row = "";
      for (let x = 0; x < cols; x++) {
        const dist = depths[x];
        const lineH = Math.min(rows, Math.floor(rows / dist));
        const drawStart = Math.floor(mid - lineH / 2);
        const drawEnd = Math.floor(mid + lineH / 2);
        let c = " ";
        if (y < drawStart) {
          // ceiling — scanlines
          const shade = Math.max(0, 2 - Math.floor((drawStart - y) / 6));
          c = " .:'"[shade] || " ";
          if ((x + y + (s.turn || 0)) % 17 === 0) c = "·";
        } else if (y > drawEnd) {
          // floor
          const fy = (y - mid) / mid;
          const si = Math.min(SHADE.length - 1, Math.floor(fy * 6));
          c = SHADE[si] || ".";
          if ((x * 3 + y) % 11 === 0) c = "=";
        } else {
          // wall column
          const near = Math.min(1, 1.8 / dist);
          let si = Math.min(SHADE.length - 1, Math.floor(near * (SHADE.length - 1)));
          if (sides[x]) si = Math.max(0, si - 1);
          c = SHADE[si];
          if (hitCh[x] === "+") c = near > 0.55 ? "+" : ":";
          if (hitCh[x] === "~") c = "~";
          // edge highlight
          if (y === drawStart || y === drawEnd) c = "|";
        }
        row += c;
      }
      lines.push(row);
    }

    // Sprite-ish overlays for nearby entities (billboards in center band)
    const vis = s.visible || [];
    for (let y = 0; y < s.height; y++) {
      for (let x = 0; x < s.width; x++) {
        if (!(vis[y] && vis[y][x])) continue;
        const ch = mapAt(s, x, y);
        if (!"itd&*!/[}%JU".includes(ch)) continue;
        if (x === s.player.x && y === s.player.y) continue;
        // transform to camera space
        const relX = x + 0.5 - px;
        const relY = y + 0.5 - py;
        const invDet = 1.0 / (planeX * dirY - dirX * planeY);
        const transformX = invDet * (dirY * relX - dirX * relY);
        const transformY = invDet * (-planeY * relX + planeX * relY);
        if (transformY <= 0.15) continue;
        const spriteScreenX = Math.floor((cols / 2) * (1 + transformX / transformY));
        const spriteH = Math.abs(Math.floor(rows / transformY));
        const drawStartY = Math.max(0, Math.floor(mid - spriteH / 2));
        const drawEndY = Math.min(rows - 1, Math.floor(mid + spriteH / 2));
        const spriteW = Math.max(2, Math.floor(spriteH * 0.45));
        const drawStartX = Math.max(0, spriteScreenX - Math.floor(spriteW / 2));
        const drawEndX = Math.min(cols - 1, spriteScreenX + Math.floor(spriteW / 2));
        for (let sx = drawStartX; sx <= drawEndX; sx++) {
          if (transformY >= depths[sx]) continue;
          for (let sy = drawStartY; sy <= drawEndY; sy++) {
            const row = lines[sy];
            const mark = sx === spriteScreenX ? ch : (sy === drawStartY || sy === drawEndY ? "|" : "*");
            lines[sy] = row.substring(0, sx) + mark + row.substring(sx + 1);
          }
          depths[sx] = transformY;
        }
      }
    }

    // HUD reticle
    const cx = Math.floor(cols / 2);
    const cy = Math.floor(rows / 2);
    if (lines[cy]) {
      const r = lines[cy];
      lines[cy] = r.substring(0, cx - 1) + "[+]" + r.substring(cx + 2);
    }

    fpvEl.textContent = lines.join("\n");
    if (compassEl) {
      const fn = s.player.facing_name || FACING_NAMES[facing] || "?";
      compassEl.textContent = FACING_GLYPH[facing] + " " + fn;
    }
    if (fpvStatus) {
      fpvStatus.textContent = `POS ${s.player.x},${s.player.y} · T${s.turn} · ${
        s.player.has_payload ? "PAYLOAD LOCKED" : "NO PAYLOAD"
      }`;
    }
  }

  // ---- Enhanced ASCII minimap (GTA corner radar — NOT PNG tiles) ----
  function miniClass(ch, visible, explored) {
    if (!visible && !explored) return "m-void";
    if (!visible) return "m-fog";
    if (ch === "@" || "^>v<".includes(ch)) return "m-player";
    if (ch === "i") return "m-enemy-i";
    if (ch === "t") return "m-enemy-t";
    if (ch === "d") return "m-enemy-d";
    if (ch === "&") return "m-npc";
    if ("*!/[}%".includes(ch)) return "m-item";
    if (ch === "J" || ch === "U") return "m-land";
    if (ch === "#") return "m-wall";
    if (ch === "+") return "m-door";
    if (ch === "=") return "m-street";
    if (ch === "~") return "m-water";
    if (ch === ",") return "m-grass";
    return "m-floor";
  }

  function enhanceCell(ch, visible, explored) {
    // 2×2 upscale (2 cols × 2 rows per map cell) — enhanced ASCII radar
    if (!visible && !explored) return ["··", "··"];
    if (!visible) {
      if (ch === "#") return ["▒░", "░▒"];
      if (ch === "+") return ["··", "++"];
      return ["··", "··"];
    }
    const pair = {
      "#": ["██", "██"],
      "+": ["╬╬", "++"],
      ".": ["··", "··"],
      "=": ["══", "──"],
      ",": [",.", ".,"],
      "~": ["≈≈", "≈≈"],
      "J": ["▐█", "J█"],
      "U": ["▐█", "U█"],
      "@": ["@@", "@@"],
      "^": ["▲▲", "││"],
      ">": ["▶▶", "▶▶"],
      "v": ["││", "▼▼"],
      "<": ["◀◀", "◀◀"],
      "&": ["&&", "▓▓"],
      i: ["ii", "▓▓"],
      t: ["tt", "▓▓"],
      d: ["dd", "▓▓"],
      "*": ["**", "**"],
      "!": ["!!", "!!"],
      "/": ["//", "//"],
      "[": ["[[", "[["],
      "}": ["}}", "}}"],
      "%": ["%%", "▓▓"],
    };
    return pair[ch] || [ch + ch, ch + ch];
  }

  function renderMinimap(s) {
    if (!minimapEl || !s) return;
    const px = s.player.x;
    const py = s.player.y;
    const facing = (s.player.facing || 0) % 4;
    const vis = s.visible || [];
    const exp = s.explored || [];
    const x0 = Math.max(0, px - MINI_R);
    const y0 = Math.max(0, py - MINI_R);
    const x1 = Math.min(s.width - 1, px + MINI_R);
    const y1 = Math.min(s.height - 1, py + MINI_R);

    let html = "";
    for (let y = y0; y <= y1; y++) {
      // two enhanced rows per map row
      let top = "";
      let bot = "";
      for (let x = x0; x <= x1; x++) {
        let ch = mapAt(s, x, y);
        const visible = !!(vis[y] && vis[y][x]);
        const explored = !!(exp[y] && exp[y][x]);
        if (x === px && y === py) ch = FACING_GLYPH[facing];
        const [a, b] = enhanceCell(ch, visible, explored);
        const cls = miniClass(ch, visible, explored);
        top += `<span class="${cls}">${escapeHtml(a)}</span>`;
        bot += `<span class="${cls}">${escapeHtml(b)}</span>`;
      }
      html += top + "\n" + bot + "\n";
    }
    minimapEl.innerHTML = html;
  }

  function buildLegend() {
    if (!legendEl) return;
    const items = [
      ["@", "you (facing glyph on radar)"],
      ["#", "wall"],
      [".", "floor"],
      ["+", "door"],
      ["=", "street"],
      ["J", "jackpoint"],
      ["U", "uplink"],
      ["&", "NPC"],
      ["i/t/d", "enemies"],
      ["%", "Payload-Zero"],
    ];
    legendEl.innerHTML = items
      .map(
        ([g, label]) =>
          `<div class="leg"><span class="g">${escapeHtml(g)}</span><span>${escapeHtml(
            label
          )}</span></div>`
      )
      .join("");
  }

  function handleSfx(s) {
    const events = Array.isArray(s.sfx) ? s.sfx.slice() : [];
    if (s.mode === "dead" && lastMode !== "dead" && !events.includes("death")) events.push("death");
    if (s.mode === "won" && lastMode !== "won" && !events.includes("win")) events.push("win");
    lastMode = s.mode;
    Sound.playList(events);
  }

  function handleCutscenes(s) {
    const ids = Array.isArray(s.cutscenes) ? s.cutscenes.slice() : [];
    if (ids.length) CutscenePlayer.enqueue(ids);
  }

  function render(s) {
    handleSfx(s);
    handleCutscenes(s);
    state = s;
    renderFpv(s);
    renderMinimap(s);

    const p = s.player;
    statsEl.innerHTML = `
      <div><strong>${escapeHtml(p.name)}</strong></div>
      <div class="hp">HP ${p.hp}/${p.max_hp}</div>
      <div class="focus">Focus ${p.focus}/${p.max_focus}</div>
      <div>Atk ${p.attack} · Def ${p.defense} · Hack ${p.hack}</div>
      <div>Facing ${escapeHtml(p.facing_name || FACING_NAMES[p.facing] || "?")} · Turn ${s.turn}</div>
      <div>Seed ${s.seed}</div>
      <div class="${p.has_payload ? "ok" : ""}">Payload-Zero: ${
        p.has_payload ? "IN SLEEVE" : "missing"
      }</div>
      <div style="margin-top:0.5rem;color:#6e7681">Quest: ${
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
    logEl.innerHTML = (s.messages || []).map((m) => `<div>${escapeHtml(m)}</div>`).join("");
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

  async function send(action, arg) {
    Sound.unlock();
    const s = await api("/api/action", { action, arg });
    render(s);
  }

  // GTA-like: WASD relative to facing; Q/E or arrows turn
  const KEYMAP = {
    w: "forward",
    ArrowUp: "forward",
    s: "back",
    ArrowDown: "back",
    a: "strafe_left",
    d: "strafe_right",
    q: "turn_left",
    ArrowLeft: "turn_left",
    e: "turn_right",
    ArrowRight: "turn_right",
    // absolute leftovers for hjkl (TUI-parity)
    h: "h",
    j: "j",
    k: "k",
    l: "l",
    g: "g",
    f: "f",
    i: "i",
    r: "r",
    u: "u",
    ".": ".",
    " ": ".",
    "?": "?",
    Escape: "escape",
  };

  window.addEventListener("keydown", (ev) => {
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    Sound.unlock();
    if (IntroPlayer.isActive()) {
      if (ev.key === " " || ev.key === "Escape" || ev.key === "Enter") {
        ev.preventDefault();
        IntroPlayer.skip();
      } else ev.preventDefault();
      return;
    }
    if (!gameplayReady) {
      ev.preventDefault();
      return;
    }
    if (CutscenePlayer.isPlaying()) {
      if (ev.key === " " || ev.key === "Escape" || ev.key === "Enter") {
        ev.preventDefault();
        CutscenePlayer.skip();
      } else ev.preventDefault();
      return;
    }
    if (ev.key === "m" || ev.key === "M") {
      ev.preventDefault();
      Sound.toggleMute();
      return;
    }
    // inventory: e = equip
    if (state && state.mode === "inventory" && (ev.key === "e" || ev.key === "E")) {
      ev.preventDefault();
      send("e");
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
    // space waits unless we want skip — already handled in cutscene
    if (ev.key === " " && state && (state.mode === "dead" || state.mode === "won")) return;
    // Restart after death/win → replay opening cinematic, then new run
    if (action === "r" && state && (state.mode === "dead" || state.mode === "won")) {
      const seed = state.seed != null ? state.seed : null;
      runIntroThenGame({ seed });
      return;
    }
    send(action);
  });

  if (btnMute) {
    btnMute.addEventListener("click", () => {
      Sound.unlock();
      Sound.toggleMute();
    });
  }
  Sound.syncUi();
  ["pointerdown", "keydown", "touchstart"].forEach((evt) => {
    window.addEventListener(evt, () => Sound.unlock(), { once: true, passive: true });
  });

  async function startGameplay(opts) {
    const replaySeed = opts && opts.seed !== undefined ? opts.seed : null;
    gameplayReady = true;
    try {
      const s = await api("/api/new", { seed: replaySeed });
      render(s);
    } catch (err) {
      if (fpvEl) fpvEl.textContent = "Failed to load game: " + err;
    }
  }

  async function runIntroThenGame(opts) {
    gameplayReady = false;
    // Mute gameplay SFX path until intro ends (no /api/new yet)
    await IntroPlayer.play();
    await startGameplay(opts || {});
  }

  async function boot() {
    Sound.preload();
    CutscenePlayer.setPerspective(false);
    buildLegend();
    try {
      const idx = await fetch(CUT_PATH + "index.json").then((r) => r.json());
      (idx.cutscenes || []).forEach((c) => CutscenePlayer.load(c.id).catch(() => {}));
    } catch (err) {
      console.warn("cutscene index missing", err);
    }
    await runIntroThenGame({ seed: null });
  }

  if (btnSkipIntro) {
    btnSkipIntro.addEventListener("click", () => {
      Sound.unlock();
      IntroPlayer.skip();
    });
  }
  if (btnReplayIntro) {
    btnReplayIntro.addEventListener("click", async () => {
      Sound.unlock();
      Sound.play("click");
      const seed = state && state.seed != null ? state.seed : null;
      await runIntroThenGame({ seed });
    });
  }

  boot();
})();
