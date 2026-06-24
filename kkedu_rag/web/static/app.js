// KKEdu RAG — streaming chat client (Technolize-style light UI, vanilla JS).
"use strict";

const $ = (id) => document.getElementById(id);
const messages = $("messages"), input = $("input"), composer = $("composer"),
      sendBtn = $("send-btn"), fileInput = $("file-input"),
      micBtn = $("mic-btn"), statusDot = $("status-dot"),
      welcome = $("welcome"), history = $("history"), suggestions = $("suggestions"),
      newChat = $("new-chat"), clearBtn = $("clear-btn"),
      docsBtn = $("docs-btn"), docBadge = $("doc-badge"),
      themeToggle = document.querySelector(".theme-toggle"),
      docsModal = $("docs-modal"), modalClose = $("modal-close"), modalList = $("modal-list"),
      modalDrop = $("modal-drop"), modalCount = $("modal-count"),
      modelBtn = $("model-btn"), modelMenu = $("model-menu"), modelName = $("model-name"),
      exportBtn = $("export-btn"), exportMenu = $("export-menu"),
      userCard = $("user-card"), profileMenu = $("profile-menu"),
      settingsModal = $("settings-modal"), settingsForm = $("settings-form"),
      settingsClose = $("settings-close"), settingsSave = $("settings-save"),
      settingsMsg = $("settings-msg"), modelList = $("model-list");

let streaming = false, hasMessages = false;
const transcript = [];                                     // {role, text} for export
let selectedSources = [];                                  // [] = all files
let conversationId = null;                                 // active chat thread (null = new)
const scopeBtn = $("scope-btn"), scopeMenu = $("scope-menu"), scopeLabel = $("scope-label");

