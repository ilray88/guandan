// === FableDan GuanDan UI ===

let gameState = null;
let gameId = null;
let selectedCards = new Set(); // Set of indices in hand array
let pollTimer = null;
let hintEnabled = false;
let autoPlayEnabled = false;

// Drag-and-drop hand reordering
let localHand = null; // local copy of hand array for reordering
let lastServerHandKey = null; // fingerprint to detect server hand changes (order-independent)
let dragSrcIdx = null; // index of card being dragged
let sortAscending = localStorage.getItem('sortAscending') === 'true'; // persisted preference
let lastTrickKey = null; // fingerprint of trick_plays to detect new plays

// === i18n ===

const I18N = {
    en: {
        // Start screen
        title: 'FableDan GuanDan',
        subtitle: 'AI GuanDan Battle',
        singleRound: 'Random Single Round',
        fullGame: 'Full Game (2 to A)',
        // Player labels
        you: 'You', next: 'Next', partner: 'Partner', prev: 'Prev',
        // Status bar
        level: 'Level', round: 'Round', us: 'Us', them: 'Them',
        handCount: 'Hand',
        yourTurn: 'Your turn',
        thinking: 'thinking...',
        roundOver: 'Round over', gameOver: 'Game over',
        // Buttons
        reset: 'Reset', menu: 'Menu',
        play: 'Play', clear: 'Clear', pass: 'Pass',
        hintOn: 'AI Hint: ON', hintOff: 'AI Hint: OFF',
        autoOn: 'AI Auto: ON', autoOff: 'AI Auto: OFF',
        confirm: 'Confirm', continue_: 'Start',
        newRound: 'New Round', nextRound: 'Next Round', newGame: 'New Game',
        // Center messages
        yourTurnBig: 'Your Turn',
        isThinking: 'is thinking...',
        leadPrefix: 'Lead',
        autoPlaying: 'AI Auto Playing',
        // Overlays
        noTribute: 'No Tribute',
        firstPlayer: 'First player',
        antiTribute: 'Anti-Tribute!',
        holds2BigJoker: 'holds 2x Big Joker',
        eachHoldBigJoker: 'each hold Big Joker',
        singleTribute: 'Single Tribute',
        doubleTribute: 'Double Tribute',
        givesTo: 'gives to',
        // Result
        victory: 'Victory!', defeat: 'Defeat',
        finishOrder: 'Finish order',
        reward: 'Reward',
        teamLevels: 'Team levels',
        gameWon: 'Game Won!', gameLost: 'Game Lost',
        // Card
        joker: 'Joker',
        // Play types
        pt_pass: 'pass', pt_single: 'single', pt_pair: 'pair', pt_triple: 'triple',
        pt_full: 'full house', pt_straight: 'straight', pt_plate: 'plate', pt_tube: 'tube',
        pt_bomb: 'bomb', pt_sflush: 'straight flush', pt_rocket: 'rocket',
        // Misc
        notValidPlay: 'Not a valid play!',
        disambiguate: 'Multiple interpretations - choose one:',
        cancel: 'Cancel',
        sortAsc: 'Sort: ->', sortDesc: 'Sort: <-',
        aiAgent: 'AI Agent',
        lang: '中文',
    },
    zh: {
        // Start screen
        title: 'FableDan 掼蛋',
        subtitle: 'AI 掼蛋对战',
        singleRound: '随机单局',
        fullGame: '完整对局 (2 到 A)',
        // Player labels
        you: '自己', next: '下家', partner: '队友', prev: '上家',
        // Status bar
        level: '等级', round: '局', us: '我方', them: '对方',
        handCount: '手牌',
        yourTurn: '你的回合',
        thinking: '思考中...',
        roundOver: '本局结束', gameOver: '游戏结束',
        // Buttons
        reset: '重置', menu: '菜单',
        play: '出牌', clear: '取消', pass: '过',
        hintOn: 'AI提示：开', hintOff: 'AI提示：关',
        autoOn: 'AI托管：开', autoOff: 'AI托管：关',
        confirm: '确认', continue_: '开始',
        newRound: '再来一局', nextRound: '下一局', newGame: '新游戏',
        // Center messages
        yourTurnBig: '你的回合',
        isThinking: '思考中...',
        leadPrefix: '领出',
        autoPlaying: 'AI 托管中',
        // Overlays
        noTribute: '无进贡',
        firstPlayer: '先手',
        antiTribute: '抗贡！',
        holds2BigJoker: '持有 2 张大王',
        eachHoldBigJoker: '各持有大王',
        singleTribute: '单进贡',
        doubleTribute: '双进贡',
        givesTo: '进贡给',
        // Result
        victory: '胜利！', defeat: '失败',
        finishOrder: '完成顺序',
        reward: '奖励',
        teamLevels: '队伍等级',
        gameWon: '赢得比赛！', gameLost: '比赛失败',
        // Card
        joker: 'Joker',
        // Play types
        pt_pass: '过', pt_single: '单张', pt_pair: '对子', pt_triple: '三不带',
        pt_full: '三带二', pt_straight: '顺子', pt_plate: '钢板', pt_tube: '三连对',
        pt_bomb: '炸弹', pt_sflush: '同花顺', pt_rocket: '王炸',
        // Misc
        notValidPlay: '不是合法的出牌！',
        disambiguate: '出牌有多种解释，请选择：',
        cancel: '取消',
        sortAsc: '排序：→', sortDesc: '排序：←',
        aiAgent: 'AI 模型',
        lang: 'EN',
    }
};

