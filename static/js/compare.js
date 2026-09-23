"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const STORAGE_KEY = "maritime-platform-compare-v1";
  const MAX_ITEMS = 4;
  const dock = document.querySelector("[data-compare-bar]");
  const toggles = document.querySelectorAll("[data-compare-toggle]");
  if (!dock && !toggles.length) return;

  const countNodes = document.querySelectorAll("[data-compare-count]");
  const navCompare = document.querySelector("[data-nav-compare]");
  const chips = dock?.querySelector("[data-compare-chips]");
  const message = dock?.querySelector("[data-compare-message]");
  const start = dock?.querySelector("[data-compare-start]");
  const clear = dock?.querySelector("[data-compare-clear]");
  const comparePage = document.querySelector("[data-compare-page]");

  const normalize = (value) => {
    if (!Array.isArray(value)) return [];
    const seen = new Set();
    return value.filter((item) => {
      const id = Number.parseInt(item?.id, 10);
      if (!Number.isInteger(id) || id < 1 || seen.has(id) || seen.size >= MAX_ITEMS) return false;
      seen.add(id);
      item.id = id;
      item.name = String(item.name || `平台 ${id}`).slice(0, 160);
      item.country = String(item.country || "").slice(0, 80);
      return true;
    });
  };

  const load = () => {
    try { return normalize(JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]")); }
    catch (_) { return []; }
  };
  let selected = load();
  let hydratedFromUrl = false;

  // A compare URL is shareable and authoritative. Server-rendered JSON only
  // contains ids and display labels for platform rows that actually exist.
  if (comparePage?.dataset.selectionAuthoritative === "true") {
    try {
      const payload = comparePage.querySelector("[data-compare-page-selection]")?.textContent || "[]";
      selected = normalize(JSON.parse(payload));
      hydratedFromUrl = true;
    } catch (_) { selected = []; }
  }

  const save = () => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(selected)); }
    catch (_) { /* The UI still works for the current page. */ }
  };
  if (hydratedFromUrl) save();

  const comparisonUrl = () => {
    if (!dock) return "/compare";
    const query = selected.length ? `?ids=${selected.map((item) => item.id).join(",")}` : "";
    return `${dock.dataset.compareUrl}${query}`;
  };
  const navigateIfComparePage = () => {
    if (!comparePage) return false;
    window.location.assign(comparisonUrl());
    return true;
  };

  const render = (status = "") => {
    const ids = new Set(selected.map((item) => item.id));
    countNodes.forEach((node) => { node.textContent = String(selected.length); });
    if (navCompare) navCompare.href = comparisonUrl();
    toggles.forEach((button) => {
      const active = ids.has(Number.parseInt(button.dataset.platformId, 10));
      button.classList.toggle("is-selected", active);
      button.setAttribute("aria-pressed", String(active));
      button.textContent = active ? "✓ 已加入对比" : "＋ 加入对比";
      if (button.closest(".compare-platform-head") && active) button.textContent = "移出对比";
    });
    if (!dock) return;
    dock.hidden = selected.length === 0;
    if (message) {
      message.textContent = status || (
        selected.length < 2 ? "再选择 1 个即可开始" :
          selected.length === MAX_ITEMS ? "已达到 4 个平台上限" : `可继续选择至 ${MAX_ITEMS} 个`
      );
    }
    if (chips) {
      chips.replaceChildren();
      selected.forEach((item) => {
        const chip = document.createElement("span");
        chip.className = "compare-chip";
        const label = document.createElement("span");
        label.textContent = item.name;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.textContent = "×";
        remove.setAttribute("aria-label", `从对比中移除 ${item.name}`);
        remove.addEventListener("click", () => {
          selected = selected.filter((candidate) => candidate.id !== item.id);
          save(); render(); navigateIfComparePage();
        });
        chip.append(label, remove);
        chips.append(chip);
      });
    }
    if (start) {
      const ready = selected.length >= 2;
      start.setAttribute("aria-disabled", String(!ready));
      if (ready) {
        start.href = comparisonUrl();
        start.removeAttribute("tabindex");
      } else {
        start.removeAttribute("href");
        start.setAttribute("tabindex", "-1");
      }
    }
  };

  toggles.forEach((button) => {
    button.addEventListener("click", () => {
      const id = Number.parseInt(button.dataset.platformId, 10);
      if (!Number.isInteger(id) || id < 1) return;
      const exists = selected.some((item) => item.id === id);
      if (exists) selected = selected.filter((item) => item.id !== id);
      else if (selected.length >= MAX_ITEMS) { render("最多同时比较 4 个平台"); return; }
      else selected.push({ id, name: button.dataset.platformName || `平台 ${id}`, country: button.dataset.platformCountry || "" });
      save(); render();
      if (button.closest(".compare-platform-head")) navigateIfComparePage();
    });
  });
  clear?.addEventListener("click", () => {
    selected = [];
    save(); render(); navigateIfComparePage();
  });
  render();
});
