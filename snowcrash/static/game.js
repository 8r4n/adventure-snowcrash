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
  const playerListEl = document.getElementById("player-list"); // optional (decluttered)
  const chatLogEl = document.getElementById("chat-log");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const ircChannelsEl = document.getElementById("irc-channels");
  const ircNicksEl = document.getElementById("irc-nicks");
  const ircTopicEl = document.getElementById("irc-topic");
  const ircChanLabel = document.getElementById("irc-chan-label");
  const ircPromptEl = document.getElementById("irc-prompt");
  const objCompassEl = document.getElementById("obj-compass");
  const fpvPosEl = document.getElementById("fpv-pos");
  const miniPlaneEl = document.getElementById("mini-plane");
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
      const long = intensive
        ? (title || "1ST PERSON — JACK-IN")
        : "1ST PERSON — VIDEO→ASCII";
      perspectiveEl.classList.add("first");
      const declutter = appEl && appEl.classList.contains("declutter");
      if (declutter) {
        perspectiveEl.textContent = "FPV";
        perspectiveEl.title = long;
      } else {
        perspectiveEl.textContent = long;
        perspectiveEl.title = "Camera perspective";
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
      // keep pill class so #app.declutter .pill.net-hud styles apply
      netHud.className = "pill net-hud" + (cls ? " " + cls : "");
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
            const nick = (typeof YearUI !== "undefined" && YearUI.getIrcNick) ? YearUI.getIrcNick() : "";
            send({ type: "join", name, id: myId || undefined, nick: nick || undefined });
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

    function fpvColPlan() {
      const pw = (fpvStage && fpvStage.clientWidth) || 800;
      const large = !!(typeof document !== "undefined" && document.body && document.body.classList.contains("large-type"));
      const narrow = typeof window !== "undefined" && window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
      const div = large || narrow ? 7.2 : 5.5;
      const minCols = large || narrow ? 72 : 110;
      const maxCols = large || narrow ? 120 : 180;
      return Math.min(maxCols, Math.max(minCols, Math.floor(pw / div)));
    }

    function ensureAscii() {
      if (ascii || !fpvCanvas || typeof VideoAsciiCanvas === "undefined") return ascii;
      const cols = fpvColPlan();
      ascii = new VideoAsciiCanvas(fpvCanvas, {
        cols,
        brightness: 1.48,
        contrast: 1.55,
        gamma: 0.78,
        saturate: 1.55,
        autoColor: true,
        bg: "#02050a",
        fit: true,
      });
      ascii.setSourceCanvas(scene);
      return ascii;
    }

    function resizeAscii() {
      const eng = ensureAscii();
      if (!eng || !fpvStage) return;
      eng.setCols(fpvColPlan());
      eng.setSourceCanvas(scene);
    }

    function wallColor(ch, side, dist) {
      const near = Math.max(0.28, Math.min(1, 1.85 / Math.max(0.2, dist)));
      let r, g, b;
      if (ch === "+") {
        r = 255; g = 210; b = 64;
      } else if (ch === "~") {
        r = 64; g = 168; b = 230;
      } else {
        r = 72; g = 235; b = 255;
      }
      if (side) {
        r *= 0.82; g *= 0.82; b *= 0.88;
      }
      r = Math.min(255, r * near * 1.35);
      g = Math.min(255, g * near * 1.35);
      b = Math.min(255, b * near * 1.4);
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
        ceil.addColorStop(0, "#1e4a72");
        ceil.addColorStop(1, "#4a96c4");
      } else if (plane === "UNDER") {
        ceil.addColorStop(0, "#0a0610");
        ceil.addColorStop(1, "#281018");
      } else {
        ceil.addColorStop(0, "#071018");
        ceil.addColorStop(1, "#102038");
      }
      sctx.fillStyle = ceil;
      sctx.fillRect(0, 0, W, mid);

      const floor = sctx.createLinearGradient(0, mid, 0, H);
      if (plane === "AIR") {
        floor.addColorStop(0, "#243848");
        floor.addColorStop(1, "#122030");
      } else if (plane === "UNDER") {
        floor.addColorStop(0, "#1a0c12");
        floor.addColorStop(1, "#0c0608");
      } else {
        floor.addColorStop(0, "#101820");
        floor.addColorStop(1, "#1a2838");
      }
      sctx.fillStyle = floor;
      sctx.fillRect(0, mid, W, H - mid);

      sctx.strokeStyle = "rgba(92,240,255,0.14)";
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
      // Light scanlines — keep CRT flavor without muddying midtones
      sctx.fillStyle = "rgba(0,0,0,0.045)";
      const phase = ((t * 60) | 0) % 4;
      for (let y = phase; y < H; y += 4) {
        sctx.fillRect(0, y, W, 1);
      }
      sctx.fillStyle = "rgba(92,240,255,0.06)";
      for (let n = 0; n < 28; n++) {
        const nx = (n * 97 + turn * 13 + ((t * 40) | 0)) % W;
        const ny = (n * 53 + turn * 7 + ((t * 25) | 0)) % H;
        sctx.fillRect(nx, ny, 2, 1);
      }
      // Soft vignette — edges only, center stays bright/neon
      const vig = sctx.createRadialGradient(cx, cy, H * 0.35, cx, cy, H * 0.92);
      vig.addColorStop(0, "rgba(0,0,0,0)");
      vig.addColorStop(0.7, "rgba(0,0,0,0.05)");
      vig.addColorStop(1, "rgba(0,0,0,0.22)");
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


  // ---- Year frontend UI (#12–#39) — defensive snapshot binding ----
  const YearUI = (() => {
    const els = {
      skillModal: document.getElementById("skill-modal"),
      skillPicks: document.getElementById("skill-picks"),
      loadoutPreview: document.getElementById("loadout-preview"),
      skillSub: document.getElementById("skill-modal-sub"),
      deathOverlay: document.getElementById("death-overlay"),
      deathCause: document.getElementById("death-cause"),
      respawnOptions: document.getElementById("respawn-options"),
      btnRespawnDefault: document.getElementById("btn-respawn-default"),
      eventTicker: document.getElementById("event-ticker"),
      toastStack: document.getElementById("toast-stack"),
      killFeed: document.getElementById("kill-feed"),
      districtPill: document.getElementById("district-pill"),
      districtSplash: document.getElementById("district-splash"),
      districtSplashName: document.getElementById("district-splash-name"),
      districtSplashTag: document.getElementById("district-splash-tag"),
      bossTelegraph: document.getElementById("boss-telegraph"),
      bossName: document.getElementById("boss-name"),
      bossBar: document.getElementById("boss-bar"),
      bossHint: document.getElementById("boss-hint"),
      npcCue: document.getElementById("npc-cue"),
      weatherCanvas: document.getElementById("weather-canvas"),
      weatherOverlay: document.getElementById("weather-overlay"),
      partyBody: document.getElementById("party-body"),
      journalBody: document.getElementById("journal-body"),
      shopBody: document.getElementById("shop-body"),
      craftBody: document.getElementById("craft-body"),
      stashBody: document.getElementById("stash-body"),
      crewBody: document.getElementById("crew-body"),
      contractsBody: document.getElementById("contracts-body"),
      seasonBody: document.getElementById("season-body"),
      raidBody: document.getElementById("raid-body"),
      iceBody: document.getElementById("ice-body"),
      partyPings: document.getElementById("party-pings"),
      arenaPill: document.getElementById("arena-pill"),
      duelBanner: document.getElementById("duel-banner"),
      duelModal: document.getElementById("duel-modal"),
      duelText: document.getElementById("duel-text"),
      theater: document.getElementById("theater-mode"),
      theaterTitle: document.getElementById("theater-title"),
      theaterStage: document.getElementById("theater-stage"),
      analytics: document.getElementById("analytics-badge"),
      panelDock: document.getElementById("panel-dock"),
      chatPanel: document.getElementById("chat-panel"),
      ircModBar: document.getElementById("irc-mod-bar"),
      ircModTarget: document.getElementById("irc-mod-target"),
      mobileHud: document.getElementById("mobile-hud"),
      side: document.getElementById("side"),
      ircNick: document.getElementById("irc-nick"),
    };

    let lastDistrictId = null;
    let lastEventSig = "";
    let lastKillSig = "";
    let lastWishSig = "";
    let lastSkillOpen = false;
    let lastDead = false;
    let weatherKind = "";
    let weatherRaf = 0;
    let weatherDrops = [];
    let modTarget = "";
    let seenFeeMsgs = new Set();
    let theaterSpeed = 1;

    function defArr(v) { return Array.isArray(v) ? v : []; }
    function defObj(v) { return v && typeof v === "object" && !Array.isArray(v) ? v : {}; }
    function defStr(v, d) { return (v == null || v === "") ? d : String(v); }
    function defNum(v, d) { const n = Number(v); return Number.isFinite(n) ? n : d; }

    function toast(text, cls, ms) {
      if (!els.toastStack || !text) return;
      const el = document.createElement("div");
      el.className = "toast" + (cls ? " " + cls : "");
      el.textContent = text;
      els.toastStack.appendChild(el);
      setTimeout(() => { try { el.remove(); } catch (_) {} }, ms || 4200);
    }

    function openPanel(name) {
      const panel = document.querySelector('.year-panel[data-panel="' + name + '"]');
      if (panel) {
        panel.open = true;
        try { panel.scrollIntoView({ block: "nearest", behavior: "smooth" }); } catch (_) {}
      }

      if (els.panelDock) {
        els.panelDock.querySelectorAll(".dock-btn").forEach((b) => {
          b.classList.toggle("active", b.getAttribute("data-panel") === name);
        });
      }
    }

    function toggleIrcCollapse() {
      if (!els.chatPanel) return;
      els.chatPanel.classList.toggle("collapsed");
      if (els.side) els.side.classList.toggle("irc-collapsed", els.chatPanel.classList.contains("collapsed"));
      const btn = document.getElementById("btn-irc-collapse");
      if (btn) btn.textContent = els.chatPanel.classList.contains("collapsed") ? "▸" : "▾";
    }

    function renderSkills(s) {
      const picks = defArr(s.skill_picks_available);
      const skills = defObj(s.skills);
      const loadout = defArr(s.loadout);
      const shouldOpen = picks.length > 0;
      if (els.loadoutPreview) {
        const sk = Object.keys(skills).map((k) => k + ":" + skills[k]).join(" · ") || "—";
        const lo = loadout.map((x) => (typeof x === "string" ? x : (x && x.name) || "?")).join(", ") || "—";
        els.loadoutPreview.textContent = "Skills " + sk + " · Loadout " + lo;
      }
      if (els.skillPicks) {
        els.skillPicks.innerHTML = picks
          .map((p, i) => {
            const id = defStr(p.id || p.key || i, String(i));
            const name = defStr(p.name || p.label || id, id);
            const desc = defStr(p.desc || p.description || "", "");
            return `<button type="button" data-skill="${escapeHtml(id)}"><strong>${escapeHtml(name)}</strong><br/><span class="dim">${escapeHtml(desc)}</span></button>`;
          })
          .join("");
      }
      if (els.skillModal) {
        if (shouldOpen && !lastSkillOpen) {
          els.skillModal.classList.remove("hidden");
          if (els.skillSub) els.skillSub.textContent = picks.length + " pick(s) available";
        } else if (!shouldOpen) {
          els.skillModal.classList.add("hidden");
        }
      }
      lastSkillOpen = shouldOpen;
    }

    function renderShop(s) {
      if (!els.shopBody) return;
      const shop = defObj(s.shop);
      const items = defArr(shop.items || shop.stock || s.shop);
      if (!items.length) {
        els.shopBody.innerHTML = '<div class="panel-empty">No vendor in range</div>';
        return;
      }
      const title = defStr(shop.name || shop.vendor, "Vendor");
      els.shopBody.innerHTML =
        `<div class="row"><strong>${escapeHtml(title)}</strong><span>$${defNum(s.credits, 0)}</span></div>` +
        items
          .map((it, i) => {
            const id = defStr(it.id || it.key || i, String(i));
            const name = defStr(it.name || it.label, id);
            const price = defNum(it.price != null ? it.price : it.cost, 0);
            return `<div class="row shop-item"><span>${escapeHtml(name)}</span><span><span class="price">$${price}</span> <button type="button" data-buy="${escapeHtml(id)}">Buy</button></span></div>`;
          })
          .join("");
    }

    function renderEvents(s) {
      const events = defArr(s.events);
      if (els.eventTicker) {
        if (events.length) {
          const top = events[0];
          const text = typeof top === "string" ? top : defStr(top.text || top.msg || top.name, "WORLD EVENT");
          els.eventTicker.hidden = false;
          els.eventTicker.textContent = "⚡ " + text;
        } else {
          els.eventTicker.hidden = true;
          els.eventTicker.textContent = "";
        }
      }
      const sig = events
        .map((e) => (typeof e === "string" ? e : defStr(e.id || e.text || e.msg, "")))
        .join("|");
      if (sig && sig !== lastEventSig) {
        const fresh = events.slice(0, 3);
        fresh.forEach((e) => {
          const t = typeof e === "string" ? e : defStr(e.text || e.msg || e.name, "");
          if (t) toast(t, "event", 5000);
        });
        lastEventSig = sig;
      }
    }

    function renderParty(s) {
      if (!els.partyBody) return;
      const party = defObj(s.party);
      const members = defArr(party.members || party.players);
      const invites = defArr(party.invites);
      const pings = defArr(party.pings);
      if (!members.length && !invites.length) {
        els.partyBody.innerHTML =
          '<div class="panel-empty">Solo · invite via Party</div>' +
          '<button type="button" data-party="invite">Invite nearby</button> ' +
          '<button type="button" data-party="ping">Ping map</button>';
      } else {
        els.partyBody.innerHTML =
          members
            .map((m) => {
              const name = defStr(m.name || m.id, "?");
              const you = m.id === s.you || m.you ? ' <span class="you">YOU</span>' : "";
              const hp = m.hp != null ? ` · ${m.hp}/${m.max_hp || "?"}` : "";
              return `<div class="row party-member"><span>${escapeHtml(name)}${you}${escapeHtml(hp)}</span></div>`;
            })
            .join("") +
          invites
            .map((inv) => {
              const from = defStr(inv.from || inv.name || inv.id, "courier");
              const id = defStr(inv.id || from, from);
              return `<div class="row"><span>Invite: ${escapeHtml(from)}</span><button type="button" data-party-accept="${escapeHtml(id)}">Accept</button></div>`;
            })
            .join("") +
          '<div class="row"><button type="button" data-party="ping">Ping</button><button type="button" data-party="leave">Leave</button></div>';
      }
      // minimap party pings
      if (els.partyPings) {
        els.partyPings.innerHTML = "";
        const wrap = document.getElementById("minimap-wrap");
        const mini = document.getElementById("minimap");
        if (wrap && mini && s.player && pings.length) {
          const px = s.player.x;
          const py = s.player.y;
          const r = MINI_R;
          pings.forEach((pg) => {
            const x = defNum(pg.x, px);
            const y = defNum(pg.y, py);
            const dx = x - (px - r);
            const dy = y - (py - r);
            const cells = r * 2 + 1;
            const leftPct = (dx / cells) * 100;
            const topPct = (dy / cells) * 100;
            if (leftPct < 0 || leftPct > 100 || topPct < 0 || topPct > 100) return;
            const dot = document.createElement("div");
            dot.className = "party-ping";
            dot.style.left = leftPct + "%";
            dot.style.top = topPct + "%";
            els.partyPings.appendChild(dot);
          });
        }
      }
    }

    function renderDeath(s) {
      const dead = !!(s.dead || s.mode === "dead");
      const opts = defArr(s.respawn_options);
      if (els.deathOverlay) {
        if (dead) {
          els.deathOverlay.classList.remove("hidden");
          if (els.deathCause) {
            const cause = defObj(s.dead);
            const sh = defObj(s.soft_hardcore);
            const pen = defObj(sh.last_penalty);
            let msg = defStr(cause.cause || cause.by || s.death_cause, "Courier down");
            if (sh.enabled && pen.summary) {
              msg = defStr(s.death_cause, msg);
              if (msg.indexOf(String(pen.summary)) < 0) {
                msg = msg + " " + String(pen.summary);
              }
            } else if (sh.enabled) {
              msg = msg + " Soft hardcore is armed.";
            }
            els.deathCause.textContent = msg;
          }
          if (els.respawnOptions) {
            if (opts.length) {
              els.respawnOptions.innerHTML = opts
                .map((o) => {
                  const id = defStr(o.id || o.key || o.name, "default");
                  const label = defStr(o.label || o.name || id, id);
                  const cost = o.cost != null ? ` ($${o.cost})` : "";
                  return `<button type="button" data-respawn="${escapeHtml(id)}">${escapeHtml(label + cost)}</button>`;
                })
                .join("");
            } else {
              els.respawnOptions.innerHTML = "";
            }
          }
        } else {
          els.deathOverlay.classList.add("hidden");
        }
      }
      // keep legacy overlay in sync when year death UI owns it
      if (dead && overlay && s.mode === "dead") {
        overlay.classList.add("hidden");
      }
      lastDead = dead;
    }

    function renderKillFeed(s) {
      if (!els.killFeed) return;
      const feed = defArr(s.kill_feed);
      const sig = feed
        .slice(0, 6)
        .map((k) => defStr(k.id || (k.killer || "") + ">" + (k.victim || "") + (k.t || ""), ""))
        .join("|");
      if (sig === lastKillSig) return;
      lastKillSig = sig;
      els.killFeed.innerHTML = feed
        .slice(0, 6)
        .map((k) => {
          const killer = defStr(k.killer || k.a || "?", "?");
          const victim = defStr(k.victim || k.b || "?", "?");
          const via = k.via ? " [" + escapeHtml(String(k.via)) + "]" : "";
          return `<div class="kf-line"><span class="killer">${escapeHtml(killer)}</span> ▸ <span class="victim">${escapeHtml(victim)}</span>${via}</div>`;
        })
        .join("");
    }

    function renderJournal(s) {
      if (!els.journalBody) return;
      const j = s.journal;
      // Backend sends { arc, step, steps[], completed }; also accept array / .quests
      let list = [];
      let header = "";
      if (Array.isArray(j)) {
        list = j;
      } else {
        const jo = defObj(j);
        if (Array.isArray(jo.quests) && jo.quests.length) {
          list = jo.quests;
        } else if (Array.isArray(jo.steps) && jo.steps.length) {
          const arc = defStr(jo.arc || jo.title || jo.name, "Quest");
          const cur = jo.step != null ? Number(jo.step) : -1;
          header = `<div class="journal-arc"><strong>${escapeHtml(arc.replace(/_/g, " "))}</strong>` +
            (cur >= 0 ? ` <span class="dim">step ${escapeHtml(String(cur))}</span>` : "") +
            `</div>`;
          list = jo.steps.map((step, i) => {
            if (typeof step === "string") {
              return { id: "step-" + i, title: "Step " + (i + 1), text: step, status: i + 1 === cur ? "active" : (i + 1 < cur ? "done" : "pending") };
            }
            const id = defStr(step.id || step.key, "step-" + i);
            const done = !!(step.done || step.completed || (cur > 0 && i + 1 < cur));
            const active = !done && (cur < 0 || i + 1 === cur || step.id === jo.current);
            return {
              id,
              title: defStr(step.title || step.name || id, id),
              text: defStr(step.text || step.objective || step.desc, ""),
              status: done ? "done" : active ? "active" : defStr(step.status, "pending"),
            };
          });
        }
      }
      const jo = defObj(j);
      const side = defArr(jo.side).map((q, i) => {
        const id = defStr(q.id || q.key, "side-" + i);
        const title = defStr(q.title || q.name || id, id);
        const st = q.done || q.completed ? "done" : defStr(q.status, "active");
        const obj = defStr(q.objective || q.text || q.desc, "");
        return `<div class="journal-quest ${escapeHtml(st)}" data-quest="${escapeHtml(id)}"><strong>${escapeHtml(title)}</strong><div class="dim">${escapeHtml(obj)}</div></div>`;
      }).join("");
      const notes = defArr(jo.notes).slice(-4).map((n) =>
        `<div class="row dim">· ${escapeHtml(String(n))}</div>`
      ).join("");
      const questHtml = list.length
        ? list.map((q) => {
            const id = defStr(q.id || q.key, "");
            const title = defStr(q.title || q.name || id, "Quest");
            const st = defStr(q.status || (q.done ? "done" : "active"), "active");
            const obj = defStr(q.objective || q.text || q.desc, "");
            return `<div class="journal-quest ${escapeHtml(st)}" data-quest="${escapeHtml(id)}"><strong>${escapeHtml(title)}</strong><div class="dim">${escapeHtml(obj)}</div><button type="button" data-track="${escapeHtml(id)}">Track</button></div>`;
          }).join("")
        : '<div class="panel-empty">No active quests</div>';
      els.journalBody.innerHTML = header + questHtml +
        (side ? `<div class="row"><strong>Side</strong></div>` + side : "") +
        (notes ? `<div class="row"><strong>Jack notes</strong></div>` + notes : "");
    }

    function renderDistrict(s) {
      const district = defObj(s.district);
      const name = defStr(district.name || district.id || s.district, "");
      const id = defStr(district.id || name, "");
      if (els.districtPill) {
        els.districtPill.textContent = name || "—";
        els.districtPill.title = defStr(district.tag || district.blurb || "District", "District");
      }
      if (id && id !== lastDistrictId && lastDistrictId != null && els.districtSplash) {
        if (els.districtSplashName) els.districtSplashName.textContent = name || id;
        if (els.districtSplashTag) els.districtSplashTag.textContent = defStr(district.tag || district.blurb, "");
        els.districtSplash.classList.remove("hidden");
        setTimeout(() => {
          if (els.districtSplash) els.districtSplash.classList.add("hidden");
        }, 2200);
      }
      if (id) lastDistrictId = id;
      else if (lastDistrictId == null) lastDistrictId = "";
    }

    function renderBoss(s) {
      const boss = defObj(s.boss);
      const active = !!(boss.id || boss.name || boss.hp != null);
      if (!els.bossTelegraph) return;
      if (!active) {
        els.bossTelegraph.classList.add("hidden");
        return;
      }
      els.bossTelegraph.classList.remove("hidden");
      if (els.bossName) els.bossName.textContent = defStr(boss.name || boss.id, "BOSS").toUpperCase();
      const hp = defNum(boss.hp, 0);
      const max = Math.max(1, defNum(boss.max_hp != null ? boss.max_hp : boss.maxhp, 100));
      if (els.bossBar) els.bossBar.style.width = Math.max(0, Math.min(100, (hp / max) * 100)) + "%";
      if (els.bossHint) els.bossHint.textContent = defStr(boss.telegraph || boss.phase || boss.hint, "");
    }

    function renderCraft(s) {
      if (!els.craftBody) return;
      const craft = defObj(s.craft);
      const recipes = defArr(craft.recipes || s.craft);
      if (!recipes.length) {
        els.craftBody.innerHTML = '<div class="panel-empty">Faraday bench offline</div>';
        return;
      }
      els.craftBody.innerHTML = recipes
        .map((r) => {
          const id = defStr(r.id || r.key || r.name, "?");
          const name = defStr(r.name || id, id);
          const locked = !!r.locked;
          const mats = defArr(r.materials || r.cost)
            .map((m) => (typeof m === "string" ? m : defStr(m.name || m.id, "?")))
            .join(", ");
          return `<div class="row craft-recipe${locked ? " locked" : ""}"><span>${escapeHtml(name)}<br/><span class="dim">${escapeHtml(mats)}</span></span>${locked ? "" : `<button type="button" data-craft="${escapeHtml(id)}">Craft</button>`}</div>`;
        })
        .join("");
    }

    function renderStash(s) {
      if (!els.stashBody) return;
      const housing = defObj(s.housing);
      const stash = defArr(housing.stash || housing.items || s.housing);
      const name = defStr(housing.name || housing.safehouse, "Safehouse");
      if (!stash.length && !housing.name && !s.housing) {
        els.stashBody.innerHTML = '<div class="panel-empty">No safehouse linked</div>';
        return;
      }
      els.stashBody.innerHTML =
        `<div class="row"><strong>${escapeHtml(name)}</strong></div>` +
        (stash.length
          ? stash
              .map((it, i) => {
                const id = defStr(it.id || i, String(i));
                const label = defStr(it.name || it.glyph || id, id);
                return `<div class="row"><span>${escapeHtml(label)}</span><button type="button" data-stash-withdraw="${escapeHtml(id)}">Take</button></div>`;
              })
              .join("")
          : '<div class="panel-empty">Stash empty</div>') +
        '<div class="row"><button type="button" data-stash="deposit">Deposit selected</button></div>';
    }

    function renderNpcCue(s) {
      if (!els.npcCue) return;
      const dlg = defObj(s.dialogue || s.npc_dialogue || defObj(s.npc).dialogue);
      const line = defStr(dlg.text || dlg.line || (typeof s.dialogue === "string" ? s.dialogue : ""), "");
      const speaker = defStr(dlg.speaker || dlg.name || defObj(s.npc).name, "NPC");
      const choices = defArr(dlg.choices || dlg.options);
      if (!line && !choices.length) {
        els.npcCue.classList.add("hidden");
        els.npcCue.innerHTML = "";
        return;
      }
      els.npcCue.classList.remove("hidden");
      els.npcCue.innerHTML =
        `<span class="npc-name">${escapeHtml(speaker)}</span>${escapeHtml(line)}` +
        (choices.length
          ? `<div class="npc-choices">${choices
              .map((c, i) => {
                const id = defStr(c.id || c.key || i, String(i));
                const label = defStr(c.label || c.text || id, id);
                return `<button type="button" data-dlg="${escapeHtml(id)}">${escapeHtml(label)}</button>`;
              })
              .join("")}</div>`
          : "");
    }

    function ensureWeatherDrops(w, h) {
      if (weatherDrops.length) return;
      for (let i = 0; i < 48; i++) {
        weatherDrops.push({
          x: Math.random() * w,
          y: Math.random() * h,
          len: 6 + Math.random() * 14,
          spd: 2 + Math.random() * 4,
          hue: Math.random() > 0.5 ? "rgba(57,197,207,0.55)" : "rgba(255,42,109,0.4)",
        });
      }
    }

    function paintWeather() {
      const canvas = els.weatherCanvas;
      if (!canvas || !weatherKind) return;
      const parent = canvas.parentElement;
      const w = (parent && parent.clientWidth) || 480;
      const h = (parent && parent.clientHeight) || 270;
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
        weatherDrops = [];
      }
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, w, h);
      if (weatherKind === "neon_rain" || weatherKind === "rain") {
        ensureWeatherDrops(w, h);
        weatherDrops.forEach((d) => {
          ctx.strokeStyle = d.hue;
          ctx.beginPath();
          ctx.moveTo(d.x, d.y);
          ctx.lineTo(d.x - 1, d.y + d.len);
          ctx.stroke();
          d.y += d.spd;
          d.x -= 0.4;
          if (d.y > h) {
            d.y = -d.len;
            d.x = Math.random() * w;
          }
        });
      } else if (weatherKind === "signal_storm" || weatherKind === "storm") {
        if (Math.random() < 0.04) {
          ctx.fillStyle = "rgba(255,255,255,0.08)";
          ctx.fillRect(0, 0, w, h);
        }
        ctx.strokeStyle = "rgba(255,42,109,0.25)";
        for (let i = 0; i < 3; i++) {
          ctx.beginPath();
          let x = Math.random() * w;
          let y = 0;
          ctx.moveTo(x, y);
          for (let j = 0; j < 6; j++) {
            x += (Math.random() - 0.5) * 40;
            y += h / 6;
            ctx.lineTo(x, y);
          }
          ctx.stroke();
        }
      }
      weatherRaf = requestAnimationFrame(paintWeather);
    }

    function renderWeather(s) {
      const weather = defObj(s.weather);
      const kind = defStr(weather.kind || weather.type || (typeof s.weather === "string" ? s.weather : ""), "");
      if (els.weatherOverlay) {
        els.weatherOverlay.classList.remove("neon-rain", "signal-storm");
        if (kind === "neon_rain" || kind === "rain") els.weatherOverlay.classList.add("neon-rain");
        if (kind === "signal_storm" || kind === "storm") els.weatherOverlay.classList.add("signal-storm");
      }
      if (kind !== weatherKind) {
        weatherKind = kind;
        weatherDrops = [];
        if (weatherRaf) {
          cancelAnimationFrame(weatherRaf);
          weatherRaf = 0;
        }
        if (els.weatherCanvas) {
          const ctx = els.weatherCanvas.getContext("2d");
          if (ctx) ctx.clearRect(0, 0, els.weatherCanvas.width, els.weatherCanvas.height);
        }
        if (kind) weatherRaf = requestAnimationFrame(paintWeather);
      }
    }

    function renderCrew(s) {
      if (!els.crewBody) return;
      const crew = defObj(s.crew);
      const members = defArr(crew.members);
      const name = defStr(crew.name || crew.tag, "");
      const rep = defObj(s.reputation);
      if (!name && !members.length) {
        els.crewBody.innerHTML = '<div class="panel-empty">No crew · form or join</div><button type="button" data-crew="form">Form crew</button>';
        return;
      }
      const repBits = Object.keys(rep)
        .slice(0, 4)
        .map((k) => k + ":" + rep[k])
        .join(" · ");
      els.crewBody.innerHTML =
        `<div class="row"><strong>${escapeHtml(name || "Crew")}</strong><span class="dim">${escapeHtml(repBits)}</span></div>` +
        members
          .map((m) => `<div class="row"><span>${escapeHtml(defStr(m.name || m.id, "?"))}</span><span class="dim">${escapeHtml(defStr(m.role, ""))}</span></div>`)
          .join("") +
        '<div class="row"><button type="button" data-crew="invite">Invite</button><button type="button" data-crew="leave">Leave</button></div>';
    }

    function renderContracts(s) {
      if (!els.contractsBody) return;
      const board = defArr(s.contracts || defObj(s.contracts).board);
      const list = Array.isArray(s.contracts) ? s.contracts : defArr(defObj(s.contracts).board || defObj(s.contracts).active);
      if (!list.length) {
        els.contractsBody.innerHTML = '<div class="panel-empty">No contracts posted</div>';
        return;
      }
      els.contractsBody.innerHTML = list
        .map((c) => {
          const id = defStr(c.id || c.key, "?");
          const title = defStr(c.title || c.name || id, id);
          const reward = c.reward != null ? "$" + c.reward : defStr(c.pay, "");
          const rep = c.reputation != null ? " · rep " + c.reputation : "";
          return `<div class="row contract-row"><span>${escapeHtml(title)}<br/><span class="rep">${escapeHtml(reward + rep)}</span></span><button type="button" data-contract="${escapeHtml(id)}">Accept</button></div>`;
        })
        .join("");
    }

    function renderPvp(s) {
      const pvp = defObj(s.pvp);
      const arena = !!(pvp.arena || pvp.in_arena || pvp.mode === "arena");
      const duel = defObj(pvp.duel || s.duel);
      if (els.arenaPill) els.arenaPill.classList.toggle("hidden", !arena);
      if (els.duelBanner) {
        const showBanner = arena || !!duel.active;
        els.duelBanner.classList.toggle("hidden", !showBanner);
        if (showBanner) els.duelBanner.textContent = arena ? "ARENA · PVP ON" : "DUEL · ACTIVE";
      }
      const challenge = defObj(duel.challenge || pvp.challenge);
      if (els.duelModal) {
        if (challenge.from || challenge.id) {
          els.duelModal.classList.remove("hidden");
          if (els.duelText) {
            els.duelText.textContent =
              defStr(challenge.from || challenge.name, "Courier") +
              " challenges you" +
              (challenge.stakes != null ? " · stakes $" + challenge.stakes : "");
          }
        } else if (!challenge.pending) {
          els.duelModal.classList.add("hidden");
        }
      }
    }

    function renderTheater(s) {
      const theater = defObj(s.theater || s.spectate || s.replay);
      const active = !!(theater.active || theater.mode || theater.frames);
      if (!els.theater) return;
      if (!active) {
        // do not auto-hide if user opened manually without backend — only hide when backend clears
        if (theater.active === false) els.theater.classList.add("hidden");
        return;
      }
      els.theater.classList.remove("hidden");
      if (els.theaterTitle) els.theaterTitle.textContent = defStr(theater.title || theater.id, "REPLAY");
      if (els.theaterStage) {
        const frame = theater.frame || theater.ascii || (defArr(theater.frames)[theater.index || 0]) || "";
        els.theaterStage.textContent = typeof frame === "string" ? frame : JSON.stringify(frame, null, 0);
      }
    }

    function renderSeason(s) {
      if (!els.seasonBody) return;
      const season = defObj(s.season);
      const tiers = defArr(season.tiers || season.rewards);
      const level = defNum(season.level != null ? season.level : season.tier, 0);
      const xp = defNum(season.xp, 0);
      const xpNext = defNum(season.xp_next, 100);
      if (!season.id && !tiers.length && !season.name) {
        els.seasonBody.innerHTML = '<div class="panel-empty">Season pass idle</div>';
        return;
      }
      els.seasonBody.innerHTML =
        `<div class="row"><strong>${escapeHtml(defStr(season.name || season.id, "Season"))}</strong><span class="season-tier">T${level}</span></div>` +
        `<div class="row dim">XP ${xp}/${xpNext}</div>` +
        tiers
          .slice(0, 8)
          .map((t) => {
            const id = defStr(t.id || t.tier || t.name, "?");
            const label = defStr(t.name || t.cosmetic || id, id);
            const claimed = !!t.claimed;
            return `<div class="row"><span>${escapeHtml(label)}</span>${claimed ? '<span class="dim">owned</span>' : `<button type="button" data-season-claim="${escapeHtml(id)}">Claim</button>`}</div>`;
          })
          .join("");
    }

    function renderRaid(s) {
      if (!els.raidBody) return;
      const raid = defObj(s.raid || defObj(s.party).raid);
      const lobby = defArr(raid.lobby || raid.members);
      if (!raid.id && !lobby.length && !raid.name) {
        els.raidBody.innerHTML = '<div class="panel-empty">No raid queued</div><button type="button" data-raid="queue">Queue raid</button>';
        return;
      }
      els.raidBody.innerHTML =
        `<div class="row"><strong>${escapeHtml(defStr(raid.name || raid.id, "Raid"))}</strong><span class="dim">${escapeHtml(defStr(raid.phase || raid.status, "lobby"))}</span></div>` +
        lobby
          .map((m) => {
            const name = defStr(m.name || m.id, "?");
            const ready = m.ready ? " ✓" : "";
            return `<div class="row"><span>${escapeHtml(name + ready)}</span></div>`;
          })
          .join("") +
        '<div class="row"><button type="button" data-raid="ready">Ready</button><button type="button" data-raid="leave">Leave</button></div>';
    }

    function renderWishToy(s) {
      const wish = defObj(s.wish_result || s.toy);
      const sig = defStr(wish.id || wish.name || wish.toast, "");
      if (sig && sig !== lastWishSig) {
        toast("Wish→toy: " + defStr(wish.name || wish.toast || sig, sig), "wish", 5500);
        lastWishSig = sig;
      }
      // also scan messages for wish/fee/repair
      const msgs = defArr(s.messages);
      msgs.forEach((m) => {
        const t = String(m || "");
        const key = t.slice(0, 80);
        if (seenFeeMsgs.has(key)) return;
        const low = t.toLowerCase();
        if (low.includes("wish") && (low.includes("granted") || low.includes("toy"))) {
          seenFeeMsgs.add(key);
          toast(t, "wish", 4500);
        } else if (low.includes("fee") || low.includes("toll")) {
          seenFeeMsgs.add(key);
          toast(t, "fee", 4000);
        } else if (low.includes("repair")) {
          seenFeeMsgs.add(key);
          toast(t, "repair", 4000);
        }
      });
      if (seenFeeMsgs.size > 80) {
        seenFeeMsgs = new Set(Array.from(seenFeeMsgs).slice(-40));
      }
    }

    function styleLogFees(s) {
      if (!logEl) return;
      // enhance last render of messages with fee/repair classes
      const msgs = defArr(s.messages);
      if (!msgs.length) return;
      logEl.innerHTML = msgs
        .map((m) => {
          const t = String(m || "");
          const low = t.toLowerCase();
          let cls = "";
          if (low.includes("fee") || low.includes("toll")) cls = "log-fee";
          else if (low.includes("repair")) cls = "log-repair";
          else if (low.includes("wish")) cls = "log-wish";
          return `<div class="${cls}">${escapeHtml(t)}</div>`;
        })
        .join("");
      logEl.scrollTop = logEl.scrollHeight;
    }


    function renderIce(s) {
      if (!els.iceBody) return;
      const ice = defObj(s.ice);
      const probes = defArr(ice.probes);
      const nearby = defArr(ice.nearby);
      const focus = defNum(ice.focus != null ? ice.focus : defObj(s.player).focus, defNum(s.focus, 0));
      const maxF = defNum(ice.max_focus != null ? ice.max_focus : defObj(s.player).max_focus, 0);
      if (!probes.length) {
        els.iceBody.innerHTML = '<div class="panel-empty">ICE layer offline</div>';
        return;
      }
      const probeRows = probes.map((p) => {
        const id = defStr(p.id, "");
        const name = defStr(p.name, id);
        const desc = defStr(p.desc, "");
        const cost = defNum(p.focus_cost, 0);
        const readyIn = defNum(p.ready_in, 0);
        const ready = !!p.ready || readyIn <= 0.05;
        const cd = ready ? "" : ` · cd ${readyIn.toFixed(1)}s`;
        const disabled = (!ready || focus < cost) ? " disabled" : "";
        const btnLabel = ({ stun: "Stun", reveal: "Reveal", scramble: "Scramble" })[id]
          || (name.split(/\s+/)[0] || "Probe");
        return `<div class="row ice-probe"><span><strong>${escapeHtml(name)}</strong> <span class="dim">(${cost} Focus${cd})</span><br/><span class="dim">${escapeHtml(desc)}</span></span><button type="button" data-ice="${escapeHtml(id)}"${disabled}>${escapeHtml(btnLabel)}</button></div>`;
      }).join("");
      const nearRows = nearby.length
        ? nearby.slice(0, 8).map((t) => {
            const kind = defStr(t.kind, "?");
            const name = defStr(t.name, kind);
            const dist = defNum(t.dist, 0);
            const flags = [t.stunned ? "STUN" : null, t.scrambled ? "SCRAM" : null].filter(Boolean).join(" ");
            return `<div class="row dim">${escapeHtml(kind)} · ${escapeHtml(name)} · d${dist}${flags ? " · " + flags : ""}</div>`;
          }).join("")
        : '<div class="panel-empty">No cameras / drones / thug decks in range</div>';
      els.iceBody.innerHTML =
        `<div class="row"><strong>Focus</strong><span>${focus}/${maxF}</span></div>` +
        `<div class="row dim">${escapeHtml(defStr(ice.hint, "Spend Focus on StreetNet ICE probes."))}</div>` +
        probeRows +
        `<div class="row"><strong>Nearby ICE</strong></div>` +
        nearRows;
    }

    function renderAnalytics(s) {
      if (!els.analytics) return;
      const a = defObj(s.analytics || s.debug);
      const tick = s.tick != null ? s.tick : "—";
      const online = s.online_count != null ? s.online_count : listLen(s);
      const bits = [
        "t" + tick,
        online + "p",
        a.fps != null ? a.fps + "fps" : null,
        a.ms != null ? a.ms + "ms" : lastPingMs != null ? lastPingMs + "ms" : null,
      ].filter(Boolean);
      els.analytics.hidden = false;
      els.analytics.textContent = bits.join(" · ");
    }

    function renderCyberHint(s) {
      const cyber = defObj(s.cyberspace);
      const btn = document.getElementById("btn-cyber-jack");
      if (btn) {
        const active = s.mode === "cyberspace" && !!cyber.active;
        const can = !!cyber.can_jack_in;
        btn.disabled = !(active || can);
        btn.textContent = active ? "Jack out" : "Jack in";
        btn.title = active
          ? "Exit cyberspace node (Esc / j)"
          : (can ? "Jack into cyberspace at jackpoint (j)" : "Reach jackpoint (J) to jack in");
        btn.dataset.cyber = active ? "out" : "in";
      }
      const fpv = document.getElementById("fpv-status");
      if (fpv && s.mode === "cyberspace" && cyber.active) {
        fpv.textContent = "CYBER · " + defStr(cyber.node_type, "node").toUpperCase();
      }
    }

    function apply(s) {
      if (!s) return;
      try {
        renderSkills(s);
        renderShop(s);
        renderEvents(s);
        renderParty(s);
        renderDeath(s);
        renderKillFeed(s);
        renderJournal(s);
        renderDistrict(s);
        renderBoss(s);
        renderCraft(s);
        renderStash(s);
        renderNpcCue(s);
        renderWeather(s);
        renderCrew(s);
        renderContracts(s);
        renderPvp(s);
        renderTheater(s);
        renderSeason(s);
        renderRaid(s);
        renderIce(s);
        renderCyberHint(s);
        renderWishToy(s);
        styleLogFees(s);
        renderAnalytics(s);
      } catch (err) {
        console.warn("YearUI apply failed", err);
      }
    }

    function bind() {
      document.querySelectorAll(".modal-close").forEach((btn) => {
        btn.addEventListener("click", () => {
          const id = btn.getAttribute("data-close");
          const modal = id ? document.getElementById(id) : btn.closest(".year-modal");
          if (modal) modal.classList.add("hidden");
        });
      });

      if (els.panelDock) {
        els.panelDock.addEventListener("click", (ev) => {
          const btn = ev.target && ev.target.closest ? ev.target.closest("[data-panel]") : null;
          if (!btn) {
            if (ev.target && ev.target.id === "btn-collapse-irc") toggleIrcCollapse();
            return;
          }
          openPanel(btn.getAttribute("data-panel"));
          Sound.play("click");
        });
      }
      document.querySelectorAll("[data-panel-open]").forEach((btn) => {
        btn.addEventListener("click", (ev) => {
          ev.preventDefault();
          openPanel(btn.getAttribute("data-panel-open"));
          Sound.play("click");
        });
      });
      const ircCollapse = document.getElementById("btn-irc-collapse");
      if (ircCollapse) ircCollapse.addEventListener("click", () => toggleIrcCollapse());

      if (els.skillPicks) {
        els.skillPicks.addEventListener("click", (ev) => {
          const btn = ev.target.closest("[data-skill]");
          if (!btn) return;
          send("skill_pick", btn.getAttribute("data-skill"));
          Sound.play("click");
        });
      }
      if (els.btnRespawnDefault) {
        els.btnRespawnDefault.addEventListener("click", () => {
          send("r");
          Sound.play("click");
        });
      }
      if (els.respawnOptions) {
        els.respawnOptions.addEventListener("click", (ev) => {
          const btn = ev.target.closest("[data-respawn]");
          if (!btn) return;
          send("respawn", btn.getAttribute("data-respawn"));
          Sound.play("click");
        });
      }
      if (els.shopBody) {
        els.shopBody.addEventListener("click", (ev) => {
          const btn = ev.target.closest("[data-buy]");
          if (!btn) return;
          send("shop_buy", btn.getAttribute("data-buy"));
          Sound.play("click");
        });
      }
      function bindPanel(el, handlers) {
        if (!el) return;
        el.addEventListener("click", (ev) => {
          for (const [attr, fn] of handlers) {
            const btn = ev.target.closest("[" + attr + "]");
            if (btn) {
              fn(btn.getAttribute(attr), btn);
              Sound.play("click");
              return;
            }
          }
        });
      }
      bindPanel(els.partyBody, [
        ["data-party", (v) => send("party_" + v)],
        ["data-party-accept", (v) => send("party_accept", v)],
      ]);
      bindPanel(els.journalBody, [["data-track", (v) => send("journal_track", v)]]);
      const jackBtn = document.getElementById("btn-cyber-jack");
      if (jackBtn && !jackBtn.dataset.bound) {
        jackBtn.dataset.bound = "1";
        jackBtn.addEventListener("click", () => {
          if (jackBtn.dataset.cyber === "out") send("jack_out");
          else send("jack_in");
        });
      }
      bindPanel(els.craftBody, [["data-craft", (v) => send("craft", v)]]);
      bindPanel(els.stashBody, [
        ["data-stash-withdraw", (v) => send("stash_withdraw", v)],
        ["data-stash", (v) => send("stash_" + v)],
      ]);
      bindPanel(els.crewBody, [["data-crew", (v) => send("crew_" + v)]]);
      bindPanel(els.contractsBody, [["data-contract", (v) => send("contract_accept", v)]]);
      bindPanel(els.seasonBody, [["data-season-claim", (v) => send("season_claim", v)]]);
      bindPanel(els.raidBody, [["data-raid", (v) => send("raid_" + v)]]);
      if (els.npcCue) {
        els.npcCue.addEventListener("click", (ev) => {
          const btn = ev.target.closest("[data-dlg]");
          if (!btn) return;
          send("dialogue", btn.getAttribute("data-dlg"));
          Sound.play("talk");
        });
      }
      const btnAccept = document.getElementById("btn-duel-accept");
      const btnDecline = document.getElementById("btn-duel-decline");
      if (btnAccept) btnAccept.addEventListener("click", () => { send("duel_accept"); if (els.duelModal) els.duelModal.classList.add("hidden"); });
      if (btnDecline) btnDecline.addEventListener("click", () => { send("duel_decline"); if (els.duelModal) els.duelModal.classList.add("hidden"); });

      const btnTheaterExit = document.getElementById("btn-theater-exit");
      if (btnTheaterExit) btnTheaterExit.addEventListener("click", () => {
        if (els.theater) els.theater.classList.add("hidden");
        send("spectate_exit");
      });
      const theaterControls = document.getElementById("theater-controls");
      if (theaterControls) {
        theaterControls.addEventListener("click", (ev) => {
          const btn = ev.target.closest("[data-theater]");
          if (!btn) return;
          const act = btn.getAttribute("data-theater");
          if (act === "speed") {
            theaterSpeed = theaterSpeed >= 2 ? 1 : theaterSpeed + 0.5;
            btn.textContent = theaterSpeed + "×";
            send("spectate_speed", String(theaterSpeed));
          } else {
            send("spectate_" + act);
          }
        });
      }

      // StreetNet mute/report (#30)
      if (ircNicksEl) {
        ircNicksEl.addEventListener("contextmenu", (ev) => {
          const li = ev.target.closest("li");
          if (!li) return;
          ev.preventDefault();
          modTarget = (li.getAttribute("data-name") || "").trim();
          if (!modTarget || !els.ircModBar) return;
          if (els.ircModTarget) els.ircModTarget.textContent = modTarget;
          els.ircModBar.classList.remove("hidden");
        });
        // long-press / click also opens mod on mobile
        ircNicksEl.addEventListener("click", (ev) => {
          if (!window.matchMedia("(max-width: 720px)").matches) return;
          const li = ev.target.closest("li");
          if (!li) return;
          modTarget = (li.getAttribute("data-name") || "").trim();
          if (!modTarget || !els.ircModBar) return;
          if (els.ircModTarget) els.ircModTarget.textContent = modTarget;
          els.ircModBar.classList.remove("hidden");
        });
      }
      const btnMuteIrc = document.getElementById("btn-irc-mute");
      const btnReport = document.getElementById("btn-irc-report");
      const btnModClose = document.getElementById("btn-irc-mod-close");
      if (btnMuteIrc) btnMuteIrc.addEventListener("click", () => {
        if (modTarget) {
          send("chat_mute", modTarget);
          Net.chat("/mute " + modTarget);
          toast("Muted " + modTarget, "party");
        }
        if (els.ircModBar) els.ircModBar.classList.add("hidden");
      });
      if (btnReport) btnReport.addEventListener("click", () => {
        if (modTarget) {
          send("chat_report", modTarget);
          Net.chat("/report " + modTarget);
          toast("Reported " + modTarget, "fee");
        }
        if (els.ircModBar) els.ircModBar.classList.add("hidden");
      });
      if (btnModClose) btnModClose.addEventListener("click", () => {
        if (els.ircModBar) els.ircModBar.classList.add("hidden");
      });

      // Mobile virtual joystick / chord pad (#31 / #75)
      const vjoy = document.getElementById("vjoy");
      const chord = document.getElementById("chord-pad");
      function blockScrollBleed(el) {
        if (!el) return;
        const block = (ev) => { ev.preventDefault(); };
        el.addEventListener("touchmove", block, { passive: false });
        el.addEventListener("gesturestart", block, { passive: false });
      }
      blockScrollBleed(els.mobileHud);
      blockScrollBleed(vjoy);
      blockScrollBleed(chord);
      function bindTouchAct(root, attr, prefix) {
        if (!root) return;
        const fire = (ev) => {
          const btn = ev.target.closest("[" + attr + "]");
          if (!btn) return;
          ev.preventDefault();
          const val = btn.getAttribute(attr);
          if (prefix === "move") send(val);
          else send(val);
          Sound.unlock();
        };
        root.addEventListener("pointerdown", fire);
      }
      bindTouchAct(vjoy, "data-move", "move");
      bindTouchAct(chord, "data-act", "act");
      // Prefer large-type FPV glyphs on narrow viewports (#75)
      try {
        const wantLarge = localStorage.getItem("snowcrash_large_type");
        const narrow = window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
        if (wantLarge === "1" || (wantLarge !== "0" && narrow)) {
          document.body.classList.add("large-type");
        }
      } catch (_) {}

      // Optional nick polish (#25)
      if (els.ircNick) {
        try {
          const savedNick = localStorage.getItem("snowcrash_nick") || "";
          if (savedNick) els.ircNick.value = savedNick;
        } catch (_) {}
      }
    }

    function getIrcNick() {
      if (!els.ircNick) return "";
      return (els.ircNick.value || "").trim().slice(0, 16);
    }

    function persistNick() {
      const n = getIrcNick();
      if (!n) return;
      try { localStorage.setItem("snowcrash_nick", n); } catch (_) {}
    }

    return { apply, bind, openPanel, toast, getIrcNick, persistNick, toggleIrcCollapse };
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
    if (miniPlaneEl) {
      miniPlaneEl.textContent = planeName + " · Z" + myZ;
    } else {
      const miniChrome = document.querySelector("#minimap-wrap .mini-chrome span:last-child");
      if (miniChrome) miniChrome.textContent = planeName + " · Z" + myZ;
    }
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
        // Quest landmarks (always show on GPS)
        let landmarkHit = false;
        if (!(x === px && y === py) && Array.isArray(s.landmarks)) {
          for (let li = 0; li < s.landmarks.length; li++) {
            const lm = s.landmarks[li];
            if (lm && lm.x === x && lm.y === y) {
              ch = lm.glyph || "•";
              landmarkHit = true;
              break;
            }
          }
        }
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
        if (landmarkHit) cls = "m-land";
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

  function ircTime(ts) {
    try {
      const d = new Date((ts || 0) * 1000);
      const hh = String(d.getHours()).padStart(2, "0");
      const mm = String(d.getMinutes()).padStart(2, "0");
      return hh + ":" + mm;
    } catch (e) {
      return "--:--";
    }
  }

  function renderIrcLine(c) {
    const ts = `<span class="irc-ts">[${ircTime(c.t)}]</span>`;
    const kind = c.kind || "say";
    if (kind === "system" || kind === "join" || kind === "part" || kind === "nick") {
      const cls = kind === "system" ? "irc-sys" : "irc-" + kind;
      return `<div class="${cls}">${ts}*** ${escapeHtml(c.text)}</div>`;
    }
    if (kind === "notice") {
      return `<div class="irc-notice">${ts}-irc- ${escapeHtml(c.text)}</div>`;
    }
    if (kind === "action") {
      return `<div class="irc-action">${ts}* ${escapeHtml(c.name)} ${escapeHtml(c.text)}</div>`;
    }
    if (kind === "pm") {
      return `<div class="irc-pm">${ts}[${escapeHtml(c.name)}] ${escapeHtml(c.text)}</div>`;
    }
    return `<div class="irc-say">${ts}<span class="cn">${escapeHtml(c.name)}</span>${escapeHtml(
      c.text
    )}</div>`;
  }

  const IRC_DEFAULT_CHANS = ["#streets", "#metaverse", "#flotilla", "#wish"];

  function renderIrc(s) {
    const irc = s.irc || {};
    const cur = irc.channel || "#streets";
    const joined = Array.isArray(irc.channels) && irc.channels.length ? irc.channels : ["#streets"];
    const topics = irc.topics || {};
    const nicks = Array.isArray(irc.nicks) ? irc.nicks : [];

    if (ircChanLabel) ircChanLabel.textContent = cur;
    if (ircTopicEl) {
      const topic = topics[cur] || (cur.startsWith("@") ? "private query" : "");
      ircTopicEl.textContent = cur + " — " + (topic || "no topic");
    }
    if (ircPromptEl && s.player) {
      ircPromptEl.textContent = "<" + (s.player.name || "courier") + ">";
    }

    if (ircChannelsEl) {
      const shown = Array.from(new Set(IRC_DEFAULT_CHANS.concat(joined)));
      ircChannelsEl.innerHTML = shown
        .map((ch) => {
          const on = ch === cur ? " active" : "";
          const mine = joined.indexOf(ch) >= 0 ? "" : " dim";
          return `<button type="button" class="irc-ch${on}${mine}" data-chan="${escapeHtml(
            ch
          )}">${escapeHtml(ch)}</button>`;
        })
        .join("");
    }

    if (ircNicksEl) {
      const list =
        nicks.length > 0
          ? nicks
          : (s.players || []).map((op) => ({
              name: op.name,
              you: op.id === s.you,
              glyph: op.glyph,
            }));
      ircNicksEl.innerHTML = list
        .map((n) => {
          const cls = n.you ? "you" : "";
          return `<li class="${cls}" data-name="${escapeHtml(n.name)}" title="${escapeHtml(n.name)}">${escapeHtml(
            n.glyph ? n.glyph + " " : ""
          )}${escapeHtml(n.name)}</li>`;
        })
        .join("");
    }

    if (chatLogEl && Array.isArray(s.chat)) {
      chatLogEl.innerHTML = s.chat.map(renderIrcLine).join("");
      chatLogEl.scrollTop = chatLogEl.scrollHeight;
    }
  }

  function render(s) {
    handleSfx(s);
    handleCutscenes(s);
    state = s;
    renderFpv(s);
    renderMinimap(s);
    if (minimapEl && Array.isArray(s.landmarks) && s.player) {
      const marks = s.landmarks.map((m) => m.glyph + ":" + m.name).join(" · ");
      minimapEl.title = marks || "Street GPS";
    }

    const p = s.player;
    myId = s.you || myId;
    const obj = s.objective || null;
    const lv = s.level != null ? s.level : 1;
    const xp = s.xp != null ? s.xp : 0;
    const xpNext = s.xp_next != null ? s.xp_next : 40;
    const credits = s.credits != null ? s.credits : 0;
    if (statsEl) {
      statsEl.innerHTML = `
      <div class="obj">${obj ? escapeHtml(obj.compass + " " + obj.bearing + " · " + obj.text + (obj.dist != null ? " (" + obj.dist + ")" : "")) : "—"}</div>
      <div><strong>${escapeHtml(p.name)}</strong> <span style="color:${escapeHtml(p.color || "#39c5cf")}">[${escapeHtml(p.glyph || "@")}]</span>
        · Lv ${lv} · <span class="hp">${p.hp}/${p.max_hp}</span></div>
      <div class="row">XP ${xp}/${xpNext} · $${credits} · Atk ${p.attack} Def ${p.defense} Hack ${p.hack}
        ${p.has_payload ? ' · <span class="ok">PAYLOAD</span>' : ""}</div>
    `;
    }
    if (objCompassEl) {
      if (obj) {
        objCompassEl.textContent = (obj.compass || "★") + " " + (obj.bearing || "") + (obj.dist != null ? " " + obj.dist : "");
        objCompassEl.title = obj.text || "Objective";
      } else {
        objCompassEl.textContent = "★ · —";
        objCompassEl.title = "Objective bearing";
      }
    }
    if (fpvPosEl && p) {
      fpvPosEl.textContent = (p.x != null ? p.x + "," + p.y : "") + " · t" + (s.tick != null ? s.tick : "");
    }
    if (miniPlaneEl) {
      miniPlaneEl.textContent = (s.plane || "STREET") + " · Z" + (p.z != null ? p.z : 0);
    }
    if (typeof playerListEl !== "undefined" && playerListEl) {
      const list = s.players || [];
      playerListEl.innerHTML = list
        .map((op) => {
          const you = op.id === s.you;
          return `<li><span class="pglyph" style="color:${escapeHtml(op.color || "#fff")}">${escapeHtml(
            op.glyph || "?"
          )}</span><span>${escapeHtml(op.name)}${you ? " YOU" : ""}</span></li>`;
        })
        .join("");
    }
    renderIrc(s);
    YearUI.apply(s);
    if (netHud && lastPingMs != null) {
      netHud.textContent = lastPingMs + "ms · " + (s.online_count || listLen(s)) + " online";
    }
    if (invEl) {
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
    }
    if (logEl) {
      logEl.innerHTML = (s.messages || []).map((m) => `<div>${escapeHtml(m)}</div>`).join("");
      logEl.scrollTop = logEl.scrollHeight;
    }

    if (!overlay) {
      /* no overlay node */
    } else if (s.mode === "help") {
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
    } else if (s.mode === "cyberspace") {
      invMode = false;
      const cyber = s.cyberspace || {};
      const rows = cyber.map || s.map || [];
      const body = Array.isArray(rows) ? rows.join("\n") : String(rows);
      const hint = cyber.hint || "Cyberspace node — grab loot, exit X, Esc jack_out.";
      const nt = cyber.node_type || "node";
      overlay.classList.remove("hidden");
      overlay.innerHTML = `<div class="box cyber-box"><div class="cyber-title">CYBERSPACE · ${escapeHtml(nt)}</div><pre class="cyber-map">${escapeHtml(body)}</pre><div class="dim">${escapeHtml(hint)}</div><div class="dim">Esc / jack_out · ice_probe stun|reveal melts I</div></div>`;
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
    // j handled below: jack_in near J / jack_out in node; else absolute south
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

    // Shift+J → quest journal (avoids clash with lowercase j jack-in)
    if (ev.key === "J") {
      ev.preventDefault();
      if (typeof YearUI !== "undefined" && YearUI.openPanel) YearUI.openPanel("journal");
      return;
    }
    // Cyberspace (#47): j jack_in at jackpoint · jack_out while jacked · else vim south
    if (ev.key === "j") {
      ev.preventDefault();
      if (state && state.mode === "cyberspace") {
        send("jack_out");
        return;
      }
      const cyber = (state && state.cyberspace) || {};
      if (cyber.can_jack_in) {
        send("jack_in");
        return;
      }
      send("s_abs");
      return;
    }

    // ICE probes (#46): z stun · x reveal · c scramble · p opens ICE dock
    if (ev.key === "p" || ev.key === "P") {
      ev.preventDefault();
      if (typeof YearUI !== "undefined" && YearUI.openPanel) YearUI.openPanel("ice");
      return;
    }
    if (ev.key === "z" || ev.key === "Z") {
      ev.preventDefault();
      send("ice_probe", "stun");
      return;
    }
    if (ev.key === "x" || ev.key === "X") {
      ev.preventDefault();
      send("ice_probe", "reveal");
      return;
    }
    if (ev.key === "c" || ev.key === "C") {
      ev.preventDefault();
      send("ice_probe", "scramble");
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
    try { YearUI.persistNick(); } catch (_) {}
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


  if (ircChannelsEl) {
    ircChannelsEl.addEventListener("click", (ev) => {
      const btn = ev.target && ev.target.closest ? ev.target.closest("[data-chan]") : null;
      if (!btn) return;
      const ch = btn.getAttribute("data-chan");
      if (!ch) return;
      Net.chat("/join " + ch);
    });
  }
  if (ircNicksEl) {
    ircNicksEl.addEventListener("dblclick", (ev) => {
      const li = ev.target && ev.target.closest ? ev.target.closest("li") : null;
      if (!li) return;
      const nick = (li.getAttribute("data-name") || "").trim();
      if (!nick || !chatInput) return;
      chatInput.value = "/msg " + nick + " ";
      chatInput.focus();
      chatFocused = true;
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

  YearUI.bind();
  boot();
})();
