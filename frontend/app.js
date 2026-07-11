"use strict";

const state = {
  auth: false,
  me: null,
  clients: [],
  client_id: "",
  all_sites: [],
  sites: [],
  entries: [],
  vendors: [],
  vendor_txns: [],
  expenses: [],
  materials: [],
  labourers: [],
  labour_payments: [],
  receipts: [],
};

// Filtered datasets kept for CSV export (set during each render)
const FILTERED = {
  material: [], labour: [], labourPay: [],
  vendorTxn: [], payments: [], receipts: [],
};

// ── API helpers ──────────────────────────────────────────────────────────
async function errorFrom(res) {
  try {
    const body = await res.json();
    return new Error(body.error || `Request failed (${res.status})`);
  } catch {
    return new Error(`Request failed (${res.status})`);
  }
}

function showLogin() {
  document.getElementById("loading").hidden = true;
  document.getElementById("app").hidden = true;
  document.getElementById("emptyState").hidden = true;
  const scr = document.getElementById("loginScreen");
  if (scr.hidden) {
    scr.hidden = false;
    scr.querySelector("input").focus();
  }
}

async function apiFetch(url, options) {
  const res = await fetch(url, options);
  if (res.ok) return res.json();
  const err = await errorFrom(res);
  if (res.status === 401) {
    err.authRequired = true;
    if (!url.includes("/login")) showLogin();
  }
  throw err;
}

const JSON_HEADERS = { "Content-Type": "application/json" };
const apiGet    = (url) => apiFetch(url);
const apiPost   = (url, payload) => apiFetch(url, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(payload) });
const apiPut    = (url, payload) => apiFetch(url, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(payload) });
const apiDelete = (url) => apiFetch(url, { method: "DELETE" });

