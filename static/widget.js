/* Ask Your Documents — embeddable chat widget.
 *
 * Usage (one tag):
 *   <script src="https://YOUR-HOST/widget.js"
 *           data-name="Harper's Bike Hire"
 *           data-colour="#0f766e"></script>
 *
 * No dependencies. Renders inside a shadow root so host-page CSS cannot
 * bleed in. All server text is inserted with textContent — never innerHTML —
 * so answers cannot inject markup.
 */
(function () {
  "use strict";

  var script = document.currentScript;
  if (!script || !script.src) return;

  var API_BASE = new URL(script.src).origin;
  var NAME = script.getAttribute("data-name") || "Ask us anything";
  var ACCENT =
    script.getAttribute("data-colour") ||
    script.getAttribute("data-color") ||
    "#1f6feb";
  // Accent goes into CSS via a custom property; reject anything that could
  // escape the declaration.
  if (!/^[#a-zA-Z0-9(),.% -]+$/.test(ACCENT)) ACCENT = "#1f6feb";

  var host = document.createElement("div");
  host.id = "ask-your-docs-widget";
  var root = host.attachShadow({ mode: "open" });
  document.body.appendChild(host);

  var style = document.createElement("style");
  style.textContent = [
    ":host { all: initial; }",
    "* { box-sizing: border-box; font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }",
    ".launcher { position: fixed; right: 20px; bottom: 20px; width: 56px; height: 56px;",
    "  border-radius: 50%; border: none; cursor: pointer; background: var(--accent);",
    "  color: #fff; font-size: 24px; line-height: 1; box-shadow: 0 4px 12px rgba(0,0,0,.25); z-index: 2147483000; }",
    ".panel { position: fixed; right: 20px; bottom: 88px; width: 360px; max-width: calc(100vw - 40px);",
    "  height: 480px; max-height: calc(100vh - 120px); display: none; flex-direction: column;",
    "  background: #fff; border-radius: 12px; overflow: hidden;",
    "  box-shadow: 0 8px 30px rgba(0,0,0,.3); z-index: 2147483001; }",
    ".panel.open { display: flex; }",
    ".header { background: var(--accent); color: #fff; padding: 12px 16px; display: flex;",
    "  align-items: center; justify-content: space-between; }",
    ".header h1 { font-size: 15px; margin: 0; font-weight: 600; }",
    ".header button { background: none; border: none; color: #fff; font-size: 18px; cursor: pointer; padding: 0 4px; }",
    ".messages { flex: 1; overflow-y: auto; padding: 12px; background: #f6f7f9; }",
    ".msg { max-width: 85%; margin-bottom: 10px; padding: 9px 12px; border-radius: 10px;",
    "  font-size: 14px; line-height: 1.45; white-space: pre-wrap; word-wrap: break-word; }",
    ".msg.user { background: var(--accent); color: #fff; margin-left: auto; }",
    ".msg.bot { background: #fff; color: #1a1a1a; border: 1px solid #e3e5e8; }",
    ".msg.bot.fallback { background: #fffbeb; border-color: #f0e2b6; }",
    ".sources { font-size: 11px; color: #667085; margin: -6px 0 10px 4px; }",
    ".contact { font-size: 13px; margin: -4px 0 10px 4px; }",
    ".contact a { color: var(--accent); }",
    ".typing { color: #98a2b3; font-style: italic; }",
    ".inputrow { display: flex; border-top: 1px solid #e3e5e8; background: #fff; }",
    ".inputrow input { flex: 1; border: none; padding: 12px 14px; font-size: 14px; outline: none; }",
    ".inputrow button { border: none; background: var(--accent); color: #fff; padding: 0 18px;",
    "  font-size: 14px; cursor: pointer; }",
    ".inputrow button:disabled { opacity: .5; cursor: default; }",
    "@media (max-width: 480px) {",
    "  .panel { right: 8px; left: 8px; bottom: 84px; width: auto; height: 70vh; }",
    "}",
  ].join("\n");
  root.appendChild(style);
  host.style.setProperty("--accent", ACCENT);
  // Custom properties don't cross a shadow boundary from an inline host style
  // in every browser; set it on both sides to be safe.
  style.textContent = ":host { --accent: " + ACCENT + "; }\n" + style.textContent;

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  var launcher = el("button", "launcher", "⁇");
  launcher.setAttribute("aria-label", "Open chat");
  var panel = el("div", "panel");
  var header = el("div", "header");
  var title = el("h1", null, NAME);
  var closeBtn = el("button", null, "×");
  closeBtn.setAttribute("aria-label", "Close chat");
  header.appendChild(title);
  header.appendChild(closeBtn);
  var messages = el("div", "messages");
  var inputRow = el("div", "inputrow");
  var input = el("input");
  input.placeholder = "Type your question…";
  input.maxLength = 500;
  var sendBtn = el("button", null, "Ask");
  inputRow.appendChild(input);
  inputRow.appendChild(sendBtn);
  panel.appendChild(header);
  panel.appendChild(messages);
  panel.appendChild(inputRow);
  root.appendChild(launcher);
  root.appendChild(panel);

  addBot("Hello! Ask me anything about our documents and I’ll answer with sources.");

  launcher.addEventListener("click", function () {
    panel.classList.toggle("open");
    if (panel.classList.contains("open")) input.focus();
  });
  closeBtn.addEventListener("click", function () {
    panel.classList.remove("open");
  });
  sendBtn.addEventListener("click", send);
  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter") send();
  });

  function addBot(text, extraClass) {
    var msg = el("div", "msg bot" + (extraClass ? " " + extraClass : ""), text);
    messages.appendChild(msg);
    messages.scrollTop = messages.scrollHeight;
    return msg;
  }

  function citationLabel(citation) {
    var label = citation.filename;
    if (citation.page !== null && citation.page !== undefined) {
      label += " (p." + citation.page + ")";
    }
    return label;
  }

  function send() {
    var question = input.value.trim();
    if (question.length < 3 || sendBtn.disabled) return;
    input.value = "";
    var userMsg = el("div", "msg user", question);
    messages.appendChild(userMsg);
    var typing = addBot("Thinking…", "typing");
    sendBtn.disabled = true;

    fetch(API_BASE + "/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question }),
    })
      .then(function (response) {
        if (response.status === 429) {
          throw new Error("rate");
        }
        if (!response.ok) throw new Error("http " + response.status);
        return response.json();
      })
      .then(function (body) {
        typing.remove();
        addBot(body.answer, body.confident ? null : "fallback");
        if (body.citations && body.citations.length) {
          var seen = [];
          body.citations.forEach(function (c) {
            var label = citationLabel(c);
            if (seen.indexOf(label) === -1) seen.push(label);
          });
          messages.appendChild(el("div", "sources", "Sources: " + seen.join(" · ")));
        }
        if (!body.confident && body.contact && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(body.contact)) {
          var contactRow = el("div", "contact");
          contactRow.appendChild(document.createTextNode("Reach a human: "));
          var link = document.createElement("a");
          link.href = "mailto:" + body.contact;
          link.textContent = body.contact;
          contactRow.appendChild(link);
          messages.appendChild(contactRow);
        }
        messages.scrollTop = messages.scrollHeight;
      })
      .catch(function (err) {
        typing.remove();
        addBot(
          err.message === "rate"
            ? "You’re sending questions quickly — please wait a minute and try again."
            : "Something went wrong. Please try again.",
          "fallback"
        );
      })
      .finally(function () {
        sendBtn.disabled = false;
        input.focus();
      });
  }
})();
