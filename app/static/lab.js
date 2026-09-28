const form = document.querySelector("#check-form");
const targetInput = document.querySelector("#target");
const countSelect = document.querySelector("#count");
const runButton = document.querySelector("#run");
const scopeList = document.querySelector("#scope-list");
const publicState = document.querySelector("#public-state");
const verdict = document.querySelector("#verdict");
const detail = document.querySelector("#detail");
const meter = document.querySelector("#latency-meter");
const journal = document.querySelector("#journal");
const linkState = document.querySelector("#link-state");
const clock = document.querySelector("#clock");
const fields = {
  target: document.querySelector("#out-target"),
  ip: document.querySelector("#out-ip"),
  sent: document.querySelector("#out-sent"),
  received: document.querySelector("#out-received"),
  latency: document.querySelector("#out-latency"),
};

function stamp() {
  return new Date().toLocaleTimeString("fr-FR", { hour12: false });
}

function log(message) {
  const item = document.createElement("li");
  const time = document.createElement("time");
  const text = document.createElement("span");
  time.dateTime = new Date().toISOString();
  time.textContent = stamp();
  text.textContent = message;
  item.append(time, text);
  journal.prepend(item);
}

function setVerdict(kind, title, message) {
  verdict.dataset.state = kind;
  verdict.textContent = title;
  detail.textContent = message;
}

function clearMetrics() {
  for (const field of Object.values(fields)) {
    field.textContent = "—";
  }
  meter.style.width = "0%";
}

function showMetrics(body) {
  fields.target.textContent = body.target;
  fields.ip.textContent = body.resolved_ip;
  fields.sent.textContent = String(body.packets_sent);
  fields.received.textContent = String(body.packets_received);
  if (body.latency_ms === null || body.latency_ms === undefined) {
    fields.latency.textContent = "—";
    meter.style.width = "0%";
    return;
  }
  fields.latency.textContent = `${body.latency_ms} ms`;
  meter.style.width = `${Math.max(6, Math.min(100, body.latency_ms))}%`;
}

function errorDetail(payload) {
  const message = payload && payload.detail;
  if (typeof message === "string") {
    return message;
  }
  if (Array.isArray(message)) {
    return message.map((item) => item.msg).filter(Boolean).join(" ");
  }
  return "Le contrôle n'a pas pu aboutir.";
}

async function loadScope() {
  const response = await fetch("/api/v1/diagnostics/scope");
  if (!response.ok) {
    throw new Error("scope");
  }
  const scope = await response.json();
  scopeList.replaceChildren();
  for (const network of scope.allowed_networks) {
    const item = document.createElement("li");
    item.textContent = network;
    scopeList.append(item);
  }
  publicState.textContent = scope.allow_public_targets
    ? "Cibles publiques ouvertes pour les hôtes listés"
    : "Cibles publiques fermées";
  countSelect.replaceChildren();
  for (let count = 1; count <= scope.max_ping_count; count += 1) {
    const option = document.createElement("option");
    option.value = String(count);
    option.textContent = String(count);
    countSelect.append(option);
  }
}

async function refreshLink() {
  try {
    const response = await fetch("/health");
    if (!response.ok) {
      throw new Error("health");
    }
    linkState.textContent = "API en ligne";
    linkState.dataset.state = "up";
  } catch {
    linkState.textContent = "API injoignable";
    linkState.dataset.state = "down";
  }
}

function tickClock() {
  const now = new Date();
  clock.dateTime = now.toISOString();
  clock.textContent = now.toLocaleTimeString("fr-FR", { hour12: false });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = targetInput.value.trim();
  runButton.disabled = true;
  setVerdict("running", "Mesure en cours", "Envoi ICMP vers l'hôte nommé.");
  clearMetrics();
  log(`Contrôle demandé pour ${target}`);
  try {
    const response = await fetch("/api/v1/diagnostics/ping", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target, count: Number(countSelect.value) }),
    });
    const payload = await response.json();
    if (!response.ok) {
      const message = errorDetail(payload);
      setVerdict("refused", "Contrôle refusé", message);
      log(message);
      return;
    }
    showMetrics(payload);
    if (payload.reachable) {
      setVerdict("up", "Hôte joignable", payload.detail);
    } else {
      setVerdict("down", "Hôte silencieux", payload.detail);
    }
    log(`${payload.resolved_ip} · ${payload.detail}`);
  } catch {
    setVerdict("refused", "Liaison interrompue", "La console n'a pas reçu de réponse de l'API.");
    log("Échec de liaison avec l'API.");
  } finally {
    runButton.disabled = false;
  }
});

tickClock();
setInterval(tickClock, 1000);
setVerdict("idle", "En attente", "Nommez un hôte du périmètre, puis lancez le contrôle.");
clearMetrics();
loadScope()
  .then(() => log("Périmètre chargé."))
  .catch(() => {
    publicState.textContent = "Périmètre indisponible";
    log("Périmètre indisponible.");
  });
refreshLink();
setInterval(refreshLink, 10000);
log("Console prête.");