// ── Small utilities ──────────────────────────────────────────────────────
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fmtQty(n) {
  return (Number(n) || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function fmtMoney(n) {
  return "₹" + (Number(n) || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function val(id) { return document.getElementById(id)?.value || ""; }

function inRange(date, from, to) {
  if (from && date < from) return false;
  if (to && date > to) return false;
  return true;
}

function currentMonthKey() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function monthLabel() {
  return new Date().toLocaleString("en-IN", { month: "long", year: "numeric" });
}

const TRASH_BTN = (attr, id) =>
  `<button class="btn-icon-danger" title="Delete" aria-label="Delete" ${attr}="${id}"><svg class="icon"><use href="#i-trash"/></svg></button>`;

const EDIT_BTN = (attr, id) =>
  `<button class="btn-icon-edit" title="Edit" aria-label="Edit" ${attr}="${id}"><svg class="icon"><use href="#i-edit"/></svg></button>`;

const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const TAB_META = {
  dashboard: ["Dashboard", "Poore kaam ka ek nazar mein summary"],
  clients:   ["Client Management", "Clients add/edit karo aur unki sites ka hisaab rakho"],
  sites:     ["Site Management", "Har client ki sites ka master record"],
  material:  ["Material Tracking", "Purchase, transfer, consumption aur live stock"],
  assets:    ["Assets Tracking", "Machinery aur equipment ka location-wise register"],
  labour:    ["Labour Management", "Labour register, site-wise filter aur payments"],
  vendors:   ["Vendor Payments", "Vendor master, bills, payments aur closing balance"],
  expenses:  ["Site Expenses", "Har site ka category-wise kharcha"],
  payments:  ["Payment Register", "Saare outgoing payments ek jagah"],
  receipts:  ["Receipt Register", "Saare incoming payments ka hisaab"],
  admin:     ["Admin Panel", "Users, roles, permissions aur audit log"],
};

function updatePageHeader(tab) {
  const [title, subtitle] = TAB_META[tab] || TAB_META.dashboard;
  document.getElementById("pageTitle").textContent = title;
  document.getElementById("pageSubtitle").textContent = subtitle;
}

function emptyRow(colspan, message) {
  return `<tr class="empty-row"><td colspan="${colspan}">
    <div class="empty-cell"><svg class="icon"><use href="#i-inbox"/></svg><span>${escapeHtml(message)}</span></div>
  </td></tr>`;
}

// Animated count-up for stat values
function setStat(id, value, money = false) {
  const el = document.getElementById(id);
  if (!el) return;
  const fmt = (v) => (money ? fmtMoney(v) : fmtQty(Math.round(v)));
  const prev = parseFloat(el.dataset.v || "0");
  el.dataset.v = value;
  if (REDUCED_MOTION || prev === value) { el.textContent = fmt(value); return; }
  const t0 = performance.now(), dur = 500;
  (function tick(t) {
    const k = Math.min(1, (t - t0) / dur);
    const eased = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(prev + (value - prev) * eased);
    if (k < 1) requestAnimationFrame(tick);
  })(t0);
}

const AVATAR_COLORS = [
  ["#eef0ff", "#4f46e5"], ["#e9f9f0", "#17945c"], ["#ffeef0", "#d13438"],
  ["#fff5e0", "#b26205"], ["#e9f3ff", "#1567d2"], ["#f5f1ff", "#7c3aed"],
];

function avatarHtml(name) {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const [bg, fg] = AVATAR_COLORS[h % AVATAR_COLORS.length];
  const initials = name.trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return `<span class="avatar" style="background:${bg};color:${fg}">${escapeHtml(initials)}</span>`;
}

function setCountPill(id, n) {
  const el = document.getElementById(id);
  if (el) el.textContent = n;
}

function applyTableFilter(input) {
  const table = document.getElementById(input.dataset.filter);
  if (!table) return;
  const q = input.value.trim().toLowerCase();
  table.querySelectorAll("tbody tr").forEach((tr) => {
    if (tr.classList.contains("empty-row")) return;
    tr.hidden = q !== "" && !tr.textContent.toLowerCase().includes(q);
  });
}

function exportCsv(filename, headers, dataRows) {
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const csv = [headers, ...dataRows].map((r) => r.map(esc).join(",")).join("\r\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

let toastTimer = null;
function toast(message, type = "success") {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = "toast " + type;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 3000);
}

let modalOpener = null;
function openModal(id) {
  const overlay = document.getElementById(id);
  modalOpener = document.activeElement; // remember trigger to restore focus on close
  overlay.hidden = false;
  overlay.querySelector("input, select")?.focus();
}
function closeModal(id) {
  document.getElementById(id).hidden = true;
  if (modalOpener?.focus) { modalOpener.focus(); modalOpener = null; }
}

function setFormBusy(form, busy) {
  form.querySelectorAll('button[type="submit"]').forEach((b) => {
    b.disabled = busy;
    b.classList.toggle("is-busy", busy);
  });
}

function setDefaultDates() {
  const today = new Date().toISOString().slice(0, 10);
  document.querySelectorAll('form input[type="date"]').forEach((d) => { if (!d.value) d.value = today; });
}

// ── Edit mode (record ko uske add-form mein load karke update) ───────────
const EDITING = {}; // formId -> record id being edited

function setSubmitLabel(form, label) {
  const btn = form.querySelector('button[type="submit"]');
  const textNode = [...btn.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE).pop();
  if (!textNode) return;
  if (!btn.dataset.label) btn.dataset.label = textNode.textContent;
  textNode.textContent = label || btn.dataset.label;
}

function exitEditMode(form) {
  if (!EDITING[form.id]) return;
  delete EDITING[form.id];
  form.classList.remove("is-editing");
  form.reset();
  setDefaultDates();
  setSubmitLabel(form, null);
  if (form.dataset.kind) updateEntryFormVisibility(form);
}

function enterEditMode(form, id) {
  EDITING[form.id] = id;
  form.classList.add("is-editing");
  setSubmitLabel(form, "Update");
  if (!form.querySelector(".btn-cancel-edit")) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "btn btn-secondary btn-cancel-edit";
    b.textContent = "Cancel";
    b.addEventListener("click", () => exitEditMode(form));
    form.querySelector('button[type="submit"]').after(b);
  }
  form.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth", block: "nearest" });
  form.querySelector("input:not([type=checkbox]), select")?.focus();
}

// Record ki keys jis form field se match karti hain wahan value bhar do
function fillForm(form, record) {
  for (const [name, value] of Object.entries(record)) {
    const el = form.elements[name];
    if (el && !(el instanceof RadioNodeList) && el.type !== "checkbox") el.value = value ?? "";
  }
}

function startSimpleEdit(formId, list, id) {
  const record = list.find((x) => x.id === id);
  if (!record) return;
  const form = document.getElementById(formId);
  form.reset();
  fillForm(form, record);
  enterEditMode(form, id);
}

function startEntryEdit(id) {
  const entry = state.entries.find((x) => x.id === id);
  if (!entry) return;
  const form = document.getElementById(entry.kind === "material" ? "formMaterial" : "formAsset");
  form.reset();
  form.querySelector(".f-type").value = entry.type;
  fillForm(form, entry);
  if (entry.type !== "Transfer") {
    form.elements.to_loc_single.value =
      (entry.type === "Purchase" ? entry.to_loc : entry.from_loc) || "";
  }
  form.querySelector('[name="create_grn"]').checked = false;
  updateEntryFormVisibility(form);
  enterEditMode(form, entry.id);
}

const EDIT_HANDLERS = {
  editEntry:         startEntryEdit,
  editClient:        (id) => startSimpleEdit("formClientMgmt", state.clients, id),
  editSite:          (id) => startSimpleEdit("formSiteMgmt", state.all_sites, id),
  editVendor:        (id) => startSimpleEdit("formVendor", state.vendors, id),
  editVendorTxn:     (id) => startSimpleEdit("formVendorTxn", state.vendor_txns, id),
  editExpense:       (id) => startSimpleEdit("formExpense", state.expenses, id),
  editLabourer:      (id) => startSimpleEdit("formLabour", state.labourers, id),
  editLabourPayment: (id) => startSimpleEdit("formLabourPay", state.labour_payments, id),
  editReceipt:       (id) => startSimpleEdit("formReceipt", state.receipts, id),
};

// ── Permissions (RBAC) ───────────────────────────────────────────────────
function isAdmin() {
  return !!state.me?.is_admin;
}

function can(module, action) {
  if (!state.me) return false;
  if (state.me.is_admin) return true;
  return !!state.me.permissions?.[module]?.[action];
}

// Kis module ke create/edit forms kaunse hain (gating ke liye)
const MODULE_FORMS = {
  clients: ["formClientMgmt"],
  sites: ["formSiteMgmt"],
  material: ["formMaterial"],
  assets: ["formAsset"],
  labour: ["formLabour", "formLabourPay"],
  vendors: ["formVendor", "formVendorTxn"],
  expenses: ["formExpense"],
  receipts: ["formReceipt"],
};

// Section-level classes + form hiding — server bhi enforce karta hai,
// ye sirf UI ko permissions ke hisaab se saaf rakhta hai.
function applyPermissionGating() {
  for (const module of Object.keys(MODULE_FORMS)) {
    const section = document.getElementById(`tab-${module}`);
    if (!section) continue;
    section.classList.toggle("perm-no-edit", !can(module, "edit"));
    section.classList.toggle("perm-no-delete", !can(module, "delete"));
    const showForm = can(module, "create") || can(module, "edit");
    for (const id of MODULE_FORMS[module]) {
      const form = document.getElementById(id);
      if (form) (form.closest(".card") || form).hidden = !showForm;
    }
  }
  // Export sab tabs par gate hota hai (payments included)
  for (const tab of ["material", "assets", "labour", "vendors", "expenses", "payments", "receipts"]) {
    document.getElementById(`tab-${tab}`)?.classList.toggle("perm-no-export", !can(tab, "export"));
  }
  // Materials master inline form + chips ke delete buttons material module se chalte hain
  const mm = document.getElementById("formMaterialMaster");
  if (mm) mm.hidden = !can("material", "create");
}

// ── Lookups ──────────────────────────────────────────────────────────────
function vendorName(id) {
  return state.vendors.find((v) => v.id === id)?.name || "";
}
function labourName(id) {
  return state.labourers.find((l) => l.id === id)?.name || "";
}

// ── Bootstrap loading ────────────────────────────────────────────────────
async function loadBootstrap(clientId) {
  const qs = clientId ? `?client_id=${encodeURIComponent(clientId)}` : "";
  const data = await apiGet(`/api/bootstrap${qs}`);
  Object.assign(state, data);
  // Server stale ids ko discard karta hai — saved id ko sync rakho
  localStorage.setItem("khata_client_id", state.client_id || "");
  renderAll();
}

// ── Rendering: shell ─────────────────────────────────────────────────────
// Empty state vs app — admin tab par admin panel hamesha khulta hai,
// chahe abhi koi client na ho (users/roles wahan se hi bante hain).
function updateAppVisibility() {
  const hasClients = state.clients.length > 0;
  const activeTab = document.querySelector(".tab-btn.active")?.dataset.tab;
  const adminView = isAdmin() && activeTab === "admin";
  document.getElementById("emptyState").hidden = hasClients || adminView || !state.me;
  document.getElementById("app").hidden = !hasClients && !adminView;
  document.getElementById("sitesBar").hidden = !hasClients || activeTab === "admin";
}

function renderShell() {
  document.getElementById("btnLogout").hidden = !state.me;
  document.getElementById("btnChangePw").hidden = !state.me;

  // Logged-in user chip
  const chip = document.getElementById("userChip");
  chip.hidden = !state.me;
  if (state.me) {
    const label = state.me.full_name || state.me.email;
    document.getElementById("userChipAvatar").innerHTML = avatarHtml(label);
    document.getElementById("userChipName").textContent = label;
    document.getElementById("userChipRole").textContent = state.me.role_name || "";
  }

  // Sidebar: sirf wahi modules jinki view permission hai; Admin Panel sirf admin ko
  const adminOk = isAdmin();
  document.querySelector(".admin-nav-label").hidden = !adminOk;
  let firstVisible = "";
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    const tab = btn.dataset.tab;
    const show = tab === "admin" ? adminOk : can(tab, "view");
    btn.hidden = !show;
    if (show && !firstVisible) firstVisible = tab;
  });
  const activeBtn = document.querySelector(".tab-btn.active");
  if ((!activeBtn || activeBtn.hidden) && firstVisible) activateTab(firstVisible);
  if (adminOk && document.querySelector(".tab-btn.active")?.dataset.tab === "admin" && !admin.loaded) {
    loadAdminPanel();
  }

  // Empty state — create permission hai to Add Client, warna admin se contact karo
  const canCreateClient = can("clients", "create");
  document.getElementById("btnEmptyAddClient").hidden = !canCreateClient;
  document.querySelector("#emptyState p").textContent = canCreateClient
    ? "Koi client nahi mila. Pehla client add karo aur entries shuru karo."
    : "Aapko abhi koi client/site assign nahi hui hai — admin se contact karo.";

  updateAppVisibility();

  const sel = document.getElementById("clientSelect");
  sel.innerHTML = '<option value="">— Select client —</option>' +
    state.clients.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
  sel.value = state.client_id || "";

  const chips = document.getElementById("sitesChips");
  chips.innerHTML = state.sites.length
    ? state.sites.map((s) => `<span class="chip">${escapeHtml(s.name)}</span>`).join("")
    : '<span class="chip">Koi site nahi — Sites tab se add karo</span>';
}

// ── Rendering: dropdowns fed by state ────────────────────────────────────
function fillSelect(sel, items, getVal, getLabel) {
  const ph = sel.dataset.placeholder;
  const prev = sel.value;
  sel.innerHTML =
    (ph !== undefined ? `<option value="">${escapeHtml(ph)}</option>` : "") +
    items.map((i) => `<option value="${escapeHtml(getVal(i))}">${escapeHtml(getLabel(i))}</option>`).join("");
  if ([...sel.options].some((o) => o.value === prev)) sel.value = prev;
}

function populateSelects() {
  const siteName = (s) => s.name;

  document.querySelectorAll(".f-location-select").forEach((sel) =>
    fillSelect(sel, state.sites, siteName, siteName));

  document.querySelectorAll(".site-select").forEach((sel) =>
    fillSelect(sel, state.sites, siteName, siteName));

  document.querySelectorAll(".contractor-select").forEach((sel) =>
    fillSelect(sel, state.vendors, (v) => v.id, (v) => v.name));

  document.querySelectorAll(".client-picker").forEach((sel) =>
    fillSelect(sel, state.clients, (c) => c.id, (c) => c.name));

  document.querySelectorAll(".vendor-filter-select").forEach((sel) =>
    fillSelect(sel, state.vendors, (v) => v.id, (v) => v.name));

  document.querySelectorAll('.entry-form select[name="vendor_id"]').forEach((sel) => {
    const optionsHtml = state.vendors.map((v) => `<option value="${v.id}">${escapeHtml(v.name)}</option>`).join("");
    const prev = sel.value;
    sel.innerHTML = '<option value="">— none —</option>' + optionsHtml;
    if ([...sel.options].some((o) => o.value === prev)) sel.value = prev;
  });

  const txnVendor = document.querySelector('#formVendorTxn select[name="vendor_id"]');
  if (txnVendor) {
    const prev = txnVendor.value;
    txnVendor.innerHTML = '<option value="">— select vendor —</option>' +
      state.vendors.map((v) => `<option value="${v.id}">${escapeHtml(v.name)}</option>`).join("");
    if ([...txnVendor.options].some((o) => o.value === prev)) txnVendor.value = prev;
  }

  const laboursSel = document.querySelector('#formLabourPay select[name="labour_id"]');
  if (laboursSel) {
    const prev = laboursSel.value;
    laboursSel.innerHTML = '<option value="">— select labour —</option>' +
      state.labourers.map((l) => `<option value="${l.id}">${escapeHtml(l.name)} (${escapeHtml(l.type)})</option>`).join("");
    if ([...laboursSel.options].some((o) => o.value === prev)) laboursSel.value = prev;
  }

  document.getElementById("materialList").innerHTML =
    state.materials.map((m) => `<option value="${escapeHtml(m.name)}"></option>`).join("");
}

// ── Clients ──────────────────────────────────────────────────────────────
function renderClientsTable() {
  const tbody = document.querySelector("#clientTable tbody");
  const status = val("fltClientStatus"), q = val("fltClientQ").trim().toLowerCase();
  const list = state.clients.filter((c) =>
    (!status || (c.status || "Active") === status) &&
    (!q || `${c.name} ${c.contact_person || ""} ${c.phone || ""} ${c.email || ""}`.toLowerCase().includes(q)));
  setCountPill("clientTableCount", list.length);
  setStat("statClientTotal", state.clients.length);
  setStat("statClientActive", state.clients.filter((c) => (c.status || "Active") === "Active").length);
  setStat("statClientSites", state.all_sites.length);
  if (!list.length) {
    tbody.innerHTML = emptyRow(7, "Koi client nahi mila");
    return;
  }
  tbody.innerHTML = list.map((c) => {
    const siteCount = state.all_sites.filter((s) => s.client_id === c.id).length;
    return `<tr>
      <td>${avatarHtml(c.name)}${escapeHtml(c.name)}</td>
      <td>${escapeHtml(c.contact_person || "")}</td>
      <td>${escapeHtml(c.phone || "")}</td>
      <td>${escapeHtml(c.email || "")}</td>
      <td class="num">${siteCount}</td>
      <td><span class="badge badge-${c.status || "Active"}">${escapeHtml(c.status || "Active")}</span></td>
      <td class="row-actions">${EDIT_BTN("data-edit-client", c.id)}${TRASH_BTN("data-del-client", c.id)}</td>
    </tr>`;
  }).join("");
}

// ── Sites ────────────────────────────────────────────────────────────────
function renderSitesTable() {
  const tbody = document.querySelector("#siteTable tbody");
  const clientId = val("fltSiteClient"), status = val("fltSiteStatus"), q = val("fltSiteQ").trim().toLowerCase();
  const list = state.all_sites.filter((s) =>
    (!clientId || s.client_id === clientId) &&
    (!status || (s.status || "Active") === status) &&
    (!q || `${s.name} ${s.client_name || ""} ${s.address || ""}`.toLowerCase().includes(q)));
  setCountPill("siteTableCount", list.length);
  setStat("statSiteTotal", state.all_sites.length);
  setStat("statSiteActive", state.all_sites.filter((s) => (s.status || "Active") === "Active").length);
  setStat("statSiteInactive", state.all_sites.filter((s) => s.status === "Inactive").length);
  if (!list.length) {
    tbody.innerHTML = emptyRow(5, "Koi site nahi mili");
    return;
  }
  tbody.innerHTML = list.map((s) => `<tr>
      <td>${escapeHtml(s.client_name || "")}</td>
      <td>${escapeHtml(s.name)}</td>
      <td>${escapeHtml(s.address || "")}</td>
      <td><span class="badge badge-${s.status || "Active"}">${escapeHtml(s.status || "Active")}</span></td>
      <td class="row-actions">${EDIT_BTN("data-edit-site", s.id)}${TRASH_BTN("data-del-site", s.id)}</td>
    </tr>`).join("");
}

// ── Materials master ─────────────────────────────────────────────────────
function renderMaterialsMaster() {
  setCountPill("materialsMasterCount", state.materials.length);
  const box = document.getElementById("materialsChips");
  if (!state.materials.length) {
    box.innerHTML = '<span class="hint">Koi material nahi — upar se add karo (Iron, Cement, Sand, Bricks, Aggregate…)</span>';
    return;
  }
  box.innerHTML = state.materials.map((m) =>
    `<span class="master-chip">${escapeHtml(m.name)}${m.unit ? ` <span class="unit">· ${escapeHtml(m.unit)}</span>` : ""}
      <button type="button" data-del-material="${m.id}" title="Remove" aria-label="Remove">×</button></span>`
  ).join("");
}

// ── Stock balance (keeps fully-consumed rows as Nil) ─────────────────────
function computeLocationBalance(kind) {
  const map = new Map();
  const add = (loc, item, unit, qty) => {
    if (!loc) return;
    const key = `${loc}␟${item}␟${unit}`;
    map.set(key, (map.get(key) || 0) + qty);
  };
  for (const e of state.entries) {
    if (e.kind !== kind) continue;
    if (e.type === "Purchase") add(e.to_loc, e.item, e.unit, e.qty);
    else if (e.type === "Sale" || e.type === "Consumed") add(e.from_loc, e.item, e.unit, -e.qty);
    else if (e.type === "Transfer") { add(e.from_loc, e.item, e.unit, -e.qty); add(e.to_loc, e.item, e.unit, e.qty); }
  }
  return [...map.entries()]
    .map(([key, qty]) => { const [loc, item, unit] = key.split("␟"); return { loc, item, unit, qty }; })
    .sort((a, b) => a.loc.localeCompare(b.loc) || a.item.localeCompare(b.item));
}

function balanceCell(qty) {
  if (Math.abs(qty) < 1e-9) return '<span class="nil-badge">Nil</span>';
  return fmtQty(qty);
}

function renderStockBalance() {
  const tbody = document.querySelector("#materialBalanceTable tbody");
  const locFilter = val("fltStockLoc");
  let rowsData = computeLocationBalance("material");
  if (locFilter) rowsData = rowsData.filter((r) => r.loc === locFilter);
  if (!rowsData.length) {
    tbody.innerHTML = emptyRow(4, "Koi stock nahi hai");
    return;
  }
  tbody.innerHTML = rowsData.map((r) =>
    `<tr><td>${escapeHtml(r.loc)}</td><td>${escapeHtml(r.item)}</td><td>${escapeHtml(r.unit)}</td><td class="num">${balanceCell(r.qty)}</td></tr>`
  ).join("");
}

function renderAssetBalance() {
  const tbody = document.querySelector("#assetBalanceTable tbody");
  const rowsData = computeLocationBalance("asset").filter((r) => Math.abs(r.qty) > 1e-9);
  if (!rowsData.length) {
    tbody.innerHTML = emptyRow(4, "Koi balance nahi hai");
    return;
  }
  tbody.innerHTML = rowsData.map((r) =>
    `<tr><td>${escapeHtml(r.loc)}</td><td>${escapeHtml(r.item)}</td><td>${escapeHtml(r.unit)}</td><td class="num">${fmtQty(r.qty)}</td></tr>`
  ).join("");
}

// ── Material / asset entries ─────────────────────────────────────────────
function renderMaterialEntries() {
  const tbody = document.querySelector("#materialTable tbody");
  const from = val("fltMatFrom"), to = val("fltMatTo"), type = val("fltMatType");
  const list = state.entries.filter((e) =>
    e.kind === "material" && inRange(e.date, from, to) && (!type || e.type === type));
  FILTERED.material = list;
  setCountPill("materialTableCount", list.length);
  if (!list.length) {
    tbody.innerHTML = emptyRow(13, "Koi entry nahi hai");
    return;
  }
  tbody.innerHTML = list.map((e) => `<tr>
      <td>${escapeHtml(e.date)}</td>
      <td><span class="badge badge-${e.type}">${escapeHtml(e.type)}</span></td>
      <td>${escapeHtml(e.item)}</td>
      <td class="num">${fmtQty(e.qty)}</td>
      <td>${escapeHtml(e.unit)}</td>
      <td class="num">${fmtMoney(e.rate)}</td>
      <td class="num">${fmtMoney(e.qty * e.rate)}</td>
      <td>${escapeHtml(e.from_loc || "")}</td>
      <td>${escapeHtml(e.to_loc || "")}</td>
      <td>${escapeHtml(e.vehicle || "")}</td>
      <td>${escapeHtml(vendorName(e.vendor_id))}</td>
      <td>${escapeHtml(e.note || "")}</td>
      <td class="row-actions">${EDIT_BTN("data-edit-entry", e.id)}${TRASH_BTN("data-del-entry", e.id)}</td>
    </tr>`).join("");
}

function renderAssetEntries() {
  const tbody = document.querySelector("#assetTable tbody");
  const list = state.entries.filter((e) => e.kind === "asset");
  setCountPill("assetTableCount", list.length);
  if (!list.length) {
    tbody.innerHTML = emptyRow(12, "Koi entry nahi hai");
    return;
  }
  tbody.innerHTML = list.map((e) => `<tr>
      <td>${escapeHtml(e.date)}</td>
      <td><span class="badge badge-${e.type}">${escapeHtml(e.type)}</span></td>
      <td>${escapeHtml(e.item)}</td>
      <td class="num">${fmtQty(e.qty)}</td>
      <td>${escapeHtml(e.unit)}</td>
      <td class="num">${fmtMoney(e.rate)}</td>
      <td class="num">${fmtMoney(e.qty * e.rate)}</td>
      <td>${escapeHtml(e.from_loc || "")}</td>
      <td>${escapeHtml(e.to_loc || "")}</td>
      <td>${escapeHtml(vendorName(e.vendor_id))}</td>
      <td>${escapeHtml(e.note || "")}</td>
      <td class="row-actions">${EDIT_BTN("data-edit-entry", e.id)}${TRASH_BTN("data-del-entry", e.id)}</td>
    </tr>`).join("");
}

// ── Labour ───────────────────────────────────────────────────────────────
function labourPaidTotal(lid) {
  return state.labour_payments.filter((p) => p.labour_id === lid).reduce((s, p) => s + p.amount, 0);
}

function renderLabourRegister() {
  const tbody = document.querySelector("#labourTable tbody");
  const site = val("fltLabSite"), type = val("fltLabType"),
        contractor = val("fltLabContractor"), status = val("fltLabStatus"),
        q = val("fltLabQ").trim().toLowerCase();
  const list = state.labourers.filter((l) =>
    (!site || l.site === site) &&
    (!type || l.type === type) &&
    (!contractor || l.contractor_id === contractor) &&
    (!status || l.status === status) &&
    (!q || `${l.name} ${l.phone} ${l.address} ${l.id_number}`.toLowerCase().includes(q)));
  FILTERED.labour = list;
  setCountPill("labourTableCount", list.length);
  if (!list.length) {
    tbody.innerHTML = emptyRow(9, "Koi labour nahi mila");
    return;
  }
  tbody.innerHTML = list.map((l) => {
    const next = l.status === "Active" ? "Inactive" : "Active";
    return `<tr>
      <td>${avatarHtml(l.name)}${escapeHtml(l.name)}</td>
      <td>${escapeHtml(l.type)}</td>
      <td>${escapeHtml(l.phone || "")}</td>
      <td>${escapeHtml(l.site || "")}</td>
      <td>${escapeHtml(vendorName(l.contractor_id))}</td>
      <td>${escapeHtml(l.joining_date || "")}</td>
      <td class="num">${fmtMoney(labourPaidTotal(l.id))}</td>
      <td><span class="badge badge-${l.status}">${escapeHtml(l.status)}</span>
          <button class="btn-link" data-toggle-labourer="${l.id}" data-next="${next}">${next === "Active" ? "Activate" : "Deactivate"}</button></td>
      <td class="row-actions">${EDIT_BTN("data-edit-labourer", l.id)}${TRASH_BTN("data-del-labourer", l.id)}</td>
    </tr>`;
  }).join("");
}

function renderLabourPayments() {
  const tbody = document.querySelector("#labourPayTable tbody");
  const from = val("fltLpFrom"), to = val("fltLpTo"), mode = val("fltLpMode"),
        q = val("fltLpQ").trim().toLowerCase();
  const list = state.labour_payments.filter((p) =>
    inRange(p.date, from, to) &&
    (!mode || p.mode === mode) &&
    (!q || `${labourName(p.labour_id)} ${p.site} ${p.reference} ${p.note}`.toLowerCase().includes(q)));
  FILTERED.labourPay = list;
  setCountPill("labourPayTableCount", list.length);
  if (!list.length) {
    tbody.innerHTML = emptyRow(8, "Koi payment nahi hai");
    return;
  }
  tbody.innerHTML = list.map((p) => `<tr>
      <td>${escapeHtml(p.date)}</td>
      <td>${escapeHtml(labourName(p.labour_id))}</td>
      <td>${escapeHtml(p.site || "")}</td>
      <td>${escapeHtml(p.mode)}</td>
      <td>${escapeHtml(p.reference || "")}</td>
      <td class="num">${fmtMoney(p.amount)}</td>
      <td>${escapeHtml(p.note || "")}</td>
      <td class="row-actions">${EDIT_BTN("data-edit-labour-payment", p.id)}${TRASH_BTN("data-del-labour-payment", p.id)}</td>
    </tr>`).join("");
}

// ── Vendors ──────────────────────────────────────────────────────────────
function renderVendorSummaryTable() {
  const tbody = document.querySelector("#vendorSummaryTable tbody");
  if (!state.vendors.length) {
    tbody.innerHTML = emptyRow(8, "Koi vendor nahi hai");
    return;
  }
  tbody.innerHTML = state.vendors.map((v) => {
    const txns = state.vendor_txns.filter((t) => t.vendor_id === v.id);
    const received = txns.filter((t) => t.type === "Goods Received").reduce((s, t) => s + t.amount, 0);
    const paid = txns.filter((t) => t.type === "Payment").reduce((s, t) => s + t.amount, 0);
    const balance = received - paid;
    const balClass = balance > 0 ? "txt-danger" : "txt-success";
    return `<tr>
      <td>${avatarHtml(v.name)}${escapeHtml(v.name)}</td>
      <td>${escapeHtml(v.category || "")}</td>
      <td>${escapeHtml(v.contact_person || v.phone || "")}</td>
      <td><span class="badge badge-${v.status || "Active"}">${escapeHtml(v.status || "Active")}</span></td>
      <td class="num">${fmtMoney(received)}</td>
      <td class="num">${fmtMoney(paid)}</td>
      <td class="num"><strong class="${balClass}">${fmtMoney(balance)}</strong></td>
      <td class="row-actions">${EDIT_BTN("data-edit-vendor", v.id)}${TRASH_BTN("data-del-vendor", v.id)}</td>
    </tr>`;
  }).join("");
}

function renderVendorTxnTable() {
  const tbody = document.querySelector("#vendorTxnTable tbody");
  const vid = val("fltVenVendor"), from = val("fltVenFrom"), to = val("fltVenTo"),
        q = val("fltVenQ").trim().toLowerCase();
  const list = state.vendor_txns.filter((t) =>
    (!vid || t.vendor_id === vid) &&
    inRange(t.date, from, to) &&
    (!q || `${vendorName(t.vendor_id)} ${t.type} ${t.mode} ${t.reference} ${t.by_name} ${t.note}`.toLowerCase().includes(q)));
  FILTERED.vendorTxn = list;
  setCountPill("vendorTxnTableCount", list.length);
  if (!list.length) {
    tbody.innerHTML = emptyRow(9, "Koi transaction nahi hai");
    return;
  }
  tbody.innerHTML = list.map((t) => {
    const badgeClass = t.type === "Payment" ? "badge-Payment" : "badge-GoodsReceived";
    return `<tr>
      <td>${escapeHtml(t.date)}</td>
      <td>${escapeHtml(vendorName(t.vendor_id))}</td>
      <td><span class="badge ${badgeClass}">${escapeHtml(t.type)}</span></td>
      <td class="num">${fmtMoney(t.amount)}</td>
      <td>${escapeHtml(t.mode || "")}</td>
      <td>${escapeHtml(t.reference || "")}</td>
      <td>${escapeHtml(t.by_name || "")}</td>
      <td>${escapeHtml(t.note || "")}</td>
      <td class="row-actions">${EDIT_BTN("data-edit-vendor-txn", t.id)}${TRASH_BTN("data-del-vendor-txn", t.id)}</td>
    </tr>`;
  }).join("");
}

// ── Expenses ─────────────────────────────────────────────────────────────
function renderExpenseTable() {
  const tbody = document.querySelector("#expenseTable tbody");
  setCountPill("expenseTableCount", state.expenses.length);
  if (!state.expenses.length) {
    tbody.innerHTML = emptyRow(10, "Koi expense nahi hai");
    return;
  }
  tbody.innerHTML = state.expenses.map((x) => `<tr>
      <td>${escapeHtml(x.date)}</td>
      <td>${escapeHtml(x.site)}</td>
      <td>${escapeHtml(x.category)}</td>
      <td>${escapeHtml(x.item)}</td>
      <td class="num">${fmtQty(x.qty)}</td>
      <td>${escapeHtml(x.unit)}</td>
      <td class="num">${fmtMoney(x.rate)}</td>
      <td class="num">${fmtMoney(x.qty * x.rate)}</td>
      <td>${escapeHtml(x.note || "")}</td>
      <td class="row-actions">${EDIT_BTN("data-edit-expense", x.id)}${TRASH_BTN("data-del-expense", x.id)}</td>
    </tr>`).join("");
}

function renderExpenseSummaryTable() {
  const tbody = document.querySelector("#expenseSummaryTable tbody");
  const totals = new Map();
  for (const x of state.expenses) totals.set(x.category, (totals.get(x.category) || 0) + x.qty * x.rate);
  if (!totals.size) {
    tbody.innerHTML = emptyRow(3, "Koi expense nahi hai");
    return;
  }
  const grand = [...totals.values()].reduce((a, b) => a + b, 0);
  tbody.innerHTML = [...totals.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([cat, total]) => {
      const pct = grand > 0 ? Math.round((total / grand) * 100) : 0;
      return `<tr>
        <td>${escapeHtml(cat)}</td>
        <td class="bar-cell"><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div></td>
        <td class="num">${fmtMoney(total)} <span class="hint">${pct}%</span></td>
      </tr>`;
    })
    .join("");
}

// ── Payment register (derived from all outgoing payments) ────────────────
function buildPaymentRegister() {
  const rows = [];
  for (const p of state.labour_payments) {
    rows.push({ date: p.date, party: labourName(p.labour_id), category: "Labour Payment",
                site: p.site || "", amount: p.amount, mode: p.mode, reference: p.reference || "", note: p.note || "" });
  }
  for (const t of state.vendor_txns) {
    if (t.type !== "Payment") continue;
    rows.push({ date: t.date, party: vendorName(t.vendor_id), category: "Vendor Payment",
                site: "", amount: t.amount, mode: t.mode || "", reference: t.reference || "", note: t.note || "" });
  }
  for (const x of state.expenses) {
    rows.push({ date: x.date, party: x.item, category: "Site Expense",
                site: x.site, amount: x.qty * x.rate, mode: "", reference: "",
                note: x.category + (x.note ? " — " + x.note : "") });
  }
  for (const e of state.entries) {
    if (e.type !== "Purchase" || e.qty * e.rate <= 0) continue;
    rows.push({ date: e.date, party: vendorName(e.vendor_id) || e.item,
                category: e.kind === "material" ? "Material Purchase" : "Asset Purchase",
                site: e.to_loc || "", amount: e.qty * e.rate, mode: "", reference: "",
                note: `${e.item} — ${fmtQty(e.qty)} ${e.unit}` });
  }
  return rows.sort((a, b) => b.date.localeCompare(a.date));
}

function renderPaymentRegister() {
  const tbody = document.querySelector("#paymentRegTable tbody");
  const cat = val("fltPayCat"), site = val("fltPaySite"),
        from = val("fltPayFrom"), to = val("fltPayTo"),
        q = val("fltPayQ").trim().toLowerCase();
  const list = buildPaymentRegister().filter((r) =>
    (!cat || r.category === cat) &&
    (!site || r.site === site) &&
    inRange(r.date, from, to) &&
    (!q || `${r.party} ${r.category} ${r.site} ${r.mode} ${r.reference} ${r.note}`.toLowerCase().includes(q)));
  FILTERED.payments = list;
  setStat("statPayTotal", list.reduce((s, r) => s + r.amount, 0), true);
  const mk = currentMonthKey();
  setStat("statPayMonth", list.filter((r) => r.date.startsWith(mk)).reduce((s, r) => s + r.amount, 0), true);
  setStat("statPayCount", list.length);
  if (!list.length) {
    tbody.innerHTML = emptyRow(8, "Koi payment nahi mila");
    return;
  }
  tbody.innerHTML = list.map((r) => `<tr>
      <td>${escapeHtml(r.date)}</td>
      <td>${escapeHtml(r.party)}</td>
      <td>${escapeHtml(r.category)}</td>
      <td>${escapeHtml(r.site)}</td>
      <td class="num">${fmtMoney(r.amount)}</td>
      <td>${escapeHtml(r.mode)}</td>
      <td>${escapeHtml(r.reference)}</td>
      <td>${escapeHtml(r.note)}</td>
    </tr>`).join("");
}

// ── Receipts ─────────────────────────────────────────────────────────────
function renderReceiptsTable() {
  const tbody = document.querySelector("#receiptTable tbody");
  const from = val("fltRecFrom"), to = val("fltRecTo"), mode = val("fltRecMode"),
        q = val("fltRecQ").trim().toLowerCase();
  const list = state.receipts.filter((r) =>
    inRange(r.date, from, to) &&
    (!mode || r.mode === mode) &&
    (!q || `${r.from_name} ${r.site} ${r.reference} ${r.note}`.toLowerCase().includes(q)));
  FILTERED.receipts = list;
  setCountPill("receiptTableCount", list.length);
  if (!list.length) {
    tbody.innerHTML = emptyRow(8, "Koi receipt nahi hai");
    return;
  }
  tbody.innerHTML = list.map((r) => `<tr>
      <td>${escapeHtml(r.date)}</td>
      <td>${escapeHtml(r.from_name)}</td>
      <td>${escapeHtml(r.site || "")}</td>
      <td class="num">${fmtMoney(r.amount)}</td>
      <td>${escapeHtml(r.mode)}</td>
      <td>${escapeHtml(r.reference || "")}</td>
      <td>${escapeHtml(r.note || "")}</td>
      <td class="row-actions">${EDIT_BTN("data-edit-receipt", r.id)}${TRASH_BTN("data-del-receipt", r.id)}</td>
    </tr>`).join("");
}

function renderReceiptModeSummary() {
  const tbody = document.querySelector("#receiptModeTable tbody");
  const totals = new Map();
  for (const r of state.receipts) totals.set(r.mode, (totals.get(r.mode) || 0) + r.amount);
  if (!totals.size) {
    tbody.innerHTML = emptyRow(3, "Koi receipt nahi hai");
    return;
  }
  const grand = [...totals.values()].reduce((a, b) => a + b, 0);
  tbody.innerHTML = [...totals.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([mode, total]) => {
      const pct = grand > 0 ? Math.round((total / grand) * 100) : 0;
      return `<tr>
        <td>${escapeHtml(mode)}</td>
        <td class="bar-cell"><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div></td>
        <td class="num">${fmtMoney(total)} <span class="hint">${pct}%</span></td>
      </tr>`;
    })
    .join("");
}

// ── Dashboard ────────────────────────────────────────────────────────────
const GODOWN_RE = /godown|store|warehouse/i;

function renderDashboard() {
  const stock = computeLocationBalance("material");
  const godown = stock.filter((r) => GODOWN_RE.test(r.loc));
  const site = stock.filter((r) => !GODOWN_RE.test(r.loc));

  const fillStockTable = (tableId, rowsData, locLabel) => {
    const tbody = document.querySelector(`#${tableId} tbody`);
    if (!rowsData.length) {
      tbody.innerHTML = emptyRow(4, `Koi ${locLabel} stock nahi hai`);
      return;
    }
    tbody.innerHTML = rowsData.map((r) =>
      `<tr><td>${escapeHtml(r.loc)}</td><td>${escapeHtml(r.item)}</td><td>${escapeHtml(r.unit)}</td><td class="num">${balanceCell(r.qty)}</td></tr>`
    ).join("");
  };
  fillStockTable("dashGodownTable", godown, "godown");
  fillStockTable("dashSiteTable", site, "site");

  // Vendor outstanding
  const venBody = document.querySelector("#dashVendorTable tbody");
  const venRows = state.vendors.map((v) => {
    const txns = state.vendor_txns.filter((t) => t.vendor_id === v.id);
    const received = txns.filter((t) => t.type === "Goods Received").reduce((s, t) => s + t.amount, 0);
    const paid = txns.filter((t) => t.type === "Payment").reduce((s, t) => s + t.amount, 0);
    return { name: v.name, received, paid, balance: received - paid };
  }).filter((r) => Math.abs(r.balance) > 1e-9).sort((a, b) => b.balance - a.balance);
  venBody.innerHTML = venRows.length
    ? venRows.map((r) => `<tr>
        <td>${escapeHtml(r.name)}</td>
        <td class="num">${fmtMoney(r.received)}</td>
        <td class="num">${fmtMoney(r.paid)}</td>
        <td class="num"><strong class="${r.balance > 0 ? "txt-danger" : "txt-success"}">${fmtMoney(r.balance)}</strong></td>
      </tr>`).join("")
    : emptyRow(4, "Koi outstanding nahi hai");

  // Monthly summary
  const mk = currentMonthKey();
  document.getElementById("dashMonthLabel").textContent = monthLabel();
  const inMonth = (d) => (d || "").startsWith(mk);
  const monthRows = [
    ["Material Purchase", state.entries.filter((e) => e.kind === "material" && e.type === "Purchase" && inMonth(e.date)).reduce((s, e) => s + e.qty * e.rate, 0)],
    ["Asset Purchase", state.entries.filter((e) => e.kind === "asset" && e.type === "Purchase" && inMonth(e.date)).reduce((s, e) => s + e.qty * e.rate, 0)],
    ["Vendor Payments", state.vendor_txns.filter((t) => t.type === "Payment" && inMonth(t.date)).reduce((s, t) => s + t.amount, 0)],
    ["Labour Payments", state.labour_payments.filter((p) => inMonth(p.date)).reduce((s, p) => s + p.amount, 0)],
    ["Site Expenses", state.expenses.filter((x) => inMonth(x.date)).reduce((s, x) => s + x.qty * x.rate, 0)],
    ["Receipts (in)", state.receipts.filter((r) => inMonth(r.date)).reduce((s, r) => s + r.amount, 0)],
  ];
  document.querySelector("#dashMonthTable tbody").innerHTML =
    monthRows.map(([label, amt]) => `<tr><td>${label}</td><td class="num">${fmtMoney(amt)}</td></tr>`).join("");

  // Recent activity (merged across registers)
  const acts = [];
  for (const e of state.entries) acts.push({ date: e.date, type: `${e.kind === "material" ? "Material" : "Asset"} ${e.type}`, detail: `${e.item} — ${fmtQty(e.qty)} ${e.unit}`, amount: e.qty * e.rate });
  for (const t of state.vendor_txns) acts.push({ date: t.date, type: `Vendor ${t.type}`, detail: vendorName(t.vendor_id), amount: t.amount });
  for (const p of state.labour_payments) acts.push({ date: p.date, type: "Labour Payment", detail: labourName(p.labour_id), amount: p.amount });
  for (const x of state.expenses) acts.push({ date: x.date, type: "Site Expense", detail: `${x.category} — ${x.item}`, amount: x.qty * x.rate });
  for (const r of state.receipts) acts.push({ date: r.date, type: "Receipt", detail: r.from_name, amount: r.amount });
  acts.sort((a, b) => b.date.localeCompare(a.date));
  const recent = acts.slice(0, 12);
  document.querySelector("#dashRecentTable tbody").innerHTML = recent.length
    ? recent.map((a) => `<tr><td>${escapeHtml(a.date)}</td><td>${escapeHtml(a.type)}</td><td>${escapeHtml(a.detail)}</td><td class="num">${a.amount ? fmtMoney(a.amount) : ""}</td></tr>`).join("")
    : emptyRow(4, "Abhi koi activity nahi hai");
}

// ── KPI stats ────────────────────────────────────────────────────────────
function renderStats() {
  const mk = currentMonthKey();

  const mat = state.entries.filter((e) => e.kind === "material");
  setStat("statMatPurchase", mat.filter((e) => e.type === "Purchase").reduce((s, e) => s + e.qty * e.rate, 0), true);
  setStat("statMatStock", computeLocationBalance("material").filter((r) => r.qty > 1e-9).length);
  setStat("statMatEntries", mat.length);

  const ast = state.entries.filter((e) => e.kind === "asset");
  setStat("statAssetValue", ast.filter((e) => e.type === "Purchase").reduce((s, e) => s + e.qty * e.rate, 0), true);
  setStat("statAssetItems", computeLocationBalance("asset").filter((r) => r.qty > 1e-9).length);
  setStat("statAssetEntries", ast.length);

  setStat("statLabActive", state.labourers.filter((l) => l.status === "Active").length);
  const labTotal = state.labour_payments.reduce((s, p) => s + p.amount, 0);
  setStat("statLabPaid", labTotal, true);
  setStat("statLabMonth", state.labour_payments.filter((p) => p.date.startsWith(mk)).reduce((s, p) => s + p.amount, 0), true);

  const received = state.vendor_txns.filter((t) => t.type === "Goods Received").reduce((s, t) => s + t.amount, 0);
  const paid = state.vendor_txns.filter((t) => t.type === "Payment").reduce((s, t) => s + t.amount, 0);
  setStat("statVenReceived", received, true);
  setStat("statVenPaid", paid, true);
  setStat("statVenDue", received - paid, true);

  setStat("statExpTotal", state.expenses.reduce((s, x) => s + x.qty * x.rate, 0), true);
  setStat("statExpCats", new Set(state.expenses.map((x) => x.category)).size);
  setStat("statExpCount", state.expenses.length);

  const recTotal = state.receipts.reduce((s, r) => s + r.amount, 0);
  setStat("statRecTotal", recTotal, true);
  setStat("statRecMonth", state.receipts.filter((r) => r.date.startsWith(mk)).reduce((s, r) => s + r.amount, 0), true);
  setStat("statRecCount", state.receipts.length);

  // Dashboard tiles
  setStat("statDashStock", computeLocationBalance("material").filter((r) => r.qty > 1e-9).length);
  setStat("statDashVendorDue", received - paid, true);
  setStat("statDashLabourPaid", labTotal, true);
  const outMonth = buildPaymentRegister().filter((r) => r.date.startsWith(mk)).reduce((s, r) => s + r.amount, 0);
  setStat("statDashMonthOut", outMonth, true);
  setStat("statDashMonthIn", state.receipts.filter((r) => r.date.startsWith(mk)).reduce((s, r) => s + r.amount, 0), true);
}

// ── Entry form: dynamic field visibility ─────────────────────────────────
function setFieldRequired(field, required) {
  const input = field.querySelector("select, input");
  if (!input) return;
  if (required) input.setAttribute("required", ""); else input.removeAttribute("required");
}

function updateEntryFormVisibility(form) {
  const type = form.querySelector(".f-type").value;
  const isTransfer = type === "Transfer";
  const isPurchase = type === "Purchase";

  const single = form.querySelector(".f-loc-single");
  const from = form.querySelector(".f-loc-from");
  const to = form.querySelector(".f-loc-to");
  single.hidden = isTransfer;
  from.hidden = !isTransfer;
  to.hidden = !isTransfer;
  setFieldRequired(single, !isTransfer);
  setFieldRequired(from, isTransfer);
  setFieldRequired(to, isTransfer);

  const vehicle = form.querySelector(".f-vehicle");
  if (vehicle) vehicle.hidden = !isTransfer;

  const vendorField = form.querySelector(".f-vendor");
  const grnField = form.querySelector(".f-grn");
  const grnCheckbox = form.querySelector('[name="create_grn"]');
  vendorField.hidden = !isPurchase;
  grnField.hidden = !isPurchase;
  if (!isPurchase) grnCheckbox.checked = false;

  const byField = form.querySelector(".f-byname");
  byField.hidden = !(isPurchase && grnCheckbox.checked);
}

async function handleEntrySubmit(e) {
  e.preventDefault();
  const form = e.target;
  const kind = form.dataset.kind;
  const type = form.querySelector(".f-type").value;
  const fd = new FormData(form);

  const payload = {
    client_id: state.client_id,
    kind,
    type,
    date: fd.get("date"),
    item: fd.get("item"),
    qty: fd.get("qty"),
    unit: fd.get("unit"),
    rate: fd.get("rate") || 0,
    note: fd.get("note") || "",
  };

  const editId = EDITING[form.id];

  if (type === "Transfer") {
    payload.from_loc = fd.get("from_loc");
    payload.to_loc = fd.get("to_loc");
    payload.vehicle = fd.get("vehicle") || "";
  } else if (type === "Purchase") {
    payload.to_loc = fd.get("to_loc_single");
    payload.vendor_id = fd.get("vendor_id") || "";
    if (fd.get("create_grn") && !editId) {
      payload.create_grn = true;
      payload.by_name = fd.get("by_name") || "Site Engineer";
    }
  } else {
    payload.from_loc = fd.get("to_loc_single");
  }

  setFormBusy(form, true);
  try {
    if (editId) {
      await apiPut(`/api/entries/${editId}`, payload);
      exitEditMode(form);
    } else {
      await apiPost("/api/entries", payload);
      form.reset();
      setDefaultDates();
      updateEntryFormVisibility(form);
    }
    await loadBootstrap(state.client_id);
    toast(editId ? "Entry updated" : "Entry added");
  } catch (err) {
    toast(err.message, "error");
  } finally {
    setFormBusy(form, false);
  }
}

// ── Delete / toggle (event delegation) ───────────────────────────────────
const DELETE_ROUTES = [
  ["delEntry", "entries"],
  ["delClient", "clients"],
  ["delSite", "sites"],
  ["delVendor", "vendors"],
  ["delVendorTxn", "vendor_txns"],
  ["delExpense", "expenses"],
  ["delMaterial", "materials"],
  ["delLabourer", "labourers"],
  ["delLabourPayment", "labour_payments"],
  ["delReceipt", "receipts"],
];

const DELETE_CONFIRMS = {
  delClient: "Client ko permanently delete karna hai? Ye undo nahi ho sakta.",
  delSite: "Site ko permanently delete karna hai? Ye undo nahi ho sakta.",
  delVendor: "Vendor delete karne se uska poora ledger bhi delete hoga. Pakka?",
  delLabourer: "Labour delete karne se uski payment history bhi delete hogi. Pakka?",
};

async function handleDeleteClick(e) {
  const toggleBtn = e.target.closest("[data-toggle-labourer]");
  if (toggleBtn) {
    try {
      await apiPost(`/api/labourers/${toggleBtn.dataset.toggleLabourer}/status`, { status: toggleBtn.dataset.next });
      await loadBootstrap(state.client_id);
      toast(`Labour ${toggleBtn.dataset.next === "Active" ? "activated" : "deactivated"}`);
    } catch (err) {
      toast(err.message, "error");
    }
    return;
  }

  const btn = e.target.closest(
    "[data-del-entry],[data-del-client],[data-del-site],[data-del-vendor],[data-del-vendor-txn],[data-del-expense],[data-del-material],[data-del-labourer],[data-del-labour-payment],[data-del-receipt]");
  if (!btn) return;

  const found = DELETE_ROUTES.find(([key]) => btn.dataset[key]);
  if (!found) return;
  const [key, endpoint] = found;

  if (!confirm(DELETE_CONFIRMS[key] || "Delete this record?")) return;
  btn.disabled = true;
  try {
    await apiDelete(`/api/${endpoint}/${btn.dataset[key]}`);
    await loadBootstrap(state.client_id);
    toast("Deleted");
  } catch (err) {
    btn.disabled = false;
    toast(err.message, "error");
  }
}

// ── CSV export ───────────────────────────────────────────────────────────
const EXPORTS = {
  material: () => exportCsv("material-entries.csv",
    ["Date", "Type", "Item", "Qty", "Unit", "Rate", "Amount", "From", "To", "Vehicle", "Vendor", "Note"],
    FILTERED.material.map((e) => [e.date, e.type, e.item, e.qty, e.unit, e.rate, e.qty * e.rate, e.from_loc, e.to_loc, e.vehicle, vendorName(e.vendor_id), e.note])),
  labour: () => exportCsv("labour-register.csv",
    ["Name", "Type", "Mobile", "Address", "ID", "Site", "Contractor", "Joining", "Status", "Total Paid"],
    FILTERED.labour.map((l) => [l.name, l.type, l.phone, l.address, l.id_number, l.site, vendorName(l.contractor_id), l.joining_date, l.status, labourPaidTotal(l.id)])),
  labourPay: () => exportCsv("labour-payments.csv",
    ["Date", "Labour", "Site", "Mode", "Reference", "Amount", "Remarks"],
    FILTERED.labourPay.map((p) => [p.date, labourName(p.labour_id), p.site, p.mode, p.reference, p.amount, p.note])),
  vendorTxn: () => exportCsv("vendor-ledger.csv",
    ["Date", "Vendor", "Type", "Amount", "Mode", "Reference", "By", "Note"],
    FILTERED.vendorTxn.map((t) => [t.date, vendorName(t.vendor_id), t.type, t.amount, t.mode, t.reference, t.by_name, t.note])),
  payments: () => exportCsv("payment-register.csv",
    ["Date", "Party", "Category", "Site", "Amount", "Mode", "Reference", "Remarks"],
    FILTERED.payments.map((r) => [r.date, r.party, r.category, r.site, r.amount, r.mode, r.reference, r.note])),
  receipts: () => exportCsv("receipt-register.csv",
    ["Date", "Received From", "Site", "Amount", "Mode", "Reference", "Remarks"],
    FILTERED.receipts.map((r) => [r.date, r.from_name, r.site, r.amount, r.mode, r.reference, r.note])),
};

// ── Admin Panel ──────────────────────────────────────────────────────────
const admin = {
  loaded: false, users: [], roles: [], clients: [], sites: [],
  modules: [], actions: [], accessUserId: null,
};
let editingUserId = null;

async function loadAdminPanel() {
  if (!isAdmin()) return;
  try {
    const data = await apiGet("/api/admin/bootstrap");
    Object.assign(admin, data, { loaded: true });
    renderAdmin();
    await loadAudit();
  } catch (err) {
    toast(err.message, "error");
  }
}

function renderAdmin() {
  setStat("statUserTotal", admin.users.length);
  setStat("statUserActive", admin.users.filter((u) => u.status === "Active").length);
  setStat("statRoleTotal", admin.roles.length);

  // Role dropdowns (user form + matrix selector)
  const roleOptions = admin.roles.map((r) => `<option value="${r.id}">${escapeHtml(r.name)}</option>`).join("");
  for (const id of ["formUser-role_id", "permRoleSelect"]) {
    const sel = document.getElementById(id);
    const prev = sel.value;
    sel.innerHTML = roleOptions;
    if ([...sel.options].some((o) => o.value === prev)) sel.value = prev;
  }
  // Matrix by default pehle non-admin role par khule (admin editable nahi hota)
  const permSel = document.getElementById("permRoleSelect");
  if (admin.roles.find((r) => r.id === permSel.value)?.is_admin) {
    const firstEditable = admin.roles.find((r) => !r.is_admin);
    if (firstEditable) permSel.value = firstEditable.id;
  }

  renderUserTable();
  renderRoleTable();
  renderPermMatrix();

  const audSel = document.getElementById("fltAudModule");
  const prev = audSel.value;
  audSel.innerHTML = '<option value="">— all —</option>' +
    ["users", "roles", ...admin.modules.map((m) => m.key)]
      .map((k) => `<option value="${k}">${k}</option>`).join("");
  if ([...audSel.options].some((o) => o.value === prev)) audSel.value = prev;
}

function accessSummary(u) {
  if (u.is_admin) return '<span class="badge badge-Active">Full access</span>';
  const parts = [];
  if (u.client_ids.length) parts.push(`${u.client_ids.length} client`);
  if (u.site_ids.length) parts.push(`${u.site_ids.length} site`);
  const ov = Object.keys(u.overrides || {}).length;
  if (ov) parts.push(`${ov} override`);
  return parts.length ? escapeHtml(parts.join(" · ")) : '<span class="txt-danger">kuch assign nahi</span>';
}

function renderUserTable() {
  const tbody = document.querySelector("#userTable tbody");
  setCountPill("userTableCount", admin.users.length);
  if (!admin.users.length) {
    tbody.innerHTML = emptyRow(7, "Koi user nahi");
    return;
  }
  tbody.innerHTML = admin.users.map((u) => {
    const next = u.status === "Active" ? "Inactive" : "Active";
    const self = u.id === state.me.id;
    const canToggleStatus = !self && u.status !== "Pending";
    const resetLabel = u.status === "Pending" ? "Resend Invite" : "Force Password Reset";
    return `<tr>
      <td>${avatarHtml(u.full_name || u.email)}${escapeHtml(u.full_name || u.email)}${self ? ' <span class="hint">(aap)</span>' : ""}</td>
      <td>${escapeHtml(u.email)}</td>
      <td><span class="role-pill${u.is_admin ? " role-admin" : ""}">${escapeHtml(u.role_name)}</span></td>
      <td>${accessSummary(u)}</td>
      <td>${escapeHtml(u.last_login || "—")}</td>
      <td><span class="badge badge-${u.status}">${escapeHtml(u.status)}</span>
          ${canToggleStatus ? `<button class="btn-link" data-user-status="${u.id}" data-next="${next}">${next === "Active" ? "Activate" : "Deactivate"}</button>` : ""}</td>
      <td class="row-actions">
        <button class="btn btn-secondary btn-sm" data-user-access="${u.id}">Access</button>
        <button class="btn btn-secondary btn-sm" data-user-resetpw="${u.id}">${resetLabel}</button>
        ${EDIT_BTN("data-user-edit", u.id)}${self ? "" : TRASH_BTN("data-user-del", u.id)}
      </td>
    </tr>`;
  }).join("");
}

function renderRoleTable() {
  const tbody = document.querySelector("#roleTable tbody");
  setCountPill("roleTableCount", admin.roles.length);
  tbody.innerHTML = admin.roles.map((r) => {
    const users = admin.users.filter((u) => u.role_id === r.id).length;
    return `<tr>
      <td><span class="role-pill${r.is_admin ? " role-admin" : ""}">${escapeHtml(r.name)}</span>${r.is_system ? ' <span class="hint">system</span>' : ""}</td>
      <td>${escapeHtml(r.description || "")}</td>
      <td class="num">${users}</td>
      <td class="row-actions">${r.is_system ? "" : TRASH_BTN("data-role-del", r.id)}</td>
    </tr>`;
  }).join("");
}

function renderPermMatrix() {
  const sel = document.getElementById("permRoleSelect");
  const role = admin.roles.find((r) => r.id === sel.value) || admin.roles[0];
  if (!role) return;
  sel.value = role.id;
  const locked = role.is_admin;
  document.getElementById("btnSaveMatrix").disabled = locked;
  document.getElementById("matrixHint").textContent = locked
    ? "Admin role ke paas hamesha full access hota hai — iska matrix edit nahi hota."
    : "Row = module, column = action. View off = module us role ke users se hide. Save karte hi turant lagoo ho jaata hai.";
  const table = document.getElementById("permMatrixTable");
  table.querySelector("thead").innerHTML =
    `<tr><th>Module</th>${admin.actions.map((a) => `<th class="ctr">${escapeHtml(a)}</th>`).join("")}</tr>`;
  table.querySelector("tbody").innerHTML = admin.modules.map((m) => `<tr>
      <td>${escapeHtml(m.label)}</td>
      ${admin.actions.map((a) =>
        `<td class="ctr"><input type="checkbox" data-pm-module="${m.key}" data-pm-action="${a}"
          ${role.permissions?.[m.key]?.[a] ? "checked" : ""} ${locked ? "disabled" : ""}></td>`).join("")}
    </tr>`).join("");
}

async function savePermMatrix() {
  const roleId = document.getElementById("permRoleSelect").value;
  const matrix = {};
  document.querySelectorAll("#permMatrixTable input[type=checkbox]").forEach((cb) => {
    (matrix[cb.dataset.pmModule] = matrix[cb.dataset.pmModule] || {})[cb.dataset.pmAction] = cb.checked;
  });
  try {
    await apiPut(`/api/admin/roles/${roleId}/permissions`, matrix);
    toast("Permissions saved — turant lagoo");
    await loadAdminPanel();
  } catch (err) {
    toast(err.message, "error");
  }
}

// ── User add/edit form ──
// Add mode: sirf email/name/role/phone — password admin kabhi set nahi karta,
// user invite email se khud karta hai. Edit mode: wahi fields + Status
// (jo tabhi Active ho sakta hai jab user apna password set kar chuka ho).
function setUserFormMode(editUser) {
  const form = document.getElementById("formUser");
  editingUserId = editUser ? editUser.id : null;
  form.classList.toggle("is-editing", !!editUser);
  document.getElementById("formUserTitle").textContent =
    editUser ? `Edit User — ${editUser.email}` : "Add User";
  form.querySelector(".field-status").hidden = !editUser;
  setSubmitLabel(form, editUser ? "Update User" : null);
  let cancel = form.querySelector(".btn-cancel-edit");
  if (editUser) {
    if (!cancel) {
      cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "btn btn-secondary btn-cancel-edit";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", () => { form.reset(); setUserFormMode(null); });
      form.querySelector('button[type="submit"]').after(cancel);
    }
    form.reset();
    fillForm(form, editUser);
    form.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth", block: "nearest" });
    form.elements.email.focus();
  } else if (cancel) {
    cancel.remove();
  }
}

// ── Access modal (assignments + overrides) ──
function openAccessModal(uid) {
  const u = admin.users.find((x) => x.id === uid);
  if (!u) return;
  admin.accessUserId = uid;
  document.getElementById("modalAccessTitle").textContent =
    `Access — ${u.full_name || u.email}` + (u.is_admin ? " (admin: hamesha full access)" : "");

  const tree = document.getElementById("accessTree");
  tree.innerHTML = admin.clients.map((cl) => {
    const clientChecked = u.client_ids.includes(cl.id);
    const sites = admin.sites.filter((s) => s.client_id === cl.id);
    return `<div class="access-client">
      <label class="access-client-row"><input type="checkbox" data-acc-client="${cl.id}" ${clientChecked ? "checked" : ""}>
        <strong>${escapeHtml(cl.name)}</strong> <span class="hint">poora client (saari sites)</span></label>
      <div class="access-sites">${sites.map((s) =>
        `<label><input type="checkbox" data-acc-site="${s.id}" data-acc-site-client="${cl.id}"
          ${u.site_ids.includes(s.id) ? "checked" : ""} ${clientChecked ? "disabled" : ""}> ${escapeHtml(s.name)}</label>`).join("")
        || '<span class="hint">is client ki koi site nahi</span>'}</div>
    </div>`;
  }).join("") || '<span class="hint">Pehle koi client banao</span>';

  const table = document.getElementById("overrideTable");
  const roleMatrix = admin.roles.find((r) => r.id === u.role_id)?.permissions || {};
  table.querySelector("thead").innerHTML =
    `<tr><th>Module</th>${admin.actions.map((a) => `<th class="ctr">${escapeHtml(a)}</th>`).join("")}</tr>`;
  table.querySelector("tbody").innerHTML = admin.modules.map((m) => `<tr>
      <td>${escapeHtml(m.label)}</td>
      ${admin.actions.map((a) => {
        const ov = u.overrides?.[m.key]?.[a];
        const cur = ov === true ? "1" : ov === false ? "0" : "";
        const roleVal = roleMatrix?.[m.key]?.[a] ? "✓" : "✗";
        return `<td class="ctr"><select class="ov-select" data-ov-module="${m.key}" data-ov-action="${a}" ${u.is_admin ? "disabled" : ""}>
          <option value=""${cur === "" ? " selected" : ""}>— (${roleVal})</option>
          <option value="1"${cur === "1" ? " selected" : ""}>✓ Allow</option>
          <option value="0"${cur === "0" ? " selected" : ""}>✗ Deny</option>
        </select></td>`;
      }).join("")}
    </tr>`).join("");
  openModal("modalAccess");
}

async function saveAccess() {
  const client_ids = [...document.querySelectorAll("#accessTree [data-acc-client]:checked")]
    .map((cb) => cb.dataset.accClient);
  const site_ids = [...document.querySelectorAll("#accessTree [data-acc-site]:checked")]
    .filter((cb) => !client_ids.includes(cb.dataset.accSiteClient)) // poora client mila to sites redundant
    .map((cb) => cb.dataset.accSite);
  const overrides = {};
  document.querySelectorAll("#overrideTable .ov-select").forEach((sel) => {
    if (sel.value === "") return;
    (overrides[sel.dataset.ovModule] = overrides[sel.dataset.ovModule] || {})[sel.dataset.ovAction] =
      sel.value === "1";
  });
  try {
    await apiPut(`/api/admin/users/${admin.accessUserId}/access`, { client_ids, site_ids, overrides });
    closeModal("modalAccess");
    toast("Access updated — user ke agle request se lagoo");
    await loadAdminPanel();
  } catch (err) {
    toast(err.message, "error");
  }
}

// ── Audit log ──
async function loadAudit() {
  const p = new URLSearchParams();
  if (val("fltAudUser").trim()) p.set("username", val("fltAudUser").trim());
  if (val("fltAudModule")) p.set("module", val("fltAudModule"));
  if (val("fltAudFrom")) p.set("from", val("fltAudFrom"));
  if (val("fltAudTo")) p.set("to", val("fltAudTo"));
  try {
    const data = await apiGet(`/api/admin/audit?${p.toString()}`);
    const tbody = document.querySelector("#auditTable tbody");
    setCountPill("auditTableCount", data.logs.length);
    tbody.innerHTML = data.logs.map((l) => `<tr>
        <td>${escapeHtml(l.ts)}</td>
        <td>${escapeHtml(l.username)}</td>
        <td><span class="audit-badge audit-${escapeHtml(l.action)}">${escapeHtml(l.action)}</span></td>
        <td>${escapeHtml(l.module || "")}</td>
        <td>${escapeHtml(l.detail || "")}</td>
        <td>${escapeHtml(l.ip || "")}</td>
      </tr>`).join("") || emptyRow(6, "Koi log nahi");
  } catch (err) {
    toast(err.message, "error");
  }
}

// ── Admin listeners (attachListeners se call hota hai) ──
function attachAdminListeners() {
  document.getElementById("tab-admin").addEventListener("click", async (e) => {
    const sub = e.target.closest(".sub-btn");
    if (sub) {
      document.querySelectorAll(".sub-btn").forEach((b) => b.classList.toggle("active", b === sub));
      document.querySelectorAll(".admin-sub").forEach((p) =>
        p.classList.toggle("active", p.id === `sub-${sub.dataset.sub}`));
      return;
    }
    const btn = e.target.closest(
      "[data-user-edit],[data-user-del],[data-user-access],[data-user-resetpw],[data-user-status],[data-role-del]");
    if (!btn) return;
    try {
      if (btn.dataset.userEdit) {
        setUserFormMode(admin.users.find((u) => u.id === btn.dataset.userEdit));
      } else if (btn.dataset.userAccess) {
        openAccessModal(btn.dataset.userAccess);
      } else if (btn.dataset.userResetpw) {
        const u = admin.users.find((x) => x.id === btn.dataset.userResetpw);
        const isReset = u?.status === "Active";
        if (!confirm(isReset
              ? "Password reset email bhejni hai? User agla naya password set karne tak login nahi kar payega."
              : "Invite email dobara bhejni hai?")) return;
        const res = await apiPost(`/api/admin/users/${btn.dataset.userResetpw}/send_reset`, {});
        if (res.email_sent) {
          toast("Email bhej di gayi");
        } else {
          alert("Email bhejne me dikkat aayi (SMTP configure nahi hai?) — ye link manually user ko bhejo:\n\n" + res.invite_link);
        }
        await loadAdminPanel();
      } else if (btn.dataset.userStatus) {
        await apiPost(`/api/admin/users/${btn.dataset.userStatus}/status`, { status: btn.dataset.next });
        toast(`User ${btn.dataset.next === "Active" ? "activate" : "deactivate"} ho gaya`);
        await loadAdminPanel();
      } else if (btn.dataset.userDel) {
        if (!confirm("User ko permanently delete karna hai? Uske assignments bhi delete honge.")) return;
        await apiDelete(`/api/admin/users/${btn.dataset.userDel}`);
        toast("User deleted");
        await loadAdminPanel();
      } else if (btn.dataset.roleDel) {
        if (!confirm("Role delete karna hai?")) return;
        await apiDelete(`/api/admin/roles/${btn.dataset.roleDel}`);
        toast("Role deleted");
        await loadAdminPanel();
      }
    } catch (err) {
      toast(err.message, "error");
    }
  });

  document.getElementById("formUser").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    const payload = {
      email: fd.get("email") || "",
      full_name: fd.get("full_name") || "",
      phone: fd.get("phone") || "",
      role_id: fd.get("role_id"),
      status: fd.get("status") || "Active",
    };
    setFormBusy(form, true);
    try {
      if (editingUserId) {
        await apiPut(`/api/admin/users/${editingUserId}`, payload);
        toast("User updated");
      } else {
        const res = await apiPost("/api/admin/users", payload);
        if (res.email_sent) {
          toast("User ban gaya — invite email bhej di gayi");
        } else {
          alert("User ban gaya, lekin invite email bhejne me dikkat aayi (SMTP configure nahi hai?) — ye link manually bhejo:\n\n" + res.invite_link);
        }
      }
      form.reset();
      setUserFormMode(null);
      await loadAdminPanel();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setFormBusy(form, false);
    }
  });

  document.getElementById("formRole").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    setFormBusy(form, true);
    try {
      await apiPost("/api/admin/roles", { name: fd.get("name"), description: fd.get("description") || "" });
      form.reset();
      toast("Role ban gaya — ab matrix me permissions set karo");
      await loadAdminPanel();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setFormBusy(form, false);
    }
  });

  document.getElementById("permRoleSelect").addEventListener("change", renderPermMatrix);
  document.getElementById("btnSaveMatrix").addEventListener("click", savePermMatrix);
  document.getElementById("btnSaveAccess").addEventListener("click", saveAccess);

  // Client tick = saari sites — individual site checkboxes disable
  document.getElementById("accessTree").addEventListener("change", (e) => {
    const cb = e.target.closest("[data-acc-client]");
    if (!cb) return;
    document.querySelectorAll(`#accessTree [data-acc-site-client="${cb.dataset.accClient}"]`)
      .forEach((s) => { s.disabled = cb.checked; });
  });

  document.getElementById("btnAuditRefresh").addEventListener("click", loadAudit);
  for (const id of ["fltAudModule", "fltAudFrom", "fltAudTo"]) {
    document.getElementById(id).addEventListener("change", loadAudit);
  }
  document.getElementById("fltAudUser").addEventListener("change", loadAudit);

  // Apna password badlo (sab users ke liye)
  document.getElementById("btnChangePw").addEventListener("click", () => {
    document.getElementById("formChangePw").reset();
    openModal("modalChangePw");
  });
  document.getElementById("formChangePw").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    if (fd.get("new_password") !== fd.get("confirm_password")) {
      toast("Naya password aur confirm match nahi kar rahe", "error");
      return;
    }
    setFormBusy(form, true);
    try {
      await apiPost("/api/change_password", {
        current_password: fd.get("current_password"),
        new_password: fd.get("new_password"),
      });
      closeModal("modalChangePw");
      form.reset();
      toast("Password badal gaya");
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setFormBusy(form, false);
    }
  });
}

