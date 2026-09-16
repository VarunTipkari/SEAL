/* SEAL AI v2 - Chat UI */
(() => {
    "use strict";

    const $ = (s, r = document) => r.querySelector(s);
    const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
    const esc = (s) => String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");

    // Markdown rendering
    function inlineFmt(t) {
        t = esc(t);
        t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
        t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        return t;
    }
    function md(src) {
        src = String(src || "");
        let out = "";
        const parts = src.split(/```/);
        for (let i = 0; i < parts.length; i++) {
            if (i % 2 === 1) {
                let code = parts[i].replace(/^[A-Za-z0-9_+-]*\n/, "").replace(/\n$/, "");
                out += '<pre class="code">' + esc(code) + "</pre>";
            } else {
                const lines = parts[i].split("\n");
                let list = null;
                const flush = () => { if (list) { out += "</ul>"; list = null; } };
                for (const raw of lines) {
                    const u = raw.match(/^\s*[-*•]\s+(.*)/);
                    const o = raw.match(/^\s*\d+[.)]\s+(.*)/);
                    const h = raw.match(/^(#{2,3})\s+(.*)/);
                    const blank = raw.trim() === "";
                    if (u) { if (list !== "u") { flush(); out += "<ul>"; list = "u"; } out += "<li>" + inlineFmt(u[1]) + "</li>"; continue; }
                    if (o) { if (list !== "o") { flush(); out += "<ul style='list-style:decimal'>"; list = "o"; } out += "<li>" + inlineFmt(o[1]) + "</li>"; continue; }
                    flush();
                    if (h) { const lvl = Math.min(3, h[1].length); out += "<h" + lvl + ">" + inlineFmt(h[2]) + "</h" + lvl + ">"; continue; }
                    if (blank) continue;
                    out += "<p>" + inlineFmt(raw) + "</p>";
                }
                flush();
            }
        }
        return out;
    }

    // UI State
    const thread = $("#thread");
    let col = null;
    const state = {
        pending: null,
        busy: false,
        attachments: [],
        history: [],
        lastModel: null,
        chatId: null,
        chatTitle: "New chat",
    };

    function attachmentForHistory(a) {
        const path = a && a.path ? a.path : "";
        return { name: a.name || "file", path, isImage: !!a.isImage || /\.(png|jpe?g|webp|gif|bmp)$/i.test(a.name || ""),
            previewUrl: path ? ("/api/upload/preview?path=" + encodeURIComponent(path)) : "" };
    }

    async function persistChat() {
        if (!state.chatId) return;
        const messages = state.history.map(m => ({
            role: m.role, text: m.text || "", model: m.model || null,
            attachments: (m.attachments || []).map(attachmentForHistory)
        }));
        try {
            const firstUser = messages.find(m => m.role === "user");
            const title = (state.chatTitle && state.chatTitle !== "New chat") ? state.chatTitle : ((firstUser && firstUser.text) || "New chat");
            state.chatTitle = title;
            await fetchJSON("/api/chats/" + encodeURIComponent(state.chatId), "PUT", { title, messages });
            refreshChatList();
        } catch (e) { console.warn("Could not save chat history", e); }
    }

    async function ensureChat() {
        if (state.chatId) return state.chatId;
        let saved = null;
        try { saved = localStorage.getItem("seal-chat-id"); } catch (e) {}
        if (saved) {
            const r = await fetchJSON("/api/chats/" + encodeURIComponent(saved)).catch(() => null);
            if (r && r.id) { await openChat(r); return r.id; }
        }
        const r = await fetchJSON("/api/chats", "POST", { title: "New chat" });
        state.chatId = r.id; state.chatTitle = r.title || "New chat";
        try { localStorage.setItem("seal-chat-id", state.chatId); } catch (e) {}
        return state.chatId;
    }

    function renderStoredMessage(m) {
        if (m.role === "user") { addUser(m.text || "", m.attachments || []); return; }
        ensureCol();
        const msg = newMsg("asst");
        const body = msg.querySelector(".body");
        const mdEl = document.createElement("div"); mdEl.className = "md"; mdEl.innerHTML = md(m.text || ""); body.appendChild(mdEl);
        if (m.model) { const meta=document.createElement("div"); meta.className="meta"; meta.innerHTML="<span>◈ "+esc(m.model)+"</span>"; body.appendChild(meta); }
        col.appendChild(msg);
    }

    async function openChat(data) {
        if (!data || !data.id) return;
        if (state.busy) return toast("Wait for the current run to finish.");
        state.chatId = data.id; state.chatTitle = data.title || "New chat"; state.history = data.messages || []; state.pending = null;
        try { localStorage.setItem("seal-chat-id", state.chatId); } catch (e) {}
        col = null; thread.innerHTML = "";
        for (const m of state.history) renderStoredMessage(m);
        if (!state.history.length) renderEmpty();
        refreshChatList(); scrollBottom();
    }

    async function refreshChatList() {
        const box = $("#chat-list"); if (!box) return;
        const r = await fetchJSON("/api/chats").catch(() => null);
        box.innerHTML = "";
        for (const c of (r && r.chats) || []) {
            const wrap=document.createElement("div"); wrap.className="chat-item-wrap";
            const b=document.createElement("button"); b.className="chat-item"+(c.id===state.chatId?" active":"");
            b.innerHTML='<div class="chat-item-title">'+esc(c.title||"New chat")+'</div><div class="chat-item-date">'+esc(c.updated_at ? new Date(c.updated_at).toLocaleString() : "")+'</div>';
            b.onclick=async()=>{ const d=await fetchJSON("/api/chats/"+encodeURIComponent(c.id)).catch(()=>null); if(d) await openChat(d); };
            const del=document.createElement("button"); del.className="chat-delete"; del.title="Delete chat"; del.textContent="✕";
            del.onclick=async(e)=>{ e.stopPropagation(); if(!confirm("Delete this chat?")) return; await fetchJSON("/api/chats/"+encodeURIComponent(c.id),"DELETE").catch(()=>null); if(c.id===state.chatId){ state.chatId=null; state.history=[]; try{localStorage.removeItem("seal-chat-id")}catch(e){} await startNewChat(false); } else refreshChatList(); };
            wrap.appendChild(b); wrap.appendChild(del); box.appendChild(wrap);
        }
    }

    async function startNewChat(create=true) {
        if (state.busy) return toast("Wait for the current run to finish.");
        const r=create ? await fetchJSON("/api/chats","POST",{title:"New chat"}).catch(()=>null) : null;
        state.chatId = r ? r.id : null; state.chatTitle = r ? (r.title||"New chat") : "New chat"; state.history=[]; state.lastModel=null;
        if (state.chatId) { try{localStorage.setItem("seal-chat-id",state.chatId)}catch(e){} }
        else { try{localStorage.removeItem("seal-chat-id")}catch(e){} }
        modelPillLabel.textContent="model auto"; $("#side-model").textContent="auto · local models"; applySeg(null); $("#mb-state").textContent="auto per task";
        clearThread(); refreshChatList();
    }
    const seen = new Set();

    function ensureCol() {
        if (!col) { col = document.createElement("div"); col.className = "msgcol"; thread.appendChild(col); }
        return col;
    }
    function scrollBottom() { thread.scrollTop = thread.scrollHeight; }

    let toastT = null;
    function toast(msg, ms = 3200) {
        const t = $("#toast");
        t.textContent = msg; t.hidden = false;
        clearTimeout(toastT); toastT = setTimeout(() => (t.hidden = true), ms);
    }

    async function fetchJSON(url, method = "GET", body) {
        const opt = { method, headers: {} };
        if (body && !(body instanceof FormData)) {
            opt.headers["Content-Type"] = "application/json";
            opt.body = JSON.stringify(body);
        } else if (body) {
            opt.body = body;
        }
        const r = await fetch(url, opt);
        if (!r.ok) { let t = ""; try { t = await r.text(); } catch (e) {} throw new Error((t && t.slice(0, 140)) || ("HTTP " + r.status)); }
        try { return await r.json(); } catch (e) { return null; }
    }
    const enc = (p) => encodeURIComponent(p);

    // Theme
    function applyTheme(t) {
        document.documentElement.setAttribute("data-theme", t);
        try { localStorage.setItem("seal-theme", t); } catch (e) {}
        $("#theme-label").textContent = t === "dark" ? "Light" : "Dark";
        $("#theme-ico").textContent = t === "dark" ? "☀" : "☾";
    }
    let theme = "dark";
    try { theme = localStorage.getItem("seal-theme") || "dark"; } catch (e) {}
    applyTheme(theme);
    $("#theme-toggle").addEventListener("click", () => applyTheme(theme = theme === "dark" ? "light" : "dark"));

    // Drawers
    function openDrawer(id) {
        $$(".drawer").forEach((d) => d.classList.toggle("open", d.id === id));
        $("#backdrop").hidden = false;
        if (id === "kb-drawer") refreshKb();
        if (id === "files-drawer") refreshFiles();
    }
    function closeDrawers() {
        $$(".drawer").forEach((d) => d.classList.remove("open"));
        $("#backdrop").hidden = true;
        setNavActive("chat");
    }
    function setNavActive(which) {
        $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.act === which));
    }
    $("#backdrop").addEventListener("click", closeDrawers);
    $$("[data-close]").forEach((b) => b.addEventListener("click", closeDrawers));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawers(); });
    $("#nav-kb").addEventListener("click", () => { closeDrawers(); openDrawer("kb-drawer"); setNavActive("kb"); });
    $("#nav-files").addEventListener("click", () => { closeDrawers(); openDrawer("files-drawer"); setNavActive("files"); });
    $("#nav-chat").addEventListener("click", () => closeDrawers());

    // Model indicator / realtime runtime status
    const modelPillLabel = $("#model-pill-label");
    const modelDot = $("#model-dot");
    const segs = { general: $("#seg-general"), vision: $("#seg-vision"), coding: $("#seg-coder"), file_manager: $("#seg-general"), files: $("#seg-general") };
    const pendingEvents = new Map();

    function normalizeRole(role) {
        return role === "files" ? "file_manager" : role;
    }

    function applySeg(key) {
        key = normalizeRole(key);
        $$(".seg").forEach((s) => s.classList.remove("active", "busy"));
        if (key && segs[key]) segs[key].classList.add("active");
        if (state.busy && key && segs[key]) segs[key].classList.add("busy");
    }

    function applyModel(m, statusText) {
        if (!m) return;
        m.role = normalizeRole(m.role || "general");
        state.lastModel = m;
        modelPillLabel.textContent = m.name || "local model";
        $("#side-model").textContent = m.role + " · " + (m.name || "local");
        applySeg(m.role);
        $("#mb-state").textContent = statusText || (state.busy ? "using · " + m.name : "last used · " + m.name);
    }

    function setBusyUI(b) {
        state.busy = b;
        $("#send-btn").disabled = b || !$("#task-input").value.trim();
        $("#send-btn").hidden = b;
        $("#stop-btn").hidden = !b;
        $("#clip").style.opacity = b ? 0.4 : 1;
        modelDot.classList.toggle("on", b);
        if (b) {
            if (state.lastModel) applySeg(state.lastModel.role);
            $("#mb-state").textContent = state.lastModel
                ? "using · " + state.lastModel.name
                : "starting…";
        } else {
            $$("#model-bar .seg").forEach((s) => s.classList.remove("busy"));
            $("#mb-state").textContent = "auto per task";
        }
        $("#head-context").textContent = b ? "working locally…" : "all local · nothing leaves this machine";
    }

    async function syncModelBar() {
        const r = await fetchJSON("/api/status").catch(() => null);
        if (!r || !Array.isArray(r.models)) return;
        const ids = { general: "seg-general", vision: "seg-vision", coding: "seg-coder", file_manager: "seg-general" };
        for (const item of r.models) {
            const el = $("#" + ids[item.role]);
            if (!el) continue;
            const id = el.querySelector(".mb-id");
            if (id) id.textContent = item.name || item.role;
        }
    }

    // Messages
    function newMsg(kind) {
        const m = document.createElement("div");
        m.className = "msg " + kind;
        m.innerHTML = kind === "user"
            ? '<div class="who"><div class="ava">ME</div></div><div class="body"></div>'
            : '<div class="who"><div class="ava">◈</div></div><div class="body"></div>';
        return m;
    }
    
    function addUser(text, attachments = []) {
        ensureCol();
        const empty = col.querySelector(".empty");
        if (empty) empty.remove();
        const m = newMsg("user");
        const body = m.querySelector(".body");
        body.textContent = text;
        for (const a of attachments) {
            const isImage = !!a.isImage || /\.(png|jpe?g|webp|gif|bmp)$/i.test(a.name || "");
            const preview = a.previewUrl || (a.path && isImage ? "/api/upload/preview?path=" + encodeURIComponent(a.path) : "");
            if (preview && isImage) {
                const img = document.createElement("img"); img.className = "chat-image"; img.src = preview; img.alt = a.name || "uploaded image"; img.loading = "lazy";
                body.appendChild(img);
                const cap = document.createElement("div"); cap.className="chat-image-name"; cap.textContent=a.name||"image"; body.appendChild(cap);
            } else if (a.name) {
                const cap=document.createElement("div"); cap.className="chat-image-name"; cap.textContent="📎 "+a.name; body.appendChild(cap);
            }
        }
        col.appendChild(m); scrollBottom();
    }
    
    function addError(text) {
        ensureCol();
        const m = document.createElement("div");
        m.className = "msg asst";
        m.innerHTML = '<div class="who"><div class="ava">◈</div></div><div class="body"><div class="err">' + esc(text) + "</div></div>";
        col.appendChild(m);
        scrollBottom();
    }

    function ensureWorking(sid, taskText) {
        if (state.pending && state.pending.sid === sid) return state.pending;
        ensureCol();
        const m = newMsg("asst");
        const body = m.querySelector(".body");
        body.innerHTML =
            '<div class="top"><span class="m-tag">SEAL</span>' +
            '<span class="st"><b>·</b><b>·</b><b>·</b></span>' +
            '<span class="act" data-act>starting…</span></div>' +
            '<div class="holder" data-holder></div>';
        const p = {
            sid, body, holder: body.querySelector("[data-holder]"),
            act: body.querySelector("[data-act]"), top: body.querySelector(".top"),
            model: null, finished: false,
        };
        state.pending = p;
        col.appendChild(m);
        scrollBottom();

        // Model events can arrive before the /api/run response reaches the browser.
        // Replay those buffered events now so the bottom indicator never misses a model switch.
        const buffered = pendingEvents.get(sid);
        if (buffered) {
            pendingEvents.delete(sid);
            buffered.forEach((ev) => handle(ev));
        }
        return p;
    }
    
    function attachModelToPending(p, m) {
        p.model = m;
        applyModel(m);
        if (!p.tagEl) {
            p.tagEl = document.createElement("span");
            p.tagEl.className = "m-tag";
            p.tagEl.style.marginLeft = "auto";
            p.top.appendChild(p.tagEl);
        }
        p.tagEl.textContent = m.name;
    }
    
    function setAct(p, txt) { if (p && !p.finished && p.act) p.act.innerHTML = txt; }

    function completePending(p, res) {
    if (!p || p.finished) return;
    p.finished = true;
    const st = p.body.querySelector(".st");
    if (st) st.remove();
    p.act && p.act.remove();
    if (p.holder) p.holder.classList.add("hidden");
    
    const wrap = document.createElement("div");
    
    // Get text from either answer or final_answer
    let text = "";
    if (res && res.final_answer) {
        text = res.final_answer;
    } else if (res && res.answer) {
        text = res.answer;
    } else if (res && res.result && res.result.answer) {
        text = res.result.answer;
    } else {
        text = "(SEAL finished with no text.)";
    }
    
    const mdEl = document.createElement("div");
    mdEl.className = "md";
    mdEl.innerHTML = md(text);
    wrap.appendChild(mdEl);
    
    if (res && res.operation_results) {
        const details = document.createElement("details");
        details.className = "op-details";
        const summary = document.createElement("summary");
        summary.textContent = "File operations (" + res.operation_results.length + ")";
        details.appendChild(summary);
        const list = document.createElement("div");
        list.className = "op-list";
        for (const op of res.operation_results) {
            const row = document.createElement("div");
            row.className = op.success ? "op-row ok" : "op-row fail";
            const action = String(op.action || "operation").replaceAll("_", " ");
            const target = op.path ? " `" + op.path + "`" : "";
            row.textContent = op.success
                ? "✓ " + action.charAt(0).toUpperCase() + action.slice(1) + target + " completed successfully."
                : "✕ " + action.charAt(0).toUpperCase() + action.slice(1) + target + " failed: " + (op.error || "Unknown error.");
            list.appendChild(row);
        }
        details.appendChild(list);
        wrap.appendChild(details);
    }
    
    const meta = document.createElement("div");
    meta.className = "meta";
    const mid = (p.model && p.model.name) || "local model";
    meta.innerHTML = "<span>◈ " + esc(mid) + "</span>";
    wrap.appendChild(meta);
    p.holder.after(wrap);
    
    if (text && text !== "(SEAL finished with no text.)") {
        state.history.push({ role: "assistant", text: text, model: mid });
        state.history = state.history.slice(-40);
        refreshChatList();
    }
    scrollBottom();
}

    async function pollResult(sid, attempts = 60) {  // Increased from 30
    for (let i = 0; i < attempts; i++) {
        const r = await fetchJSON("/api/run/" + sid).catch(() => null);
        if (r && (
            r.status === "ok" ||
            r.status === "error" ||
            r.final_answer !== undefined ||
            r.answer !== undefined ||
            r.error !== undefined
        )) {
            console.log("Poll result:", r);
            return r;
        }
        await new Promise((res) => setTimeout(res, 500));  // Increased from 250
    }
    return null;
}

    // Send
    const input = $("#task-input");
    function emptyInput() { input.value = ""; input.style.height = "auto"; updateSend(); }

    async function doSend(text) {
        text = (text || "").trim();
        if (!text || state.busy) return;
        const attachments = state.attachments.slice();
        const files = attachments.map((a) => a.path);
        await ensureChat();
        const userMessage = { role: "user", text, attachments: attachments.map(attachmentForHistory) };
        state.history.push(userMessage);
        state.history = state.history.slice(-40);
        // The backend owns conversation memory. The user turn is persisted there
        // before the model starts, so the model always receives the authoritative
        // current-chat history.
        setBusyUI(true);
        addUser(text, attachments);
        clearAttachments();
        emptyInput();
        try {
            const res = await fetchJSON("/api/run", "POST", { task: text, files, chat_id: state.chatId });
            if (!res || !res.sid) {
                state.history.pop();
                addError("SEAL could not start the task.");
                setBusyUI(false);
                return;
            }
            const p = ensureWorking(res.sid, text);
            p.task = text;
        } catch (e) {
            state.history.pop();
            addError("Could not reach SEAL: " + e.message);
            setBusyUI(false);
        }
    }

    function stopRun() {
        fetchJSON("/api/cancel", "POST", {}).catch(() => {});
        if (state.pending) setAct(state.pending, "stopping…");
    }

    function updateSend() {
        const t = input.value.trim();
        const b = $("#send-btn");
        if (!state.busy) b.disabled = !t;
    }
    function autoGrow() {
        input.style.height = "auto";
        input.style.height = Math.min(180, input.scrollHeight) + "px";
        updateSend();
    }
    input.addEventListener("input", autoGrow);
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); doSend(input.value); }
    });
    $("#send-btn").addEventListener("click", () => doSend(input.value));
    $("#stop-btn").addEventListener("click", stopRun);

    // Attachments
    function clearAttachments() {
        state.attachments = [];
        $("#attach-row").innerHTML = "";
    }
    function addAttachmentChip(a) {
        state.attachments.push(a);
        const chip = document.createElement("div");
        chip.className = "att";
        if (a.previewUrl && /\.(png|jpe?g|webp|gif|bmp)$/i.test(a.name || "")) {
            const thumb = document.createElement("img");
            thumb.className = "att-thumb";
            thumb.src = a.previewUrl;
            thumb.alt = a.name || "image";
            chip.appendChild(thumb);
        }
        const label = document.createElement("span");
        label.textContent = a.name;
        chip.appendChild(label);
        const remove = document.createElement("button");
        remove.title = "remove"; remove.textContent = "✕";
        chip.appendChild(remove);
        remove.addEventListener("click", () => {
            state.attachments = state.attachments.filter((x) => x.path !== a.path);
            chip.remove();
        });
        $("#attach-row").appendChild(chip);
    }
    $("#clip").addEventListener("click", () => $("#file-input").click());
    $("#file-input").addEventListener("change", async () => {
        const fi = $("#file-input");
        const picked = Array.from(fi.files || []);
        fi.value = "";
        if (!picked.length) return;
        for (const f of picked) {
            const fd = new FormData();
            fd.append("file", f);
            try {
                const r = await fetch("/api/upload", { method: "POST", body: fd });
                if (!r.ok) { toast("Upload failed: " + f.name); continue; }
                const j = await r.json();
                const localPreview = f.type && f.type.startsWith("image/") ? URL.createObjectURL(f) : null;
                addAttachmentChip({ name: f.name, path: j.path, previewUrl: localPreview || j.preview_url || ("/api/upload/preview?path=" + encodeURIComponent(j.path)), isImage: !!localPreview });
            } catch (e) { toast("Upload failed: " + f.name); }
        }
    });

    // Empty state
    function renderEmpty() {
        ensureCol();
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.innerHTML = '<div class="logo" style="margin:0 auto">◈</div>' +
            "<h1>How can SEAL help?</h1>" +
            '<div class="tag">Local AI · on-prem · 3 models</div>' +
            '<div class="sugg">' +
            '<button onclick="doSend(\'Create a file called hello.py with a simple function\')">Create file</button>' +
            '<button onclick="doSend(\'List all files in the workspace\')">List files</button>' +
            '<button onclick="doSend(\'Search for TODO in all files\')">Search files</button>' +
            '</div>';
        col.appendChild(empty);
        scrollBottom();
    }

    function clearThread() {
        col = null;
        thread.innerHTML = "";
        state.attachments = [];
        $("#attach-row").innerHTML = "";
        renderEmpty();
    }

    async function reset() { await startNewChat(true); }
    $("#btn-new").addEventListener("click", reset);

    // SSE Event Stream
    function connect() {
        const es = new EventSource("/api/stream");
        es.onmessage = (e) => {
            let ev;
            try { ev = JSON.parse(e.data); } catch (err) { return; }
            if (ev.seq != null) { if (seen.has(ev.seq)) return; seen.add(ev.seq); }
            handle(ev);
        };
        es.onerror = () => {};
    }

    function handle(ev) {
        const evt = ev.evt;
        let p = state.pending;

        // Keep run/model events that arrive before the browser creates its pending UI.
        // This is common because the backend starts the background task immediately.
        if (!p && ev.sid && evt !== "run.started" && evt !== "run.done" && evt !== "run.error" && evt !== "run.cancelled") {
            if (!pendingEvents.has(ev.sid)) pendingEvents.set(ev.sid, []);
            pendingEvents.get(ev.sid).push(ev);
            return;
        }

        if (evt === "run.started" && ev.sid) {
            if (state.busy && !state.pending) {
                p = ensureWorking(ev.sid, ev.task || "");
            }
        }

        if (evt === "model_start") {
            p = state.pending;
            if (p) {
                const role = normalizeRole(ev.role || "general");
                const name = ev.model || "local";
                attachModelToPending(p, { role, name });
                applyModel({ role, name }, "using · " + name);
                setAct(p, "using · " + esc(name));
            }
            return;
        }

        p = state.pending;
        if (!p) return;

        if (evt === "thinking") {
            const name = ev.model || (state.lastModel && state.lastModel.name) || "local";
            const role = normalizeRole(ev.role || (state.lastModel && state.lastModel.role) || "general");
            applyModel({ role, name }, "thinking · " + name);
            setAct(p, "thinking · " + esc(ev.message || name));
        }

        if (evt === "model_done") {
            const name = ev.model || (state.lastModel && state.lastModel.name) || "local";
            const role = normalizeRole(ev.role || (state.lastModel && state.lastModel.role) || "general");
            applyModel({ role, name }, "completed · " + name);
            setAct(p, "done · " + esc(name));
        }

        if (evt === "operation") {
            setAct(p, "📁 " + esc(ev.message || ""));
        }

        if (evt === "operation_error") {
            setAct(p, "⚠ " + esc(ev.message || ""));
        }

        if (evt === "handoff") {
            setAct(p, "↔ " + esc(ev.message || "model handoff"));
        }

        if (evt === "run.done" && ev.sid === p.sid) {
            (async () => {
                const res = await pollResult(p.sid);
                if (state.pending === p && !p.finished) {
                    completePending(p, res);
                    state.pending = null;
                    setBusyUI(false);
                    input.focus();
                }
            })();
        }

        if (evt === "run.error" && ev.sid === p.sid) {
            completePending(p, { answer: "Error: " + (ev.error || "Unknown error") });
            state.pending = null;
            setBusyUI(false);
        }

        if (evt === "run.cancelled" && ev.sid === p.sid) {
            completePending(p, { answer: "Stopped by the user." });
            state.pending = null;
            setBusyUI(false);
        }
    }

    // Knowledge Base
    const kbDocs = $("#kb-docs");
    const kbCounts = $("#kb-counts");

    async function refreshKb() {
        const r = await fetchJSON("/api/kb/docs").catch(() => null);
        if (!r || !r.docs) return;
        kbCounts.textContent = r.docs.length + " documents";
        kbDocs.innerHTML = "";
        r.docs.forEach((d) => {
            const row = document.createElement("div");
            row.className = "kb-doc";
            row.innerHTML = '<span class="dd">' + esc(d) + "</span><span class='ni'>›</span>";
            kbDocs.appendChild(row);
        });
    }

    $("#kb-query").addEventListener("keydown", (e) => { if (e.key === "Enter") runKbSearch(); });
    $("#kb-search-btn").addEventListener("click", runKbSearch);

    async function runKbSearch() {
        const q = $("#kb-query").value.trim();
        const box = $("#kb-results");
        if (!q) { box.innerHTML = ""; return; }
        box.innerHTML = '<div class="nores">searching…</div>';
        const r = await fetchJSON("/api/kb/search?q=" + enc(q) + "&k=4").catch(() => null);
        if (!r || !r.hits || !r.hits.length) { box.innerHTML = '<div class="nores">No results found.</div>'; return; }
        box.innerHTML = "";
        r.hits.forEach((h) => {
            const hit = document.createElement("div");
            hit.className = "hit";
            hit.innerHTML = '<div class="h-src">' + esc(h.doc) + ' <span class="h-sc">' + h.score + "</span></div>" +
                '<div class="h-tx">' + esc(h.text.slice(0, 260)) + (h.text.length > 260 ? "…" : "") + "</div>";
            box.appendChild(hit);
        });
    }

    $("#kb-add-btn").addEventListener("click", () => $("#kb-add-input").click());
    $("#kb-add-input").addEventListener("change", async () => {
        const fi = $("#kb-add-input");
        const picked = Array.from(fi.files || []);
        fi.value = "";
        if (!picked.length) return;
        const fd = new FormData();
        picked.forEach((f) => fd.append("files", f));
        const st = $("#kb-add-status");
        st.textContent = "Adding " + picked.length + " file(s)…";
        try {
            const r = await fetchJSON("/api/kb/add", "POST", fd);
            st.textContent = "Added " + (r.added || []).length + " file(s)";
            toast("Knowledge files added");
        } catch (e) { st.textContent = "Failed: " + e.message; }
        refreshKb();
    });

    // File Browser
    const fileBrowser = $("#file-browser");
    async function refreshFiles() {
        const r = await fetchJSON("/api/files/list").catch(() => null);
        if (!r || !r.files) return;
        fileBrowser.innerHTML = r.files.length ? "" : '<div class="nores">No files in workspace.</div>';
        r.files.slice(0, 200).forEach((f) => {
            const row = document.createElement("div");
            row.className = "file-item";
            const ext = f.split('.').pop() || '';
            const icon = {
                'py': '🐍', 'js': '📜', 'ts': '📘', 'html': '🌐', 'css': '🎨',
                'json': '📋', 'md': '📝', 'txt': '📄', 'csv': '📊', 'png': '🖼️',
                'jpg': '🖼️', 'jpeg': '🖼️'
            }[ext] || '📄';
            row.innerHTML = '<span class="ficon">' + icon + '</span><span class="fname">' + esc(f) + '</span>';
            fileBrowser.appendChild(row);
        });
    }

    $("#file-search-btn").addEventListener("click", async () => {
        const q = $("#file-search").value.trim();
        if (!q) return refreshFiles();
        const r = await fetchJSON("/api/files/search", "POST", { query: q }).catch(() => null);
        if (!r || !r.results) return;
        fileBrowser.innerHTML = r.results.length ? "" : '<div class="nores">No matches found.</div>';
        r.results.forEach((f) => {
            const row = document.createElement("div");
            row.className = "file-item";
            row.innerHTML = '<span class="ficon">🔍</span><span class="fname">' + esc(f.path) + '</span>';
            fileBrowser.appendChild(row);
        });
    });

    // Boot: restore the last conversation from the persistent chat store.
    async function boot() {
        setBusyUI(false);
        const r = await fetchJSON("/api/chats").catch(() => null);
        let cid = null;
        try { cid = localStorage.getItem("seal-chat-id"); } catch (e) {}
        let data = null;
        if (cid) data = await fetchJSON("/api/chats/" + encodeURIComponent(cid)).catch(() => null);
        if (!data && r && r.chats && r.chats.length) {
            data = await fetchJSON("/api/chats/" + encodeURIComponent(r.chats[0].id)).catch(() => null);
        }
        if (data) await openChat(data);
        else await startNewChat(true);
        connect();
        syncModelBar();
        refreshChatList();
        refreshKb();
        refreshFiles();
    }
    boot();

    // Expose for inline onclick
    window.doSend = doSend;
})();