let currentLang = localStorage.getItem('lang') || 'zh';

function t(key) {
    return (I18N[currentLang] && I18N[currentLang][key]) || I18N.en[key] || key;
}

function tPlayType(type) {
    return t('pt_' + type) || type;
}

function toggleLang() {
    currentLang = currentLang === 'en' ? 'zh' : 'en';
    localStorage.setItem('lang', currentLang);
    applyLang();
}

function applyLang() {
    // Update static HTML elements
    document.getElementById('titlebar-title').textContent = t('title');
    document.getElementById('start-title').textContent = t('title');
    document.getElementById('start-subtitle').textContent = t('subtitle');
    document.getElementById('btn-single-round').textContent = t('singleRound');
    document.getElementById('btn-full-game').textContent = t('fullGame');
    document.getElementById('btn-reset').textContent = t('reset');
    document.getElementById('btn-menu').textContent = t('menu');
    document.getElementById('btn-lang').textContent = t('lang');
    document.getElementById('btn-lang-start').textContent = t('lang');
    document.getElementById('label-agent').textContent = t('aiAgent');
    document.getElementById('btn-info-continue').textContent = t('continue_');
    document.getElementById('btn-back-menu').textContent = t('menu');
    document.getElementById('btn-disambig-cancel').textContent = t('cancel');
    // Player labels in HTML
    document.querySelector('#player-top .player-label').textContent = t('partner');
    document.querySelector('#player-left .player-label').textContent = t('prev');
    document.querySelector('#player-right .player-label').textContent = t('next');
    // Dynamic elements re-render
    if (gameState) render();
}

// === Sound Effects (Web Audio API) ===

const AudioCtx = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;

function getAudioCtx() {
    if (!audioCtx) audioCtx = new AudioCtx();
    return audioCtx;
}

function playTone(freq, duration, type = 'triangle', gain = 0.3) {
    const ctx = getAudioCtx();
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    g.gain.setValueAtTime(gain, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.connect(g);
    g.connect(ctx.destination);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + duration);
}

function playNoise(duration, gain = 0.15) {
    const ctx = getAudioCtx();
    const bufSize = ctx.sampleRate * duration;
    const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < bufSize; i++) data[i] = Math.random() * 2 - 1;
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const g = ctx.createGain();
    g.gain.setValueAtTime(gain, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    src.connect(g);
    g.connect(ctx.destination);
    src.start();
}

function sfxPlay() {
    // Card slap: short noise burst + tap tone
    playNoise(0.08, 0.12);
    playTone(800, 0.06, 'square', 0.08);
}

function sfxPass() {
    playTone(300, 0.12, 'sine', 0.08);
}

function sfxBomb() {
    // Punchy impact: sharp attack + quick pitch drop + noise hit
    const ctx = getAudioCtx();
    const osc1 = ctx.createOscillator();
    const g1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(400, ctx.currentTime);
    osc1.frequency.exponentialRampToValueAtTime(60, ctx.currentTime + 0.15);
    g1.gain.setValueAtTime(0.5, ctx.currentTime);
    g1.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
    osc1.connect(g1);
    g1.connect(ctx.destination);
    osc1.start(ctx.currentTime);
    osc1.stop(ctx.currentTime + 0.25);
    const osc2 = ctx.createOscillator();
    const g2 = ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.value = 55;
    g2.gain.setValueAtTime(0.4, ctx.currentTime);
    g2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc2.connect(g2);
    g2.connect(ctx.destination);
    osc2.start(ctx.currentTime);
    osc2.stop(ctx.currentTime + 0.3);
    playNoise(0.06, 0.25);
}

function sfxFlushBomb() {
    // Ascending chime
    const notes = [523, 659, 784, 988, 1175]; // C5 E5 G5 B5 D6
    notes.forEach((f, i) => {
        setTimeout(() => playTone(f, 0.25, 'sine', 0.25), i * 60);
    });
}