// ── Full render ──────────────────────────────────────────────────────────
function renderAll() {
  renderShell();
  applyPermissionGating();
  if (!state.clients.length) return;

  populateSelects();
  renderClientsTable();
  renderSitesTable();
  renderMaterialsMaster();
  renderMaterialEntries();
  renderAssetEntries();
  renderStockBalance();
  renderAssetBalance();
  renderLabourRegister();
  renderLabourPayments();
  renderVendorSummaryTable();
  renderVendorTxnTable();
  renderExpenseTable();
  renderExpenseSummaryTable();
  renderPaymentRegister();
  renderReceiptsTable();
  renderReceiptModeSummary();
  renderDashboard();
  renderStats();

  document.querySelectorAll(".entry-form[data-kind]").forEach(updateEntryFormVisibility);
  document.querySelectorAll(".table-search").forEach((i) => { if (i.value) applyTableFilter(i); });
}

// Scoped re-renders when a filter changes (no data reload needed)
const SCOPE_RENDER = {
  clients: () => { renderClientsTable(); },
  sites: () => { renderSitesTable(); },
  material: () => { renderMaterialEntries(); },
  stock: () => { renderStockBalance(); },
  labour: () => { renderLabourRegister(); },
  labourPay: () => { renderLabourPayments(); },
  vendorTxn: () => { renderVendorTxnTable(); },
  payments: () => { renderPaymentRegister(); },
  receipts: () => { renderReceiptsTable(); },
};

