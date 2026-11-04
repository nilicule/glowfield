"use strict";

/* Ambient night sky shared by every page: drifting fireflies and swaying grass. */
(function makeSky() {
  const sky = document.querySelector(".sky");
  for (let i = 0; i < 18; i++) {
    const dot = document.createElement("i");
    dot.style.left = `${Math.random() * 100}%`;
    dot.style.top = `${Math.random() * 100}%`;
    dot.style.setProperty("--dur", `${8 + Math.random() * 10}s`);
    dot.style.setProperty("--delay", `${-Math.random() * 15}s`);
    dot.style.setProperty("--dx", `${(Math.random() - 0.5) * 120}px`);
    dot.style.setProperty("--dy", `${(Math.random() - 0.5) * 120}px`);
    sky.appendChild(dot);
  }
  // Grass blades along the meadow, each swaying at its own pace.
  const grass = document.querySelector(".meadow .grass");
  const ns = "http://www.w3.org/2000/svg";
  for (let x = 0; x < 1200; x += 9 + Math.random() * 14) {
    const h = 18 + Math.random() * 34, lean = (Math.random() - 0.5) * 14;
    const base = 185 + Math.random() * 30;
    const blade = document.createElementNS(ns, "path");
    blade.setAttribute("d", `M${x} ${base} q${lean / 2} ${-h / 2} ${lean} ${-h} q${2 - lean / 2} ${h / 2} 3 ${h}z`);
    blade.style.setProperty("--d", `${2.5 + Math.random() * 3}s`);
    blade.style.animationDelay = `${-Math.random() * 5}s`;
    grass.appendChild(blade);
  }
})();
