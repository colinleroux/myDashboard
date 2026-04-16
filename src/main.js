import Alpine from "alpinejs";
import "./main.css";

window.Alpine = Alpine;
Alpine.start();

const html = document.documentElement;
const themeToggle = document.querySelector(".js-theme-toggle");

const applyTheme = (theme) => {
  html.setAttribute("data-theme", theme);
  localStorage.setItem("theme", theme);
  if (themeToggle) {
    themeToggle.textContent = theme === "dark" ? "Light mode" : "Dark mode";
  }
};

const initializeTheme = () => {
  const saved = localStorage.getItem("theme");
  if (saved === "dark" || saved === "light") {
    applyTheme(saved);
    return;
  }

  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(prefersDark ? "dark" : "light");
};

initializeTheme();

if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    const current = html.getAttribute("data-theme") === "dark" ? "dark" : "light";
    applyTheme(current === "dark" ? "light" : "dark");
  });
}

const closeDialog = (dialog) => {
  if (!dialog) return;
  dialog.close();
};

document.querySelectorAll(".js-open-site-modal").forEach((button) => {
  button.addEventListener("click", () => {
    const modalId = button.dataset.modalId;
    const dialog = document.getElementById(modalId);
    if (dialog && typeof dialog.showModal === "function") {
      dialog.showModal();
    }
  });
});

document.querySelectorAll(".js-close-site-modal").forEach((button) => {
  button.addEventListener("click", () => {
    closeDialog(button.closest("dialog"));
  });
});

document.querySelectorAll("dialog.site-modal").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    const box = dialog.querySelector(".site-modal-card");
    if (!box) return;
    const rect = box.getBoundingClientRect();
    const clickedOutside =
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom;
    if (clickedOutside) {
      dialog.close();
    }
  });
});

const createAssetPathRow = () => {
  const row = document.createElement("div");
  row.className = "asset-path-row";

  const input = document.createElement("input");
  input.name = "asset_paths";
  input.placeholder = "Asset path";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn-ghost js-remove-asset-path";
  button.textContent = "Remove";

  row.appendChild(input);
  row.appendChild(button);
  return row;
};

document.querySelectorAll(".js-asset-paths-group").forEach((group) => {
  const list = group.querySelector(".asset-paths-list");
  const addButton = group.querySelector(".js-add-asset-path");
  if (!list || !addButton) return;

  addButton.addEventListener("click", () => {
    list.appendChild(createAssetPathRow());
  });

  group.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (!target.classList.contains("js-remove-asset-path")) return;

    const row = target.closest(".asset-path-row");
    if (!row) return;

    const remainingRows = list.querySelectorAll(".asset-path-row");
    if (remainingRows.length <= 1) {
      const input = row.querySelector("input[name='asset_paths']");
      if (input) input.value = "";
      return;
    }

    row.remove();
  });
});