// ── Simple form submit helper ────────────────────────────────────────────
function wireForm(formId, endpoint, buildPayload, successMsg, { keepValues = false } = {}) {
  const form = document.getElementById(formId);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const editId = EDITING[formId];
    setFormBusy(form, true);
    try {
      if (editId) {
        await apiPut(`${endpoint}/${editId}`, buildPayload(fd));
        exitEditMode(form);
      } else {
        await apiPost(endpoint, buildPayload(fd));
        if (!keepValues) { form.reset(); setDefaultDates(); }
      }
      await loadBootstrap(state.client_id);
      toast(editId ? "Updated" : successMsg);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setFormBusy(form, false);
    }
  });
}

// ── Wire up static listeners (run once) ──────────────────────────────────
function activateTab(tab) {
  const btn = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
  const panel = document.getElementById(`tab-${tab}`);
  if (!btn || !panel) return;
  document.querySelectorAll(".tab-btn").forEach((b) => {
    const isActive = b === btn;
    b.classList.toggle("active", isActive);
    b.setAttribute("aria-selected", isActive ? "true" : "false");
    b.tabIndex = isActive ? 0 : -1; // roving tabindex (WAI-ARIA tabs pattern)
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    const isActive = p === panel;
    p.classList.toggle("active", isActive);
    p.tabIndex = isActive ? 0 : -1;
  });
  updatePageHeader(tab);
  updateAppVisibility();
  if (tab === "admin" && isAdmin() && !admin.loaded) loadAdminPanel();
  localStorage.setItem("khata_tab", tab);
}

