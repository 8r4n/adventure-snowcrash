/**
 * Shared high-fidelity canvas→colored-ASCII for Snowcrash.
 * Samples luminance to a dense charset and paints each glyph with source RGB.
 * Sources: <video>, Canvas, or ImageData — used by intro, live FPV, and cutscenes.
 */
(function (global) {
  "use strict";

  const DEFAULT_CHARSET =
    " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$";

  /**
   * Core ASCII sampler — draws colored glyphs onto a display canvas.
   */
  class AsciiRenderer {
    /**
     * @param {HTMLCanvasElement} canvas
     * @param {object} [opts]
     */
    constructor(canvas, opts = {}) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d", { alpha: false });
      this.cols = opts.cols || 160;
      this.charset = opts.charset || DEFAULT_CHARSET;
      this.brightness = opts.brightness != null ? opts.brightness : 1.28;
      this.contrast = opts.contrast != null ? opts.contrast : 1.35;
      // <1 lifts dark midtones into denser glyphs (readability on neon scenes)
      this.gamma = opts.gamma != null ? opts.gamma : 0.82;
      // >1 punches chroma toward neon without washing luminance
      this.saturate = opts.saturate != null ? opts.saturate : 1.35;
      this.fontFamily =
        opts.fontFamily || '"JetBrains Mono","Fira Code",ui-monospace,monospace';
      this.bg = opts.bg || "#03060a";
      this.autoColor = opts.autoColor !== false;
      this.monoColor = opts.monoColor || "#5cf0ff";
      this.fit = opts.fit !== false;
      this.cellAspect = opts.cellAspect != null ? opts.cellAspect : 0.55;

      this._sample = document.createElement("canvas");
      this._sctx = this._sample.getContext("2d", {
        willReadFrequently: true,
        alpha: false,
      });

      this._charW = 8;
      this._charH = 12;
      this._rows = 40;
      this._fontSize = 10;
      this._sourceCanvas = null;
      this._sourceAspect = 16 / 9;
    }

    /**
     * @param {number} cols
     */
    setCols(cols) {
      this.cols = Math.max(40, Math.min(240, cols | 0));
      this._resizeSample();
    }

    /**
     * Bind an external canvas as the continuous sample source (e.g. FPV scene).
     * @param {HTMLCanvasElement|null} canvas
     */
    setSourceCanvas(canvas) {
      this._sourceCanvas = canvas || null;
      if (canvas && canvas.width && canvas.height) {
        this._sourceAspect = canvas.width / Math.max(1, canvas.height);
      }
      this._resizeSample();
    }

    /**
     * Resize sample grid from a known pixel size (video or canvas).
     * @param {number} [srcW]
     * @param {number} [srcH]
     */
    resizeForSource(srcW, srcH) {
      if (srcW && srcH) {
        this._sourceAspect = srcW / Math.max(1, srcH);
      }
      this._resizeSample();
    }

    _resizeSample() {
      const aspect = this._sourceAspect || 16 / 9;
      const cellAspect = this.cellAspect;
      this._rows = Math.max(20, Math.round((this.cols / aspect) * cellAspect));
      this._sample.width = this.cols;
      this._sample.height = this._rows;

      if (this.fit && this.canvas.parentElement) {
        const pw = this.canvas.parentElement.clientWidth || window.innerWidth;
        const ph = this.canvas.parentElement.clientHeight || window.innerHeight;
        this.canvas.width = Math.max(1, pw);
        this.canvas.height = Math.max(1, ph);
      } else if (!this.canvas.width || !this.canvas.height) {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
      }

      this._charW = this.canvas.width / this.cols;
      this._charH = this.canvas.height / this._rows;
      const fontSize = Math.max(
        6,
        Math.floor(Math.min(this._charW / cellAspect, this._charH) * 0.95)
      );
      this._fontSize = fontSize;
      this.ctx.font = `${fontSize}px ${this.fontFamily}`;
      this.ctx.textBaseline = "top";
      this.ctx.textAlign = "left";
    }

    clear() {
      this.ctx.fillStyle = this.bg;
      this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    /**
     * Sample an ImageData (or Uint8ClampedArray + w/h) and paint glyphs.
     * @param {ImageData|{data:Uint8ClampedArray,width:number,height:number}} imageData
     */
    renderFromImageData(imageData) {
      if (!imageData || !imageData.data) return;
      const srcW = imageData.width;
      const srcH = imageData.height;
      if (!srcW || !srcH) return;

      // Ensure sample grid matches intended cols; blit via temp if sizes differ
      if (this._sample.width !== this.cols || this._sample.height !== this._rows) {
        this._resizeSample();
      }

      let data;
      let cols = this.cols;
      let rows = this._rows;

      if (srcW === cols && srcH === rows) {
        data = imageData.data;
      } else {
        // Draw into sample canvas then re-read at grid resolution
        const tmp = document.createElement("canvas");
        tmp.width = srcW;
        tmp.height = srcH;
        const tctx = tmp.getContext("2d", { willReadFrequently: true, alpha: false });
        tctx.putImageData(
          imageData instanceof ImageData
            ? imageData
            : new ImageData(imageData.data, srcW, srcH),
          0,
          0
        );
        this._sctx.drawImage(tmp, 0, 0, cols, rows);
        try {
          data = this._sctx.getImageData(0, 0, cols, rows).data;
        } catch (_) {
          return;
        }
      }

      this._paintGlyphs(data, cols, rows);
    }

    /**
     * Sample any canvas/video/image drawable and paint glyphs.
     * @param {CanvasImageSource} source
     * @param {number} [srcW]
     * @param {number} [srcH]
     */
    renderFromCanvas(source, srcW, srcH) {
      if (!source) return;
      const w =
        srcW ||
        source.videoWidth ||
        source.naturalWidth ||
        source.width ||
        0;
      const h =
        srcH ||
        source.videoHeight ||
        source.naturalHeight ||
        source.height ||
        0;
      if (w && h) {
        this._sourceAspect = w / Math.max(1, h);
      }
      if (
        this._sample.width !== this.cols ||
        this._sample.height !== this._rows ||
        !this._fontSize
      ) {
        this._resizeSample();
      }

      const cols = this.cols;
      const rows = this._rows;
      const sctx = this._sctx;
      sctx.drawImage(source, 0, 0, cols, rows);
      let data;
      try {
        data = sctx.getImageData(0, 0, cols, rows).data;
      } catch (_) {
        return;
      }
      this._paintGlyphs(data, cols, rows);
    }

    /**
     * Re-sample the bound source canvas (setSourceCanvas).
     */
    renderSource() {
      if (!this._sourceCanvas) return;
      this.renderFromCanvas(this._sourceCanvas);
    }

    /**
     * @param {Uint8ClampedArray} data
     * @param {number} cols
     * @param {number} rows
     */
    _paintGlyphs(data, cols, rows) {
      const ctx = this.ctx;
      const cw = this._charW;
      const ch = this._charH;
      const set = this.charset;
      const setLen = set.length;
      const bright = this.brightness;
      const contrast = this.contrast;
      const gamma = this.gamma > 0 ? this.gamma : 1;
      const sat = this.saturate != null ? this.saturate : 1;
      const auto = this.autoColor;

      ctx.fillStyle = this.bg;
      ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
      ctx.font = `${this._fontSize}px ${this.fontFamily}`;
      ctx.textBaseline = "top";

      for (let y = 0; y < rows; y++) {
        const py = y * ch;
        for (let x = 0; x < cols; x++) {
          const i = (y * cols + x) * 4;
          let r = data[i];
          let g = data[i + 1];
          let b = data[i + 2];
          r = Math.min(255, Math.max(0, ((r - 128) * contrast + 128) * bright));
          g = Math.min(255, Math.max(0, ((g - 128) * contrast + 128) * bright));
          b = Math.min(255, Math.max(0, ((b - 128) * contrast + 128) * bright));
          if (sat !== 1) {
            const gray = 0.2126 * r + 0.7152 * g + 0.0722 * b;
            r = Math.min(255, Math.max(0, gray + (r - gray) * sat));
            g = Math.min(255, Math.max(0, gray + (g - gray) * sat));
            b = Math.min(255, Math.max(0, gray + (b - gray) * sat));
          }
          let lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
          if (gamma !== 1) lum = Math.pow(Math.max(0, Math.min(1, lum)), gamma);
          // Bias away from empty space so dim walls still draw a glyph
          const idx = Math.min(
            setLen - 1,
            Math.max(lum > 0.02 ? 1 : 0, Math.floor(lum * setLen))
          );
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

    /**
     * Factory: AsciiRenderer bound to a display canvas, sampling from a scene canvas.
     * @param {HTMLCanvasElement} displayCanvas
     * @param {HTMLCanvasElement} sourceCanvas
     * @param {object} [opts]
     */
    static fromCanvas(displayCanvas, sourceCanvas, opts = {}) {
      const r = new AsciiRenderer(displayCanvas, opts);
      r.setSourceCanvas(sourceCanvas);
      return r;
    }
  }

  /**
   * Video-driven ASCII player (intro / cutscene MP4s).
   * Also accepts setSourceCanvas / renderFromImageData for live FPV.
   */
  class VideoAsciiCanvas {
    /**
     * @param {HTMLCanvasElement} canvas
     * @param {object} [opts]
     */
    constructor(canvas, opts = {}) {
      this.canvas = canvas;
      this._renderer = new AsciiRenderer(canvas, opts);
      this.cols = this._renderer.cols;
      this.charset = this._renderer.charset;
      this.brightness = this._renderer.brightness;
      this.contrast = this._renderer.contrast;
      this.gamma = this._renderer.gamma;
      this.saturate = this._renderer.saturate;
      this.fontFamily = this._renderer.fontFamily;
      this.bg = this._renderer.bg;
      this.autoColor = this._renderer.autoColor;
      this.monoColor = this._renderer.monoColor;
      this.fit = this._renderer.fit;

      this._video = document.createElement("video");
      this._video.muted = true;
      this._video.playsInline = true;
      this._video.preload = "auto";
      this._video.setAttribute("playsinline", "");
      this._video.setAttribute("muted", "");
      this._video.crossOrigin = "anonymous";

      this._raf = 0;
      this._running = false;
      this._onEnded = null;
      this._mode = "idle"; // idle | video | canvas

      this._onVideoEnded = () => {
        if (typeof this._onEnded === "function") this._onEnded();
      };
      this._video.addEventListener("ended", this._onVideoEnded);
    }

    get video() {
      return this._video;
    }

    get renderer() {
      return this._renderer;
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
          this._renderer.resizeForSource(v.videoWidth, v.videoHeight);
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
      this._renderer.setCols(this.cols);
    }

    /**
     * Bind an offscreen/scene canvas as continuous ASCII source (live FPV).
     * @param {HTMLCanvasElement|null} canvas
     */
    setSourceCanvas(canvas) {
      this._renderer.setSourceCanvas(canvas);
      this._mode = canvas ? "canvas" : this._mode;
    }

    /**
     * One-shot render from ImageData through the shared sampler.
     * @param {ImageData} imageData
     */
    renderFromImageData(imageData) {
      if (imageData && imageData.width && imageData.height) {
        this._renderer.resizeForSource(imageData.width, imageData.height);
      }
      this._renderer.renderFromImageData(imageData);
    }

    /**
     * One-shot render from a canvas drawable.
     * @param {CanvasImageSource} source
     */
    renderFromCanvas(source) {
      this._renderer.renderFromCanvas(source);
    }

    /**
     * @param {{ onEnded?: function }} [opts]
     */
    async play(opts = {}) {
      this._onEnded = opts.onEnded || null;
      this._mode = "video";
      this._renderer.resizeForSource(
        this._video.videoWidth,
        this._video.videoHeight
      );
      this._running = true;
      try {
        this._video.currentTime = 0;
        await this._video.play();
      } catch (err) {
        console.warn("VideoAsciiCanvas play()", err);
      }
      this._loop();
    }

    /**
     * Start a continuous rAF loop sampling the bound source canvas.
     * @param {{ onFrame?: function }} [opts]
     */
    startCanvasLoop(opts = {}) {
      this._onEnded = null;
      this._mode = "canvas";
      this._running = true;
      this._onFrame = opts.onFrame || null;
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
      this._renderer.clear();
      this._mode = "idle";
    }

    destroy() {
      this.stop();
      this._video.removeEventListener("ended", this._onVideoEnded);
      this._video.removeAttribute("src");
      this._video.load();
    }

    _loop = () => {
      if (!this._running) return;
      this._drawFrame();
      this._raf = requestAnimationFrame(this._loop);
    };

    _drawFrame() {
      if (this._mode === "canvas") {
        if (typeof this._onFrame === "function") this._onFrame();
        this._renderer.renderSource();
        return;
      }
      // video mode
      const v = this._video;
      if (!v.videoWidth) return;
      this._renderer.renderFromCanvas(v, v.videoWidth, v.videoHeight);
    }
  }

  global.AsciiRenderer = AsciiRenderer;
  global.VideoAsciiCanvas = VideoAsciiCanvas;
})(typeof window !== "undefined" ? window : globalThis);
