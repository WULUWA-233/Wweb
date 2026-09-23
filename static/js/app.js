"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;

  const navToggle = document.querySelector("[data-nav-toggle]");
  const nav = document.getElementById("primary-nav");
  if (navToggle && nav) {
    navToggle.addEventListener("click", () => {
      const open = nav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", String(open));
    });
  }

  const drawer = document.querySelector("[data-filter-drawer]");
  const filterOpen = document.querySelector("[data-filter-open]");
  const filterClose = drawer ? drawer.querySelectorAll("[data-filter-close]") : [];
  let previousFocus = null;
  const openDrawer = () => {
    if (!drawer) return;
    previousFocus = document.activeElement;
    drawer.hidden = false;
    body.classList.add("has-overlay");
    filterOpen?.setAttribute("aria-expanded", "true");
    drawer.querySelector(".filter-drawer-panel [data-filter-close]")?.focus();
  };
  const closeDrawer = () => {
    if (!drawer) return;
    drawer.hidden = true;
    body.classList.remove("has-overlay");
    filterOpen?.setAttribute("aria-expanded", "false");
    if (previousFocus instanceof HTMLElement) previousFocus.focus();
  };
  filterOpen?.addEventListener("click", openDrawer);
  filterClose.forEach((button) => button.addEventListener("click", closeDrawer));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && drawer && !drawer.hidden) closeDrawer();
    if (event.key === "Tab" && drawer && !drawer.hidden) {
      const focusable = [...drawer.querySelectorAll(".filter-drawer-panel button:not([disabled]), .filter-drawer-panel a[href], .filter-drawer-panel input:not([type='hidden']):not([disabled])")]
        .filter((element) => element.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });

  document.querySelectorAll("img[data-image-fallback]").forEach((image) => {
    image.addEventListener("error", () => {
      const fallback = image.dataset.imageFallback;
      if (fallback && image.src !== new URL(fallback, window.location.href).href) image.src = fallback;
    });
  });

  document.querySelectorAll("[data-gallery]").forEach((gallery) => {
    const main = gallery.querySelector("[data-gallery-main]");
    const caption = gallery.querySelector("[data-gallery-caption]");
    const source = gallery.querySelector("[data-gallery-source]");
    const thumbs = gallery.querySelectorAll("[data-gallery-thumb]");
    thumbs.forEach((thumb) => {
      thumb.addEventListener("click", () => {
        if (!main) return;
        main.src = thumb.dataset.src || main.src;
        main.alt = thumb.dataset.alt || main.alt;
        if (caption) caption.textContent = thumb.dataset.caption || "平台图片";
        if (source) {
          const sourceUrl = thumb.dataset.sourceUrl || "";
          source.hidden = !sourceUrl;
          if (sourceUrl) {
            source.href = sourceUrl;
            source.textContent = `${thumb.dataset.sourceName || "查看图片来源"} ↗`;
          }
        }
        thumbs.forEach((item) => {
          const active = item === thumb;
          item.classList.toggle("is-active", active);
          item.setAttribute("aria-pressed", String(active));
        });
      });
    });
  });
});