function sfxJokerBomb() {
    // Epic explosion: low rumble + high sparkle + noise
    const ctx = getAudioCtx();
    const osc1 = ctx.createOscillator();
    const g1 = ctx.createGain();
    osc1.type = 'sawtooth';
    osc1.frequency.setValueAtTime(100, ctx.currentTime);
    osc1.frequency.exponentialRampToValueAtTime(25, ctx.currentTime + 0.8);
    g1.gain.setValueAtTime(0.5, ctx.currentTime);
    g1.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.8);
    osc1.connect(g1);
    g1.connect(ctx.destination);
    osc1.start(ctx.currentTime);
    osc1.stop(ctx.currentTime + 0.8);
    [1047, 1319, 1568, 1976, 2349].forEach((f, i) => {
        setTimeout(() => playTone(f, 0.4, 'sine', 0.2), i * 80);
    });
    playNoise(0.5, 0.25);
}

function sfxForPlayType(type) {
    switch (type) {
        case 'pass': sfxPass(); break;
        case 'rocket': sfxJokerBomb(); break;
        case 'sflush': sfxFlushBomb(); break;
        case 'bomb': sfxBomb(); break;
        default: sfxPlay(); break;
    }
}

function checkNewPlays(newState) {
    const newTricks = newState.trick_plays || [];
    const oldTricks = (gameState && gameState.trick_plays) || [];
    const newKey = JSON.stringify(newTricks);
    if (newKey === lastTrickKey) return;
    lastTrickKey = newKey;
    // Find the entry that changed (new play or reset) and play its sound
    for (const nt of newTricks) {
        const old = oldTricks.find(ot => ot.player === nt.player);
        if (!old || JSON.stringify(old) !== JSON.stringify(nt)) {
            sfxForPlayType(nt.type);
            break;
        }
    }
}

// === API helpers ===

async function api(endpoint, method = 'GET', body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(endpoint, opts);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
        console.error('API error:', err);
        return null;
    }
    return resp.json();
}

// === Agent selection ===

async function loadAgents() {
    const agents = await api('/api/agents', 'GET');
    if (!agents) return;
    const select = document.getElementById('agent-select');
    select.innerHTML = '';
    for (const a of agents) {
        const opt = document.createElement('option');
        opt.value = a.key;
        opt.textContent = a.name;
        if (a.key === 'rule') opt.selected = true;
        select.appendChild(opt);
    }
}

// Load agents on page init
loadAgents();

// Heartbeat: ping server every 30s so it knows the browser is still open.
setInterval(() => {
    fetch('/api/heartbeat').catch(() => {});
}, 30000);

// === Game lifecycle ===

async function startGame(mode) {
    // Disable buttons to prevent double-click
    const btnSingle = document.getElementById('btn-single-round');
    const btnFull = document.getElementById('btn-full-game');
    btnSingle.disabled = true;
    btnFull.disabled = true;
    btnSingle.textContent = t('confirm') + '...';

    try {
        const agent = document.getElementById('agent-select').value;
        const state = await api('/api/new-game', 'POST', { mode, agent });
        if (!state) return;
        gameId = state.game_id;
        gameState = state;
        selectedCards.clear();
        localHand = null;
        lastServerHandKey = null;
        lastTrickKey = null;
        hintEnabled = false;
        autoPlayEnabled = false;

        document.getElementById('start-screen').classList.remove('active');
        document.getElementById('game-screen').classList.add('active');

        render();
        showRoundStartOverlay();
    } finally {
        btnSingle.disabled = false;
        btnFull.disabled = false;
        btnSingle.textContent = t('singleRound');
    }
}

function backToMenu() {
    stopPolling();
    gameState = null;
    gameId = null;
    localHand = null;
    lastServerHandKey = null;
    lastTrickKey = null;
    selectedCards.clear();

    document.getElementById('game-screen').classList.remove('active');
    document.getElementById('start-screen').classList.add('active');
    document.getElementById('result-overlay').classList.add('hidden');
    document.getElementById('info-overlay').classList.add('hidden');
    document.getElementById('disambig-overlay').classList.add('hidden');
}

async function resetGame() {
    if (!gameState) return;
    stopPolling();
    document.getElementById('result-overlay').classList.add('hidden');
    document.getElementById('info-overlay').classList.add('hidden');
    document.getElementById('disambig-overlay').classList.add('hidden');
    selectedCards.clear();
    localHand = null;
    lastServerHandKey = null;
    lastTrickKey = null;

    const mode = gameState.mode;
    const state = await api('/api/new-game', 'POST', { mode });
    if (!state) return;
    gameId = state.game_id;
    gameState = state;

    render();
    showRoundStartOverlay();
}

async function newRound() {
    document.getElementById('result-overlay').classList.add('hidden');
    document.getElementById('info-overlay').classList.add('hidden');
    document.getElementById('disambig-overlay').classList.add('hidden');
    selectedCards.clear();
    localHand = null;
    lastServerHandKey = null;
    lastTrickKey = null;

    let state;
    if (gameState && gameState.mode === 'full_game') {
        state = await api('/api/next-round', 'POST', { game_id: gameId });
    } else {
        state = await api('/api/new-round', 'POST', { game_id: gameId });
    }
    if (!state) return;
    gameState = state;
    render();
    showRoundStartOverlay();
}