// ---- Markdown (escape first, then format) ----
function escapeHtml(s) { return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function renderMarkdown(md) {
  const lines = escapeHtml(md).split("\n");
  let html = "", inList = false, inTable = false;
  const inline = (t) => t
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
  const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
  const closeTable = () => { if (inTable) { html += "</table>"; inTable = false; } };
  for (const line of lines) {
    const t = line.trim();
    if (/^[-*]\s+/.test(t)) {
      closeTable(); if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${inline(t.replace(/^[-*]\s+/, ""))}</li>`;
    } else if (/^\|(.+)\|$/.test(t)) {
      closeList();
      if (/^\|[\s:|-]+\|$/.test(t)) continue;
      if (!inTable) { html += "<table>"; inTable = true; }
      html += `<tr>${t.slice(1,-1).split("|").map((c)=>`<td>${inline(c.trim())}</td>`).join("")}</tr>`;
    } else if (t === "") { closeList(); closeTable(); }
    else { closeList(); closeTable(); html += `<p>${inline(t)}</p>`; }
  }
  closeList(); closeTable();
  return html;
}

// ---- View switching ----
function enterChat() {
  if (hasMessages) return;
  hasMessages = true; welcome.style.display = "none";
  messages.classList.remove("hide");
}
function addMessage(role, text = "") {
  enterChat();
  const msg = document.createElement("div");
  msg.className = `msg ${role}`;
  msg.innerHTML = `<div class="avatar">${role === "user" ? "B" : "K"}</div>
    <div class="bubble"><div class="role">${role === "user" ? "You" : "KKEdu RAG"}</div>
    <div class="tool"></div><div class="content"></div></div>`;
  messages.appendChild(msg);
  if (role === "user") msg.querySelector(".content").textContent = text;
  scrollDown();
  return msg;
}
function scrollDown() { const s = $("scroll"); s.scrollTop = s.scrollHeight; }

// ---- Chat threads (SQL-backed history) ----
async function loadConversations() {
  const data = await (await fetch("/api/conversations")).json();
  const list = data.conversations || [];
  history.innerHTML = list.length ? "" : '<li class="empty">No conversations yet</li>';
  for (const cv of list) {
    const li = document.createElement("li");
    li.className = "history-item" + (cv.id === conversationId ? " active" : "");
    li.innerHTML = `<span class="ht" title="${escapeHtml(cv.title)}">${escapeHtml(cv.title)}</span>
      <button class="ht-del" title="Delete" data-id="${cv.id}">
        <svg viewBox="0 0 24 24" class="icon"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m-1 0v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6"/></svg></button>`;
    li.querySelector(".ht").addEventListener("click", () => openConversation(cv.id));
    li.querySelector(".ht-del").addEventListener("click", (e) => { e.stopPropagation(); deleteConversation(cv.id); });
    history.appendChild(li);
  }
}
async function openConversation(id) {
  const data = await (await fetch(`/api/conversations/${id}`)).json();
  conversationId = id; transcript.length = 0;
  messages.innerHTML = ""; welcome.style.display = "none"; messages.classList.remove("hide");
  hasMessages = true;
  for (const m of data.messages) {
    const text = typeof m.content === "string" ? m.content
      : (Array.isArray(m.content) ? m.content.map((p) => p.text || "").join("") : "");
    if (m.role !== "user" && !text.trim()) continue;
    const el = addMessage(m.role === "user" ? "user" : "bot", text);
    if (m.role !== "user") el.querySelector(".content").innerHTML = renderMarkdown(text);
    transcript.push({ role: m.role, text });
  }
  loadConversations(); scrollDown();
}
async function deleteConversation(id) {
  if (!(await customConfirm("Delete this conversation?"))) return;
  await fetch(`/api/conversations/${id}/delete`, { method: "POST" });
  if (id === conversationId) startNewChat();
  loadConversations(); toast("Conversation deleted.");
}

// ---- Send + stream ----
async function send(text) {
  if (streaming || !text.trim()) return;
  streaming = true; sendBtn.disabled = true;
  addMessage("user", text);
  transcript.push({ role: "user", text });
  const bot = addMessage("bot");
  const toolBox = bot.querySelector(".tool"), content = bot.querySelector(".content");
  content.innerHTML = '<span class="cursor"></span>';
  let raw = "";
  try {
    const resp = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, sources: selectedSources, conversation_id: conversationId }),
    });
    if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);
    const reader = resp.body.getReader(), decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n"); buf = parts.pop();
      for (const part of parts) {
        const line = part.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const ev = JSON.parse(line.slice(6));
        if (ev.type === "meta") {
          conversationId = ev.conversation_id;             // bind this turn to its thread
        } else if (ev.type === "token") {
          raw += ev.text; content.innerHTML = renderMarkdown(raw) + '<span class="cursor"></span>'; scrollDown();
        } else if (ev.type === "tool") {
          toolBox.innerHTML = ev.label
            ? `<span class="tool-chip"><span class="spinner"></span>${ev.label}…</span>` : "";
        } else if (ev.type === "correction" || ev.type === "done") {
          raw = ev.text; toolBox.innerHTML = "";           // answer finalized -> clear any chip
        }
        else if (ev.type === "error") { throw new Error(ev.text); }
      }
    }
    toolBox.innerHTML = ""; content.innerHTML = renderMarkdown(raw);
    transcript.push({ role: "assistant", text: raw });
    loadConversations();                                   // refresh sidebar history
  } catch (err) {
    toolBox.innerHTML = "";
    content.innerHTML = `<p style="color:#e0556a">⚠ ${escapeHtml(String(err.message || err))}</p>`;
  } finally { streaming = false; sendBtn.disabled = false; scrollDown(); input.focus(); }
}

// ---- Upload ----
// ---- Processing modal (animated upload + indexing) ----
const proc = {
  modal: $("proc-modal"), card: document.querySelector(".proc-card"),
  title: $("proc-title"), files: $("proc-files"), bar: document.querySelector(".proc-bar"),
  fill: $("proc-fill"), steps: $("proc-steps"), result: $("proc-result"),
  close: $("proc-close"), glyph: $("proc-glyph"), orb: $("proc-orb"),
};
const _sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function procStep(name, state) {                           // state: 'active' | 'done'
  const li = proc.steps.querySelector(`[data-step="${name}"]`);
  if (!li) return;
  li.classList.remove("active", "done"); li.classList.add(state);
}
function procReset(files) {
  proc.card.classList.remove("ok");
  proc.glyph.innerHTML = '<path d="M3 5.5A1.5 1.5 0 0 1 4.5 4H9a3 3 0 0 1 3 3 3 3 0 0 1 3-3h4.5A1.5 1.5 0 0 1 21 5.5v11a1.5 1.5 0 0 1-1.5 1.5H15a3 3 0 0 0-3 3 3 3 0 0 0-3-3H4.5A1.5 1.5 0 0 1 3 16.5z"/><path d="M12 7v13"/>';
  proc.title.textContent = "Processing documents";
  proc.files.textContent = [...files].map((f) => f.name).join(", ");
  proc.steps.querySelectorAll("li").forEach((li) => li.classList.remove("active", "done"));
  proc.bar.classList.add("indet"); proc.fill.style.right = "";
  proc.result.hidden = true; proc.result.innerHTML = ""; proc.close.hidden = true;
  proc.modal.hidden = false;
}
function procFinish(results, status) {
  proc.bar.classList.remove("indet"); proc.fill.style.right = "0%";
  proc.steps.querySelectorAll("li").forEach((li) => li.classList.add("done"));
  proc.card.classList.add("ok"); proc.title.textContent = "Indexing complete";
  proc.glyph.innerHTML = '<path d="M20 6 9 17l-5-5"/>';
  proc.result.innerHTML = results.map((r) => r.error
    ? `<div class="row bad"><span>${escapeHtml(r.filename)}</span><span class="n">${escapeHtml(r.error)}</span></div>`
    : `<div class="row"><span>${escapeHtml(r.filename)}</span><span class="n">${r.chunks} chunks indexed</span></div>`).join("");
  proc.result.hidden = false; proc.close.hidden = false;
}
proc.close.addEventListener("click", () => { proc.modal.hidden = true; });