function attachListeners() {
  document.querySelectorAll(".tab-panel").forEach((p) => p.setAttribute("role", "tabpanel"));
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tab));
  });

  // Arrow-key navigation between tabs (WAI-ARIA tabs pattern)
  const tabList = document.querySelector(".side-nav");
  tabList?.addEventListener("keydown", (e) => {
    if (!["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
    const tabs = [...document.querySelectorAll(".tab-btn")];
    const current = tabs.indexOf(document.activeElement);
    if (current === -1) return;
    e.preventDefault();
    let next = current;
    if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    else if (e.key === "ArrowDown" || e.key === "ArrowRight") next = (current + 1) % tabs.length;
    else next = (current - 1 + tabs.length) % tabs.length;
    const btn = tabs[next];
    activateTab(btn.dataset.tab);
    btn.focus();
  });

  document.addEventListener("input", (e) => {
    if (e.target.matches(".table-search")) applyTableFilter(e.target);
    if (e.target.matches(".flt")) SCOPE_RENDER[e.target.dataset.scope]?.();
  });
  document.addEventListener("change", (e) => {
    if (e.target.matches(".flt")) SCOPE_RENDER[e.target.dataset.scope]?.();
    if (e.target.id === "fltStockLoc") renderStockBalance();
  });

  document.addEventListener("click", (e) => {
    const exp = e.target.closest("[data-export]");
    if (exp) { EXPORTS[exp.dataset.export]?.(); return; }
    const editBtn = e.target.closest(
      "[data-edit-entry],[data-edit-client],[data-edit-site],[data-edit-vendor],[data-edit-vendor-txn],[data-edit-expense],[data-edit-labourer],[data-edit-labour-payment],[data-edit-receipt]");
    if (editBtn) {
      const key = Object.keys(EDIT_HANDLERS).find((k) => editBtn.dataset[k]);
      if (key) EDIT_HANDLERS[key](editBtn.dataset[key]);
      return;
    }
    handleDeleteClick(e);
  });

  document.getElementById("clientSelect").addEventListener("change", async (e) => {
    const id = e.target.value;
    localStorage.setItem("khata_client_id", id);
    try {
      await loadBootstrap(id);
    } catch (err) {
      toast(err.message, "error");
    }
  });

  document.getElementById("formLogin").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    setFormBusy(form, true);
    try {
      await apiPost("/api/login", { email: fd.get("email"), password: fd.get("password") });
      form.reset();
      document.getElementById("loginScreen").hidden = true;
      document.getElementById("loading").hidden = false;
      admin.loaded = false; // naya user — admin panel dobara load hoga
      await loadBootstrap(localStorage.getItem("khata_client_id") || "");
    } catch (err) {
      toast(err.message, "error");
    } finally {
      document.getElementById("loading").hidden = true;
      setFormBusy(form, false);
    }
  });

  document.getElementById("btnLogout").addEventListener("click", async () => {
    try { await apiPost("/api/logout", {}); } catch { /* session pehle se khatam */ }
    location.reload();
  });

  document.getElementById("btnEmptyAddClient").addEventListener("click", () => openModal("modalClient"));
  document.querySelectorAll("[data-close-modal]").forEach((btn) =>
    btn.addEventListener("click", () => closeModal(btn.closest(".modal-overlay").id))
  );

  document.querySelectorAll(".modal-overlay").forEach((overlay) => {
    overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(overlay.id); });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") document.querySelectorAll(".modal-overlay").forEach((o) => { if (!o.hidden) closeModal(o.id); });
  });

  document.getElementById("formClient").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    const sites = (fd.get("sites") || "").split(",").map((s) => s.trim()).filter(Boolean);
    setFormBusy(form, true);
    try {
      const res = await apiPost("/api/clients", {
        name: fd.get("name"),
        contact_person: fd.get("contact_person") || "",
        phone: fd.get("phone") || "",
        email: fd.get("email") || "",
        address: fd.get("address") || "",
        status: fd.get("status") || "Active",
        sites,
      });
      form.reset();
      closeModal("modalClient");
      localStorage.setItem("khata_client_id", res.id);
      await loadBootstrap(res.id);
      toast("Client added");
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setFormBusy(form, false);
    }
  });

  document.querySelectorAll(".entry-form[data-kind]").forEach((form) => {
    form.addEventListener("submit", handleEntrySubmit);
    form.querySelector(".f-type").addEventListener("change", () => updateEntryFormVisibility(form));
    form.querySelector('[name="create_grn"]').addEventListener("change", () => updateEntryFormVisibility(form));
  });

  // Material form: auto-fill unit from materials master
  const matItem = document.querySelector('#formMaterial input[name="item"]');
  matItem.addEventListener("change", () => {
    const m = state.materials.find((x) => x.name.toLowerCase() === matItem.value.trim().toLowerCase());
    const unitInput = document.querySelector('#formMaterial input[name="unit"]');
    if (m && m.unit && !unitInput.value) unitInput.value = m.unit;
  });

  wireForm("formClientMgmt", "/api/clients", (fd) => ({
    name: fd.get("name"),
    contact_person: fd.get("contact_person") || "",
    phone: fd.get("phone") || "",
    email: fd.get("email") || "",
    address: fd.get("address") || "",
    status: fd.get("status") || "Active",
  }), "Client added");

  wireForm("formSiteMgmt", "/api/sites", (fd) => ({
    client_id: fd.get("client_id"),
    name: fd.get("name"),
    address: fd.get("address") || "",
    status: fd.get("status") || "Active",
  }), "Site created");

  wireForm("formMaterialMaster", "/api/materials", (fd) => ({
    client_id: state.client_id,
    name: fd.get("name"),
    unit: fd.get("unit") || "",
    category: fd.get("category") || "",
  }), "Material added");

  wireForm("formLabour", "/api/labourers", (fd) => ({
    client_id: state.client_id,
    name: fd.get("name"),
    phone: fd.get("phone") || "",
    address: fd.get("address") || "",
    id_number: fd.get("id_number") || "",
    type: fd.get("type"),
    contractor_id: fd.get("contractor_id") || "",
    site: fd.get("site") || "",
    joining_date: fd.get("joining_date") || "",
    status: fd.get("status") || "Active",
  }), "Labour added");

  wireForm("formLabourPay", "/api/labour_payments", (fd) => ({
    client_id: state.client_id,
    labour_id: fd.get("labour_id"),
    site: fd.get("site") || "",
    amount: fd.get("amount"),
    date: fd.get("date"),
    mode: fd.get("mode") || "Cash",
    reference: fd.get("reference") || "",
    note: fd.get("note") || "",
  }), "Payment recorded");

  wireForm("formVendor", "/api/vendors", (fd) => ({
    client_id: state.client_id,
    name: fd.get("name"),
    phone: fd.get("phone") || "",
    contact_person: fd.get("contact_person") || "",
    gst: fd.get("gst") || "",
    address: fd.get("address") || "",
    category: fd.get("category") || "",
    status: fd.get("status") || "Active",
  }), "Vendor added");

  wireForm("formVendorTxn", "/api/vendor_txns", (fd) => ({
    client_id: state.client_id,
    vendor_id: fd.get("vendor_id"),
    type: fd.get("type"),
    amount: fd.get("amount"),
    date: fd.get("date"),
    by_name: fd.get("by_name") || "",
    mode: fd.get("mode") || "",
    reference: fd.get("reference") || "",
    note: fd.get("note") || "",
  }), "Transaction added");

  wireForm("formExpense", "/api/expenses", (fd) => ({
    client_id: state.client_id,
    site: fd.get("site"),
    date: fd.get("date"),
    category: fd.get("category"),
    item: fd.get("item"),
    qty: fd.get("qty"),
    unit: fd.get("unit") || "nos",
    rate: fd.get("rate") || 0,
    note: fd.get("note") || "",
  }), "Expense added");

  wireForm("formReceipt", "/api/receipts", (fd) => ({
    client_id: state.client_id,
    date: fd.get("date"),
    from_name: fd.get("from_name"),
    amount: fd.get("amount"),
    mode: fd.get("mode") || "Cash",
    reference: fd.get("reference") || "",
    site: fd.get("site") || "",
    note: fd.get("note") || "",
  }), "Receipt added");

  attachAdminListeners();
}