// === Round Start Overlay ===

function _miniCardHTML(cardInfo) {
    if (!cardInfo) return '?';
    const tmp = document.createElement('div');
    tmp.appendChild(createCardElement(cardInfo, true));
    const el = tmp.firstChild;
    el.style.display = 'inline-flex';
    el.style.cursor = 'default';
    el.style.verticalAlign = 'middle';
    return el.outerHTML;
}

function jokerRow(count) {
    const info = { card_int: 53, rank: 'bj', display: t('joker'), suit: 'joker', suit_symbol: '🃏', is_wild: false, is_level: false };
    let html = '<div class="joker-row">';
    for (let i = 0; i < count; i++) html += _miniCardHTML(info);
    html += '</div>';
    return html;
}

function _showOverlay(title, html, onContinue) {
    document.getElementById('info-title').textContent = title;
    document.getElementById('info-title').className = '';
    document.getElementById('info-details').innerHTML = html;
    const btn = document.getElementById('btn-info-continue');
    btn.onclick = () => {
        document.getElementById('info-overlay').classList.add('hidden');
        onContinue();
    };
    document.getElementById('info-overlay').classList.remove('hidden');
}

function showRoundStartOverlay() {
    const info = gameState.round_start_info;
    if (!info) { confirmStart(); return; }

    const title = `${t('level')} ${info.level_name || info.level}`;
    let html = '';

    if (info.tribute_type === 'none' || !info.tribute_type) {
        html += `<p>${t('noTribute')}</p>`;
    } else if (info.tribute_type === 'anti') {
        html += `<p class="overlay-accent">${t('antiTribute')}</p>`;
        const holders = info.anti_holders || [];
        if (holders.length === 1) {
            html += `<p>${playerLabel(holders[0])} ${t('holds2BigJoker')}</p>`;
            html += jokerRow(2);
        } else if (holders.length === 2) {
            html += `<p>${playerLabel(holders[0])}, ${playerLabel(holders[1])} ${t('eachHoldBigJoker')}</p>`;
            html += jokerRow(1);
            html += jokerRow(1);
        }
    } else if (info.tribute_type === 'single') {
        html += `<p class="overlay-accent">${t('singleTribute')}</p>`;
        html += `<p>${playerLabel(info.givers[0])} ${t('givesTo')} ${playerLabel(info.receivers[0])}</p>`;
    } else if (info.tribute_type === 'double') {
        html += `<p class="overlay-accent">${t('doubleTribute')}</p>`;
        html += `<p>${playerLabel(info.givers[0])}, ${playerLabel(info.givers[1])} ${t('givesTo')} ${playerLabel(info.receivers[0])}, ${playerLabel(info.receivers[1])}</p>`;
    }

    html += `<p>${t('firstPlayer')}: ${playerLabel(info.first_player)}</p>`;
    _showOverlay(title, html, confirmStart);
}

async function confirmStart() {
    document.getElementById('info-overlay').classList.add('hidden');
    const state = await api('/api/confirm-start', 'POST', { game_id: gameId });
    if (state) {
        gameState = state;
        render();
    }
    startPolling();
}

// === Polling for AI turns ===

