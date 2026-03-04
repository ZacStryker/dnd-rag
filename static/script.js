(function () {
    'use strict';

    const appData      = document.getElementById('app-data');
    const STATUS_URL          = appData.dataset.statusUrl;
    const CHAT_URL            = appData.dataset.chatUrl;
    const ANTHROPIC_STATUS_URL = appData.dataset.anthropicStatusUrl;

    const indexBadge    = document.getElementById('indexBadge');
    const statusText    = document.getElementById('statusText');
    const apiBadge      = document.getElementById('apiBadge');
    const apiStatusText = document.getElementById('apiStatusText');
    const ragBadge      = document.getElementById('ragBadge');
    const ragStatusText = document.getElementById('ragStatusText');
    const errorBanner  = document.getElementById('errorBanner');
    const initPanel    = document.getElementById('initPanel');
    const initMsg      = document.getElementById('initMsg');
    const chatUI       = document.getElementById('chatUI');
    const messages     = document.getElementById('messages');
    const suggestions  = document.getElementById('suggestions');
    const input        = document.getElementById('questionInput');
    const sendBtn      = document.getElementById('sendBtn');

    let ready          = false;
    let msgCounter     = 0;
    let pollTimer      = null;
    let indexColor     = '';
    let apiIndicator   = 'unknown';

    // ── Status polling ────────────────────────────────────────────

    function updateRagStatus() {
        var color, text;
        if (indexColor === 'green' && apiIndicator === 'none') {
            color = 'green'; text = 'Ready';
        } else if (indexColor === 'red' || apiIndicator === 'major' || apiIndicator === 'critical') {
            color = 'red'; text = 'Unavailable';
        } else {
            color = 'yellow'; text = 'Degraded';
        }
        ragBadge.className    = 'metric-badge ' + color;
        ragStatusText.textContent = text;
    }

    function setStatus(color, text) {
        indexColor             = color;
        indexBadge.className   = 'metric-badge ' + color;
        statusText.textContent = text;
        updateRagStatus();
    }

    function showError(msg) {
        errorBanner.textContent = msg;
        errorBanner.style.display = 'block';
    }

    function hideError() {
        errorBanner.style.display = 'none';
    }

    function pollStatus() {
        fetch(STATUS_URL)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var foundAny = data.sources && data.sources.some(function (s) { return s.found; });
                if (!foundAny) {
                    setStatus('red', 'No PDFs found — add dmg.pdf / phb.pdf to projects/rag_chatbot/data/');
                    initPanel.style.display  = 'none';
                    chatUI.style.display     = 'none';
                    return;
                }

                if (data.error) {
                    setStatus('red', 'Indexing error: ' + data.error);
                    initMsg.textContent      = 'Error: ' + data.error;
                    initPanel.style.display  = 'flex';
                    chatUI.style.display     = 'none';
                    return;
                }

                if (data.initialized) {
                    var labels = data.sources
                        .filter(function (s) { return s.indexed; })
                        .map(function (s) { return s.label; })
                        .join(' + ');
                    setStatus('green', data.chunk_count + ' chunks');
                    initPanel.style.display = 'none';
                    chatUI.style.display    = 'block';
                    ready = true;
                    clearInterval(pollTimer);
                    return;
                }

                if (data.indexing) {
                    setStatus('yellow', 'Indexing rulebook…');
                    initPanel.style.display = 'flex';
                    chatUI.style.display    = 'none';
                    return;
                }

                // PDF found but indexing hasn't started (shouldn't normally happen)
                setStatus('yellow', 'Starting indexer…');
                initPanel.style.display = 'flex';
                chatUI.style.display    = 'none';
            })
            .catch(function () {
                setStatus('red', 'Could not reach server');
            });
    }

    pollStatus();
    pollTimer = setInterval(pollStatus, 3000);

    // ── Claude API status ─────────────────────────────────────────

    function pollApiStatus() {
        fetch(ANTHROPIC_STATUS_URL)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                apiIndicator = data.indicator || 'unknown';
                var color, text;
                if (apiIndicator === 'none') {
                    color = 'green'; text = 'API Operational';
                } else if (apiIndicator === 'minor') {
                    color = 'yellow'; text = 'Degraded Performance';
                } else if (apiIndicator === 'major') {
                    color = 'red'; text = 'Partial Outage';
                } else if (apiIndicator === 'critical') {
                    color = 'red'; text = 'Major Outage';
                } else {
                    color = 'red'; text = 'Status Unknown';
                }
                apiBadge.className    = 'metric-badge ' + color;
                apiStatusText.textContent = text;
                updateRagStatus();
            })
            .catch(function () {
                apiIndicator = 'unknown';
                apiBadge.className    = 'metric-badge red';
                apiStatusText.textContent = 'Status Unavailable';
                updateRagStatus();
            });
    }

    pollApiStatus();
    setInterval(pollApiStatus, 60000);

    // ── Message helpers ───────────────────────────────────────────

    function addUserMessage(text) {
        var div = document.createElement('div');
        div.className = 'msg user';
        div.innerHTML = '<div class="msg-bubble">' + escHtml(text) + '</div>';
        messages.appendChild(div);
        scrollBottom();
    }

    function addAiMessage() {
        msgCounter++;
        var id  = 'msg-' + msgCounter;
        var div = document.createElement('div');
        div.className = 'msg ai';
        div.id = id;
        div.innerHTML =
            '<div class="msg-bubble" id="bubble-' + id + '"></div>' +
            '<div class="sources-area" id="src-' + id + '"></div>';
        messages.appendChild(div);
        scrollBottom();
        return id;
    }

    function appendToken(msgId, text) {
        var bubble = document.getElementById('bubble-' + msgId);
        if (bubble) {
            bubble.textContent += text;
            scrollBottom();
        }
    }

    function renderSources(msgId, sources) {
        var area = document.getElementById('src-' + msgId);
        if (!area || !sources.length) return;

        var btn = document.createElement('button');
        btn.className = 'sources-toggle';
        btn.textContent = '\uD83D\uDCDA ' + sources.length + ' source' +
                          (sources.length > 1 ? 's' : '') + ' — click to expand';

        var list = document.createElement('div');
        list.className = 'sources-list';

        sources.forEach(function (src) {
            var card = document.createElement('div');
            card.className = 'source-card';
            var label = src.source ? src.source + ' p. ' + src.page : 'p. ' + src.page;
            card.innerHTML =
                '<span class="page-badge">' + label + '</span>' +
                '<p>' + escHtml(src.text) + '</p>' +
                '<span class="score">relevance score: ' + src.score + '</span>';
            list.appendChild(card);
        });

        btn.addEventListener('click', function () {
            var open = list.classList.toggle('open');
            btn.textContent = (open ? '\uD83D\uDCDA ' : '\uD83D\uDCDA ') +
                sources.length + ' source' + (sources.length > 1 ? 's' : '') +
                (open ? ' — click to collapse' : ' — click to expand');
        });

        area.appendChild(btn);
        area.appendChild(list);
    }

    function scrollBottom() {
        messages.scrollTop = messages.scrollHeight;
    }

    function escHtml(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // ── Send question ─────────────────────────────────────────────

    async function sendQuestion(question) {
        if (!ready || !question) return;

        hideError();
        suggestions.style.display = 'none';
        addUserMessage(question);

        input.value  = '';
        sendBtn.disabled = true;

        var msgId    = addAiMessage();
        var pendingSources = null;

        try {
            var response = await fetch(CHAT_URL, {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ question: question }),
            });

            if (!response.ok) {
                var err = await response.json().catch(function () { return {}; });
                throw new Error(err.error || 'Request failed (' + response.status + ')');
            }

            var reader  = response.body.getReader();
            var decoder = new TextDecoder();
            var buffer  = '';

            while (true) {
                var chunk = await reader.read();
                if (chunk.done) break;

                buffer += decoder.decode(chunk.value, { stream: true });
                var lines = buffer.split('\n');
                buffer = lines.pop();

                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i];
                    if (!line.startsWith('data: ')) continue;
                    var data = JSON.parse(line.slice(6));

                    if (data.type === 'sources') {
                        pendingSources = data.sources;
                    } else if (data.type === 'token') {
                        appendToken(msgId, data.text);
                    } else if (data.type === 'done') {
                        if (pendingSources) renderSources(msgId, pendingSources);
                    }
                }
            }

        } catch (err) {
            showError(err.message || 'Something went wrong. Please try again.');
            var bubble = document.getElementById('bubble-' + msgId);
            if (bubble && !bubble.textContent) {
                bubble.textContent = '⚠ Failed to get a response.';
            }
        } finally {
            sendBtn.disabled = false;
            input.focus();
            suggestions.style.display = 'block';
        }
    }

    // ── Event listeners ───────────────────────────────────────────

    sendBtn.addEventListener('click', function () {
        sendQuestion(input.value.trim());
    });

    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuestion(input.value.trim());
        }
    });

    document.querySelectorAll('.chip').forEach(function (chip) {
        chip.addEventListener('click', function () {
            sendQuestion(chip.dataset.q);
        });
    });

}());
