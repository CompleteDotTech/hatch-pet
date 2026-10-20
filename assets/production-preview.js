/* Standalone local review: bounded image cache, exact indexing, no network API. */
"use strict";
(() => {
  const manifest = JSON.parse(document.getElementById("production-manifest").textContent);
  const $ = id => document.getElementById(id);
  const count = manifest.frames.length;
  const fps = manifest.fps.numerator / manifest.fps.denominator;
  const [width, height] = manifest.resolution;
  const canvas = $("canvas"), comparison = $("comparison"), audio = $("audio");
  const stage = document.createElement("canvas"), pinnedStage = document.createElement("canvas");
  for (const item of [canvas, comparison, stage, pinnedStage]) { item.width = width; item.height = height; }
  const state = {frame: 0, renderedFrame: -1, pinned: null, playing: false, epoch: 0, paintEpoch: 0,
    startFrame: 0, startTime: 0, animation: null, painting: false};
  const hidden = new Set();
  const images = new Map();
  const imageLimit = Math.max(1, Math.min(64, Math.floor(32 * 1024 * 1024 / (width * height * 4))));
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");

  function relativePath(path) {
    if (typeof path !== "string" || !path || path.startsWith("/") || /[\\:]/.test(path) || path.split("/").includes("..")) {
      throw new Error("Preview source path must remain inside this render directory.");
    }
    return path;
  }

  function imageFor(path) {
    path = relativePath(path);
    if (images.has(path)) {
      const retained = images.get(path); images.delete(path); images.set(path, retained); return retained;
    }
    const promise = new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("Could not load local rendered image: " + path));
      image.src = path;
    });
    images.set(path, promise);
    while (images.size > imageLimit) images.delete(images.keys().next().value);
    return promise;
  }

  async function compose(index, target) {
    const entry = manifest.frames[index], context = target.getContext("2d");
    context.clearRect(0, 0, width, height);
    context.globalAlpha = 1;
    if (!hidden.size) {
      context.drawImage(await imageFor(entry.path), 0, 0);
      return;
    }
    context.fillStyle = manifest.settings.background;
    context.fillRect(0, 0, width, height);
    for (const layer of entry.layers || []) {
      if (!hidden.has(layer.track)) context.drawImage(await imageFor(layer.path), 0, 0);
    }
  }

  function inspect(index) {
    const entry = manifest.frames[index];
    $("frame-number").value = index;
    $("scrubber").value = index;
    $("frame-label").textContent = `${index} / ${count - 1}`;
    $("caption").textContent = `Frame ${index} · ${(index / fps).toFixed(3)} s`;
    $("interval").textContent = `[${index * manifest.fps.denominator}/${manifest.fps.numerator}, ${(index + 1) * manifest.fps.denominator}/${manifest.fps.numerator}) seconds`;
    $("shot").textContent = `${entry.shot_id || manifest.shot_id || "—"} / ${entry.shot_frame ?? index}`;
    $("evidence").textContent = JSON.stringify({frame: index, sha256: entry.sha256,
      evaluation_sha256: entry.evaluation_sha256, sources: entry.sources,
      events: entry.events || {}, interactions: entry.interactions || []}, null, 2);
    const lines = (manifest.dialogue || []).filter(line => line.start_frame <= index && index < line.end_frame);
    $("dialogue").textContent = lines.map(line => `${line.speaker || "Audio"}: ${line.text}`).join(" · ");
  }

  async function paint() {
    if (state.painting || !count) return;
    state.painting = true;
    try {
      let completed;
      do {
        const epoch = state.paintEpoch, index = state.frame, pinned = state.pinned;
        const mode = $("comparison-mode").value;
        await compose(index, stage);
        if (pinned !== null && mode !== "off") await compose(pinned, pinnedStage);
        if (epoch !== state.paintEpoch) continue;
        const context = canvas.getContext("2d");
        context.clearRect(0, 0, width, height); context.globalAlpha = 1; context.drawImage(stage, 0, 0);
        if (pinned !== null && mode === "onion") {
          context.globalAlpha = .45; context.drawImage(pinnedStage, 0, 0); context.globalAlpha = 1;
        }
        $("comparison-panel").hidden = pinned === null || mode !== "side";
        if (pinned !== null && mode === "side") {
          const other = comparison.getContext("2d"); other.clearRect(0, 0, width, height); other.drawImage(pinnedStage, 0, 0);
          $("comparison-caption").textContent = `Pinned frame ${pinned} · ${(pinned / fps).toFixed(3)} s`;
        }
        state.renderedFrame = index;
        inspect(index);
        completed = epoch;
      } while (completed !== state.paintEpoch);
      $("error").textContent = "";
    } catch (error) { $("error").textContent = error.message; pause(); }
    finally { state.painting = false; }
  }

  function requestPaint() { state.paintEpoch++; void paint(); }
  function clamp(value) { return Math.max(0, Math.min(count - 1, Math.trunc(Number(value) || 0))); }
  function pause() {
    state.epoch++; state.playing = false;
    cancelAnimationFrame(state.animation); audio.pause(); $("play").textContent = "Play";
  }
  function setFrame(value) { state.frame = clamp(value); requestPaint(); }

  async function seekAudio(seconds, epoch) {
    if (!manifest.audio) return;
    // Metadata-only loading may advertise an empty seekable interval even when
    // the WAV is buffered. Request audio data after the user enables sound.
    if (audio.preload !== "auto") { audio.preload = "auto"; audio.load(); }
    if (audio.readyState === 0) {
      await new Promise((resolve, reject) => {
        const finish = () => { audio.removeEventListener("loadedmetadata", ready); audio.removeEventListener("error", failed); clearTimeout(timer); };
        const ready = () => { finish(); resolve(); };
        const failed = () => { finish(); reject(new Error("Could not load the local PCM WAV.")); };
        const timer = setTimeout(failed, 5000);
        audio.addEventListener("loadedmetadata", ready); audio.addEventListener("error", failed);
        audio.load();
      });
    }
    if (epoch !== state.epoch) return;
    const seekable = () => seconds === 0 || Array.from({length: audio.seekable.length}, (_, index) =>
      audio.seekable.start(index) <= seconds && audio.seekable.end(index) >= seconds).some(Boolean);
    if (!seekable()) {
      await new Promise((resolve, reject) => {
        const events = ["progress", "canplay", "canplaythrough", "durationchange", "loadeddata"];
        const finish = () => { for (const name of events) audio.removeEventListener(name, ready); clearTimeout(timer); };
        const ready = () => { if (epoch !== state.epoch || seekable()) { finish(); resolve(); } };
        const timer = setTimeout(() => { finish(); reject(new Error("Local audio is not seekable yet; try again after it loads.")); }, 5000);
        for (const name of events) audio.addEventListener(name, ready);
        ready();
      });
    }
    if (epoch !== state.epoch) return;
    if (Math.abs(audio.currentTime - seconds) < 0.000001 && !audio.seeking) return;
    await new Promise((resolve, reject) => {
      const finish = () => { audio.removeEventListener("seeked", ready); clearTimeout(timer); };
      const ready = () => { finish(); resolve(); };
      const timer = setTimeout(() => { finish(); reject(new Error("Audio seek did not complete; disable audio to inspect frames.")); }, 5000);
      audio.addEventListener("seeked", ready);
      audio.currentTime = seconds;
    });
    if (epoch === state.epoch && Math.abs(audio.currentTime - seconds) > .002) {
      throw new Error("The browser could not seek to the requested audio time.");
    }
  }

  function seek(value) {
    pause(); setFrame(value);
    const epoch = state.epoch;
    if ($("audio-enabled").checked) void seekAudio(state.frame / fps, epoch).catch(error => {
      if (epoch === state.epoch) $("error").textContent = error.message;
    });
  }
  function tick(now) {
    if (!state.playing) return;
    // Only this loop reads the audio clock. Native asynchronous seeking cannot
    // overwrite a paused scrub position or replay a stale seek event.
    const next = $("audio-enabled").checked
      ? (audio.seeking ? state.frame : Math.floor(audio.currentTime * fps + 1e-7))
      : state.startFrame + Math.floor((now - state.startTime) * fps / 1000);
    if (next >= count) { setFrame(count - 1); pause(); return; }
    if (next !== state.frame) setFrame(next);
    state.animation = requestAnimationFrame(tick);
  }
  async function play() {
    if (state.playing) { pause(); return; }
    if (state.frame === count - 1) setFrame(0);
    const epoch = ++state.epoch;
    try {
      if ($("audio-enabled").checked) {
        await seekAudio(state.frame / fps, epoch);
        if (epoch !== state.epoch) return;
        await audio.play();
        if (epoch !== state.epoch) { audio.pause(); return; }
      }
      state.playing = true; state.startFrame = state.frame; state.startTime = performance.now();
      $("play").textContent = "Pause"; state.animation = requestAnimationFrame(tick);
    } catch (error) { if (epoch === state.epoch) { pause(); $("error").textContent = error.message; } }
  }
  function pin() {
    state.pinned = state.frame;
    if ($("comparison-mode").value === "off") $("comparison-mode").value = "side";
    requestPaint();
  }

  $("title").textContent = `${manifest.scene_id || manifest.shot_id || "Production"} · local review`;
  $("origin").textContent = manifest.fixture ? "Synthetic regression fixture" : "Production source artwork";
  $("fps").textContent = `${manifest.fps.numerator}/${manifest.fps.denominator} fps`;
  $("resolution").textContent = `${width} × ${height} · sRGB · straight RGBA`;
  $("render-status").textContent = `${manifest.status} · ${count}/${manifest.frame_count} frames`;
  $("status").textContent = reduced.matches ? "Reduced motion preference respected: playback starts only when you press Play." : "Use the arrow keys to step. Playback starts only when you press Play.";
  $("frame-number").max = count - 1; $("scrubber").max = count - 1;
  if (manifest.audio) audio.src = relativePath(manifest.audio.path);
  else $("audio-enabled").disabled = true;
  const tracks = [...new Set(manifest.frames.flatMap(frame => (frame.layers || []).map(layer => layer.track)))];
  for (const track of tracks) {
    const label = document.createElement("label"), input = document.createElement("input");
    input.type = "checkbox"; input.checked = true; input.dataset.track = track;
    input.addEventListener("change", () => { input.checked ? hidden.delete(track) : hidden.add(track); requestPaint(); });
    label.append(input, document.createTextNode(track)); $("tracks").append(label);
  }
  $("previous").addEventListener("click", () => seek(state.frame - 1));
  $("next").addEventListener("click", () => seek(state.frame + 1));
  $("frame-number").addEventListener("change", event => seek(event.target.value));
  $("scrubber").addEventListener("input", event => seek(event.target.value));
  $("play").addEventListener("click", () => void play()); $("pin").addEventListener("click", pin);
  $("comparison-mode").addEventListener("change", () => { if (state.pinned === null) state.pinned = state.frame; requestPaint(); });
  $("audio-enabled").addEventListener("change", () => pause());
  audio.addEventListener("ended", () => { setFrame(count - 1); pause(); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
  document.addEventListener("keydown", event => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(event.target.tagName)) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); seek(state.frame + (event.key === "ArrowLeft" ? -1 : 1)); }
  });
  window.hatchPreview = {manifest, seek, pin, pause, play,
    get frame() { return state.frame; }, get renderedFrame() { return state.renderedFrame; },
    get playing() { return state.playing; }, get pinned() { return state.pinned; },
    get cachedImages() { return images.size; }};
  if (!count) { $("error").textContent = "No rendered frames are available. Resume the render first."; $("play").disabled = true; }
  else requestPaint();
})();