function startPolling() {
    stopPolling();
    pollTimer = setInterval(pollState, 1500);
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

async function pollState() {
    if (!gameId) return;
    const state = await api(`/api/state?game_id=${gameId}`);
    if (!state) {
        // Session lost (e.g. server restarted) — stop polling, go back to menu
        stopPolling();
        backToMenu();
        return;
    }

    const changed = JSON.stringify(state) !== JSON.stringify(gameState);
    if (changed) {
        checkNewPlays(state);
        gameState = state;
        render();
    }
}

// === Actions ===

async function playSelected() {
    if (!gameState || !gameState.is_human_turn || gameState.auto_play) return;

    // Build sorted list of selected card_ints
    const hand = localHand || gameState.hand;
    const selCardInts = [];
    selectedCards.forEach(idx => {
        if (idx < hand.length) selCardInts.push(hand[idx].card_int);
    });
    selCardInts.sort((a, b) => a - b);

    // Find ALL matching legal plays (same card_ints, possibly different type/rank)
    const matches = [];
    for (const play of gameState.legal_plays) {
        const playInts = (play.cards || []).map(c => c.card_int).sort((a, b) => a - b);
        if (playInts.length === selCardInts.length &&
            playInts.every((v, i) => v === selCardInts[i])) {
            matches.push(play);
        }
    }

    if (matches.length === 0) {
        showMessage(t('notValidPlay'));
        return;
    }

    if (matches.length === 1) {
        await executePlay(matches[0].index);
        return;
    }

    // Ambiguous — show disambiguation picker
    showDisambiguationPicker(matches);
}

function showDisambiguationPicker(matches) {
    const overlay = document.getElementById('disambig-overlay');
    const container = document.getElementById('disambig-options');
    document.getElementById('disambig-title').textContent = t('disambiguate');
    container.innerHTML = '';

    for (const play of matches) {
        const option = document.createElement('div');
        option.className = 'disambig-option';
        option.onclick = async () => {
            overlay.classList.add('hidden');
            await executePlay(play.index);
        };

        // Cards row
        const cardsRow = document.createElement('div');
        cardsRow.className = 'disambig-cards';
        for (const card of play.cards) {
            cardsRow.appendChild(createCardElement(card, true));
        }
        option.appendChild(cardsRow);

        // Label: play type + rank
        const label = document.createElement('div');
        label.className = 'disambig-label';
        const typeStr = tPlayType(play.type);
        label.textContent = play.rank ? `${typeStr} ${play.rank}` : typeStr;
        option.appendChild(label);

        container.appendChild(option);
    }

    overlay.classList.remove('hidden');

    // Cancel button
    const cancelBtn = document.getElementById('btn-disambig-cancel');
    cancelBtn.textContent = t('cancel');
    cancelBtn.onclick = () => {
        overlay.classList.add('hidden');
    };
}

async function executePlay(actionIndex) {
    const state = await api('/api/play', 'POST', { game_id: gameId, action_index: actionIndex });
    if (!state) return;
    checkNewPlays(state);
    gameState = state;
    selectedCards.clear();
    render();
}

async function playPass() {
    if (!gameState || !gameState.is_human_turn || gameState.auto_play) return;
    const state = await api('/api/pass', 'POST', { game_id: gameId });
    if (!state) return;
    checkNewPlays(state);
    gameState = state;
    selectedCards.clear();
    render();
}

async function toggleHint() {
    hintEnabled = !hintEnabled;
    const state = await api('/api/hint', 'POST', { game_id: gameId, enabled: hintEnabled });
    if (state) {
        gameState = state;
        render();
    }
}

async function toggleAutoPlay() {
    autoPlayEnabled = !autoPlayEnabled;
    const state = await api('/api/auto-play', 'POST', { game_id: gameId, enabled: autoPlayEnabled });
    if (state) {
        gameState = state;
        render();
    }
}

function toggleSortOrder() {
    sortAscending = !sortAscending;
    localStorage.setItem('sortAscending', sortAscending);
    // Re-sort from server hand (which is always sorted descending)
    const serverHand = gameState.hand || [];
    if (sortAscending) {
        localHand = serverHand.slice().reverse();
    } else {
        localHand = serverHand.slice();
    }
    selectedCards.clear();
    renderHand();
    renderActionBar();
    saveHandOrder();
}

function selectHintPlay(cardInts) {
    // Auto-select cards matching a hint
    selectedCards.clear();
    const hand = localHand || gameState.hand;
    const needed = [...cardInts];

    for (let i = 0; i < hand.length; i++) {
        const idx = needed.indexOf(hand[i].card_int);
        if (idx >= 0) {
            selectedCards.add(i);
            needed.splice(idx, 1);
        }
    }
    renderHand();
    renderActionBar();
}

function clearSelection() {
    selectedCards.clear();
    renderHand();
    renderActionBar();
}

function saveHandOrder() {
    if (!localHand || !gameId) return;
    const card_order = localHand.map(c => c.card_int);
    api('/api/reorder-hand', 'POST', { game_id: gameId, card_order }).catch(() => {});
}

// === Rendering ===

function render() {
    if (!gameState) return;

    // Sync toggle state from server (source of truth)
    hintEnabled = !!gameState.hint_enabled;
    autoPlayEnabled = !!gameState.auto_play;

    renderStatusBar();
    renderOpponents();
    renderTrick();
    renderHints();
    renderResult();
    renderHand();
    renderActionBar();
}

function renderStatusBar() {
    const s = gameState;
    document.getElementById('status-level').textContent = `${t('level')}: ${s.level_name || s.round_level}`;
    document.getElementById('status-round').textContent = currentLang === 'zh'
        ? `第 ${s.round_number} 局`
        : `${t('round')}: ${s.round_number}`;
    document.getElementById('status-teams').textContent =
        `${t('us')}: ${s.team_levels[0]} vs ${t('them')}: ${s.team_levels[1]}`;
    document.getElementById('status-hand').textContent = `${t('handCount')}: ${s.hand_count}`;

    let turnText = '';
    if (s.phase === 'playing') {
        if (s.is_human_turn) turnText = t('yourTurn');
        else turnText = `${playerLabel(s.current_player)} ${t('thinking')}`;
    } else if (s.phase === 'round_over') {
        turnText = t('roundOver');
    } else if (s.phase === 'game_over') {
        turnText = t('gameOver');
    }
    document.getElementById('status-turn').textContent = turnText;
}

function playerLabel(seat) {
    const keys = { 0: 'you', 1: 'next', 2: 'partner', 3: 'prev' };
    return keys[seat] ? t(keys[seat]) : `P${seat}`;
}

function renderOpponents() {
    const opponents = gameState.opponents || [];
    const posMap = { top: 'player-top', left: 'player-left', right: 'player-right' };

    for (const opp of opponents) {
        const el = document.getElementById(posMap[opp.position]);
        if (!el) continue;

        // Active turn indicator
        el.classList.toggle('active-turn', gameState.current_player === opp.seat);

        // Card count
        const countEl = el.querySelector('.player-card-count');
        countEl.textContent = opp.finished ? '' : `${opp.card_count}`;
        countEl.classList.toggle('warn', opp.warn_low);

        // Card backs (actual count, overlapping handles space)
        const backsEl = el.querySelector('.player-cards-back');
        const numBacks = opp.finished ? 0 : opp.card_count;
        backsEl.innerHTML = '';
        for (let i = 0; i < numBacks; i++) {
            const back = document.createElement('div');
            back.className = 'card-back';
            backsEl.appendChild(back);
        }

        // Status
        const statusEl = el.querySelector('.player-status');
        if (opp.finished) {
            statusEl.textContent = `#${opp.finish_rank}`;
        } else {
            statusEl.textContent = '';
        }
    }

    // Human active indicator
    const bottomEl = document.getElementById('player-bottom');
    bottomEl.classList.toggle('active-turn', gameState.current_player === 0);
}

function handFingerprint(hand) {
    // Order-independent fingerprint: sorted card_ints
    return hand.map(c => c.card_int).sort((a, b) => a - b).join(',');
}

function syncLocalHand() {
    // Build an order-independent fingerprint to detect actual card changes
    const serverHand = gameState.hand || [];
    const key = handFingerprint(serverHand);

    if (key !== lastServerHandKey) {
        lastServerHandKey = key;
        selectedCards.clear();

        if (localHand && localHand.length > 0) {
            // Preserve user's custom order: remove played cards, add new cards
            const serverCounts = {};
            for (const c of serverHand) {
                serverCounts[c.card_int] = (serverCounts[c.card_int] || 0) + 1;
            }

            // Walk localHand, keep cards that still exist in server hand
            const kept = [];
            const usedCounts = {};
            for (const c of localHand) {
                const ci = c.card_int;
                const used = usedCounts[ci] || 0;
                if (used < (serverCounts[ci] || 0)) {
                    const match = serverHand.find(sc => sc.card_int === ci);
                    kept.push(match || c);
                    usedCounts[ci] = used + 1;
                }
            }

            // Add any new cards from server not in localHand
            const keptCounts = {};
            for (const c of kept) {
                keptCounts[c.card_int] = (keptCounts[c.card_int] || 0) + 1;
            }
            const newCards = [];
            const addedCounts = {};
            for (const c of serverHand) {
                const ci = c.card_int;
                const have = (keptCounts[ci] || 0) + (addedCounts[ci] || 0);
                if (have < (serverCounts[ci] || 0)) {
                    newCards.push(c);
                    addedCounts[ci] = (addedCounts[ci] || 0) + 1;
                }
            }

            localHand = sortAscending ? [...newCards, ...kept] : [...kept, ...newCards];
        } else {
            // First time — use server order
            if (sortAscending) {
                localHand = serverHand.slice().reverse();
            } else {
                localHand = serverHand.slice();
            }
        }
    }
}

function renderHand() {
    syncLocalHand();

    const area = document.getElementById('hand-area');
    area.innerHTML = '';

    if (!localHand || localHand.length === 0) return;

    localHand.forEach((card, idx) => {
        const el = createCardElement(card, false);
        el.classList.toggle('selected', selectedCards.has(idx));
        el.setAttribute('draggable', 'true');
        el.dataset.idx = idx;

        // Click to select/deselect
        el.addEventListener('click', (e) => {
            // Ignore if this was the end of a drag
            if (el.dataset.wasDragged === 'true') {
                el.dataset.wasDragged = 'false';
                return;
            }
            if (!gameState.is_human_turn || gameState.auto_play) return;
            if (selectedCards.has(idx)) {
                selectedCards.delete(idx);
            } else {
                selectedCards.add(idx);
            }
            renderHand();
            renderActionBar();
        });

        // Drag start
        el.addEventListener('dragstart', (e) => {
            dragSrcIdx = idx;
            el.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
        });

        // Drag over (allow drop)
        el.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            el.classList.add('drag-over');
        });

        el.addEventListener('dragleave', () => {
            el.classList.remove('drag-over');
        });

        // Drop — move card from dragSrcIdx to this position
        el.addEventListener('drop', (e) => {
            e.preventDefault();
            el.classList.remove('drag-over');
            if (dragSrcIdx === null || dragSrcIdx === idx) return;

            // Move the card in localHand
            const [moved] = localHand.splice(dragSrcIdx, 1);
            localHand.splice(idx, 0, moved);

            // Remap selected cards
            selectedCards.clear();

            dragSrcIdx = null;
            renderHand();
            saveHandOrder();
        });

        el.addEventListener('dragend', () => {
            el.classList.remove('dragging');
            el.dataset.wasDragged = 'true';
            dragSrcIdx = null;
        });

        area.appendChild(el);
    });
}