async function upload(files) {
  if (!files.length) return;
  procReset(files);
  procStep("upload", "active");
  const fd = new FormData(); [...files].forEach((f) => fd.append("files", f));
  try {
    const reqP = fetch("/api/upload", { method: "POST", body: fd }).then((r) => r.json());
    await _sleep(450); procStep("upload", "done"); procStep("embed", "active");
    const data = await reqP;                               // real work finishes here
    await _sleep(350); procStep("embed", "done"); procStep("index", "active");
    await _sleep(350); procStep("index", "done"); procStep("done", "active");
    await _sleep(200);
    applyStatus(data.status);
    procFinish(data.results, data.status);
    if (!docsModal.hidden) refreshDocs();                  // live-update open modal
    const ok = data.results.filter((r) => !r.error).length;
    toast(`Indexed ${ok} file(s).`);
  } catch (err) {
    proc.bar.classList.remove("indet");
    proc.title.textContent = "Upload failed";
    proc.result.innerHTML = `<div class="row bad"><span>${escapeHtml(String(err.message || err))}</span></div>`;
    proc.result.hidden = false; proc.close.hidden = false;
  }
}
function applyStatus(s) {
  statusDot.classList.toggle("ready", s.ready);
  docBadge.textContent = s.ready ? s.records : "";
  docsBtn.title = s.ready ? `${s.records} documents · ${s.chunks} chunks` : "No documents";
}

// ---- Documents modal ----
function openModal() { docsModal.hidden = false; refreshDocs(); }
function closeModal() { docsModal.hidden = true; }
async function refreshDocs() {
  const data = await (await fetch("/api/documents")).json();
  applyStatus(data.status);
  modalCount.textContent = data.documents.length
    ? `${data.documents.length} file(s) · ${data.status.chunks} chunks` : "";
  modalList.innerHTML = data.documents.length ? "" :
    '<li class="empty">No documents yet — add some to get grounded answers.</li>';
  for (const d of data.documents) {
    const li = document.createElement("li"); li.className = "doc-row";
    li.innerHTML = `<span class="file-ic"><svg viewBox="0 0 24 24" class="icon"><path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H17a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H5.5A1.5 1.5 0 0 1 4 18.5z"/><path d="M4 17.5A1.5 1.5 0 0 1 5.5 16H18"/></svg></span>
      <span class="info"><span class="name">${escapeHtml(d.source)}</span>
      <span class="sub">${d.records} record(s) · ${d.chunks} chunks</span></span>
      <button class="remove" title="Remove" aria-label="Remove ${escapeHtml(d.source)}">
        <svg viewBox="0 0 24 24" class="icon"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m-1 0v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6"/></svg></button>`;
    li.querySelector(".remove").addEventListener("click", () => removeDoc(d.source));
    modalList.appendChild(li);
  }
}
async function removeDoc(source) {
  if (!(await customConfirm(`Remove "${source}" from the index?`))) return;
  const data = await (await fetch("/api/documents/remove", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source }),
  })).json();
  applyStatus(data.status); refreshDocs();
  toast(data.removed ? "Removed." : "Not found.");
}

