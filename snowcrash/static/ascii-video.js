/**
 * VideoAsciiCanvas — high-fidelity video→colored-ASCII for Snowcrash.
 * Samples each video frame onto an offscreen canvas, maps luminance to a dense
 * charset, and paints each glyph with the source pixel's RGB color.
 *
 * Inspired by the general approach of canvas-based ASCII video renderers
 * (e.g. react-video-ascii / asciify-engine style), vanilla JS — no React.
 */
(function (global) {
  "use strict";

  const DEFAULT_CHARSET =
    " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$";

  class VideoAsciiCanvas {
    /**
     * @param {HTMLCanvasElement} canvas
     * @param {object} [opts]
     */
    constructor(canvas, opts = {}) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d", { alpha: false });
      this.cols = opts.cols || 160;
      this.charset = opts.charset || DEFAULT_CHARSET;
      this.brightness = opts.brightness != null ? opts.brightness : 1.15;
      this.contrast = opts.contrast != null ? opts.contrast : 1.1;
      this.fontFamily = opts.fontFamily || '"JetBrains Mono","Fira Code",ui-monospace,monospace';
      this.bg = opts.bg || "#05080c";
      this.autoColor = opts.autoColor !== false;
      this.monoColor = opts.monoColor || "#39c5cf";
      this.fit = opts.fit !== false;

      this._video = document.createElement("video");
      this._video.muted = true;
      this._video.playsInline = true;
      this._video.preload = "auto";
      this._video.setAttribute("playsinline", "");
      this._video.setAttribute("muted", "");
      this._video.crossOrigin = "anonymous";

      this._sample = document.createElement("canvas");
      this._sctx = this._sample.getContext("2d", {
        willReadFrequently: true,
        alpha: false,
      });

      this._raf = 0;
      this._running = false;
      this._onEnded = null;
      this._charW = 8;
      this._charH = 12;
      this._rows = 40;

      this._onVideoEnded = () => {
        if (typeof this._onEnded === "function") this._onEnded();
      };
      this._video.addEventListener("ended", this._onVideoEnded);
    }

    get video() {
      return this._video;
    }

    get playing() {
      return this._running && !this._video.paused && !this._video.ended;
    }

    /**
     * Load a video URL (mp4). Resolves when enough data is ready.
     * @param {string} url
     * @returns {Promise<void>}
     */
    load(url) {
      return new Promise((resolve, reject) => {
        const v = this._video;
        const onReady = () => {
          cleanup();
          this._resizeSample();
          resolve();
        };
        const onErr = () => {
          cleanup();
          reject(new Error("Failed to load video: " + url));
        };
        const cleanup = () => {
          v.removeEventListener("loadeddata", onReady);
          v.removeEventListener("error", onErr);
        };
        v.addEventListener("loadeddata", onReady);
        v.addEventListener("error", onErr);
        v.loop = false;
        v.src = url;
        v.load();
      });
    }

    setCols(cols) {
      this.cols = Math.max(40, Math.min(240, cols | 0));
      this._resizeSample();
    }

    _resizeSample() {
      const v = this._video;
      const vw = v.videoWidth || 640;
      const vh = v.videoHeight || 360;
      const aspect = vw / Math.max(1, vh);
      // monospace glyphs are taller than wide — compensate so image isn't stretched
      const cellAspect = 0.55;
      this._rows = Math.max(20, Math.round(this.cols / aspect * cellAspect));
      this._sample.width = this.cols;
      this._sample.height = this._rows;

      if (this.fit && this.canvas.parentElement) {
        const pw = this.canvas.parentElement.clientWidth || window.innerWidth;
        const ph = this.canvas.parentElement.clientHeight || window.innerHeight;
        this.canvas.width = pw;
        this.canvas.height = ph;
      } else if (!this.canvas.width || !this.canvas.height) {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
      }

      this._charW = this.canvas.width / this.cols;
      this._charH = this.canvas.height / this._rows;
      const fontSize = Math.max(6, Math.floor(Math.min(this._charW / cellAspect, this._charH) * 0.95));
      this._fontSize = fontSize;
      this.ctx.font = `${fontSize}px ${this.fontFamily}`;
      this.ctx.textBaseline = "top";
      this.ctx.textAlign = "left";
    }

    /**
     * @param {{ onEnded?: function }} [opts]
     */
    async play(opts = {}) {
      this._onEnded = opts.onEnded || null;
      this._resizeSample();
      this._running = true;
      try {
        this._video.currentTime = 0;
        await this._video.play();
      } catch (err) {
        // Autoplay may require a gesture; still start the draw loop
        console.warn("VideoAsciiCanvas play()", err);
      }
      this._loop();
    }

    pause() {
      this._video.pause();
    }

    stop() {
      this._running = false;
      if (this._raf) {
        cancelAnimationFrame(this._raf);
        this._raf = 0;
      }
      try {
        this._video.pause();
        this._video.currentTime = 0;
      } catch (_) {}
      this._clear();
    }

    destroy() {
      this.stop();
      this._video.removeEventListener("ended", this._onVideoEnded);
      this._video.removeAttribute("src");
      this._video.load();
    }

    _clear() {
      this.ctx.fillStyle = this.bg;
      this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    _loop = () => {
      if (!this._running) return;
      this._drawFrame();
      this._raf = requestAnimationFrame(this._loop);
    };

    _drawFrame() {
      const v = this._video;
      if (!v.videoWidth) return;

      const cols = this.cols;
      const rows = this._rows;
      const sctx = this._sctx;
      sctx.drawImage(v, 0, 0, cols, rows);
      let data;
      try {
        data = sctx.getImageData(0, 0, cols, rows).data;
      } catch (err) {
        return;
      }

      const ctx = this.ctx;
      const cw = this._charW;
      const ch = this._charH;
      const set = this.charset;
      const setLen = set.length;
      const bright = this.brightness;
      const contrast = this.contrast;
      const auto = this.autoColor;

      ctx.fillStyle = this.bg;
      ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
      ctx.font = `${this._fontSize}px ${this.fontFamily}`;
      ctx.textBaseline = "top";

      // Batch by color when possible is hard; per-glyph fillStyle is fine at ~160×50
      for (let y = 0; y < rows; y++) {
        const py = y * ch;
        for (let x = 0; x < cols; x++) {
          const i = (y * cols + x) * 4;
          let r = data[i];
          let g = data[i + 1];
          let b = data[i + 2];
          // contrast + brightness
          r = Math.min(255, Math.max(0, (r - 128) * contrast + 128) * bright);
          g = Math.min(255, Math.max(0, (g - 128) * contrast + 128) * bright);
          b = Math.min(255, Math.max(0, (b - 128) * contrast + 128) * bright);
          const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
          const idx = Math.min(setLen - 1, Math.floor(lum * setLen));
          const glyph = set[idx];
          if (glyph === " ") continue;
          if (auto) {
            ctx.fillStyle = `rgb(${r | 0},${g | 0},${b | 0})`;
          } else {
            ctx.fillStyle = this.monoColor;
          }
          ctx.fillText(glyph, x * cw, py);
        }
      }
    }
  }

  global.VideoAsciiCanvas = VideoAsciiCanvas;
})(typeof window !== "undefined" ? window : globalThis);