function createCardElement(card, mini = false) {
    const el = document.createElement('div');
    el.className = `card suit-${card.suit}`;
    if (mini) el.classList.add('mini');

    if (card.suit === 'joker') {
        el.classList.add(card.rank === 'bj' ? 'joker-big' : 'joker-small');
    }

    // Badge: W for wild, L for level card (top-left)
    if (card.is_wild) {
        const badge = document.createElement('div');
        badge.className = 'card-badge badge-wild';
        badge.textContent = 'W';
        el.appendChild(badge);
    } else if (card.is_level) {
        const badge = document.createElement('div');
        badge.className = 'card-badge badge-level';
        badge.textContent = 'L';
        el.appendChild(badge);
    }

    const rankEl = document.createElement('div');
    rankEl.className = 'card-rank';
    if (card.display) {
        rankEl.textContent = card.display;
    } else if (card.suit === 'joker') {
        rankEl.textContent = t('joker');
    } else {
        rankEl.textContent = card.rank;
    }
    el.appendChild(rankEl);

    const suitEl = document.createElement('div');
    suitEl.className = 'card-suit';
    suitEl.textContent = card.suit_symbol;
    el.appendChild(suitEl);

    return el;
}

function renderTrick() {
    const tricks = gameState.trick_plays || [];
    const slotMap = { 0: 'trick-bottom', 1: 'trick-right', 2: 'trick-top', 3: 'trick-left' };
    // Top/bottom are horizontal (team axis), left/right are vertical (opponent axis)
    const isVertical = { 'trick-left': true, 'trick-right': true };

    // Clear all slots
    for (const id of Object.values(slotMap)) {
        document.getElementById(id).innerHTML = '';
    }

    for (const play of tricks) {
        const slotId = slotMap[play.player];
        const slot = document.getElementById(slotId);
        if (!slot) continue;

        const isLeading = !!play.is_lead;
        const entryClass = isVertical[slotId] ? 'trick-play-entry-v' : 'trick-play-entry-h';
        const entry = document.createElement('div');
        entry.className = entryClass;
        if (isLeading) entry.classList.add('trick-leading');

        const label = document.createElement('div');
        label.className = 'trick-label';
        label.textContent = playerLabel(play.player);

        const contentEl = document.createElement('div');
        if (play.is_pass) {
            contentEl.className = 'trick-pass';
            contentEl.textContent = t('pass');
        } else {
            contentEl.className = 'trick-cards';
            for (const c of play.cards) {
                contentEl.appendChild(createCardElement(c, true));
            }
        }
        // For right slot: content before label; otherwise label before content
        if (slotId === 'trick-right') {
            entry.appendChild(contentEl);
            entry.appendChild(label);
        } else {
            entry.appendChild(label);
            entry.appendChild(contentEl);
        }

        slot.appendChild(entry);
    }

    // Center message
    const msgEl = document.getElementById('center-message');
    msgEl.className = '';
    const lead = gameState.lead_player;
    const leadText = (lead !== null && lead !== undefined && gameState.phase === 'playing')
        ? `${t('leadPrefix')}: ${playerLabel(lead)}` : '';

    if (gameState.phase === 'playing' && gameState.is_human_turn && !autoPlayEnabled) {
        msgEl.innerHTML = `<div class="center-lead">${leadText}</div><div class="center-main your-turn">${t('yourTurnBig')}</div>`;
    } else if (gameState.phase === 'playing' && !gameState.is_human_turn && !autoPlayEnabled) {
        msgEl.innerHTML = `<div class="center-lead">${leadText}</div><div class="center-main">${playerLabel(gameState.current_player)} ${t('isThinking')}</div>`;
    } else if (gameState.phase === 'playing' && autoPlayEnabled) {
        msgEl.innerHTML = `<div class="center-lead">${leadText}</div><div class="center-main auto-playing">${t('autoPlaying')}</div>`;
    } else {
        msgEl.innerHTML = '';
    }
}