// ---- Toast & Confirm ----
let toastTimer;
function toast(msg) {
  let el = document.querySelector(".toast");
  if (!el) { el = document.createElement("div"); el.className = "toast"; document.body.appendChild(el); }
  el.textContent = msg; el.classList.add("show");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove("show"), 2200);
}

function customConfirm(msg) {
  return new Promise((resolve) => {
    const modal = $("confirm-modal"), msgEl = $("confirm-msg");
    const btnCancel = $("confirm-cancel"), btnOk = $("confirm-ok");
    msgEl.textContent = msg;
    modal.hidden = false;
    
    const cleanup = () => {
      btnCancel.removeEventListener("click", onCancel);
      btnOk.removeEventListener("click", onOk);
      modal.hidden = true;
    };
    const onCancel = () => { cleanup(); resolve(false); };
    const onOk = () => { cleanup(); resolve(true); };
    
    btnCancel.addEventListener("click", onCancel);
    btnOk.addEventListener("click", onOk);
  });
}

// ---- Wiring ----
composer.addEventListener("submit", (e) => { e.preventDefault(); const t = input.value; input.value = ""; autoSize(); send(t); });
input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); composer.requestSubmit(); } });
input.addEventListener("input", autoSize);
function autoSize() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 200) + "px"; }

suggestions.addEventListener("click", (e) => { const c = e.target.closest(".recent-card"); if (c) send(c.dataset.q); });
// Attach files / welcome CTA are native <label for="file-input"> — the browser
// opens the picker; we only react to the resulting change event. Documents nav
// opens the modal.
docsBtn.addEventListener("click", (e) => { e.preventDefault(); openModal(); });
fileInput.addEventListener("change", () => { upload(fileInput.files); fileInput.value = ""; });
const modalFileInput = $("modal-file-input");
modalFileInput.addEventListener("change", () => { upload(modalFileInput.files); modalFileInput.value = ""; });
micBtn.addEventListener("click", () => toast("Voice input is coming soon."));

// modal controls
modalClose.addEventListener("click", closeModal);
docsModal.addEventListener("click", (e) => { if (e.target === docsModal) closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !docsModal.hidden) closeModal(); });
// modal-drop / add are native labels (for="modal-file-input"); just handle drag-drop
["dragover","dragenter"].forEach((e) => modalDrop.addEventListener(e, (ev) => { ev.preventDefault(); modalDrop.classList.add("drag"); }));
["dragleave","drop"].forEach((e) => modalDrop.addEventListener(e, () => modalDrop.classList.remove("drag")));
modalDrop.addEventListener("drop", (ev) => { ev.preventDefault(); upload(ev.dataTransfer.files); });

function startNewChat() {
  conversationId = null;                                   // next message opens a fresh thread
  messages.innerHTML = ""; messages.classList.add("hide"); transcript.length = 0;
  welcome.style.display = ""; hasMessages = false;
  loadConversations();
}
[newChat, clearBtn].forEach((el) => el.addEventListener("click", () => { startNewChat(); toast("New chat started."); }));

// theme toggle (light default; dark applies a class on <body>)
themeToggle.addEventListener("click", (e) => {
  const btn = e.target.closest("button"); if (!btn) return;
  themeToggle.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b === btn));
  const t = btn.dataset.theme;
  const dark = t === "dark" || (t === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.body.classList.toggle("dark", dark);
  toast(`Theme: ${t}`);
});

fetch("/api/status").then((r) => r.json()).then(applyStatus).catch(() => {});
loadConversations();                                       // populate sidebar history on load

// ─────────── Dropdown menus — single delegated coordinator ───────────
// One document-level handler runs the whole menu system, so there are no
// click-order / stopPropagation races (the class of bug that kept breaking
// Settings). Triggers carry data-menu="<id>"; clicking a trigger toggles its
// menu, clicking inside a menu lets the item act, clicking elsewhere closes all.
function closeAllMenus(except) {
  document.querySelectorAll(".menu").forEach((m) => { if (m !== except) m.hidden = true; });
}
function toggleMenu(menu) { const willOpen = menu.hidden; closeAllMenus(menu); menu.hidden = !willOpen; }

