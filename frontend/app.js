"use strict";

const state = {
  clients: [],
  client_id: "",
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

async function apiGet(url) {
  const res = await fetch(url);
  if (!res.ok) throw await errorFrom(res);
  return res.json();
}

async function apiPost(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw await errorFrom(res);
  return res.json();
}

async function apiDelete(url) {
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok) throw await errorFrom(res);
  return res.json();
}

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

const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const TAB_META = {
  dashboard: ["Dashboard", "Poore kaam ka ek nazar mein summary"],
  material:  ["Material Tracking", "Purchase, transfer, consumption aur live stock"],
  assets:    ["Assets Tracking", "Machinery aur equipment ka location-wise register"],
  labour:    ["Labour Management", "Labour register, site-wise filter aur payments"],
  vendors:   ["Vendor Payments", "Vendor master, bills, payments aur closing balance"],
  expenses:  ["Site Expenses", "Har site ka category-wise kharcha"],
  payments:  ["Payment Register", "Saare outgoing payments ek jagah"],
  receipts:  ["Receipt Register", "Saare incoming payments ka hisaab"],
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

function openModal(id) {
  const overlay = document.getElementById(id);
  overlay.hidden = false;
  overlay.querySelector("input, select")?.focus();
}
function closeModal(id) { document.getElementById(id).hidden = true; }

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
  renderAll();
}

// ── Rendering: shell ─────────────────────────────────────────────────────
function renderShell() {
  const hasClients = state.clients.length > 0;
  document.getElementById("emptyState").hidden = hasClients;
  document.getElementById("app").hidden = !hasClients;
  document.getElementById("sitesBar").hidden = !hasClients;
  document.getElementById("btnAddSite").disabled = !state.client_id;

  const sel = document.getElementById("clientSelect");
  sel.innerHTML = '<option value="">— Select client —</option>' +
    state.clients.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
  sel.value = state.client_id || "";

  const chips = document.getElementById("sitesChips");
  chips.innerHTML = state.sites.length
    ? state.sites.map((s) => `<span class="chip">${escapeHtml(s.name)}</span>`).join("")
    : '<span class="chip">Koi site nahi — "+ Site" se add karo</span>';
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
      <td>${TRASH_BTN("data-del-entry", e.id)}</td>
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
      <td>${TRASH_BTN("data-del-entry", e.id)}</td>
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
      <td>${TRASH_BTN("data-del-labourer", l.id)}</td>
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
      <td>${TRASH_BTN("data-del-labour-payment", p.id)}</td>
    </tr>`).join("");
}

// ── Vendors ──────────────────────────────────────────────────────────────
function renderVendorSummaryTable() {
  const tbody = document.querySelector("#vendorSummaryTable tbody");
  if (!state.vendors.length) {
    tbody.innerHTML = emptyRow(7, "Koi vendor nahi hai");
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
      <td>${TRASH_BTN("data-del-vendor-txn", t.id)}</td>
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
      <td>${TRASH_BTN("data-del-expense", x.id)}</td>
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
      <td>${TRASH_BTN("data-del-receipt", r.id)}</td>
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

  if (type === "Transfer") {
    payload.from_loc = fd.get("from_loc");
    payload.to_loc = fd.get("to_loc");
    payload.vehicle = fd.get("vehicle") || "";
  } else if (type === "Purchase") {
    payload.to_loc = fd.get("to_loc_single");
    payload.vendor_id = fd.get("vendor_id") || "";
    if (fd.get("create_grn")) {
      payload.create_grn = true;
      payload.by_name = fd.get("by_name") || "Site Engineer";
    }
  } else {
    payload.from_loc = fd.get("to_loc_single");
  }

  setFormBusy(form, true);
  try {
    await apiPost("/api/entries", payload);
    form.reset();
    setDefaultDates();
    updateEntryFormVisibility(form);
    await loadBootstrap(state.client_id);
    toast("Entry added");
  } catch (err) {
    toast(err.message, "error");
  } finally {
    setFormBusy(form, false);
  }
}

// ── Delete / toggle (event delegation) ───────────────────────────────────
const DELETE_ROUTES = [
  ["delEntry", "entries"],
  ["delVendorTxn", "vendor_txns"],
  ["delExpense", "expenses"],
  ["delMaterial", "materials"],
  ["delLabourer", "labourers"],
  ["delLabourPayment", "labour_payments"],
  ["delReceipt", "receipts"],
];

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
    "[data-del-entry],[data-del-vendor-txn],[data-del-expense],[data-del-material],[data-del-labourer],[data-del-labour-payment],[data-del-receipt]");
  if (!btn) return;

  const found = DELETE_ROUTES.find(([key]) => btn.dataset[key]);
  if (!found) return;
  const [key, endpoint] = found;

  if (!confirm("Delete this record?")) return;
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

// ── Full render ──────────────────────────────────────────────────────────
function renderAll() {
  renderShell();
  if (!state.clients.length) return;

  populateSelects();
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
    setFormBusy(form, true);
    try {
      await apiPost(endpoint, buildPayload(fd));
      if (!keepValues) { form.reset(); setDefaultDates(); }
      await loadBootstrap(state.client_id);
      toast(successMsg);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setFormBusy(form, false);
    }
  });
}

// ── Wire up static listeners (run once) ──────────────────────────────────
function attachListeners() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
      updatePageHeader(btn.dataset.tab);
    });
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

  document.getElementById("btnAddClient").addEventListener("click", () => openModal("modalClient"));
  document.getElementById("btnEmptyAddClient").addEventListener("click", () => openModal("modalClient"));
  document.getElementById("btnAddSite").addEventListener("click", () => openModal("modalSite"));
  document.querySelectorAll("[data-close-modal]").forEach((btn) =>
    btn.addEventListener("click", () => btn.closest(".modal-overlay").hidden = true)
  );

  document.querySelectorAll(".modal-overlay").forEach((overlay) => {
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.hidden = true; });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") document.querySelectorAll(".modal-overlay").forEach((o) => o.hidden = true);
  });

  document.getElementById("formClient").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    const sites = (fd.get("sites") || "").split(",").map((s) => s.trim()).filter(Boolean);
    setFormBusy(form, true);
    try {
      const res = await apiPost("/api/clients", { name: fd.get("name"), sites });
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

  document.getElementById("formSite").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    setFormBusy(form, true);
    try {
      await apiPost("/api/sites", { name: fd.get("name"), client_id: state.client_id });
      form.reset();
      closeModal("modalSite");
      await loadBootstrap(state.client_id);
      toast("Site added");
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
}

// ── Init ─────────────────────────────────────────────────────────────────
(async function init() {
  setDefaultDates();
  attachListeners();
  updatePageHeader("dashboard");
  try {
    const savedClientId = localStorage.getItem("khata_client_id") || "";
    await loadBootstrap(savedClientId);
  } catch (err) {
    toast(err.message, "error");
  } finally {
    document.getElementById("loading").hidden = true;
  }
})();