function renderHints() {
    const area = document.getElementById('hint-area');
    const hints = gameState.hints || [];

    if (!hintEnabled || hints.length === 0 || !gameState.is_human_turn || gameState.auto_play) {
        area.classList.add('hidden');
        return;
    }

    area.classList.remove('hidden');
    area.innerHTML = '';

    for (const hint of hints) {
        const item = document.createElement('div');
        item.className = 'hint-item';
        item.addEventListener('click', () => selectHintPlay((hint.cards || []).map(c => c.card_int)));

        // Cards
        const cardsDiv = document.createElement('div');
        cardsDiv.className = 'hint-cards';
        if (hint.type === 'pass') {
            const passEl = document.createElement('div');
            passEl.className = 'hint-pass-icon';
            passEl.textContent = t('pass');
            cardsDiv.appendChild(passEl);
        } else {
            for (const c of hint.cards) {
                cardsDiv.appendChild(createCardElement(c, true));
            }
        }
        item.appendChild(cardsDiv);

        // Type + rank
        const typeEl = document.createElement('div');
        typeEl.className = 'hint-type';
        const typeStr = tPlayType(hint.type);
        typeEl.textContent = hint.rank ? `${typeStr} ${hint.rank}` : typeStr;
        item.appendChild(typeEl);

        // Q-value
        const qEl = document.createElement('div');
        qEl.className = 'hint-q-value';
        const q = hint.q_value;
        qEl.textContent = (q !== null && q !== undefined) ? `Q: ${q.toFixed(3)}` : 'Q: --';
        item.appendChild(qEl);

        area.appendChild(item);
    }
}