document.addEventListener("click", (e) => {
  if (e.target.closest(".menu")) return;                   // click inside a menu -> item handles it
  const trigger = e.target.closest("[data-menu]");         // a menu trigger (e.g. user-card)
  if (trigger) { toggleMenu($(trigger.getAttribute("data-menu"))); return; }
  closeAllMenus();                                         // outside click -> close everything
});
async function loadModels() {
  const d = await (await fetch("/api/models")).json();
  modelName.textContent = (d.current || "model").replace(/:.*/, (m) => m.length > 10 ? m : m);
  modelMenu.innerHTML = "";
  modelList.innerHTML = "";
  (d.models || []).forEach((m) => {
    const b = document.createElement("button"); b.textContent = m;
    if (m === d.current) b.classList.add("on");
    b.addEventListener("click", () => switchModel(m));
    modelMenu.appendChild(b);
    modelList.insertAdjacentHTML("beforeend", `<option value="${m}">`);
  });
  if (!d.models || !d.models.length) modelMenu.innerHTML = `<button disabled>${d.error ? "Ollama unreachable" : "No models"}</button>`;
}
async function switchModel(model) {
  await fetch("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ chat_model: model }) });
  modelName.textContent = model; modelMenu.hidden = true;
  toast(`Model: ${model}`); loadModels();
}
// model menu items are clickable via their own handlers; trigger uses data-menu

// ─────────── Export dropdown ───────────
function convoText(fmt) {
  if (fmt === "json") return JSON.stringify({ exported: new Date().toISOString(), turns: transcript }, null, 2);
  const md = transcript.map((t) => `### ${t.role === "user" ? "You" : "KKEdu RAG"}\n\n${t.text}`).join("\n\n---\n\n");
  return md;
}
function download(name, text, mime) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: mime })); a.download = name; a.click();
  URL.revokeObjectURL(a.href);
}
function exportAs(fmt) {
  exportMenu.hidden = true;
  if (!transcript.length) return toast("Nothing to export yet.");
  if (fmt === "json") return download("conversation.json", convoText("json"), "application/json");
  if (fmt === "md") return download("conversation.md", convoText("md"), "text/markdown");
  if (fmt === "doc") {
    const body = transcript.map((t) => `<h3>${t.role === "user" ? "You" : "KKEdu RAG"}</h3>${renderMarkdown(t.text)}`).join("<hr>");
    const html = `<html><head><meta charset="utf-8"></head><body style="font-family:Arial">${body}</body></html>`;
    return download("conversation.doc", html, "application/msword");
  }
  if (fmt === "pdf") {                                    // print-to-PDF, no deps
    const body = transcript.map((t) => `<h3>${t.role === "user" ? "You" : "KKEdu RAG"}</h3>${renderMarkdown(t.text)}`).join("<hr>");
    const w = window.open("", "_blank");
    w.document.write(`<html><head><title>Conversation</title><style>body{font-family:Arial;max-width:720px;margin:40px auto;color:#222}h3{margin-top:24px}hr{border:none;border-top:1px solid #ddd;margin:18px 0}</style></head><body>${body}<script>onload=()=>print()<\/script></body></html>`);
    w.document.close();
  }
}
exportMenu.addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { exportAs(b.dataset.fmt); closeAllMenus(); } });

// ─────────── Profile menu items (trigger uses data-menu) ───────────
$("logout-btn").addEventListener("click", () => { closeAllMenus(); toast("Logged out (demo)."); });
$("open-settings").addEventListener("click", () => { closeAllMenus(); openSettings(); });

async function openSettings() {
  const s = await (await fetch("/api/settings")).json();
  for (const [k, v] of Object.entries(s)) {
    const el = settingsForm.elements[k]; if (el) el.value = v;
  }
  // populate model datalist for the chat_model field
  loadModels();
  settingsMsg.textContent = ""; settingsModal.hidden = false;
  switchSettingsTab("system");                              // always open on System
}
function closeSettings() { settingsModal.hidden = true; }
settingsClose.addEventListener("click", closeSettings);
settingsModal.addEventListener("click", (e) => { if (e.target === settingsModal) closeSettings(); });
settingsSave.addEventListener("click", async () => {
  const patch = {};
  for (const el of settingsForm.elements) {
    if (!el.name) continue;
    patch[el.name] = el.type === "number" ? Number(el.value) : el.value;
  }
  settingsMsg.textContent = "Applying…";
  try {
    const d = await (await fetch("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) })).json();
    settingsMsg.textContent = "Saved & applied live.";
    modelName.textContent = d.settings.chat_model;
    setTimeout(closeSettings, 700); toast("Settings applied.");
  } catch (err) { settingsMsg.textContent = "Failed: " + err.message; }
});

// (menu open/close is handled by the single delegated coordinator above)
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeSettings(); closeAllMenus(); } });