// ── Invite / set-password flow (?invite=TOKEN in URL) ────────────────────
function getInviteToken() {
  return new URLSearchParams(location.search).get("invite") || "";
}

function clearInviteParam() {
  const url = new URL(location.href);
  url.searchParams.delete("invite");
  history.replaceState({}, "", url.pathname + url.search + url.hash);
}

// True return karta hai agar invite screen le raha hai control — us case me
// init() normal login/bootstrap flow skip kar deta hai.
async function tryInviteFlow() {
  const token = getInviteToken();
  if (!token) return false;

  document.getElementById("loading").hidden = true;
  document.getElementById("app").hidden = true;
  document.getElementById("emptyState").hidden = true;
  const scr = document.getElementById("inviteScreen");

  let info;
  try {
    info = await apiGet(`/api/invite/${encodeURIComponent(token)}`);
  } catch (err) {
    toast(err.message, "error");
    clearInviteParam();
    return false;
  }

  document.getElementById("inviteForEmail").textContent =
    `${info.full_name || info.email} (${info.email}) — apna password set karo`;
  scr.hidden = false;

  document.getElementById("formAcceptInvite").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    if (fd.get("password") !== fd.get("confirm_password")) {
      toast("Password aur confirm match nahi kar rahe", "error");
      return;
    }
    setFormBusy(form, true);
    try {
      await apiPost("/api/accept_invite", { token, password: fd.get("password") });
      clearInviteParam();
      scr.hidden = true;
      document.getElementById("loading").hidden = false;
      await loadBootstrap(localStorage.getItem("khata_client_id") || "");
      toast("Password set ho gaya — welcome!");
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setFormBusy(form, false);
      document.getElementById("loading").hidden = true;
    }
  }, { once: true });

  return true;
}

// ── Init ─────────────────────────────────────────────────────────────────
(async function init() {
  setDefaultDates();
  attachListeners();
  activateTab(localStorage.getItem("khata_tab") || "dashboard");
  if (await tryInviteFlow()) return;
  try {
    const savedClientId = localStorage.getItem("khata_client_id") || "";
    await loadBootstrap(savedClientId);
  } catch (err) {
    if (!err.authRequired) toast(err.message, "error");
  } finally {
    document.getElementById("loading").hidden = true;
  }
})();