function renderActionBar() {
    const isMyTurn = gameState.is_human_turn && gameState.phase === 'playing' && !autoPlayEnabled;

    // Check if pass is a legal play (it's not available when leading)
    const hasPass = gameState.legal_plays && gameState.legal_plays.some(p => p.type === 'pass');

    document.getElementById('btn-play').disabled = !isMyTurn || selectedCards.size === 0;
    document.getElementById('btn-clear').disabled = selectedCards.size === 0;
    document.getElementById('btn-pass').disabled = !isMyTurn || !hasPass;

    const hintBtn = document.getElementById('btn-hint');
    hintBtn.textContent = hintEnabled ? t('hintOn') : t('hintOff');
    hintBtn.classList.toggle('active', hintEnabled);

    const autoBtn = document.getElementById('btn-auto');
    autoBtn.textContent = autoPlayEnabled ? t('autoOn') : t('autoOff');
    autoBtn.classList.toggle('active', autoPlayEnabled);

    document.getElementById('btn-sort').textContent = sortAscending ? t('sortAsc') : t('sortDesc');
    document.getElementById('btn-play').textContent = t('play');
    document.getElementById('btn-pass').textContent = t('pass');
    document.getElementById('btn-clear').textContent = t('clear');
}

function renderResult() {
    const overlay = document.getElementById('result-overlay');
    const result = gameState.result;

    if (!result || (gameState.phase !== 'round_over' && gameState.phase !== 'game_over')) {
        overlay.classList.add('hidden');
        return;
    }

    overlay.classList.remove('hidden');

    const titleEl = document.getElementById('result-title');
    if (result.human_won) {
        titleEl.textContent = t('victory');
        titleEl.className = 'win';
    } else {
        titleEl.textContent = t('defeat');
        titleEl.className = 'lose';
    }

    const detailsEl = document.getElementById('result-details');
    const fo = result.finish_order || [];
    const orderStr = fo.map((p, i) => `#${i + 1}: ${playerLabel(p)}`).join(' | ');

    let html = `<p>${t('finishOrder')}: ${orderStr}</p>`;
    const reward = result.rewards ? result.rewards['0'] : null;
    if (reward !== null && reward !== undefined) {
        html += `<p>${t('reward')}: ${reward > 0 ? '+' : ''}${reward}</p>`;
    }

    if (result.team_levels) {
        html += `<p>${t('teamLevels')}: ${t('us')} ${result.team_levels[0]} vs ${t('them')} ${result.team_levels[1]}</p>`;
    }

    if (gameState.phase === 'game_over') {
        html += `<p class="game-over-line">${result.human_won ? t('gameWon') : t('gameLost')}</p>`;
    }

    detailsEl.innerHTML = html;

    // Button text
    const newRoundBtn = document.getElementById('btn-new-round');
    if (gameState.phase === 'game_over') {
        newRoundBtn.textContent = t('newGame');
        newRoundBtn.onclick = backToMenu;
    } else if (gameState.mode === 'full_game') {
        newRoundBtn.textContent = t('nextRound');
        newRoundBtn.onclick = newRound;
    } else {
        newRoundBtn.textContent = t('newRound');
        newRoundBtn.onclick = newRound;
    }
}

function showMessage(msg) {
    const el = document.getElementById('center-message');
    el.textContent = msg;
    setTimeout(() => {
        if (el.textContent === msg) el.textContent = '';
    }, 2000);
}

// === Title bar ===

function skipOverlay() {
    const info = document.getElementById('info-overlay');
    const result = document.getElementById('result-overlay');
    if (!info.classList.contains('hidden')) {
        // Skip round-start overlay: confirm and start
        confirmStart();
    } else if (!result.classList.contains('hidden')) {
        // Skip result overlay: trigger the primary action
        const btn = document.getElementById('btn-new-round');
        if (btn.onclick) btn.onclick();
    }
}