// ─────────── Settings tabs: System · Users & Roles ───────────
const settingsTabs = $("settings-tabs"), settingsFoot = $("settings-foot"), tabUsers = $("tab-users"),
      usersList = $("users-list"), usersSub = $("users-sub"),
      userForm = $("user-form"), userFormTitle = $("user-form-title"), userFormMsg = $("user-form-msg"),
      userAddBtn = $("user-add-btn"), userCancel = $("user-cancel"), permChecklist = $("perm-checklist");
let rbacMeta = { roles: ["admin", "member"], permissions: {}, role_defaults: {} };
let currentUser = null, editingUserId = null;

function switchSettingsTab(tab) {
  document.querySelectorAll(".stab").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
  document.querySelectorAll(".settings-pane").forEach((p) => p.classList.toggle("on", p.dataset.pane === tab));
  settingsFoot.style.display = tab === "system" ? "" : "none";   // Save&apply is for System only
  if (tab === "users") { userForm.hidden = true; loadUsers(); }
}
settingsTabs.addEventListener("click", (e) => { const b = e.target.closest(".stab"); if (b) switchSettingsTab(b.dataset.tab); });

const ICON_EDIT = '<svg viewBox="0 0 24 24" class="icon"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>';
const ICON_DEL = '<svg viewBox="0 0 24 24" class="icon"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m-1 0v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6"/></svg>';

async function loadUsers() {
  try {
    const d = await (await fetch("/api/users")).json();
    rbacMeta = d.rbac || rbacMeta; currentUser = d.current || null;
    renderPermChecklist();
    renderUsers(d.users || []);
  } catch (err) { usersSub.textContent = "Failed to load users."; }
}
function renderPermChecklist() {
  permChecklist.innerHTML = "";
  for (const [key, label] of Object.entries(rbacMeta.permissions || {}))
    permChecklist.insertAdjacentHTML("beforeend",
      `<label class="perm-item"><input type="checkbox" value="${key}" /><span>${escapeHtml(label)}</span></label>`);
}
function renderUsers(list) {
  usersSub.textContent = `${list.length} user${list.length === 1 ? "" : "s"} · add, edit roles & permissions, or remove`;
  usersList.innerHTML = list.length ? "" : '<li class="empty">No users yet.</li>';
  for (const u of list) {
    const me = currentUser && currentUser.id === u.id;
    const li = document.createElement("li"); li.className = "user-row";
    li.innerHTML = `
      <span class="u-avatar ${u.role}">${escapeHtml((u.name || "?").trim().charAt(0).toUpperCase())}</span>
      <span class="u-info">
        <span class="u-name">${escapeHtml(u.name)}${me ? ' <em class="you">you</em>' : ""}</span>
        <span class="u-email">${escapeHtml(u.email)}</span>
      </span>
      <span class="role-badge ${u.role}">${escapeHtml(u.role)}</span>
      <span class="u-perms" title="${escapeHtml(u.permissions.map((p) => rbacMeta.permissions[p] || p).join(", "))}">${u.permissions.length} perm${u.permissions.length === 1 ? "" : "s"}</span>
      <span class="u-actions">
        <button class="icon-btn" type="button" title="Edit" data-act="edit">${ICON_EDIT}</button>
        <button class="icon-btn" type="button" title="Remove" data-act="del">${ICON_DEL}</button>
      </span>`;
    li.querySelector('[data-act="edit"]').addEventListener("click", () => openUserForm(u));
    li.querySelector('[data-act="del"]').addEventListener("click", () => deleteUser(u));
    usersList.appendChild(li);
  }
}
function setPerms(perms) {
  const set = new Set(perms || []);
  permChecklist.querySelectorAll("input").forEach((c) => (c.checked = set.has(c.value)));
}
function getPerms() { return [...permChecklist.querySelectorAll("input:checked")].map((c) => c.value); }
function openUserForm(u) {
  editingUserId = u ? u.id : null;
  userFormTitle.textContent = u ? `Edit ${u.name}` : "Add user";
  userForm.elements.name.value = u ? u.name : "";
  userForm.elements.email.value = u ? u.email : "";
  userForm.elements.role.value = u ? u.role : "member";
  setPerms(u ? u.permissions : rbacMeta.role_defaults[u ? u.role : "member"]);
  userFormMsg.textContent = ""; userForm.hidden = false; userForm.elements.name.focus();
}
userAddBtn.addEventListener("click", () => openUserForm(null));
userCancel.addEventListener("click", () => { userForm.hidden = true; });
$("user-role").addEventListener("change", (e) => setPerms(rbacMeta.role_defaults[e.target.value] || []));
userForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    name: userForm.elements.name.value.trim(), email: userForm.elements.email.value.trim(),
    role: userForm.elements.role.value, permissions: getPerms(),
  };
  if (!payload.name || !payload.email) { userFormMsg.textContent = "Name and email are required."; return; }
  userFormMsg.textContent = "Saving…";
  const url = editingUserId ? `/api/users/${editingUserId}` : "/api/users";
  try {
    const r = await fetch(url, { method: editingUserId ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const d = await r.json();
    if (!r.ok || d.error) { userFormMsg.textContent = d.error || "Failed to save user."; return; }
    userForm.hidden = true; toast(editingUserId ? "User updated." : "User created.");
    loadUsers(); loadCurrentUser();
  } catch (err) { userFormMsg.textContent = "Failed: " + (err.message || err); }
});
async function deleteUser(u) {
  if (!(await customConfirm(`Remove ${u.name} (${u.email})?`))) return;
  try {
    const r = await fetch(`/api/users/${u.id}/delete`, { method: "POST" });
    const d = await r.json();
    if (!r.ok || d.error) { toast(d.error || "Failed to remove user."); return; }
    toast("User removed."); loadUsers(); loadCurrentUser();
  } catch (err) { toast("Failed: " + (err.message || err)); }
}

