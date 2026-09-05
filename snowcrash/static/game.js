(() => {
  const fpvEl = document.getElementById("fpv");
  const fpvCanvas = document.getElementById("fpv-canvas");
  const fpvStage = document.getElementById("fpv-stage");
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
  const cutCanvas = document.getElementById("cut-canvas");
  const fpvStatus = document.getElementById("fpv-status");
  const introEl = document.getElementById("intro");
  const introCanvas = document.getElementById("intro-canvas");
  const introChapterEl = document.getElementById("intro-chapter");
  const btnSkipIntro = document.getElementById("btn-skip-intro");
  const btnReplayIntro = document.getElementById("btn-replay-intro");
  const appEl = document.getElementById("app");
  const nameGate = document.getElementById("name-gate");
  const nameForm = document.getElementById("name-form");
  const displayNameEl = document.getElementById("display-name");
  const playerListEl = document.getElementById("player-list");
  const chatLogEl = document.getElementById("chat-log");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const netHud = document.getElementById("net-hud");

  let state = null;
  let invMode = false;
  let lastMode = null;
  let cutscenePlaying = false;
  let gameplayReady = false;
  let introActive = false;
  let displayName = "";
  let myId = null;
  let chatFocused = false;
  let lastPingMs = null;

  const SFX_PATH = "/static/sfx/";
  const CUT_PATH = "/static/cutscenes/";
  const SFX_IDS = [
    "step", "bump", "melee", "hurt", "kill", "pulse", "pickup",
    "use", "talk", "door", "win", "death", "click",
  ];
  const FACING_NAMES = ["N", "E", "S", "W"];
  const FACING_GLYPH = ["^", ">", "v", "<"];
  const WALL_CHARS = "#~";
  const SCENE_W = 480;
  const SCENE_H = 270;
  const MINI_R = 10; // radar radius in map cells
  const SHADE = " .:-=+*#%@";
  /** Filled by FpvEngine below — avoids TDZ with CutscenePlayer. */
  const FpvBridge = { pause() {}, resume() {}, render(_s) {}, kick() {} };

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

  // ---- Cutscenes (jack-in intensives via shared video→ASCII) ----
  const CutscenePlayer = (() => {
    const cache = {};
    const mp4Probe = {};
    let timer = null;
    let queue = [];
    let cutAscii = null;
    let packAbort = false;

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

    function ensureCutAscii() {
      if (cutAscii || !cutCanvas || typeof VideoAsciiCanvas === "undefined") return cutAscii;
      const cols = Math.min(160, Math.max(100, Math.floor((cutCanvas.parentElement?.clientWidth || 800) / 6)));
      cutAscii = new VideoAsciiCanvas(cutCanvas, {
        cols,
        brightness: 1.2,
        contrast: 1.12,
        autoColor: true,
        bg: "#05080c",
        fit: true,
      });
      return cutAscii;
    }

    async function load(id) {
      if (cache[id]) return cache[id];
      const res = await fetch(CUT_PATH + id + ".json");
      if (!res.ok) throw new Error("cutscene missing: " + id);
      cache[id] = await res.json();
      return cache[id];
    }

    async function hasMp4(id) {
      if (id in mp4Probe) return mp4Probe[id];
      try {
        const res = await fetch(CUT_PATH + id + ".mp4", { method: "HEAD" });
        mp4Probe[id] = res.ok;
      } catch (_) {
        mp4Probe[id] = false;
      }
      return mp4Probe[id];
    }

    function hide() {
      packAbort = true;
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      if (cutAscii) cutAscii.stop();
      cutscenePlaying = false;
      if (cutsceneEl) cutsceneEl.classList.add("hidden");
      setPerspective(false);
      // resume live FPV loop
      FpvBridge.resume();
    }

    function finishOne() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      if (cutAscii) {
        try { cutAscii.pause(); } catch (_) {}
      }
      if (queue.length) {
        playNext();
        return;
      }
      hide();
    }

    /** Paint a JSON ASCII frame onto an offscreen canvas with neon colors, then ASCII-sample. */
    function renderJsonFrame(engine, frameText) {
      const lines = String(frameText || "").split("\n");
      const rows = Math.max(1, lines.length);
      const cols = Math.max(1, ...lines.map((l) => l.length));
      const off = document.createElement("canvas");
      off.width = cols * 4;
      off.height = rows * 6;
      const ctx = off.getContext("2d", { alpha: false });
      ctx.fillStyle = "#05080c";
      ctx.fillRect(0, 0, off.width, off.height);
      for (let y = 0; y < rows; y++) {
        const line = lines[y] || "";
        for (let x = 0; x < cols; x++) {
          const ch = line[x] || " ";
          if (ch === " ") continue;
          const code = ch.charCodeAt(0);
          const dens = Math.min(1, (code - 32) / 90);
          let r, g, b;
          if ("@#%".includes(ch)) {
            r = 255; g = 42; b = 109;
          } else if ("=+~".includes(ch)) {
            r = 57; g = 197; b = 207;
          } else if (";:".includes(ch)) {
            r = 40; g = 160; b = 180;
          } else if ("*+".includes(ch)) {
            r = 240; g = 180; b = 41;
          } else {
            r = 30 + dens * 180;
            g = 180 + dens * 40;
            b = 200 + dens * 40;
          }
          const pulse = 0.85 + 0.15 * Math.sin((x + y) * 0.4);
          ctx.fillStyle = `rgb(${(r * pulse) | 0},${(g * pulse) | 0},${(b * pulse) | 0})`;
          ctx.fillRect(x * 4, y * 6, 4, 6);
        }
      }
      // scanline tint
      ctx.fillStyle = "rgba(0,0,0,0.18)";
      for (let y = 0; y < off.height; y += 3) ctx.fillRect(0, y, off.width, 1);
      engine.renderFromCanvas(off);
    }

    function playJsonPack(pack) {
      cutscenePlaying = true;
      packAbort = false;
      const title = pack.title || ("1ST PERSON — " + (pack.id || "").toUpperCase());
      setPerspective(true, title);
      if (cutTitleEl) cutTitleEl.textContent = title;
      if (cutsceneEl) cutsceneEl.classList.remove("hidden");
      FpvBridge.pause();
      if (cutAscii) {
        try { cutAscii.stop(); } catch (_) {}
      }

      const frames = pack.frames || [];
      if (!frames.length) {
        finishOne();
        return;
      }
      const engine = ensureCutAscii();
      let i = 0;
      if (engine) {
        engine.setCols(Math.min(160, Math.max(100, Math.floor((cutCanvas.parentElement?.clientWidth || 800) / 6))));
        renderJsonFrame(engine, frames[0]);
      } else if (cutFramesEl) {
        cutFramesEl.classList.remove("hidden");
        cutFramesEl.textContent = frames[0];
      }
      const fps = pack.fps || 10;
      timer = setInterval(() => {
        if (packAbort) return;
        i += 1;
        if (i >= frames.length) {
          finishOne();
          return;
        }
        if (engine) renderJsonFrame(engine, frames[i]);
        else if (cutFramesEl) cutFramesEl.textContent = frames[i];
      }, Math.max(40, Math.floor(1000 / fps)));
    }

    async function playVideoPack(id, pack) {
      cutscenePlaying = true;
      packAbort = false;
      const title = pack.title || ("1ST PERSON — " + (pack.id || "").toUpperCase());
      setPerspective(true, title);
      if (cutTitleEl) cutTitleEl.textContent = title;
      if (cutsceneEl) cutsceneEl.classList.remove("hidden");
      FpvBridge.pause();
      if (cutAscii) {
        try { cutAscii.stop(); } catch (_) {}
      }

      const engine = ensureCutAscii();
      if (!engine) {
        playJsonPack(pack);
        return;
      }
      try {
        await engine.load(CUT_PATH + id + ".mp4");
        if (packAbort) return;
        engine.setCols(Math.min(160, Math.max(100, Math.floor((cutCanvas.parentElement?.clientWidth || 800) / 6))));
        await engine.play({
          onEnded: () => {
            if (!packAbort) finishOne();
          },
        });
      } catch (err) {
        console.warn("cutscene mp4 failed, falling back to JSON", id, err);
        playJsonPack(pack);
      }
    }

    async function playNext() {
      const id = queue.shift();
      if (!id) {
        finishOne();
        return;
      }
      try {
        const pack = await load(id);
        // Prefer MP4 through shared VideoAsciiCanvas; JSON packs remain as fallback.
        if (await hasMp4(id)) {
          await playVideoPack(id, pack);
        } else {
          playJsonPack(pack);
        }
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
        '<p class="intro-sub">Fractured franchise cities</p>',
    },
    {
      at: 4.0,
      html:
        '<p class="intro-kicker">COURIER DOSSIER</p>' +
        '<h1 class="intro-title" style="letter-spacing:0.22em;font-size:clamp(1.4rem,4vw,2.2rem)">RIN VALE</h1>' +
        '<p class="intro-body">Freelance Metaverse courier and street hacker. ' +
        "You ride the neon seams between meatspace and the Layer — paid to move what shouldn't move.</p>",
    },
    {
      at: 8.5,
      html:
        '<p class="intro-kicker">PARALLEL LAYER</p>' +
        '<h1 class="intro-title" style="letter-spacing:0.16em;font-size:clamp(1.2rem,3.5vw,1.9rem)">THE METAVERSE</h1>' +
        '<p class="intro-body">Above the asphalt: a social overlay of jackpoints, avatars, and uplink nodes. ' +
        "Street deals echo upstairs. What you speak can rewrite code — and flesh.</p>",
    },
    {
      at: 13.0,
      html:
        '<p class="intro-kicker">THREAT VECTOR</p>' +
        '<h1 class="intro-title" style="letter-spacing:0.16em;font-size:clamp(1.2rem,3.5vw,1.9rem)">PAYLOAD-ZERO</h1>' +
        '<p class="intro-body">Neurolinguistic malware in a Faraday sleeve. ' +
        "Infected avatars hunt it. Counter-incantation at the uplink fractures the Babel stack.</p>",
    },
    {
      at: 17.5,
      html:
        '<p class="intro-kicker">BROADCAST</p>' +
        '<h1 class="intro-title" style="letter-spacing:0.14em;font-size:clamp(1.1rem,3.2vw,1.7rem)">THE FLOTILLA</h1>' +
        '<p class="intro-body">Cable Baron Cassian Vox pushes a constellation of refugee signal-ships. ' +
        "Propaganda rides the same band as the desperate. Listen carefully.</p>",
    },
    {
      at: 21.5,
      html:
        '<p class="intro-kicker">JACK IN</p>' +
        '<h1 class="intro-title">SNOWCRASH</h1>' +
        '<p class="intro-sub">Enter the streets</p>' +
        '<p class="intro-body">WASD move · Q/E turn · recover Payload-Zero · punch the uplink · /wish to petition.</p>',
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

  const Net = (() => {
    let ws = null;
    let joined = false;
    let reconnectTimer = null;
    let pingTimer = null;
    let wantOpen = false;

    function setHud(text, cls) {
      if (!netHud) return;
      netHud.textContent = text;
      netHud.className = "net-hud" + (cls ? " " + cls : "");
    }

    function wsUrl() {
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      return proto + "//" + location.host + "/ws";
    }

    function send(obj) {
      if (!ws || ws.readyState !== 1) return false;
      ws.send(JSON.stringify(obj));
      return true;
    }

    function handleMessage(msg) {
      if (!msg || !msg.type) return;
      if (msg.type === "welcome") {
        myId = msg.you;
        joined = true;
        setHud("ONLINE · sync", "");
        if (msg.state) render(msg.state);
        return;
      }
      if (msg.type === "snapshot" && msg.state) {
        render(msg.state);
        return;
      }
      if (msg.type === "pong") {
        if (typeof msg.t === "number") {
          lastPingMs = Math.max(0, Math.round(performance.now() - msg.t));
          const n = (state && state.online_count) || 0;
          setHud((lastPingMs != null ? lastPingMs + "ms · " : "") + n + " online", "");
        }
        return;
      }
      if (msg.type === "error") {
        console.warn("ws error", msg.error);
      }
    }

    function startPing() {
      stopPing();
      pingTimer = setInterval(() => {
        send({ type: "ping", t: performance.now() });
      }, 2500);
    }
    function stopPing() {
      if (pingTimer) clearInterval(pingTimer);
      pingTimer = null;
    }

    function connect(name) {
      wantOpen = true;
      displayName = name;
      return new Promise((resolve, reject) => {
        try {
          if (ws) {
            try { ws.close(); } catch (_) {}
          }
          setHud("connecting…", "warn");
          ws = new WebSocket(wsUrl());
          ws.onopen = () => {
            send({ type: "join", name, id: myId || undefined });
            startPing();
          };
          ws.onmessage = (ev) => {
            let msg;
            try { msg = JSON.parse(ev.data); } catch (_) { return; }
            const first = !joined;
            handleMessage(msg);
            if (first && msg.type === "welcome") resolve(msg);
          };
          ws.onclose = () => {
            joined = false;
            stopPing();
            setHud("reconnecting…", "warn");
            if (!wantOpen) return;
            if (reconnectTimer) clearTimeout(reconnectTimer);
            reconnectTimer = setTimeout(() => connect(displayName).catch(() => {}), 1200);
          };
          ws.onerror = () => {
            setHud("socket error", "err");
          };
        } catch (err) {
          reject(err);
        }
      });
    }

    function action(action, arg) {
      return send({ type: "action", action, arg: arg == null ? null : arg });
    }
    function chat(text) {
      return send({ type: "chat", text });
    }
    function disconnect() {
      wantOpen = false;
      stopPing();
      if (ws) try { ws.close(); } catch (_) {}
    }

    return { connect, action, chat, disconnect, send, isJoined: () => joined };
  })();

  async function api(path, body) {
    // Legacy HTTP fallback (bootstrap only)
    const opts = body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: displayName || "Courier", ...body }),
        }
      : {};
    const res = await fetch(path, opts);
    return res.json();
  }

  function listLen(s) {
    return (s && s.online_count != null) ? s.online_count : ((s && s.players) || []).length;
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

  // ---- Live FPV: offscreen neon scene → shared colored ASCII canvas ----
  const FpvEngine = (() => {
    const scene = document.createElement("canvas");
    scene.width = SCENE_W;
    scene.height = SCENE_H;
    const sctx = scene.getContext("2d", { alpha: false });

    let ascii = null;
    let running = false;
    let paused = false;
    let noiseT = 0;
    let lastState = null;
    let rafId = 0;

    const ENTITY_RGB = {
      i: [255, 42, 109],
      t: [255, 123, 114],
      d: [121, 192, 255],
      "&": [210, 168, 255],
      "*": [240, 180, 41],
      "!": [240, 180, 41],
      "/": [240, 180, 41],
      "[": [240, 180, 41],
      "}": [240, 180, 41],
      "%": [61, 214, 140],
      J: [61, 214, 140],
      U: [57, 197, 207],
      "+": [240, 180, 41],
    };

    function ensureAscii() {
      if (ascii || !fpvCanvas || typeof VideoAsciiCanvas === "undefined") return ascii;
      const pw = (fpvStage && fpvStage.clientWidth) || 800;
      const cols = Math.min(180, Math.max(110, Math.floor(pw / 5.5)));
      ascii = new VideoAsciiCanvas(fpvCanvas, {
        cols,
        brightness: 1.18,
        contrast: 1.12,
        autoColor: true,
        bg: "#05080c",
        fit: true,
      });
      ascii.setSourceCanvas(scene);
      return ascii;
    }

    function resizeAscii() {
      const eng = ensureAscii();
      if (!eng || !fpvStage) return;
      const cols = Math.min(180, Math.max(110, Math.floor(fpvStage.clientWidth / 5.5)));
      eng.setCols(cols);
      eng.setSourceCanvas(scene);
    }

    function wallColor(ch, side, dist) {
      const near = Math.max(0.15, Math.min(1, 1.6 / Math.max(0.2, dist)));
      let r, g, b;
      if (ch === "+") {
        r = 240; g = 180; b = 41;
      } else if (ch === "~") {
        r = 42; g = 111; b = 158;
      } else {
        r = 40; g = 190; b = 205;
      }
      if (side) {
        r *= 0.72; g *= 0.72; b *= 0.78;
      }
      r = Math.min(255, r * near * 1.15);
      g = Math.min(255, g * near * 1.15);
      b = Math.min(255, b * near * 1.2);
      return [r | 0, g | 0, b | 0];
    }

    function paintScene(s, t) {
      if (!s || !sctx) return;
      const W = SCENE_W;
      const H = SCENE_H;
      const px = s.player.x + 0.5;
      const py = s.player.y + 0.5;
      const facing = (s.player.facing || 0) % 4;
      const dirX = [0, 1, 0, -1][facing];
      const dirY = [-1, 0, 1, 0][facing];
      const planeX = -dirY * 0.66;
      const planeY = dirX * 0.66;
      const mid = H / 2;
      const plane = (s.plane || (s.player && s.player.plane) || "STREET").toUpperCase();

      const ceil = sctx.createLinearGradient(0, 0, 0, mid);
      if (plane === "AIR") {
        ceil.addColorStop(0, "#1a3a5c");
        ceil.addColorStop(1, "#3d7ea6");
      } else if (plane === "UNDER") {
        ceil.addColorStop(0, "#050308");
        ceil.addColorStop(1, "#1a0a12");
      } else {
        ceil.addColorStop(0, "#060a14");
        ceil.addColorStop(1, "#0a1528");
      }
      sctx.fillStyle = ceil;
      sctx.fillRect(0, 0, W, mid);

      const floor = sctx.createLinearGradient(0, mid, 0, H);
      if (plane === "AIR") {
        floor.addColorStop(0, "#1a2838");
        floor.addColorStop(1, "#0c1824");
      } else if (plane === "UNDER") {
        floor.addColorStop(0, "#12080c");
        floor.addColorStop(1, "#080406");
      } else {
        floor.addColorStop(0, "#0a1018");
        floor.addColorStop(1, "#121c28");
      }
      sctx.fillStyle = floor;
      sctx.fillRect(0, mid, W, H - mid);

      sctx.strokeStyle = "rgba(57,197,207,0.08)";
      sctx.lineWidth = 1;
      for (let i = 1; i <= 8; i++) {
        const y = mid + (i * i * (H - mid)) / 80;
        sctx.beginPath();
        sctx.moveTo(0, y);
        sctx.lineTo(W, y);
        sctx.stroke();
      }

      const depths = new Float32Array(W);

      for (let col = 0; col < W; col++) {
        const camX = (2 * col) / W - 1;
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

        const lineH = Math.min(H, Math.floor(H / perp));
        const drawStart = Math.floor(mid - lineH / 2);
        const drawEnd = Math.floor(mid + lineH / 2);
        const rgb = wallColor(ch, side, perp);
        sctx.fillStyle = "rgb(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + ")";
        sctx.fillRect(col, drawStart, 1, Math.max(1, drawEnd - drawStart));
        sctx.fillStyle = "rgba(232,251,255," + Math.min(0.55, 0.35 / perp) + ")";
        sctx.fillRect(col, drawStart, 1, 1);
        sctx.fillRect(col, drawEnd, 1, 1);
      }

      function hexToRgb(hex) {
        if (!hex || hex[0] !== "#" || hex.length < 7) return [255, 42, 109];
        return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
      }
      function drawBillboard(x, y, ch, rgb, label) {
        const relX = x + 0.5 - px;
        const relY = y + 0.5 - py;
        const invDet = 1.0 / (planeX * dirY - dirX * planeY);
        const transformX = invDet * (dirY * relX - dirX * relY);
        const transformY = invDet * (-planeY * relX + planeX * relY);
        if (transformY <= 0.15) return;
        const spriteScreenX = Math.floor((W / 2) * (1 + transformX / transformY));
        const spriteH = Math.abs(Math.floor(H / transformY));
        const drawStartY = Math.max(0, Math.floor(mid - spriteH / 2));
        const drawEndY = Math.min(H - 1, Math.floor(mid + spriteH / 2));
        const spriteW = Math.max(4, Math.floor(spriteH * 0.4));
        const drawStartX = Math.max(0, spriteScreenX - Math.floor(spriteW / 2));
        const drawEndX = Math.min(W - 1, spriteScreenX + Math.floor(spriteW / 2));
        for (let sx = drawStartX; sx <= drawEndX; sx++) {
          if (transformY >= depths[sx]) continue;
          const edge = sx === drawStartX || sx === drawEndX;
          const glow = edge ? 1.25 : 1;
          const rr = Math.min(255, rgb[0] * glow);
          const gg = Math.min(255, rgb[1] * glow);
          const bb = Math.min(255, rgb[2] * glow);
          sctx.fillStyle = "rgb(" + (rr | 0) + "," + (gg | 0) + "," + (bb | 0) + ")";
          sctx.fillRect(sx, drawStartY, 1, drawEndY - drawStartY + 1);
          sctx.fillStyle = "rgba(255,255,255,0.35)";
          sctx.fillRect(sx, drawStartY, 1, 2);
          depths[sx] = transformY;
        }
        sctx.fillStyle = "#e8fbff";
        sctx.font = Math.max(10, Math.floor(spriteH * 0.35)) + "px monospace";
        sctx.textAlign = "center";
        sctx.fillText(ch, spriteScreenX, mid + 4);
        if (label) {
          sctx.fillStyle = "rgba(232,251,255,0.9)";
          sctx.font = Math.max(8, Math.floor(spriteH * 0.18)) + "px monospace";
          sctx.fillText(label, spriteScreenX, Math.max(12, drawStartY - 2));
        }
      }

      const vis = s.visible || [];
      // Local FOV window only — full-map scan is too heavy on MMORPG sizes
      const pr = 10;
      const yLo = Math.max(0, s.player.y - pr);
      const yHi = Math.min(s.height - 1, s.player.y + pr);
      const xLo = Math.max(0, s.player.x - pr);
      const xHi = Math.min(s.width - 1, s.player.x + pr);
      for (let y = yLo; y <= yHi; y++) {
        for (let x = xLo; x <= xHi; x++) {
          if (!(vis[y] && vis[y][x])) continue;
          const ch = mapAt(s, x, y);
          if (!"itd&*!/[}%JU".includes(ch)) continue;
          if (x === s.player.x && y === s.player.y) continue;
          const rgb = ENTITY_RGB[ch] || [57, 197, 207];
          drawBillboard(x, y, ch, rgb, null);
        }
      }
      // Other couriers as distinct billboards (even if glyph overwrites map cell)
      (s.players || []).forEach((op) => {
        if (!op || op.id === s.you || op.id === (s.player && s.player.id)) return;
        if (!op.alive || op.x < 0) return;
        if (!(vis[op.y] && vis[op.y][op.x])) return;
        const rgb = hexToRgb(op.color);
        drawBillboard(op.x, op.y, op.glyph || "A", rgb, op.name || "");
      });

      const cx = (W / 2) | 0;
      const cy = (H / 2) | 0;
      sctx.strokeStyle = "rgba(57,197,207,0.85)";
      sctx.lineWidth = 1;
      sctx.beginPath();
      sctx.moveTo(cx - 10, cy);
      sctx.lineTo(cx - 3, cy);
      sctx.moveTo(cx + 3, cy);
      sctx.lineTo(cx + 10, cy);
      sctx.moveTo(cx, cy - 8);
      sctx.lineTo(cx, cy - 3);
      sctx.moveTo(cx, cy + 3);
      sctx.lineTo(cx, cy + 8);
      sctx.stroke();
      sctx.fillStyle = "rgba(255,42,109,0.9)";
      sctx.fillRect(cx - 1, cy - 1, 3, 3);

      const turn = s.turn || 0;
      sctx.fillStyle = "rgba(0,0,0,0.12)";
      const phase = ((t * 60) | 0) % 3;
      for (let y = phase; y < H; y += 3) {
        sctx.fillRect(0, y, W, 1);
      }
      sctx.fillStyle = "rgba(57,197,207,0.08)";
      for (let n = 0; n < 40; n++) {
        const nx = (n * 97 + turn * 13 + ((t * 40) | 0)) % W;
        const ny = (n * 53 + turn * 7 + ((t * 25) | 0)) % H;
        sctx.fillRect(nx, ny, 2, 1);
      }
      const vig = sctx.createRadialGradient(cx, cy, H * 0.2, cx, cy, H * 0.75);
      vig.addColorStop(0, "rgba(0,0,0,0)");
      vig.addColorStop(1, "rgba(0,0,0,0.45)");
      sctx.fillStyle = vig;
      sctx.fillRect(0, 0, W, H);
    }

    function pushAscii() {
      const eng = ensureAscii();
      if (!eng) return;
      eng.renderFromCanvas(scene);
    }

    function updateHud(s) {
      if (!s) return;
      const facing = (s.player.facing || 0) % 4;
      if (compassEl) {
        const fn = s.player.facing_name || FACING_NAMES[facing] || "?";
        compassEl.textContent = FACING_GLYPH[facing] + " " + fn;
      }
      if (fpvStatus) {
        fpvStatus.textContent =
          "POS " +
          s.player.x +
          "," +
          s.player.y +
          " · T" +
          s.turn +
          " · " +
          (s.player.has_payload ? "PAYLOAD LOCKED" : "NO PAYLOAD");
      }
    }

    function render(s) {
      lastState = s;
      if (!s) return;
      paintScene(s, noiseT);
      pushAscii();
      updateHud(s);
    }

    function loop(ts) {
      if (!running) return;
      rafId = requestAnimationFrame(loop);
      if (paused || !lastState) return;
      noiseT = (ts || 0) / 1000;
      // idle refresh ~12fps for scanlines/noise without burning CPU
      if (((ts / 80) | 0) === ((noiseT * 12) | 0) || true) {
        // throttle: only repaint every ~80ms
      }
      if (!loop._last || ts - loop._last > 80) {
        loop._last = ts;
        paintScene(lastState, noiseT);
        pushAscii();
      }
    }

    function start() {
      ensureAscii();
      resizeAscii();
      running = true;
      paused = false;
      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(loop);
    }

    function pause() {
      paused = true;
    }

    function resume() {
      paused = false;
      if (lastState) render(lastState);
    }

    function stop() {
      running = false;
      if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = 0;
      }
      if (ascii) ascii.stop();
    }

    function kick() {
      // force a redraw after layout changes
      resizeAscii();
      if (lastState) render(lastState);
    }

    // wire bridge for CutscenePlayer
    FpvBridge.pause = pause;
    FpvBridge.resume = resume;
    FpvBridge.render = render;
    FpvBridge.kick = kick;

    window.addEventListener("resize", () => {
      if (!running) return;
      kick();
    });

    return { start, stop, pause, resume, render, kick, scene };
  })();

  function renderFpv(s) {
    if (!s) return;
    FpvEngine.render(s);
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
    if (pair[ch]) return pair[ch];
    if (ch && ch.length === 1 && /[A-Z0-9]/.test(ch)) return [ch + ch, "▓▓"];
    return pair[ch] || [ch + ch, ch + ch];
  }

  function renderMinimap(s) {
    if (!minimapEl || !s) return;
    const px = s.player.x;
    const py = s.player.y;
    const facing = (s.player.facing || 0) % 4;
    const myZ = s.player.z != null ? s.player.z : (s.z != null ? s.z : 0);
    const planeName = s.plane || s.player.plane || "STREET";
    const miniChrome = document.querySelector("#minimap-wrap .mini-chrome span:last-child");
    if (miniChrome) miniChrome.textContent = planeName + " · Z" + myZ;
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
        let otherColor = null;
        if (!(x === px && y === py) && s.players) {
          for (let i = 0; i < s.players.length; i++) {
            const op = s.players[i];
            if (!op || !op.alive || op.x !== x || op.y !== y || op.id === s.you) continue;
            const oz = op.z != null ? op.z : 0;
            if (oz === myZ) {
              ch = op.glyph || "A";
              otherColor = op.color || "#ff2a6d";
            } else {
              ch = "·";
              otherColor = "rgba(200,200,220,0.35)";
            }
            break;
          }
        }
        const [a, b] = enhanceCell(ch, visible, explored);
        let cls = miniClass(ch, visible, explored);
        if (otherColor) cls = "m-other";
        const style = otherColor ? ' style="color:' + otherColor + '"' : "";
        top += `<span class="${cls}"${style}>${escapeHtml(a)}</span>`;
        bot += `<span class="${cls}"${style}>${escapeHtml(b)}</span>`;
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
      ["A-Z", "other couriers"],
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
    myId = s.you || myId;
    statsEl.innerHTML = `
      <div><strong>${escapeHtml(p.name)}</strong> <span style="color:${escapeHtml(p.color || "#39c5cf")}">[${escapeHtml(p.glyph || "@")}]</span></div>
      <div class="hp">HP ${p.hp}/${p.max_hp}</div>
      <div class="focus">Focus ${p.focus}/${p.max_focus}</div>
      <div>Atk ${p.attack} · Def ${p.defense} · Hack ${p.hack}</div>
      <div>Facing ${escapeHtml(p.facing_name || FACING_NAMES[p.facing] || "?")} · Plane ${escapeHtml(s.plane || p.plane || "STREET")} (z${p.z != null ? p.z : (s.z != null ? s.z : 0)}) · Tick ${s.tick != null ? s.tick : s.turn}</div>
      <div>Seed ${s.seed} · ${s.online_count != null ? s.online_count : (s.players || []).length} online</div>
      <div class="${p.has_payload ? "ok" : ""}">Payload-Zero: ${
        p.has_payload ? "IN SLEEVE (yours)" : "missing"
      }</div>
      <div style="margin-top:0.5rem;color:#6e7681">Quest: ${
        Object.keys(s.quest_flags || {}).join(", ") || "—"
      }</div>
    `;
    if (playerListEl) {
      const list = s.players || [];
      playerListEl.innerHTML = list
        .map((op) => {
          const you = op.id === s.you;
          return `<li><span class="pglyph" style="color:${escapeHtml(op.color || "#fff")}">${escapeHtml(
            op.glyph || "?"
          )}</span><span>${escapeHtml(op.name)}${you ? ' <span class="you-tag">YOU</span>' : ""}${
            op.has_payload ? " · %" : ""
          }${op.won ? " · WIN" : ""}</span></li>`;
        })
        .join("");
    }
    if (chatLogEl && Array.isArray(s.chat)) {
      chatLogEl.innerHTML = s.chat
        .map((c) => {
          if (c.kind === "system") {
            return `<div class="chat-sys">* ${escapeHtml(c.text)}</div>`;
          }
          return `<div class="chat-say"><span class="cn">${escapeHtml(c.name)}</span>: ${escapeHtml(
            c.text
          )}</div>`;
        })
        .join("");
      chatLogEl.scrollTop = chatLogEl.scrollHeight;
    }
    if (netHud && lastPingMs != null) {
      netHud.textContent = lastPingMs + "ms · " + (s.online_count || listLen(s)) + " online";
    }
    invEl.innerHTML = "";
    (s.inventory || []).forEach((it, i) => {
      const li = document.createElement("li");
      li.textContent = `${i}: ${it.glyph} ${it.name}`;
      if (it.equipped) li.classList.add("equipped");
      if (it.kind === "wish") li.classList.add("wish");
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
      overlay.innerHTML = `<div class="box banner">YOU WIN<br/><span style="font-size:0.85rem;color:#c9d1d9">Personal quest done. <kbd>r</kbd> respawn</span></div>`;
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
    if (Net.isJoined()) {
      Net.action(action, arg);
      return;
    }
    const s = await api("/api/action", { action, arg });
    render(s);
  }

  // 8-way relative (WASD + chords) · Q/E turn · t/b/[ /] plane shift
  const KEYMAP = {
    q: "turn_left",
    ArrowLeft: "turn_left",
    e: "turn_right",
    ArrowRight: "turn_right",
    g: "g",
    f: "f",
    i: "i",
    r: "r",
    u: "u",
    ".": ".",
    " ": ".",
    "?": "?",
    Escape: "escape",
    t: "plane_up",
    "[": "plane_up",
    b: "plane_down",
    "]": "plane_down",
    h: "w_abs",
    j: "s_abs",
    k: "n_abs",
    l: "e_abs",
    y: "nw",
    // note: letter n is SE absolute — avoid during chat; gameplay ok
  };

  const NUMPAD_8 = {
    8: "n",
    9: "ne",
    6: "e",
    3: "se",
    2: "s",
    1: "sw",
    4: "w",
    7: "nw",
    5: ".",
  };

  const moveKeysHeld = new Set();

  function normalizeMoveKey(key) {
    if (key === "ArrowUp") return "w";
    if (key === "ArrowDown") return "s";
    return key.length === 1 ? key.toLowerCase() : key;
  }

  function chordMoveAction() {
    const w = moveKeysHeld.has("w");
    const a = moveKeysHeld.has("a");
    const s = moveKeysHeld.has("s");
    const d = moveKeysHeld.has("d");
    if (w && a && !s && !d) return "forward_left";
    if (w && d && !s && !a) return "forward_right";
    if (s && a && !w && !d) return "back_left";
    if (s && d && !w && !a) return "back_right";
    if (w && !s) return "forward";
    if (s && !w) return "back";
    if (a && !d) return "strafe_left";
    if (d && !a) return "strafe_right";
    return null;
  }

  window.addEventListener("keyup", (ev) => {
    const nk = normalizeMoveKey(ev.key);
    if (nk === "w" || nk === "a" || nk === "s" || nk === "d") moveKeysHeld.delete(nk);
  });
  window.addEventListener("blur", () => moveKeysHeld.clear());

  window.addEventListener("keydown", (ev) => {
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    // Never steal keys from login / chat / any text field
    const tEl = ev.target;
    const tag = (tEl && tEl.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || (tEl && tEl.isContentEditable)) {
      return;
    }
    if (nameGate && !nameGate.classList.contains("hidden")) {
      return;
    }
    Sound.unlock();
    if (chatFocused || (chatInput && document.activeElement === chatInput)) {
      if (ev.key === "Escape") {
        chatInput.blur();
        chatFocused = false;
        ev.preventDefault();
      }
      return;
    }
    if (ev.key === "Enter" && gameplayReady && !CutscenePlayer.isPlaying() && !IntroPlayer.isActive()) {
      ev.preventDefault();
      if (chatInput) {
        chatInput.focus();
        chatFocused = true;
      }
      return;
    }
    if (IntroPlayer.isActive()) {
      if (ev.key === " " || ev.key === "Escape" || ev.key === "Enter") {
        ev.preventDefault();
        IntroPlayer.skip();
      } else ev.preventDefault();
      return;
    }
    if (!gameplayReady) {
      // Name gate / pre-game: do not preventDefault (blocks typing)
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
    if (state && state.mode === "inventory" && (ev.key === "e" || ev.key === "E")) {
      ev.preventDefault();
      send("e");
      return;
    }
    if (ev.key === "PageUp") {
      ev.preventDefault();
      if (!(state && state.mode === "inventory")) send("plane_up");
      return;
    }
    if (ev.key === "PageDown") {
      ev.preventDefault();
      if (!(state && state.mode === "inventory")) send("plane_down");
      return;
    }
    if (ev.code && ev.code.startsWith("Numpad")) {
      const digit = ev.code.replace("Numpad", "");
      if (NUMPAD_8[digit]) {
        ev.preventDefault();
        send(NUMPAD_8[digit]);
        return;
      }
    }

    const nk = normalizeMoveKey(ev.key);
    if (nk === "w" || nk === "a" || nk === "s" || nk === "d") {
      moveKeysHeld.add(nk);
      const moveAct = chordMoveAction();
      if (moveAct) {
        ev.preventDefault();
        if (state && state.mode === "help") {
          send("escape");
          return;
        }
        send(moveAct);
      }
      return;
    }

    const action = KEYMAP[ev.key] || KEYMAP[nk];
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
    if (ev.key === " " && state && (state.mode === "dead" || state.mode === "won")) return;
    if (action === "r" && state && (state.mode === "dead" || state.mode === "won")) {
      const seed = state.seed != null ? state.seed : null;
      runIntroThenGame({ seed });
      return;
    }
    if ((action === "plane_down" || action === "plane_up") && state && state.mode === "inventory") {
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
    gameplayReady = true;
    FpvEngine.start();
    try {
      await Net.connect(displayName);
      FpvEngine.kick();
    } catch (err) {
      console.error("Failed to join world:", err);
      if (fpvStatus) fpvStatus.textContent = "Failed to join world";
      // HTTP fallback join
      try {
        const s = await api("/api/new", { name: displayName });
        render(s);
      } catch (e2) {
        console.error(e2);
      }
    }
  }

  async function runIntroThenGame(opts) {
    gameplayReady = false;
    FpvEngine.pause();
    if (introEl) introEl.classList.remove("hidden");
    await IntroPlayer.play();
    if (introEl) introEl.classList.add("hidden");
    await startGameplay(opts || {});
  }

  function resolveNameFromUrl() {
    try {
      const u = new URL(location.href);
      const n = u.searchParams.get("name");
      if (n && n.trim()) return n.trim().slice(0, 24);
    } catch (_) {}
    return "";
  }

  async function beginWithName(name) {
    displayName = (name || "Courier").trim().slice(0, 24) || "Courier";
    try {
      localStorage.setItem("snowcrash_name", displayName);
    } catch (_) {}
    if (nameGate) nameGate.classList.add("hidden");
    await runIntroThenGame({});
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

    const fromUrl = resolveNameFromUrl();
    let saved = "";
    try { saved = localStorage.getItem("snowcrash_name") || ""; } catch (_) {}
    if (displayNameEl) displayNameEl.value = fromUrl || saved || "";

    if (fromUrl) {
      await beginWithName(fromUrl);
      return;
    }
    if (nameForm) {
      nameForm.addEventListener("submit", (ev) => {
        ev.preventDefault();
        Sound.unlock();
        const n = displayNameEl ? displayNameEl.value : "Courier";
        beginWithName(n);
      });
    }
    if (nameGate) nameGate.classList.remove("hidden");
    if (displayNameEl) setTimeout(() => displayNameEl.focus(), 50);
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


  if (chatForm && chatInput) {
    chatForm.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const raw = (chatInput.value || "").trim();
      if (!raw) return;
      let text = raw;
      if (text.toLowerCase().startsWith("/say ")) text = text.slice(5);
      // /wish and /feature pass through to server for inventory petition
      Net.chat(text);
      chatInput.value = "";
      chatInput.blur();
      chatFocused = false;
    });
    chatInput.addEventListener("focus", () => { chatFocused = true; });
    chatInput.addEventListener("blur", () => { chatFocused = false; });
  }

  const btnWish = document.getElementById("btn-wish");
  if (btnWish && chatInput) {
    btnWish.addEventListener("click", () => {
      Sound.unlock();
      chatInput.focus();
      chatFocused = true;
      if (!chatInput.value.startsWith("/wish")) {
        chatInput.value = "/wish ";
      }
      try {
        chatInput.setSelectionRange(chatInput.value.length, chatInput.value.length);
      } catch (_) {}
    });
  }

  boot();
})();