// Reflect the signed-in user in the sidebar card + gate the Users tab to admins.
async function loadCurrentUser() {
  try {
    const d = await (await fetch("/api/users")).json();
    currentUser = d.current || null;
    if (!currentUser) return;
    const who = document.querySelector("#user-card .who");
    if (who) who.innerHTML = `${escapeHtml(currentUser.name)}<small>${escapeHtml(currentUser.email)}</small>`;
    tabUsers.style.display = currentUser.role === "admin" ? "" : "none";   // RBAC gate
  } catch {}
}
loadCurrentUser();

loadModels();

// ─────────── Composer document-scope selector ───────────
async function loadScope() {
  const data = await (await fetch("/api/documents")).json();
  const docs = data.documents || [];
  selectedSources = selectedSources.filter((s) => docs.some((d) => d.source === s));  // drop gone files
  renderScope(docs); updateScopeLabel();
}
function renderScope(docs) {
  scopeMenu.innerHTML = "";
  if (!docs.length) { scopeMenu.innerHTML = '<div class="scope-empty">No documents yet</div>'; return; }
  const mkRow = (on, nm, ct, onClick) => {
    const r = document.createElement("div");
    r.className = "scope-row" + (on ? " on" : "");
    r.innerHTML = `<span class="box"></span><span class="nm" title="${escapeHtml(nm)}">${escapeHtml(nm)}</span><span class="ct">${ct}</span>`;
    r.addEventListener("click", onClick); return r;
  };
  scopeMenu.appendChild(mkRow(selectedSources.length === 0, "All files", docs.length,
    () => { selectedSources = []; renderScope(docs); updateScopeLabel(); }));
  scopeMenu.insertAdjacentHTML("beforeend", '<div class="divider"></div>');
  for (const d of docs) {
    scopeMenu.appendChild(mkRow(selectedSources.includes(d.source), d.source, d.chunks, () => {
      const i = selectedSources.indexOf(d.source);
      if (i >= 0) selectedSources.splice(i, 1); else selectedSources.push(d.source);
      renderScope(docs); updateScopeLabel();
    }));
  }
}
function updateScopeLabel() {
  const n = selectedSources.length;
  scopeLabel.textContent = n === 0 ? "All files" : n === 1 ? selectedSources[0] : `${n} files`;
  scopeBtn.title = n === 0 ? "Answer from all documents" : "Scoped to: " + selectedSources.join(", ");
}
scopeBtn.addEventListener("click", () => loadScope());     // refresh list; coordinator toggles via data-menu
loadScope();
