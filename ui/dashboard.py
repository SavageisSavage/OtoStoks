"""
Automated trading terminal dashboard HTML and client-side application.
Features 7 responsive tabs, institutional high-contrast Light & Dark themes,
and minimalist vector SVG icons. Strictly zero emojis.
"""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" type="image/png" href="/icon.png">
  <title>OtoStoks Terminal - Institutional Quantitative Execution</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root, html.dark {
      --bg-base: #07090e;
      --bg-panel: #0d1117;
      --bg-card: #131822;
      --bg-input: #0f141d;
      --bg-hover: #1a2233;
      --border-subtle: #1e2638;
      --border-strong: #2c384e;
      --text-main: #e2e8f0;
      --text-title: #ffffff;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      
      --accent-green: #10b981;
      --accent-green-bg: rgba(16, 185, 129, 0.12);
      --accent-green-border: rgba(16, 185, 129, 0.35);
      
      --accent-red: #f43f5e;
      --accent-red-bg: rgba(244, 63, 94, 0.12);
      --accent-red-border: rgba(244, 63, 94, 0.35);
      
      --accent-blue: #3b82f6;
      --accent-blue-bg: rgba(59, 130, 246, 0.15);
      --accent-blue-border: rgba(59, 130, 246, 0.4);
      
      --accent-purple: #a855f7;
      --accent-amber: #f59e0b;
      --accent-amber-bg: rgba(245, 158, 11, 0.12);
      
      --log-bg: #090c13;
      --chart-grid: rgba(255, 255, 255, 0.04);
      --chart-tick: #64748b;
      --shadow-soft: 0 2px 8px rgba(0, 0, 0, 0.4);
    }

    html.light {
      --bg-base: #f1f5f9;
      --bg-panel: #ffffff;
      --bg-card: #ffffff;
      --bg-input: #f8fafc;
      --bg-hover: #f1f5f9;
      --border-subtle: #e2e8f0;
      --border-strong: #cbd5e1;
      --text-main: #334155;
      --text-title: #0f172a;
      --text-muted: #64748b;
      --text-dim: #94a3b8;
      
      --accent-green: #059669;
      --accent-green-bg: #ecfdf5;
      --accent-green-border: #a7f3d0;
      
      --accent-red: #e11d48;
      --accent-red-bg: #fff1f2;
      --accent-red-border: #fecdd3;
      
      --accent-blue: #2563eb;
      --accent-blue-bg: #eff6ff;
      --accent-blue-border: #bfdbfe;
      
      --accent-purple: #7c3aed;
      --accent-amber: #d97706;
      --accent-amber-bg: #fffbeb;
      
      --log-bg: #f8fafc;
      --chart-grid: rgba(0, 0, 0, 0.06);
      --chart-tick: #64748b;
      --shadow-soft: 0 1px 3px rgba(0, 0, 0, 0.08);
    }

    body {
      background-color: var(--bg-base);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0;
      padding: 0;
      overflow-x: hidden;
      font-feature-settings: "cv02", "cv03", "cv04", "cv11";
      transition: background-color 0.15s ease, color 0.15s ease;
    }
    .font-mono {
      font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    .tabular {
      font-variant-numeric: tabular-nums;
    }
    .panel {
      background-color: var(--bg-panel);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      box-shadow: var(--shadow-soft);
      transition: background-color 0.15s ease, border-color 0.15s ease;
    }
    .card {
      background-color: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      box-shadow: var(--shadow-soft);
      transition: background-color 0.15s ease, border-color 0.15s ease;
    }
    .text-title {
      color: var(--text-title);
    }
    .text-muted {
      color: var(--text-muted);
    }
    .text-dim {
      color: var(--text-dim);
    }
    .btn-secondary {
      background-color: var(--bg-input);
      border: 1px solid var(--border-strong);
      color: var(--text-main);
      transition: all 0.15s ease;
    }
    .btn-secondary:hover {
      background-color: var(--bg-hover);
      color: var(--text-title);
    }
    input, select {
      background-color: var(--bg-input) !important;
      color: var(--text-title) !important;
      border: 1px solid var(--border-strong) !important;
      transition: border-color 0.15s ease, background-color 0.15s ease;
    }
    input:focus, select:focus {
      border-color: var(--accent-blue) !important;
      outline: none;
    }
    table th {
      color: var(--text-muted);
      border-bottom: 1px solid var(--border-subtle);
    }
    table td {
      border-bottom: 1px solid var(--border-subtle);
    }
    tbody tr:hover {
      background-color: var(--bg-hover);
    }
    ::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    ::-webkit-scrollbar-track {
      background: var(--bg-base);
    }
    ::-webkit-scrollbar-thumb {
      background: var(--border-strong);
      border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: var(--text-dim);
    }
    .flash-up {
      animation: flashGreen 0.75s ease-out;
    }
    .flash-down {
      animation: flashRed 0.75s ease-out;
    }
    @keyframes flashGreen {
      0% { background-color: var(--accent-green-bg); }
      100% { background-color: transparent; }
    }
    @keyframes flashRed {
      0% { background-color: var(--accent-red-bg); }
      100% { background-color: transparent; }
    }
    input[type=range] {
      -webkit-appearance: none;
      background: transparent !important;
      border: none !important;
    }
    input[type=range]:focus {
      outline: none;
    }
    input[type=range]::-webkit-slider-runnable-track {
      width: 100%;
      height: 6px;
      cursor: pointer;
      background: var(--border-strong);
      border-radius: 3px;
    }
    input[type=range]::-webkit-slider-thumb {
      height: 14px;
      width: 14px;
      border-radius: 50%;
      background: var(--accent-blue);
      cursor: pointer;
      -webkit-appearance: none;
      margin-top: -4px;
      box-shadow: 0 0 4px rgba(37, 99, 235, 0.5);
    }
    .pulse-dot {
      box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
      animation: pulseGreen 2s infinite;
    }
    @keyframes pulseGreen {
      0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
      70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
      100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    .tab-content {
      display: none;
    }
    .tab-content.active {
      display: block;
    }
    .tab-nav-btn {
      transition: all 0.15s ease-in-out;
      border-bottom: 2px solid transparent;
      color: var(--text-muted);
    }
    .tab-nav-btn:hover {
      color: var(--text-title);
      background-color: var(--bg-hover);
    }
    .tab-nav-btn.active {
      border-bottom-color: var(--accent-blue);
      color: var(--accent-blue) !important;
      font-weight: 600;
    }
    .badge-buy {
      background-color: var(--accent-green-bg);
      color: var(--accent-green);
      border: 1px solid var(--accent-green-border);
    }
    .badge-sell {
      background-color: var(--accent-red-bg);
      color: var(--accent-red);
      border: 1px solid var(--accent-red-border);
    }
    .badge-neutral {
      background-color: var(--bg-hover);
      color: var(--text-muted);
      border: 1px solid var(--border-subtle);
    }
    .badge-blue {
      background-color: var(--accent-blue-bg);
      color: var(--accent-blue);
      border: 1px solid var(--accent-blue-border);
    }
  </style>
</head>
<body class="p-2.5 sm:p-3.5 antialiased">

  <!-- ========================================================================= -->
  <!-- 1. APPLICATION TOP BAR & NAVIGATION                                       -->
  <!-- ========================================================================= -->
  <header class="panel px-4 py-2.5 mb-3">
    <div class="flex flex-wrap items-center justify-between gap-3 mb-2">
      <!-- Brand & System Status -->
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2.5">
          <img src="/icon.png" alt="OtoStoks" class="w-7 h-7 rounded border border-slate-600 bg-slate-900 object-contain shadow-sm">
          <div>
            <div class="flex items-center gap-2">
              <span class="font-bold text-sm text-title tracking-tight">OTOSTOKS TERMINAL</span>
              <span class="text-[10px] uppercase font-semibold tracking-wider px-1.5 py-0.2 rounded badge-blue">v5.0 PRO</span>
            </div>
          </div>
        </div>

        <div class="hidden sm:block h-5 w-px" style="background-color: var(--border-subtle)"></div>

        <!-- Live Bridge Status Pill -->
        <div class="flex items-center gap-2">
          <span id="connIndicator" class="w-2 h-2 rounded-full bg-amber-400 pulse-dot"></span>
          <span id="gameConnBadge" class="text-xs font-mono text-muted">GAME: AWAITING BRIDGE</span>
        </div>

        <!-- Engine Latency & Mode Badge -->
        <div class="hidden md:flex items-center gap-2 text-xs text-muted">
          <span id="latencyWrap" title="Median time from a new market frame to decisions being dispatched">
            Cycle: <strong id="latencyDisplay" class="text-title tabular">--</strong>
          </span>
          <span class="text-dim">|</span>
          <span id="modeBadge" class="px-2 py-0.5 rounded text-[11px] font-medium badge-neutral">SUGGESTION MODE</span>
        </div>
      </div>

      <!-- Right Controls: Crash Indicator, Sound, Theme Toggle, Mode Toggle -->
      <div class="flex items-center gap-2">
        <!-- BASE Crash Indicator -->
        <div id="baseCrashBanner" class="hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono" style="background-color: var(--accent-blue-bg); border: 1px solid var(--accent-blue-border); color: var(--accent-blue)">
          <span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
          <span>BASE Crash in:</span>
          <strong id="baseCrashCountdown" class="tabular">Syncing...</strong>
        </div>

        <!-- Audio Tone Toggle -->
        <button id="soundToggleBtn" onclick="toggleSound()" title="Toggle Execution Audio Tones" class="btn-secondary px-2.5 py-1.5 rounded text-xs flex items-center gap-1.5">
          <svg class="w-3.5 h-3.5 text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
          </svg>
          <span id="soundLabel" class="hidden sm:inline">Audio: ON</span>
        </button>

        <!-- Achievements Toggle -->
        <button id="achievementsToggleBtn" onclick="toggleAchievements()" title="Toggle Achievements Hunter Micro-Trades" class="btn-secondary px-2.5 py-1.5 rounded text-xs flex items-center gap-1.5">
          <span id="achieveDot" class="w-1.5 h-1.5 rounded-full bg-slate-500"></span>
          <span id="achieveText" class="hidden sm:inline">Hunter: OFF</span>
        </button>

        <!-- Theme Toggle (Light / Dark) -->
        <button id="themeToggleBtn" onclick="toggleTheme()" title="Toggle Light / Dark Mode" class="btn-secondary px-2.5 py-1.5 rounded text-xs flex items-center gap-1.5 font-medium">
          <svg id="themeIconSun" class="w-3.5 h-3.5 text-amber-500 hidden" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
          <svg id="themeIconMoon" class="w-3.5 h-3.5 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
          <span id="themeLabel" class="hidden sm:inline">Dark</span>
        </button>

        <!-- Autonomous Auto Mode Master Toggle -->
        <button id="modeToggleBtn" onclick="toggleMode()" class="px-3.5 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs shadow transition-all flex items-center gap-1.5 active:scale-95">
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          <span>Engage Auto Mode</span>
        </button>
      </div>
    </div>

    <!-- 7 CLEAN TABS NAVIGATION BAR -->
    <nav class="flex items-center gap-1 sm:gap-2 border-t pt-2 overflow-x-auto text-xs" style="border-color: var(--border-subtle)">
      <!-- 1. Main Panel -->
      <button onclick="switchTab('tab-main')" class="tab-nav-btn active px-3 py-1.5 rounded flex items-center gap-1.5" data-tab="tab-main">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>
        <span>Main Panel</span>
      </button>

      <!-- 2. News -->
      <button onclick="switchTab('tab-news')" class="tab-nav-btn px-3 py-1.5 rounded flex items-center gap-1.5" data-tab="tab-news">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/></svg>
        <span>News</span>
        <span id="newsCountBadge" class="px-1.5 py-0.2 rounded-full badge-blue text-[10px] tabular">Steam</span>
      </button>

      <!-- 3. Auto Actions -->
      <button onclick="switchTab('tab-auto')" class="tab-nav-btn px-3 py-1.5 rounded flex items-center gap-1.5" data-tab="tab-auto">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
        <span>Auto Actions</span>
        <span id="autoRulesNavCount" class="px-1.5 py-0.2 rounded-full badge-neutral text-[10px] tabular">0</span>
      </button>

      <!-- 4. Portfolio -->
      <button onclick="switchTab('tab-portfolio')" class="tab-nav-btn px-3 py-1.5 rounded flex items-center gap-1.5" data-tab="tab-portfolio">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
        <span>Portfolio</span>
      </button>

      <!-- 5. Stats & Audit -->
      <button onclick="switchTab('tab-stats')" class="tab-nav-btn px-3 py-1.5 rounded flex items-center gap-1.5" data-tab="tab-stats">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>
        <span>Stats &amp; Audit</span>
      </button>

      <!-- 6. Skins (Experimental) -->
      <button onclick="switchTab('tab-skins')" class="tab-nav-btn px-3 py-1.5 rounded flex items-center gap-1.5" data-tab="tab-skins">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.563-2.512 5.563-5.563C21.996 6.5 17.5 2 12 2Z"/></svg>
        <span>Skins</span>
        <span class="text-[9px] px-1 py-0.2 rounded badge-blue">EXP</span>
      </button>

      <!-- 7. Settings -->
      <button onclick="switchTab('tab-settings')" class="tab-nav-btn px-3 py-1.5 rounded flex items-center gap-1.5" data-tab="tab-settings">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        <span>Settings</span>
      </button>
    </nav>
  </header>

  <!-- ========================================================================= -->
  <!-- TAB 1: MAIN PANEL                                                         -->
  <!-- ========================================================================= -->
  <main id="tab-main" class="tab-content active space-y-3">
    <!-- Top Financial Overview Ribbon -->
    <section class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
      <!-- Net Worth -->
      <div class="card p-3">
        <div class="flex items-center justify-between text-xs text-muted mb-1">
          <span>Portfolio Net Worth</span>
          <span id="pnlTag" class="text-[11px] font-mono font-medium text-emerald-500">+$0.00</span>
        </div>
        <div id="netWorthDisplay" class="text-lg lg:text-xl font-bold text-title tabular">$0.00</div>
        <div class="flex items-center justify-between text-[11px] text-dim mt-1">
          <span id="ipoTag">IPO: 0</span>
          <span>Total Valuation</span>
        </div>
      </div>

      <!-- Available Cash -->
      <div class="card p-3">
        <div class="text-xs text-muted mb-1">Available Cash</div>
        <div id="cashDisplay" class="text-lg lg:text-xl font-bold text-emerald-500 tabular">$0.00</div>
        <div class="text-[11px] text-dim mt-1">Ready Reserves</div>
      </div>

      <!-- Session Realized P&L -->
      <div class="card p-3">
        <div class="flex items-center justify-between text-xs text-muted mb-1">
          <span>Session Total P&amp;L</span>
          <span id="sessionTradesCount" class="text-[11px] font-mono text-dim">0 Trades</span>
        </div>
        <div id="sessionPnlDisplay" class="text-lg lg:text-xl font-bold text-emerald-500 tabular">+$0.00</div>
        <div class="text-[11px] text-dim mt-1">Harvested Profit</div>
      </div>

      <!-- Win Rate -->
      <div class="card p-3">
        <div class="flex items-center justify-between text-xs text-muted mb-1">
          <span>Win Rate</span>
          <span id="winLossCounts" class="text-[11px] font-mono text-dim">0W - 0L</span>
        </div>
        <div id="winRateDisplay" class="text-lg lg:text-xl font-bold text-blue-500 tabular">0.0%</div>
        <div class="text-[11px] text-dim mt-1">Success Ratio</div>
      </div>

      <!-- AI Forecast Accuracy -->
      <div class="card p-3">
        <div class="flex items-center justify-between text-xs text-muted mb-1">
          <span>AI Accuracy</span>
          <span id="activePresetBadge" class="text-[10px] font-bold px-1.5 py-0.2 rounded badge-blue">TURBO</span>
        </div>
        <div id="modelAccText" class="text-lg lg:text-xl font-bold text-purple-500 tabular">Calibrating...</div>
        <div class="flex items-center justify-between text-[11px] text-dim mt-1">
          <span>Ticks: <strong id="dbTicksCount" class="text-title tabular">0</strong></span>
          <span>Retrain: <strong id="retrainCountdown" class="text-title tabular">60s</strong></span>
        </div>
      </div>

      <!-- Dividend Vault Yield -->
      <div class="card p-3">
        <div class="flex items-center justify-between text-xs text-muted mb-1">
          <span>Dividend Flow</span>
          <span id="universeCount" class="text-[11px] font-mono text-dim">0 Stocks</span>
        </div>
        <div id="divIncomeDisplay" class="text-lg lg:text-xl font-bold text-amber-500 tabular">+$0.00 / min</div>
        <div class="flex items-center justify-between text-[11px] mt-1">
          <span id="vaultStatusTag" class="text-dim">Vault: Inactive</span>
          <span id="totalDividendsDisplay" class="text-amber-500 font-mono font-medium">Harvested: $0.00</span>
        </div>
      </div>
    </section>

    <!-- Strategy Presets & Order Allocation Ribbon -->
    <section class="panel p-3">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <span class="text-xs font-bold uppercase tracking-wider text-title">Strategy Profile:</span>
          <div class="inline-flex rounded p-0.5 border" style="background-color: var(--bg-input); border-color: var(--border-subtle)">
            <button onclick="selectStrategyPreset('TURBO')" class="preset-btn px-3 py-1 rounded text-xs font-semibold bg-blue-600 text-white shadow-sm" data-preset="TURBO">TURBO SNOWBALL</button>
            <button onclick="selectStrategyPreset('GROWTH')" class="preset-btn px-3 py-1 rounded text-xs font-medium text-muted hover:text-title" data-preset="GROWTH">BALANCED GROWTH</button>
            <button onclick="selectStrategyPreset('DEFENSIVE')" class="preset-btn px-3 py-1 rounded text-xs font-medium text-muted hover:text-title" data-preset="DEFENSIVE">DEFENSIVE SHIELD</button>
            <button onclick="selectStrategyPreset('BILLIONAIRE')" class="preset-btn px-3 py-1 rounded text-xs font-medium text-amber-500 hover:text-amber-400" data-preset="BILLIONAIRE">BILLIONAIRE VAULT</button>
          </div>
        </div>

        <!-- Global Order Allocation Size Pills -->
        <div class="flex items-center gap-2">
          <span class="text-xs text-muted">Order Allocation:</span>
          <div class="inline-flex rounded p-0.5 border" style="background-color: var(--bg-input); border-color: var(--border-subtle)">
            <button onclick="setGlobalTradeSize(10)" class="size-pill px-2 py-0.5 rounded text-[11px] font-medium text-muted hover:text-title" data-size="10">10%</button>
            <button onclick="setGlobalTradeSize(25)" class="size-pill px-2 py-0.5 rounded text-[11px] font-medium text-muted hover:text-title" data-size="25">25%</button>
            <button onclick="setGlobalTradeSize(50)" class="size-pill px-2 py-0.5 rounded text-[11px] font-medium text-muted hover:text-title" data-size="50">50%</button>
            <button onclick="setGlobalTradeSize(75)" class="size-pill px-2 py-0.5 rounded text-[11px] font-medium text-muted hover:text-title" data-size="75">75%</button>
            <button onclick="setGlobalTradeSize(100)" class="size-pill px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-600 text-white" data-size="100">Max</button>
          </div>
          <input type="range" id="tradeSizeSlider" min="5" max="100" value="100" oninput="onTradeSliderChange(this.value)" class="w-20 hidden sm:block">
          <span id="tradeSizeDisplay" class="text-xs font-mono font-bold text-blue-500 tabular">100%</span>
        </div>

        <!-- Emergency Panic Liquidation -->
        <button onclick="liquidateAll()" class="px-3 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white text-xs font-medium flex items-center gap-1.5 transition-colors shadow">
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <span>Liquidate All</span>
        </button>
      </div>
    </section>

    <!-- Live Market Securities Monitor Table -->
    <section class="panel p-3.5">
      <div class="flex flex-wrap items-center justify-between gap-3 mb-2.5">
        <div class="flex items-center gap-2">
          <div class="w-2 h-2 rounded-full bg-blue-500"></div>
          <span class="font-bold text-xs uppercase tracking-wider text-title">Live Market Securities</span>
          <span class="text-[11px] text-dim font-mono">Institutional Real-Time Execution</span>
        </div>

        <!-- Universe Filters & Search -->
        <div class="flex items-center gap-2">
          <div class="inline-flex rounded p-0.5 border text-xs" style="background-color: var(--bg-input); border-color: var(--border-subtle)">
            <button onclick="setCategoryFilter('ALL')" class="cat-pill px-2.5 py-0.5 rounded text-[11px] font-semibold bg-blue-600 text-white" data-cat="ALL">ALL</button>
            <button onclick="setCategoryFilter('HOLDINGS')" class="cat-pill px-2.5 py-0.5 rounded text-[11px] font-medium text-muted hover:text-title" data-cat="HOLDINGS">HOLDINGS</button>
            <button onclick="setCategoryFilter('MEME')" class="cat-pill px-2.5 py-0.5 rounded text-[11px] font-medium text-muted hover:text-title" data-cat="MEME">VOLATILE</button>
            <button onclick="setCategoryFilter('INDEX')" class="cat-pill px-2.5 py-0.5 rounded text-[11px] font-medium text-muted hover:text-title" data-cat="INDEX">DIVIDEND</button>
          </div>

          <div class="relative">
            <input type="text" id="searchInput" placeholder="Search ticker..." oninput="onSearchInput(this.value)" class="text-xs rounded px-2.5 py-1 pl-7 w-36 sm:w-44">
            <svg class="w-3.5 h-3.5 text-muted absolute left-2 top-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          </div>
        </div>
      </div>

      <!-- Securities Table -->
      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="uppercase font-mono text-[11px]">
              <th class="py-2 px-2.5 font-medium">Security</th>
              <th class="py-2 px-2.5 font-medium">Price</th>
              <th class="py-2 px-2.5 font-medium">Trend</th>
              <th class="py-2 px-2.5 font-medium">AI Signal</th>
              <th class="py-2 px-2.5 font-medium">Confidence</th>
              <th class="py-2 px-2.5 font-medium">Forecast</th>
              <th class="py-2 px-2.5 font-medium">Position</th>
              <th class="py-2 px-2.5 font-medium">Unrealized P&amp;L</th>
              <th class="py-2 px-2.5 text-right font-medium">Execution</th>
            </tr>
          </thead>
          <tbody id="stocksTableBody" class="font-mono">
            <!-- Dynamically populated via updateDashboard() -->
          </tbody>
        </table>
      </div>
    </section>

    <!-- Technical Analysis Chart & Execution Logs Terminal -->
    <section class="grid grid-cols-1 lg:grid-cols-3 gap-3">
      <!-- Chart Panel -->
      <div class="panel p-3.5 lg:col-span-2 flex flex-col">
        <div class="flex items-center justify-between mb-2 pb-2 border-b" style="border-color: var(--border-subtle)">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-blue-500"></span>
            <span class="font-bold text-xs uppercase tracking-wider text-title">Live Technical Chart</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="inline-flex rounded p-0.5 border text-xs" style="background-color: var(--bg-input); border-color: var(--border-subtle)">
              <button id="chartViewPriceBtn" onclick="setChartMode('price')" class="px-2.5 py-0.5 rounded text-[11px] font-semibold bg-blue-600 text-white">Price ($)</button>
              <button id="chartViewCompareBtn" onclick="setChartMode('compare')" class="px-2.5 py-0.5 rounded text-[11px] font-medium text-muted hover:text-title">Compare Returns (%)</button>
            </div>
            <select id="chartStockSelect" onchange="onChartStockChange(this.value)" class="text-xs rounded px-2.5 py-1">
              <option value="ALL">All Active Universe</option>
            </select>
          </div>
        </div>
        <div class="w-full h-44 relative">
          <canvas id="marketChart"></canvas>
        </div>
      </div>

      <!-- Execution Terminal Logs -->
      <div class="panel p-3.5 flex flex-col">
        <div class="flex items-center justify-between mb-2 pb-2 border-b" style="border-color: var(--border-subtle)">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span class="font-bold text-xs uppercase tracking-wider text-title">Execution Audit Log</span>
          </div>
          <button onclick="exportTradeHistoryCSV()" title="Export Execution History to CSV" class="btn-secondary px-2 py-0.5 rounded text-[11px] font-medium flex items-center gap-1">
            <svg class="w-3 h-3 text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            <span>Export CSV</span>
          </button>
        </div>
        <div id="logsContainer" class="rounded p-2.5 flex-1 h-44 overflow-y-auto font-mono text-[11px] space-y-1 border" style="background-color: var(--log-bg); border-color: var(--border-subtle)">
          <div class="text-dim italic">Waiting for market orders and signals...</div>
        </div>
      </div>
    </section>
  </main>

  <!-- ========================================================================= -->
  <!-- TAB 2: NEWS & GAME UPDATES                                                -->
  <!-- ========================================================================= -->
  <section id="tab-news" class="tab-content space-y-3">
    <!-- Scheduled Resets & Arbitrage Banner -->
    <div id="scheduledEventsRibbon" class="panel px-3.5 py-2.5" style="background-color: var(--accent-amber-bg); border: 1px solid var(--accent-amber)">
      <div class="flex items-center justify-between mb-1">
        <div class="flex items-center gap-2">
          <div class="w-2 h-2 rounded-full bg-amber-500 pulse-dot"></div>
          <span class="text-xs font-bold uppercase tracking-wider text-title">Scheduled Resets &amp; Price Arbitrage:</span>
        </div>
        <span class="text-[10px] text-dim font-mono">Predictable Market Cycles</span>
      </div>
      <div id="scheduledEventsList" class="flex items-center gap-2 flex-wrap text-xs font-mono mt-1.5">
        <div class="text-muted italic">No price reset anomalies scheduled in next 10 minutes.</div>
      </div>
    </div>

    <!-- Official Steam Updates Header -->
    <div class="panel p-3.5">
      <div class="flex items-center justify-between mb-3 pb-2 border-b" style="border-color: var(--border-subtle)">
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/></svg>
          <span class="font-bold text-sm text-title">Official Screen Stocks Announcements &amp; Patch Notes</span>
          <span class="text-[10px] px-1.5 py-0.2 rounded badge-neutral font-mono">AppID: 4356780</span>
        </div>
        <div class="flex items-center gap-2">
          <button onclick="fetchSteamNews(true)" class="btn-secondary px-2.5 py-1 rounded text-xs flex items-center gap-1.5">
            <svg class="w-3 h-3 text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
            <span>Refresh News</span>
          </button>
          <a href="https://store.steampowered.com/news/app/4356780" target="_blank" class="px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-xs text-white font-medium flex items-center gap-1 shadow">
            <span>View on Steam</span>
            <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
          </a>
        </div>
      </div>

      <!-- News Cards Grid -->
      <div id="steamNewsContainer" class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div class="p-4 text-center text-muted italic">Fetching official patch notes and announcements from Steam...</div>
      </div>
    </div>
  </section>

  <!-- ========================================================================= -->
  <!-- TAB 3: AUTO ACTIONS (INFINITE CONDITIONAL RULES - ZERO COOLDOWN)           -->
  <!-- ========================================================================= -->
  <section id="tab-auto" class="tab-content space-y-3">
    <!-- Trigger Builder Form Card -->
    <div class="panel p-4">
      <div class="flex items-center justify-between pb-2 border-b mb-3" style="border-color: var(--border-subtle)">
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4 text-amber-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          <span class="font-bold text-sm text-title">Create Zero-Cooldown Conditional Action Rule</span>
        </div>
        <span class="text-xs text-emerald-500 font-mono">Executes Instantly &bull; Infinite Rules Supported</span>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-5 gap-2.5 mb-3 text-xs">
        <div>
          <label class="text-[10px] text-muted uppercase font-semibold">Stock Ticker</label>
          <input type="text" id="arStockInput" placeholder="$PLAIN" class="w-full rounded px-2.5 py-1.5 font-mono uppercase mt-1">
        </div>
        <div>
          <label class="text-[10px] text-muted uppercase font-semibold">Order Action</label>
          <select id="arActionSelect" class="w-full rounded px-2 py-1.5 font-mono mt-1">
            <option value="buy">BUY (Long)</option>
            <option value="sell">SELL</option>
            <option value="short">SHORT</option>
            <option value="cover">COVER</option>
            <option value="close">CLOSE ALL</option>
          </select>
        </div>
        <div>
          <label class="text-[10px] text-muted uppercase font-semibold">Condition</label>
          <select id="arWhenSelect" class="w-full rounded px-2 py-1.5 mt-1">
            <option value="below">Price Below (&le;)</option>
            <option value="above">Price Above (&ge;)</option>
          </select>
        </div>
        <div>
          <label class="text-[10px] text-muted uppercase font-semibold">Target Price ($)</label>
          <input type="number" id="arPriceInput" step="0.01" placeholder="400.00" class="w-full rounded px-2.5 py-1.5 font-mono mt-1">
        </div>
        <div>
          <label class="text-[10px] text-muted uppercase font-semibold">Order Size</label>
          <div class="inline-flex rounded p-0.5 border w-full mt-1" style="background-color: var(--bg-input); border-color: var(--border-subtle)">
            <button type="button" onclick="setArSize(25)" class="ar-size-pill flex-1 py-1 rounded text-[11px] font-medium text-muted" data-size="25">25%</button>
            <button type="button" onclick="setArSize(50)" class="ar-size-pill flex-1 py-1 rounded text-[11px] font-medium text-muted" data-size="50">50%</button>
            <button type="button" onclick="setArSize(100)" class="ar-size-pill flex-1 py-1 rounded text-[11px] font-semibold bg-blue-600 text-white" data-size="100">100%</button>
          </div>
        </div>
      </div>

      <div class="flex items-center justify-between pt-1">
        <label class="flex items-center gap-2 text-xs text-muted cursor-pointer">
          <input type="checkbox" id="arRepeatCheck" class="rounded">
          <span>Repeat continuously without cooldown (re-arm after execution)</span>
        </label>
        <button onclick="addAutoActionRule()" class="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs rounded transition-colors shadow flex items-center gap-1.5">
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          <span>Arm Action Rule</span>
        </button>
      </div>
    </div>

    <!-- Active Rules Table -->
    <div class="panel p-4">
      <div class="flex items-center justify-between pb-2 border-b mb-2" style="border-color: var(--border-subtle)">
        <div class="flex items-center gap-2">
          <span class="font-bold text-xs uppercase tracking-wider text-title">Active Action Rules</span>
          <span class="text-[11px] text-dim font-mono">(<span id="autoRulesCount">0</span> rules running)</span>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs font-mono">
          <thead>
            <tr class="uppercase text-[11px]">
              <th class="py-2 px-2.5">Security</th>
              <th class="py-2 px-2.5">Action</th>
              <th class="py-2 px-2.5">Trigger Condition</th>
              <th class="py-2 px-2.5">Target Price</th>
              <th class="py-2 px-2.5">Allocation</th>
              <th class="py-2 px-2.5">Repeat</th>
              <th class="py-2 px-2.5 text-right">Controls</th>
            </tr>
          </thead>
          <tbody id="autoRulesTableBody">
            <tr><td colspan="7" class="py-3 text-center text-dim italic">No custom auto actions configured. Arm one above to begin!</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- ========================================================================= -->
  <!-- TAB 4: PORTFOLIO & CAPITAL ALLOCATION                                      -->
  <!-- ========================================================================= -->
  <section id="tab-portfolio" class="tab-content space-y-3">
    <!-- Net Worth & Breakdown Ribbon -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
      <div class="card p-3.5">
        <div class="text-xs text-muted mb-1">Total Net Worth</div>
        <div id="pfNetWorth" class="text-xl font-bold text-title tabular">$0.00</div>
        <div class="text-[11px] text-dim mt-1">Full Portfolio Value</div>
      </div>
      <div class="card p-3.5">
        <div class="text-xs text-muted mb-1">Usable Ready Cash</div>
        <div id="pfCash" class="text-xl font-bold text-emerald-500 tabular">$0.00</div>
        <div class="text-[11px] text-dim mt-1">Liquid Reserves</div>
      </div>
      <div class="card p-3.5">
        <div class="text-xs text-muted mb-1">Capital in Longs</div>
        <div id="pfLongVal" class="text-xl font-bold text-blue-500 tabular">$0.00</div>
        <div class="text-[11px] text-dim mt-1">Bullish Holdings</div>
      </div>
      <div class="card p-3.5">
        <div class="text-xs text-muted mb-1">Capital in Shorts</div>
        <div id="pfShortVal" class="text-xl font-bold text-rose-500 tabular">$0.00</div>
        <div class="text-[11px] text-dim mt-1">Bearish Borrowed Positions</div>
      </div>
    </div>

    <!-- Asset Allocation Bar -->
    <div class="panel p-3.5">
      <div class="flex items-center justify-between text-xs mb-2">
        <span class="font-bold uppercase tracking-wider text-title">Capital Allocation Distribution</span>
        <div class="flex items-center gap-3 text-[11px] font-mono">
          <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded bg-emerald-500"></span> Cash: <strong id="pfCashPct">100%</strong></span>
          <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded bg-blue-500"></span> Longs: <strong id="pfLongPct">0%</strong></span>
          <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 rounded bg-rose-500"></span> Shorts: <strong id="pfShortPct">0%</strong></span>
        </div>
      </div>
      <div class="w-full h-3 rounded overflow-hidden flex" style="background-color: var(--border-subtle)">
        <div id="pfBarCash" style="width: 100%" class="h-full bg-emerald-500 transition-all"></div>
        <div id="pfBarLong" style="width: 0%" class="h-full bg-blue-500 transition-all"></div>
        <div id="pfBarShort" style="width: 0%" class="h-full bg-rose-500 transition-all"></div>
      </div>
    </div>

    <!-- Active Holdings Table -->
    <div class="panel p-3.5">
      <div class="flex items-center justify-between pb-2 border-b mb-2" style="border-color: var(--border-subtle)">
        <span class="font-bold text-xs uppercase tracking-wider text-title">Active Portfolio Positions</span>
        <button onclick="refreshPortfolio()" class="btn-secondary px-2 py-0.5 rounded text-[11px]">Refresh</button>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs font-mono">
          <thead>
            <tr class="uppercase text-[11px]">
              <th class="py-2 px-2.5">Security</th>
              <th class="py-2 px-2.5">Side</th>
              <th class="py-2 px-2.5">Shares</th>
              <th class="py-2 px-2.5">Avg Entry</th>
              <th class="py-2 px-2.5">Current Price</th>
              <th class="py-2 px-2.5">Total Value</th>
              <th class="py-2 px-2.5">Unrealized %</th>
              <th class="py-2 px-2.5">Dollar Gain</th>
              <th class="py-2 px-2.5 text-right">Close</th>
            </tr>
          </thead>
          <tbody id="portfolioTableBody">
            <tr><td colspan="9" class="py-3 text-center text-dim italic">No open positions. 100% Cash Ready.</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- ========================================================================= -->
  <!-- TAB 5: STATS & AUDIT (7-DAY NET WORTH & FUMBLES ANALYSIS)                  -->
  <!-- ========================================================================= -->
  <section id="tab-stats" class="tab-content space-y-3">
    <!-- Performance Summary Cards -->
    <div class="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
      <div class="card p-3">
        <div class="text-xs text-muted mb-1">Win Rate</div>
        <div id="statsWinRate" class="text-xl font-bold text-blue-500 tabular">0.0%</div>
        <div id="statsWinCount" class="text-[11px] text-dim mt-1">0 wins / 0 closed</div>
      </div>
      <div class="card p-3">
        <div class="text-xs text-muted mb-1">Profit Factor</div>
        <div id="statsProfitFactor" class="text-xl font-bold text-emerald-500 tabular">1.00</div>
        <div class="text-[11px] text-dim mt-1">Win/Loss Ratio</div>
      </div>
      <div class="card p-3">
        <div class="text-xs text-muted mb-1">Total Profit Won</div>
        <div id="statsTotalWon" class="text-xl font-bold text-emerald-500 tabular">+$0.00</div>
        <div class="text-[11px] text-dim mt-1">Cumulative Harvests</div>
      </div>
      <div class="card p-3">
        <div class="text-xs text-muted mb-1">Total Lost (Fumbles)</div>
        <div id="statsTotalLost" class="text-xl font-bold text-rose-500 tabular">-$0.00</div>
        <div class="text-[11px] text-dim mt-1">Drawdowns Stopped</div>
      </div>
      <div class="card p-3 flex flex-col justify-between">
        <div class="text-xs text-muted">Institutional Audit</div>
        <button onclick="exportAllCSV()" class="w-full py-1.5 px-2 bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs rounded transition-colors flex items-center justify-center gap-1.5 shadow">
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          <span>Export Everything CSV</span>
        </button>
      </div>
    </div>

    <!-- Past 7 Days Net Worth Ledger -->
    <div class="panel p-3.5">
      <div class="flex items-center justify-between pb-2 border-b mb-2" style="border-color: var(--border-subtle)">
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>
          <span class="font-bold text-xs uppercase tracking-wider text-title">Past 7 Days Net Worth Performance</span>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs font-mono">
          <thead>
            <tr class="uppercase text-[11px]">
              <th class="py-2 px-2.5">Date</th>
              <th class="py-2 px-2.5">Starting Val</th>
              <th class="py-2 px-2.5">Day High</th>
              <th class="py-2 px-2.5">Day Low</th>
              <th class="py-2 px-2.5">Current Val</th>
              <th class="py-2 px-2.5">Net Day Gain</th>
              <th class="py-2 px-2.5 text-right">% Change</th>
            </tr>
          </thead>
          <tbody id="dailyStatsTableBody">
            <tr><td colspan="7" class="py-3 text-center text-dim italic">No historical daily records yet. Valuations log automatically.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Best Investments vs Fumbles Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <!-- Best Investments -->
      <div class="panel p-3.5">
        <div class="flex items-center gap-2 pb-2 border-b mb-2" style="border-color: var(--border-subtle)">
          <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
          <span class="font-bold text-xs uppercase tracking-wider text-emerald-500">Top 10 Best Investments</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs font-mono">
            <thead>
              <tr class="text-[10px] uppercase">
                <th class="py-1 px-1.5">Time</th>
                <th class="py-1 px-1.5">Ticker</th>
                <th class="py-1 px-1.5">Price</th>
                <th class="py-1 px-1.5">Gain %</th>
                <th class="py-1 px-1.5 text-right">Profit ($)</th>
              </tr>
            </thead>
            <tbody id="topWinsTableBody">
              <tr><td colspan="5" class="py-2 text-center text-dim italic">No closed winning trades recorded yet.</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Fumbles & Biggest Losses -->
      <div class="panel p-3.5">
        <div class="flex items-center gap-2 pb-2 border-b mb-2" style="border-color: var(--border-subtle)">
          <span class="w-2 h-2 rounded-full bg-rose-500"></span>
          <span class="font-bold text-xs uppercase tracking-wider text-rose-500">Top 10 Fumbles (Biggest Losses / Missed Exits)</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs font-mono">
            <thead>
              <tr class="text-[10px] uppercase">
                <th class="py-1 px-1.5">Time</th>
                <th class="py-1 px-1.5">Ticker</th>
                <th class="py-1 px-1.5">Price</th>
                <th class="py-1 px-1.5">Loss %</th>
                <th class="py-1 px-1.5 text-right">Loss ($)</th>
              </tr>
            </thead>
            <tbody id="fumblesTableBody">
              <tr><td colspan="5" class="py-2 text-center text-dim italic">No closed loss fumbles recorded. Risk limits working!</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>

  <!-- ========================================================================= -->
  <!-- TAB 6: SKINS (EXPERIMENTAL WALLPAPER MANAGER FOR SCREEN STOCKS)           -->
  <!-- ========================================================================= -->
  <section id="tab-skins" class="tab-content space-y-3">
    <!-- Upload New Skin Card -->
    <div class="panel p-4">
      <div class="flex items-center justify-between pb-2 border-b mb-3" style="border-color: var(--border-subtle)">
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4 text-purple-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7"/><line x1="16" y1="5" x2="22" y2="5"/><line x1="19" y1="2" x2="19" y2="8"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>
          <span class="font-bold text-sm text-title">Upload Custom Wallpaper or Skin for Screen Stocks</span>
        </div>
        <span class="text-xs text-purple-500 font-mono">Supports PNG &amp; JPG &bull; Auto Mod Injection</span>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
        <div class="sm:col-span-2">
          <label class="text-[10px] text-muted uppercase font-semibold">Skin Image File (PNG or JPG)</label>
          <input type="file" id="skinFileInput" accept=".png,.jpg,.jpeg" class="w-full rounded px-2.5 py-1.5 mt-1">
        </div>
        <div>
          <label class="text-[10px] text-muted uppercase font-semibold">Skin Display Name</label>
          <input type="text" id="skinNameInput" placeholder="Cyber Neon" class="w-full rounded px-2.5 py-1.5 mt-1">
        </div>
        <div class="flex items-end">
          <button onclick="uploadSkin()" class="w-full py-2 px-3 bg-purple-600 hover:bg-purple-500 text-white font-medium text-xs rounded transition-colors shadow flex items-center justify-center gap-1.5">
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            <span>Install &amp; Save Skin</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Installed Skins Grid -->
    <div class="panel p-4">
      <div class="flex items-center justify-between pb-2 border-b mb-3" style="border-color: var(--border-subtle)">
        <div class="flex items-center gap-2">
          <span class="font-bold text-xs uppercase tracking-wider text-title">Installed Screen Stocks Skins</span>
          <span class="text-[11px] text-dim font-mono">(Located in mods/skins/)</span>
        </div>
        <button onclick="fetchSkins()" class="btn-secondary px-2.5 py-0.5 rounded text-[11px]">Refresh Skins</button>
      </div>

      <div id="skinsGrid" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        <div class="col-span-full py-4 text-center text-dim italic">Scanning installed skins...</div>
      </div>
    </div>
  </section>

  <!-- ========================================================================= -->
  <!-- TAB 7: SETTINGS & IN-GAME CONTROLS                                        -->
  <!-- ========================================================================= -->
  <section id="tab-settings" class="tab-content space-y-3">
    <!-- Bot Quantitative Settings -->
    <div class="panel p-4">
      <div class="flex items-center justify-between pb-2 border-b mb-3" style="border-color: var(--border-subtle)">
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          <span class="font-bold text-sm text-title">OtoStoks Bot Execution &amp; Risk Parameters</span>
        </div>
        <button onclick="saveSettings()" class="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs rounded transition-colors shadow">
          Save Bot Settings
        </button>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <!-- Stop Loss -->
        <div class="card p-2.5">
          <div class="flex items-center justify-between text-xs mb-1">
            <span class="font-medium text-title">Trailing Stop-Loss</span>
            <button id="stopLossToggleBtn" onclick="toggleStopLoss()" class="text-[11px] font-mono px-1.5 py-0.2 rounded badge-buy font-semibold">ACTIVE</button>
          </div>
          <div class="flex items-center gap-2 mt-2">
            <input type="range" id="stopLossSlider" min="2" max="30" step="1" value="15" oninput="onStopLossSliderChange(this.value)" class="w-full">
            <span id="stopLossVal" class="text-xs font-mono text-rose-500 font-bold tabular w-10 text-right">15%</span>
          </div>
        </div>

        <!-- Take Profit -->
        <div class="card p-2.5">
          <div class="flex items-center justify-between text-xs mb-1">
            <span class="font-medium text-title">Take-Profit Threshold</span>
            <button id="minProfitToggleBtn" onclick="toggleMinProfit()" class="text-[11px] font-mono px-1.5 py-0.2 rounded badge-buy font-semibold">ACTIVE</button>
          </div>
          <div class="flex items-center gap-2 mt-2">
            <input type="range" id="minProfitSlider" min="1" max="25" step="1" value="6" oninput="onMinProfitSliderChange(this.value)" class="w-full">
            <span id="minProfitVal" class="text-xs font-mono text-emerald-500 font-bold tabular w-10 text-right">6%</span>
          </div>
        </div>

        <!-- Tech Target Multiplier -->
        <div class="card p-2.5">
          <div class="flex items-center justify-between text-xs mb-1">
            <span class="font-medium text-title">$TECH Target Multiplier</span>
            <span class="text-[11px] text-dim font-mono">Special Profile</span>
          </div>
          <div class="flex items-center gap-2 mt-2">
            <input type="range" id="techTargetSlider" min="10" max="40" step="1" value="16" oninput="onTechSliderChange(this.value)" class="w-full">
            <span id="techTargetVal" class="text-xs font-mono text-purple-500 font-bold tabular w-10 text-right">$16</span>
          </div>
        </div>

        <!-- Max Concurrent Positions & Auto Timer -->
        <div class="card p-2.5 flex flex-col justify-between">
          <div class="flex items-center justify-between text-xs">
            <span class="font-medium text-title">Concurrent Positions</span>
            <span id="maxPosVal" class="text-xs font-mono text-blue-500 font-bold tabular">5</span>
          </div>
          <input type="range" id="maxPosSlider" min="1" max="15" value="5" oninput="onMaxPosChange(this.value)" class="w-full my-1">
          <div class="flex items-center justify-between text-[11px] text-muted">
            <span>Auto Timer: <span id="autoTimeRemaining" class="text-title font-mono tabular">Unlimited</span></span>
            <input type="number" id="autoTimeLimit" min="0" max="48" step="0.5" value="0" onchange="saveSettings()" class="w-12 text-[11px] rounded px-1 text-center" title="Hours (0 = unlimited)">
          </div>
        </div>
      </div>

      <!-- Background Market Tracking Opt-In & Desktop Notifications -->
      <div class="card p-3 mt-3" style="background-color: var(--bg-input)">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <label class="flex items-center gap-2.5 cursor-pointer">
            <input type="checkbox" id="bgTrackingCheck" onchange="saveSettings()" class="rounded">
            <div>
              <span class="font-semibold text-title">Opt-in Background Market Tracking</span>
              <p class="text-[11px] text-muted mt-0.5">Keep tracking market movements and alpha signals in background even after closing the window.</p>
            </div>
          </label>
          <label class="flex items-center gap-2.5 cursor-pointer">
            <input type="checkbox" id="closeToTrayCheck" onchange="saveSettings()" class="rounded" checked>
            <div>
              <span class="font-semibold text-title">Native Desktop Notifications</span>
              <p class="text-[11px] text-muted mt-0.5">Show native OS notification when window is closed reminding you that the background tracker is active.</p>
            </div>
          </label>
        </div>
      </div>
    </div>

    <!-- Direct Screen Stocks In-Game Settings Editor -->
    <div class="panel p-4">
      <div class="flex items-center justify-between pb-2 border-b mb-3" style="border-color: var(--border-subtle)">
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>
          <span class="font-bold text-sm text-title">Direct In-Game Settings (thesmallshort_online_settings.sav)</span>
        </div>
        <button onclick="saveInGameSettings()" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs rounded transition-colors shadow">
          Apply to Screen Stocks Save
        </button>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
        <!-- SFX Volume -->
        <div class="card p-2.5">
          <div class="flex items-center justify-between mb-1">
            <span class="font-medium text-title">SFX Volume</span>
            <span id="igSfxVal" class="font-mono text-emerald-500 font-bold tabular">100%</span>
          </div>
          <input type="range" id="igSfxSlider" min="0" max="1" step="0.05" value="1" oninput="document.getElementById('igSfxVal').innerText = Math.round(this.value*100) + '%'" class="w-full mt-2">
        </div>

        <!-- Music Volume -->
        <div class="card p-2.5">
          <div class="flex items-center justify-between mb-1">
            <span class="font-medium text-title">Music Volume</span>
            <span id="igMusicVal" class="font-mono text-emerald-500 font-bold tabular">100%</span>
          </div>
          <input type="range" id="igMusicSlider" min="0" max="1" step="0.05" value="1" oninput="document.getElementById('igMusicVal').innerText = Math.round(this.value*100) + '%'" class="w-full mt-2">
        </div>

        <!-- Unfocused Opacity -->
        <div class="card p-2.5">
          <div class="flex items-center justify-between mb-1">
            <span class="font-medium text-title">Unfocused Window Opacity</span>
            <span id="igOpacityVal" class="font-mono text-blue-500 font-bold tabular">100%</span>
          </div>
          <input type="range" id="igOpacitySlider" min="20" max="100" step="5" value="100" oninput="document.getElementById('igOpacityVal').innerText = this.value + '%'" class="w-full mt-2">
        </div>

        <!-- Audio Muted -->
        <div class="card p-2.5 flex items-center justify-between">
          <span class="text-title">Audio Muted</span>
          <input type="checkbox" id="igMutedCheck" class="rounded">
        </div>

        <!-- Screen Shake -->
        <div class="card p-2.5 flex items-center justify-between">
          <span class="text-title">Screen Shake</span>
          <input type="checkbox" id="igShakeCheck" class="rounded" checked>
        </div>

        <!-- Frame Rate Limit -->
        <div class="card p-2.5 flex items-center justify-between">
          <span class="text-title">Frame Rate Limit</span>
          <select id="igFramerateSelect" class="rounded px-2 py-1 text-xs font-mono">
            <option value="0">30 FPS</option>
            <option value="1">60 FPS</option>
            <option value="2">120 FPS</option>
            <option value="3" selected>Unlimited</option>
          </select>
        </div>

        <!-- Scientific Notation -->
        <div class="card p-2.5 flex items-center justify-between">
          <span class="text-title">Scientific Notation</span>
          <input type="checkbox" id="igScientificCheck" class="rounded">
        </div>

        <!-- Advanced Mode -->
        <div class="card p-2.5 flex items-center justify-between">
          <span class="text-title">Advanced Mode</span>
          <input type="checkbox" id="igAdvancedCheck" class="rounded">
        </div>

        <!-- Fullscreen -->
        <div class="card p-2.5 flex items-center justify-between">
          <span class="text-title">Fullscreen</span>
          <input type="checkbox" id="igFullscreenCheck" class="rounded">
        </div>
      </div>
    </div>
  </section>

  <!-- Toast Notification Container -->
  <div id="toastContainer" class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"></div>

  <!-- ========================================================================= -->
  <!-- JAVASCRIPT APPLICATION CORE                                               -->
  <!-- ========================================================================= -->
  <script>
    let ws = null;
    let chart = null;
    let lastRenderedStocks = [];
    let lastHistoryData = null;
    let currentCategoryFilter = 'ALL';
    let currentSearchTerm = '';
    let currentChartTicker = 'ALL';
    let globalTradeSizePct = 100;
    let isSoundEnabled = true;
    let chartMode = 'price';
    let currentArSizePct = 100;
    let currentTheme = localStorage.getItem('otostoks_theme') || 'dark';

    const audioCtx = (typeof AudioContext !== 'undefined' || typeof webkitAudioContext !== 'undefined')
      ? new (window.AudioContext || window.webkitAudioContext)()
      : null;

    function applyTheme(theme) {
      currentTheme = theme;
      localStorage.setItem('otostoks_theme', theme);
      const root = document.documentElement;
      const sun = document.getElementById('themeIconSun');
      const moon = document.getElementById('themeIconMoon');
      const lbl = document.getElementById('themeLabel');

      if (theme === 'light') {
        root.classList.remove('dark');
        root.classList.add('light');
        if (sun) sun.classList.remove('hidden');
        if (moon) moon.classList.add('hidden');
        if (lbl) lbl.innerText = 'Light';
      } else {
        root.classList.remove('light');
        root.classList.add('dark');
        if (sun) sun.classList.add('hidden');
        if (moon) moon.classList.remove('hidden');
        if (lbl) lbl.innerText = 'Dark';
      }

      // Update Chart Colors for Theme
      if (chart) {
        const isLight = (theme === 'light');
        const gridCol = isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.04)';
        const textCol = isLight ? '#475569' : '#94a3b8';
        if (chart.options.scales.x) {
          chart.options.scales.x.grid.color = gridCol;
          chart.options.scales.x.ticks.color = textCol;
        }
        if (chart.options.scales.y) {
          chart.options.scales.y.grid.color = gridCol;
          chart.options.scales.y.ticks.color = textCol;
        }
        if (chart.options.plugins.legend) {
          chart.options.plugins.legend.labels.color = textCol;
        }
        chart.update('none');
      }
    }

    function toggleTheme() {
      applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
      showTradeToast(`Switched to ${currentTheme.toUpperCase()} theme`, 'info');
      saveSettings();
    }

    function switchTab(tabId) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-nav-btn').forEach(el => el.classList.remove('active'));

      const targetTab = document.getElementById(tabId);
      if (targetTab) targetTab.classList.add('active');

      const btn = document.querySelector(`.tab-nav-btn[data-tab="${tabId}"]`);
      if (btn) btn.classList.add('active');

      if (tabId === 'tab-news') fetchSteamNews();
      else if (tabId === 'tab-portfolio') refreshPortfolio();
      else if (tabId === 'tab-stats') fetchPerformanceStats();
      else if (tabId === 'tab-skins') fetchSkins();
      else if (tabId === 'tab-settings') fetchInGameSettings();
    }

    function playAudioTone(freq = 600, duration = 0.1, type = 'sine') {
      if (!isSoundEnabled || !audioCtx) return;
      try {
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = type;
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + duration);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + duration);
      } catch (e) {}
    }

    function toggleSound() {
      isSoundEnabled = !isSoundEnabled;
      const lbl = document.getElementById('soundLabel');
      if (lbl) lbl.innerText = `Audio: ${isSoundEnabled ? 'ON' : 'OFF'}`;
      showTradeToast(`Audio feedback ${isSoundEnabled ? 'enabled' : 'disabled'}`, 'info');
    }

    function renderSparklineSVG(pts, isUp = true) {
      if (!pts || pts.length < 2) return '';
      const min = Math.min(...pts);
      const max = Math.max(...pts);
      const range = (max - min) === 0 ? 1 : (max - min);
      const w = 58;
      const h = 18;
      const coords = pts.map((val, idx) => {
        const x = (idx / (pts.length - 1)) * w;
        const y = h - ((val - min) / range) * (h - 4) - 2;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ');

      const strokeCol = isUp ? '#10b981' : '#f43f5e';
      return `<svg width="${w}" height="${h}" class="inline-block"><polyline fill="none" stroke="${strokeCol}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" points="${coords}"/></svg>`;
    }

    function getProfileBadge(ticker, name) {
      const t = String(ticker || '').toUpperCase().replace('$', '');
      const n = String(name || '').toUpperCase().replace('$', '');
      if (t === 'BANK' || n === 'BANK') return '<span class="text-[10px] px-1 py-0.2 rounded font-bold" style="background-color: var(--accent-amber-bg); color: var(--accent-amber); border: 1px solid var(--accent-amber)">CASH VAULT</span>';
      if (t === 'TECH' || n === 'TECH') return '<span class="text-[10px] px-1 py-0.2 rounded font-bold" style="background-color: rgba(168, 85, 247, 0.15); color: var(--accent-purple); border: 1px solid var(--accent-purple)">EXPONENT</span>';
      if (t === 'PUMP' || n === 'PUMP') return '<span class="text-[10px] px-1 py-0.2 rounded font-bold badge-buy">PARABOLIC</span>';
      if (t === 'DUMP' || n === 'DUMP') return '<span class="text-[10px] px-1 py-0.2 rounded font-bold badge-sell">MEAN REV</span>';
      if (t === 'WAVE' || n === 'WAVE') return '<span class="text-[10px] px-1 py-0.2 rounded font-bold badge-blue">HARMONIC</span>';
      if (t === 'PLAIN' || t === 'BASE' || n === 'BASE') return '<span class="text-[10px] px-1 py-0.2 rounded font-bold badge-blue">CRASH 00:30</span>';
      if (t === 'STEP') return '<span class="text-[10px] px-1 py-0.2 rounded font-bold badge-buy">DIVIDEND</span>';
      return '<span class="text-[10px] px-1 py-0.2 rounded badge-neutral">ALPHA</span>';
    }

    function onTradeSliderChange(val) {
      globalTradeSizePct = parseInt(val, 10);
      document.getElementById('tradeSizeDisplay').innerText = `${globalTradeSizePct}%`;
      document.querySelectorAll('.size-pill').forEach(btn => {
        const btnVal = parseInt(btn.dataset.size, 10);
        if (btnVal === globalTradeSizePct) {
          btn.className = 'size-pill px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-600 text-white';
        } else {
          btn.className = 'size-pill px-2 py-0.5 rounded text-[11px] font-medium text-muted hover:text-title';
        }
      });
    }

    function setGlobalTradeSize(pct) {
      const slider = document.getElementById('tradeSizeSlider');
      if (slider) slider.value = pct;
      onTradeSliderChange(pct);
    }

    function selectStrategyPreset(presetName) {
      fetch('/api/preset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset: presetName })
      })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          document.querySelectorAll('.preset-btn').forEach(b => {
            if (b.dataset.preset === presetName) {
              b.className = 'preset-btn px-3 py-1 rounded text-xs font-semibold bg-blue-600 text-white shadow-sm';
            } else {
              b.className = 'preset-btn px-3 py-1 rounded text-xs font-medium text-muted hover:text-title';
            }
          });
          const badge = document.getElementById('activePresetBadge');
          if (badge) badge.innerText = presetName;
          showTradeToast(`Activated preset: ${presetName}`, 'info');
        }
      })
      .catch(err => showTradeToast(`Failed setting preset: ${err}`, 'error'));
    }

    function exportTradeHistoryCSV() {
      window.location.href = '/api/export_trades';
    }

    function exportAllCSV() {
      window.location.href = '/api/export_all_csv';
    }

    function setCategoryFilter(cat) {
      currentCategoryFilter = cat;
      document.querySelectorAll('.cat-pill').forEach(btn => {
        if (btn.dataset.cat === cat) {
          btn.className = 'cat-pill px-2.5 py-0.5 rounded text-[11px] font-semibold bg-blue-600 text-white';
        } else {
          btn.className = 'cat-pill px-2.5 py-0.5 rounded text-[11px] font-medium text-muted hover:text-title';
        }
      });
      applyTableFilter();
    }

    function onSearchInput(val) {
      currentSearchTerm = (val || '').trim().toUpperCase();
      applyTableFilter();
    }

    function applyTableFilter() {
      const rows = document.querySelectorAll('#stocksTableBody tr');
      rows.forEach(tr => {
        const ticker = tr.dataset.ticker || '';
        const hasPos = (tr.dataset.hasHolding === 'true');
        const isMeme = ['PUMP', 'DUMP', 'WAVE', 'QUIK', 'TECH'].some(k => ticker.includes(k));
        const isIndex = ['BANK', 'STEP', 'IDXA', 'IDXB'].some(k => ticker.includes(k));

        let matchesCat = true;
        if (currentCategoryFilter === 'HOLDINGS') matchesCat = hasPos;
        else if (currentCategoryFilter === 'MEME') matchesCat = isMeme;
        else if (currentCategoryFilter === 'INDEX') matchesCat = isIndex;

        let matchesSearch = true;
        if (currentSearchTerm) {
          matchesSearch = ticker.includes(currentSearchTerm);
        }

        tr.style.display = (matchesCat && matchesSearch) ? '' : 'none';
      });
    }

    function executeStockAction(ticker, action) {
      const pct = globalTradeSizePct;
      fetch('/api/trade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: ticker,
          action: action,
          pct: pct,
          is_max: (pct >= 100 || action === 'close')
        })
      })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          playAudioTone(action === 'buy' ? 750 : (action === 'short' ? 450 : 600), 0.12);
          showTradeToast(`${action.toUpperCase()} ${ticker} (${pct}%) filled at $${(data.filledPrice || 0).toFixed(2)}`, 'success');
        } else {
          playAudioTone(250, 0.25, 'sawtooth');
          showTradeToast(`Order rejected: ${data.message || 'Unknown error'}`, 'error');
        }
      })
      .catch(err => {
        playAudioTone(250, 0.25, 'sawtooth');
        showTradeToast(`Execution dispatch failed: ${err}`, 'error');
      });
    }

    function showTradeToast(msg, kind = 'info') {
      const container = document.getElementById('toastContainer');
      if (!container) return;
      const el = document.createElement('div');
      let borderCol = 'border-blue-500 bg-slate-900 text-blue-200';
      if (kind === 'success') borderCol = 'border-emerald-500 bg-slate-900 text-emerald-200';
      if (kind === 'error') borderCol = 'border-rose-500 bg-slate-900 text-rose-200';

      el.className = `px-3.5 py-2 rounded border shadow-lg text-xs font-mono flex items-center gap-2 pointer-events-auto transition-all ${borderCol}`;
      el.innerHTML = `<span>${msg}</span>`;
      container.appendChild(el);
      setTimeout(() => {
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 300);
      }, 3500);
    }

    function setChartMode(mode) {
      chartMode = mode;
      const btnPrice = document.getElementById('chartViewPriceBtn');
      const btnComp = document.getElementById('chartViewCompareBtn');
      if (btnPrice && btnComp) {
        if (mode === 'price') {
          btnPrice.className = 'px-2.5 py-0.5 rounded text-[11px] font-semibold bg-blue-600 text-white';
          btnComp.className = 'px-2.5 py-0.5 rounded text-[11px] font-medium text-muted hover:text-title';
        } else {
          btnComp.className = 'px-2.5 py-0.5 rounded text-[11px] font-semibold bg-blue-600 text-white';
          btnPrice.className = 'px-2.5 py-0.5 rounded text-[11px] font-medium text-muted hover:text-title';
        }
      }
      renderChartData();
    }

    function renderChartData() {
      if (!chart || !lastHistoryData) return;
      const history = lastHistoryData || {};
      const chartSeries = history.series || {};
      const timestamps = history.timestamps || [];
      if (timestamps.length === 0) return;

      chart.data.labels = timestamps;
      const palette = ['#3b82f6', '#10b981', '#f43f5e', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#14b8a6', '#64748b'];
      let targetTickers = Object.keys(chartSeries);
      if (currentChartTicker !== 'ALL') {
        targetTickers = chartSeries[currentChartTicker] ? [currentChartTicker] : [];
      }

      let colorIdx = 0;
      chart.data.datasets = targetTickers.map(ticker => {
        const col = palette[colorIdx % palette.length];
        colorIdx++;
        const rawPts = chartSeries[ticker] || [];
        let finalData = rawPts;

        if (chartMode === 'compare') {
          const base = rawPts[0] || 1.0;
          finalData = rawPts.map(v => base > 0 ? Number((((v - base) / base) * 100).toFixed(2)) : 0.0);
        }

        return {
          label: (chartMode === 'compare') ? `${ticker} (%)` : ticker,
          data: finalData,
          borderColor: col,
          backgroundColor: (currentChartTicker !== 'ALL' && chartMode === 'price') ? 'rgba(59, 130, 246, 0.08)' : 'transparent',
          fill: (currentChartTicker !== 'ALL' && chartMode === 'price'),
          tension: 0.25,
          borderWidth: 2,
          pointRadius: (currentChartTicker !== 'ALL') ? 2 : 0
        };
      });

      if (chart.options.scales && chart.options.scales.y) {
        chart.options.scales.y.title = {
          display: true,
          text: (chartMode === 'compare') ? 'Return (%)' : 'Price ($)',
          color: (currentTheme === 'light' ? '#475569' : '#94a3b8')
        };
      }
      chart.update('none');
    }

    function onChartStockChange(ticker) {
      currentChartTicker = ticker;
      renderChartData();
    }

    function initChart() {
      const canvasEl = document.getElementById('marketChart');
      if (!canvasEl) return;
      const ctx = canvasEl.getContext('2d');
      const isLight = (currentTheme === 'light');
      const gridCol = isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.04)';
      const textCol = isLight ? '#475569' : '#94a3b8';

      chart = new Chart(ctx, {
        type: 'line',
        data: { labels: [], datasets: [] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: {
            legend: {
              display: true,
              position: 'top',
              labels: { boxWidth: 10, boxHeight: 2, color: textCol, font: { size: 10, family: 'Inter' } }
            },
            tooltip: {
              mode: 'index',
              intersect: false,
              callbacks: {
                label: function(ctx) {
                  return ` ${ctx.dataset.label}: ${chartMode === 'compare' ? (ctx.raw >= 0 ? '+' : '') + ctx.raw + '%' : '$' + Number(ctx.raw).toFixed(2)}`;
                }
              }
            }
          },
          scales: {
            x: {
              ticks: { maxTicksLimit: 8, color: textCol, font: { size: 10, family: 'JetBrains Mono' } },
              grid: { color: gridCol }
            },
            y: {
              position: 'right',
              ticks: {
                color: textCol,
                font: { size: 10, family: 'JetBrains Mono' },
                callback: function(v) { return chartMode === 'compare' ? `${v}%` : `$${v}`; }
              },
              grid: { color: gridCol }
            }
          }
        }
      });
    }

    // Auto Actions Rules Logic
    function setArSize(pct) {
      currentArSizePct = pct;
      document.querySelectorAll('.ar-size-pill').forEach(btn => {
        if (parseInt(btn.dataset.size, 10) === pct) {
          btn.className = 'ar-size-pill flex-1 py-1 rounded text-[11px] font-semibold bg-blue-600 text-white';
        } else {
          btn.className = 'ar-size-pill flex-1 py-1 rounded text-[11px] font-medium text-muted';
        }
      });
    }

    function addAutoActionRule() {
      const stock = (document.getElementById('arStockInput').value || '').trim();
      const action = document.getElementById('arActionSelect').value;
      const when = document.getElementById('arWhenSelect').value;
      const price = parseFloat(document.getElementById('arPriceInput').value);
      const repeat = document.getElementById('arRepeatCheck').checked;

      if (!stock || isNaN(price) || price <= 0) {
        showTradeToast('Please enter a valid stock ticker and positive target price.', 'error');
        return;
      }

      fetch('/api/auto-rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stock: stock,
          action: action,
          when: when,
          price: price,
          percent: currentArSizePct,
          repeat: repeat
        })
      })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          showTradeToast(`Armed trigger: ${action.toUpperCase()} ${stock} when ${when} $${price.toFixed(2)}`, 'success');
          document.getElementById('arStockInput').value = '';
          document.getElementById('arPriceInput').value = '';
        }
      })
      .catch(err => showTradeToast(`Failed adding rule: ${err}`, 'error'));
    }

    function deleteAutoActionRule(ruleId) {
      fetch(`/api/auto-rules/${ruleId}`, { method: 'DELETE' })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') showTradeToast('Removed auto action trigger', 'info');
      });
    }

    function toggleAutoActionRule(ruleId) {
      fetch(`/api/auto-rules/${ruleId}/toggle`, { method: 'POST' })
      .then(res => res.json());
    }

    function renderAutoRulesTable(rules) {
      const tb = document.getElementById('autoRulesTableBody');
      const countEl = document.getElementById('autoRulesCount');
      const navCount = document.getElementById('autoRulesNavCount');
      const count = rules ? rules.length : 0;
      if (countEl) countEl.innerText = count;
      if (navCount) navCount.innerText = count;
      if (!tb) return;
      if (!rules || rules.length === 0) {
        tb.innerHTML = '<tr><td colspan="7" class="py-3 text-center text-dim italic">No custom auto actions configured. Arm one above to begin!</td></tr>';
        return;
      }
      tb.innerHTML = rules.map(r => `
        <tr class="${r.enabled ? 'text-title' : 'text-dim opacity-60'}">
          <td class="py-2 px-2.5 font-bold">${r.stock}</td>
          <td class="py-2 px-2.5 uppercase font-semibold ${r.action === 'buy' ? 'text-emerald-500' : (r.action === 'short' ? 'text-rose-500' : 'text-blue-500')}">${r.action}</td>
          <td class="py-2 px-2.5 text-muted">${r.when === 'below' ? '&le; Below' : '&ge; Above'}</td>
          <td class="py-2 px-2.5 tabular font-bold text-title">$${Number(r.price).toFixed(2)}</td>
          <td class="py-2 px-2.5">${r.percent}%</td>
          <td class="py-2 px-2.5">${r.repeat ? '<span class="text-emerald-500 font-semibold">Continuous</span>' : '<span class="text-dim">Single</span>'}</td>
          <td class="py-2 px-2.5 text-right">
            <button onclick="toggleAutoActionRule('${r.id}')" class="px-2 py-0.5 rounded text-[11px] ${r.enabled ? 'badge-buy' : 'badge-neutral'} mr-1">${r.enabled ? 'ACTIVE' : 'OFF'}</button>
            <button onclick="deleteAutoActionRule('${r.id}')" class="px-2 py-0.5 rounded text-[11px] badge-sell hover:bg-rose-600 hover:text-white">&times;</button>
          </td>
        </tr>
      `).join('');
    }

    // Steam News Fetcher
    function fetchSteamNews(manual = false) {
      const c = document.getElementById('steamNewsContainer');
      if (manual && c) c.innerHTML = '<div class="col-span-full py-4 text-center text-muted italic">Checking Steam Web API for latest announcements...</div>';
      fetch('/api/news')
      .then(res => res.json())
      .then(data => {
        const news = data.news || [];
        if (c) {
          if (news.length === 0) {
            c.innerHTML = '<div class="col-span-full py-4 text-center text-dim italic">No news announcements available.</div>';
            return;
          }
          c.innerHTML = news.map(item => `
            <div class="card p-3.5 flex flex-col justify-between hover:border-blue-500 transition-colors">
              <div>
                <div class="flex items-center justify-between text-[11px] text-muted mb-1">
                  <span class="font-semibold text-blue-500">${item.feedlabel || 'Game Update'}</span>
                  <span class="font-mono text-dim">${item.date || 'Recent'}</span>
                </div>
                <h3 class="font-bold text-sm text-title mb-2">${item.title}</h3>
                <div class="text-xs text-muted leading-relaxed mb-3 line-clamp-4">${item.summary || 'No details provided.'}</div>
              </div>
              <div class="flex items-center justify-between pt-2 border-t text-[11px]" style="border-color: var(--border-subtle)">
                <span class="text-dim">By ${item.author || 'Developer'}</span>
                <a href="${item.url}" target="_blank" class="text-blue-500 hover:text-blue-400 font-semibold flex items-center gap-1">
                  <span>Full Patch Notes</span>
                  <svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
                </a>
              </div>
            </div>
          `).join('');
        }
      })
      .catch(err => {
        if (c) c.innerHTML = `<div class="col-span-full py-4 text-center text-rose-500">Failed loading Steam news: ${err}</div>`;
      });
    }

    // Portfolio Refresh
    function refreshPortfolio() {
      fetch('/api/portfolio')
      .then(res => res.json())
      .then(data => {
        document.getElementById('pfNetWorth').innerText = `$${Number(data.net_worth || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        document.getElementById('pfCash').innerText = `$${Number(data.cash || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        document.getElementById('pfLongVal').innerText = `$${Number(data.long_value || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        document.getElementById('pfShortVal').innerText = `$${Number(data.short_value || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

        document.getElementById('pfCashPct').innerText = `${data.cash_pct || 100}%`;
        document.getElementById('pfLongPct').innerText = `${data.long_pct || 0}%`;
        document.getElementById('pfShortPct').innerText = `${data.short_pct || 0}%`;

        document.getElementById('pfBarCash').style.width = `${data.cash_pct || 100}%`;
        document.getElementById('pfBarLong').style.width = `${data.long_pct || 0}%`;
        document.getElementById('pfBarShort').style.width = `${data.short_pct || 0}%`;

        const tb = document.getElementById('portfolioTableBody');
        const pos = data.positions || [];
        if (pos.length === 0) {
          tb.innerHTML = '<tr><td colspan="9" class="py-3 text-center text-dim italic">No open positions. 100% Cash Ready.</td></tr>';
          return;
        }
        tb.innerHTML = pos.map(p => `
          <tr>
            <td class="py-2 px-2.5 font-bold text-title">${p.ticker}</td>
            <td class="py-2 px-2.5"><span class="px-1.5 py-0.2 rounded text-[10px] font-semibold ${p.side === 'SHORT' ? 'badge-sell' : 'badge-blue'}">${p.side}</span></td>
            <td class="py-2 px-2.5 tabular text-title">${Number(p.shares).toLocaleString()}</td>
            <td class="py-2 px-2.5 tabular">$${Number(p.entry_price).toFixed(2)}</td>
            <td class="py-2 px-2.5 tabular font-bold text-title">$${Number(p.price).toFixed(2)}</td>
            <td class="py-2 px-2.5 tabular font-bold text-title">$${Number(p.total_value).toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
            <td class="py-2 px-2.5 tabular ${p.profit_pct >= 0 ? 'text-emerald-500' : 'text-rose-500'} font-bold">${p.profit_pct >= 0 ? '+' : ''}${p.profit_pct.toFixed(2)}%</td>
            <td class="py-2 px-2.5 tabular ${p.dollar_pnl >= 0 ? 'text-emerald-500' : 'text-rose-500'}">${p.dollar_pnl >= 0 ? '+' : ''}$${p.dollar_pnl.toFixed(2)}</td>
            <td class="py-2 px-2.5 text-right">
              <button onclick="executeStockAction('${p.ticker}', 'close')" class="btn-secondary px-2 py-0.5 rounded text-[11px]">Close</button>
            </td>
          </tr>
        `).join('');
      })
      .catch(err => console.log('Portfolio error:', err));
    }

    // Stats & Audit Fetcher
    function fetchPerformanceStats() {
      fetch('/api/stats')
      .then(res => res.json())
      .then(data => {
        document.getElementById('statsWinRate').innerText = `${data.win_rate || 0.0}%`;
        document.getElementById('statsProfitFactor').innerText = Number(data.profit_factor || 1.0).toFixed(2);
        document.getElementById('statsTotalWon').innerText = `+$${Number(data.total_won_dollars || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        document.getElementById('statsTotalLost').innerText = `-$${Number(data.total_lost_dollars || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        document.getElementById('statsWinCount').innerText = `${data.closed_trades_count || 0} closed trades`;

        // 7 Days Net Worth Ledger
        const dailyTb = document.getElementById('dailyStatsTableBody');
        const past = data.past_7_days || [];
        if (past.length === 0) {
          dailyTb.innerHTML = '<tr><td colspan="7" class="py-3 text-center text-dim italic">No historical daily records yet. Valuations log automatically.</td></tr>';
        } else {
          dailyTb.innerHTML = past.map(d => `
            <tr>
              <td class="py-2 px-2.5 font-bold text-title">${d.date}</td>
              <td class="py-2 px-2.5 tabular">$${Number(d.start).toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
              <td class="py-2 px-2.5 tabular text-emerald-500 font-bold">$${Number(d.high).toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
              <td class="py-2 px-2.5 tabular text-rose-500">$${Number(d.low).toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
              <td class="py-2 px-2.5 tabular font-bold text-title">$${Number(d.current).toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
              <td class="py-2 px-2.5 tabular ${d.profit >= 0 ? 'text-emerald-500' : 'text-rose-500'} font-bold">${d.profit >= 0 ? '+' : ''}$${Number(d.profit).toFixed(2)}</td>
              <td class="py-2 px-2.5 text-right tabular ${d.pct >= 0 ? 'text-emerald-500' : 'text-rose-500'} font-bold">${d.pct >= 0 ? '+' : ''}${d.pct.toFixed(2)}%</td>
            </tr>
          `).join('');
        }

        // Top Wins
        const winsTb = document.getElementById('topWinsTableBody');
        const wins = data.top_investments || [];
        if (wins.length === 0) {
          winsTb.innerHTML = '<tr><td colspan="5" class="py-2 text-center text-dim italic">No closed winning trades recorded yet.</td></tr>';
        } else {
          winsTb.innerHTML = wins.map(w => `
            <tr>
              <td class="py-1 px-1.5 text-dim">${w.time_str}</td>
              <td class="py-1 px-1.5 font-bold text-title">${w.ticker}</td>
              <td class="py-1 px-1.5 tabular text-title">$${Number(w.price).toFixed(2)}</td>
              <td class="py-1 px-1.5 text-emerald-500 tabular font-bold">+${w.profit_pct.toFixed(2)}%</td>
              <td class="py-1 px-1.5 text-right text-emerald-500 tabular font-bold">+$${w.dollar_gain.toFixed(2)}</td>
            </tr>
          `).join('');
        }

        // Fumbles
        const fumblesTb = document.getElementById('fumblesTableBody');
        const fumbles = data.fumbles || [];
        if (fumbles.length === 0) {
          fumblesTb.innerHTML = '<tr><td colspan="5" class="py-2 text-center text-dim italic">No closed loss fumbles recorded. Risk limits working!</td></tr>';
        } else {
          fumblesTb.innerHTML = fumbles.map(f => `
            <tr>
              <td class="py-1 px-1.5 text-dim">${f.time_str}</td>
              <td class="py-1 px-1.5 font-bold text-title">${f.ticker}</td>
              <td class="py-1 px-1.5 tabular text-title">$${Number(f.price).toFixed(2)}</td>
              <td class="py-1 px-1.5 text-rose-500 tabular font-bold">${f.profit_pct.toFixed(2)}%</td>
              <td class="py-1 px-1.5 text-right text-rose-500 tabular font-bold">-$${Math.abs(f.dollar_gain).toFixed(2)}</td>
            </tr>
          `).join('');
        }
      });
    }

    // Skins Manager
    function fetchSkins() {
      const grid = document.getElementById('skinsGrid');
      fetch('/api/skins')
      .then(res => res.json())
      .then(data => {
        const skins = data.skins || [];
        if (skins.length === 0) {
          grid.innerHTML = '<div class="col-span-full py-4 text-center text-dim italic">No custom skins installed. Upload a PNG/JPG above to create one!</div>';
          return;
        }
        grid.innerHTML = skins.map(s => `
          <div class="card p-3 flex flex-col justify-between border ${s.equipped ? 'border-purple-500 shadow-md shadow-purple-500/20' : ''}">
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="font-bold text-xs truncate text-title" title="${s.name}">${s.name}</span>
                ${s.equipped ? '<span class="text-[9px] font-bold px-1.5 py-0.2 rounded badge-blue">EQUIPPED</span>' : ''}
              </div>
              <div class="w-full h-24 rounded flex items-center justify-center border mb-2 overflow-hidden" style="background-color: var(--bg-input); border-color: var(--border-subtle)">
                <span class="text-xs font-mono text-muted">${s.file || s.id}</span>
              </div>
            </div>
            <div class="flex items-center gap-1.5 pt-2 border-t" style="border-color: var(--border-subtle)">
              <button onclick="equipSkin('${s.id}')" class="flex-1 py-1 rounded text-xs font-medium ${s.equipped ? 'badge-blue font-bold' : 'bg-blue-600 hover:bg-blue-500 text-white'}">${s.equipped ? 'Equipped' : 'Equip'}</button>
              <button onclick="deleteSkin('${s.id}')" class="px-2 py-1 rounded badge-sell hover:bg-rose-600 hover:text-white text-xs">&times;</button>
            </div>
          </div>
        `).join('');
      })
      .catch(err => {
        grid.innerHTML = `<div class="col-span-full py-4 text-center text-rose-500">Error loading skins: ${err}</div>`;
      });
    }

    function equipSkin(skinId) {
      fetch('/api/skins/equip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skin_id: skinId })
      })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          showTradeToast(`Equipped skin: ${skinId} in Screen Stocks!`, 'success');
          fetchSkins();
        } else {
          showTradeToast(`Failed equipping skin: ${data.detail || 'Error'}`, 'error');
        }
      });
    }

    function deleteSkin(skinId) {
      if (confirm(`Delete custom skin ${skinId}?`)) {
        fetch(`/api/skins/${skinId}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
          showTradeToast(`Deleted skin: ${skinId}`, 'info');
          fetchSkins();
        });
      }
    }

    function uploadSkin() {
      const fileInput = document.getElementById('skinFileInput');
      const nameInput = document.getElementById('skinNameInput');
      if (!fileInput.files || fileInput.files.length === 0) {
        showTradeToast('Please choose a PNG or JPG wallpaper file.', 'error');
        return;
      }
      const file = fileInput.files[0];
      const skinName = (nameInput.value || file.name.split('.')[0]).trim();
      const reader = new FileReader();
      reader.onload = function(e) {
        const b64 = e.target.result;
        const ext = file.name.split('.').pop().toLowerCase();
        fetch('/api/skins', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: skinName,
            image_base64: b64,
            file_ext: ext
          })
        })
        .then(res => res.json())
        .then(data => {
          if (data.status === 'success') {
            showTradeToast(`Installed skin '${skinName}' successfully!`, 'success');
            fileInput.value = '';
            nameInput.value = '';
            fetchSkins();
          } else {
            showTradeToast(`Skin upload failed: ${data.detail || 'Error'}`, 'error');
          }
        })
        .catch(err => showTradeToast(`Skin upload failed: ${err}`, 'error'));
      };
      reader.readAsDataURL(file);
    }

    // In-Game Settings Fetch & Save
    function fetchInGameSettings() {
      fetch('/api/game_settings')
      .then(res => res.json())
      .then(data => {
        const s = data.settings || {};
        if (s.sfxVolume !== undefined) {
          document.getElementById('igSfxSlider').value = s.sfxVolume;
          document.getElementById('igSfxVal').innerText = Math.round(s.sfxVolume * 100) + '%';
        }
        if (s.musicVolume !== undefined) {
          document.getElementById('igMusicSlider').value = s.musicVolume;
          document.getElementById('igMusicVal').innerText = Math.round(s.musicVolume * 100) + '%';
        }
        if (s.unfocusedWindowOpacityPercent !== undefined) {
          document.getElementById('igOpacitySlider').value = s.unfocusedWindowOpacityPercent;
          document.getElementById('igOpacityVal').innerText = s.unfocusedWindowOpacityPercent + '%';
        }
        if (s.audioMuted !== undefined) document.getElementById('igMutedCheck').checked = Boolean(s.audioMuted);
        if (s.screenShake !== undefined) document.getElementById('igShakeCheck').checked = Boolean(s.screenShake);
        if (s.frameRateIndex !== undefined) document.getElementById('igFramerateSelect').value = s.frameRateIndex;
        if (s.scientificNotation !== undefined) document.getElementById('igScientificCheck').checked = Boolean(s.scientificNotation);
        if (s.advancedMode !== undefined) document.getElementById('igAdvancedCheck').checked = Boolean(s.advancedMode);
        if (s.fullscreen !== undefined) document.getElementById('igFullscreenCheck').checked = Boolean(s.fullscreen);
      });
    }

    function saveInGameSettings() {
      const payload = {
        sfxVolume: parseFloat(document.getElementById('igSfxSlider').value),
        musicVolume: parseFloat(document.getElementById('igMusicSlider').value),
        unfocusedWindowOpacityPercent: parseInt(document.getElementById('igOpacitySlider').value, 10),
        audioMuted: document.getElementById('igMutedCheck').checked,
        screenShake: document.getElementById('igShakeCheck').checked,
        frameRateIndex: parseInt(document.getElementById('igFramerateSelect').value, 10),
        scientificNotation: document.getElementById('igScientificCheck').checked,
        advancedMode: document.getElementById('igAdvancedCheck').checked,
        fullscreen: document.getElementById('igFullscreenCheck').checked
      };

      fetch('/api/game_settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          showTradeToast('Direct Screen Stocks settings saved!', 'success');
        } else {
          showTradeToast(`Failed saving in-game settings: ${data.detail}`, 'error');
        }
      });
    }

    function renderScheduledEvents(events) {
      const ribbon = document.getElementById('scheduledEventsRibbon');
      const list = document.getElementById('scheduledEventsList');
      if (!ribbon || !list) return;
      if (!events || events.length === 0) {
        list.innerHTML = '<div class="text-muted italic">No price reset anomalies scheduled in next 10 minutes.</div>';
        return;
      }
      list.innerHTML = events.map(ev => {
        const isDrop = (ev.direction === 'drop');
        const min = Math.floor(ev.left_seconds / 60);
        const sec = ev.left_seconds % 60;
        const timeStr = `${min}:${String(sec).padStart(2, '0')}`;
        const badgeColor = isDrop ? 'badge-sell' : 'badge-buy';
        return `
          <div class="px-2.5 py-1 rounded ${badgeColor} flex items-center gap-1.5">
            <strong>${ev.stock}</strong>
            <span class="text-[10px] uppercase font-semibold">${isDrop ? 'Crash Target' : 'Pump Target'} $${Number(ev.target).toFixed(2)}</span>
            <span class="text-dim text-[10px]">in ${timeStr}</span>
          </div>
        `;
      }).join('');
    }

    function connectWS() {
      const proto = (window.location.protocol === 'https:') ? 'wss:' : 'ws:';
      const wsUrl = `${proto}//${window.location.host}/ws`;
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        const ind = document.getElementById('connIndicator');
        if (ind) ind.className = 'w-2 h-2 rounded-full bg-emerald-400 pulse-dot';
      };

      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          updateDashboard(data);
        } catch (e) {}
      };

      ws.onclose = () => {
        const ind = document.getElementById('connIndicator');
        if (ind) ind.className = 'w-2 h-2 rounded-full bg-rose-500';
        setTimeout(connectWS, 1500);
      };
    }

    function updateDashboard(data) {
      if (!data) return;

      // 1. Operating Mode & Badges
      const isAuto = (data.mode === 'AUTO');
      const modeBadge = document.getElementById('modeBadge');
      const modeToggleBtn = document.getElementById('modeToggleBtn');
      if (modeBadge && modeToggleBtn) {
        if (isAuto) {
          modeBadge.className = 'px-2 py-0.5 rounded text-[11px] font-semibold badge-buy';
          modeBadge.innerText = 'AUTO RUNNING';
          modeToggleBtn.className = 'px-3.5 py-1.5 rounded bg-rose-600 hover:bg-rose-500 text-white font-medium text-xs shadow transition-all flex items-center gap-1.5 active:scale-95';
          modeToggleBtn.innerHTML = `
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>
            <span>Stop Auto Mode</span>
          `;
        } else {
          modeBadge.className = 'px-2 py-0.5 rounded text-[11px] font-semibold badge-neutral';
          modeBadge.innerText = 'SUGGESTION MODE';
          modeToggleBtn.className = 'px-3.5 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs shadow transition-all flex items-center gap-1.5 active:scale-95';
          modeToggleBtn.innerHTML = `
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            <span>Engage Auto Mode</span>
          `;
        }
      }

      // Auto Time Remaining
      const autoRemEl = document.getElementById('autoTimeRemaining');
      if (autoRemEl && data.auto_time_remaining) {
        autoRemEl.innerText = data.auto_time_remaining;
      }

      // 2. Game Bridge Connection Indicator & Transport Label
      const isGameConnected = data.game_connected || (data.connected && data.game_running);
      const connDot = document.getElementById('connIndicator');
      const gameBadge = document.getElementById('gameConnBadge');
      if (isGameConnected) {
        if (connDot) connDot.className = 'w-2 h-2 rounded-full bg-emerald-400 pulse-dot';
        if (gameBadge) {
          gameBadge.className = 'text-xs font-mono text-emerald-500 font-semibold';
          const trans = (data.bridge_transport === 'native_mod') ? 'NATIVE MOD' : 'LOCAL BRIDGE';
          gameBadge.innerText = `GAME: ONLINE (${trans})`;
        }
      } else {
        if (connDot) connDot.className = 'w-2 h-2 rounded-full bg-amber-400 pulse-dot';
        if (gameBadge) {
          gameBadge.className = 'text-xs font-mono text-muted';
          gameBadge.innerText = 'GAME: AWAITING BRIDGE';
        }
      }

      // Latency Display. Shows the median frame-to-decision cycle, because that
      // is the number that bounds how stale a signal can be when it reaches the
      // game; inference alone is only a slice of it. The per-stage p50s go in the
      // tooltip so the breakdown is visible without cluttering the header.
      const latEl = document.getElementById('latencyDisplay');
      if (latEl) {
        const p = data.pipeline || {};
        const hasCycle = p.cycle && p.cycle.n;
        const shown = hasCycle ? p.cycle.p50 : (data.inf_latency_ms || 0);
        latEl.innerText = `${Number(shown).toFixed(2)} ms`;
        const stages = ['snapshot_wait', 'features', 'inference', 'decision', 'dispatch']
          .filter(k => p[k] && p[k].n)
          .map(k => `${k} ${Number(p[k].p50).toFixed(2)} ms`);
        const tip = stages.length ? `median ms per stage (p50)\n${stages.join('\n')}` : '';
        latEl.title = tip;
        const wrap = document.getElementById('latencyWrap');
        if (wrap && tip) wrap.title = tip;
      }

      // Special BASE Crash Indicator
      const baseCrashVal = document.getElementById('baseCrashCountdown');
      if (baseCrashVal && data.db_stats && data.db_stats.base_crash_countdown) {
        baseCrashVal.innerText = data.db_stats.base_crash_countdown;
      }

      // Achievements Hunter Pill
      const achieveDot = document.getElementById('achieveDot');
      const achieveText = document.getElementById('achieveText');
      if (achieveDot && achieveText) {
        if (data.achievements_enabled) {
          achieveDot.className = 'w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-dot';
          achieveText.innerText = 'Hunter: ON';
        } else {
          achieveDot.className = 'w-1.5 h-1.5 rounded-full bg-slate-500';
          achieveText.innerText = 'Hunter: OFF';
        }
      }

      // 3. Financial Metrics Ribbon
      const p = data.player || {};
      const netWorthEl = document.getElementById('netWorthDisplay');
      const cashEl = document.getElementById('cashDisplay');
      const pnlTag = document.getElementById('pnlTag');
      const ipoTag = document.getElementById('ipoTag');

      if (netWorthEl && p.netWorth) netWorthEl.innerText = p.netWorth;
      if (cashEl && p.cash) cashEl.innerText = p.cash;
      if (ipoTag && p.ipoCount !== undefined) ipoTag.innerText = `IPO: ${p.ipoCount}`;

      if (pnlTag && p.totalUnrealizedPnL !== undefined) {
        const uPnl = Number(p.totalUnrealizedPnL);
        pnlTag.innerText = `${uPnl >= 0 ? '+' : ''}$${uPnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        pnlTag.className = `text-[11px] font-mono font-medium ${uPnl >= 0 ? 'text-emerald-500' : 'text-rose-500'}`;
      }

      // Session Stats
      const sess = data.session_stats || {};
      const sessPnlEl = document.getElementById('sessionPnlDisplay');
      const sessCountEl = document.getElementById('sessionTradesCount');
      const winRateEl = document.getElementById('winRateDisplay');
      const winLossEl = document.getElementById('winLossCounts');
      const presetBadge = document.getElementById('activePresetBadge');

      if (sessPnlEl && sess.realized_pnl !== undefined) {
        const rPnl = Number(sess.realized_pnl);
        sessPnlEl.innerText = `${rPnl >= 0 ? '+' : ''}$${rPnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        sessPnlEl.className = `text-lg lg:text-xl font-bold tabular ${rPnl >= 0 ? 'text-emerald-500' : 'text-rose-500'}`;
      }
      if (sessCountEl && sess.trades_count !== undefined) {
        sessCountEl.innerText = `${sess.trades_count} Trades`;
      }
      if (winRateEl && sess.win_rate !== undefined) {
        winRateEl.innerText = `${Number(sess.win_rate).toFixed(1)}%`;
      }
      if (winLossEl && sess.wins !== undefined && sess.losses !== undefined) {
        winLossEl.innerText = `${sess.wins}W - ${sess.losses}L`;
      }
      if (presetBadge && sess.active_preset) {
        presetBadge.innerText = sess.active_preset;
      }

      // AI Accuracy & Learning Stats
      const db = data.db_stats || {};
      const modelAccEl = document.getElementById('modelAccText');
      const dbTicksEl = document.getElementById('dbTicksCount');
      const retrainCountEl = document.getElementById('retrainCountdown');
      if (modelAccEl) {
        const acc = (data.retrain_accuracy !== undefined && data.retrain_accuracy !== null) ? data.retrain_accuracy : db.retrain_accuracy;
        if (acc !== undefined && acc !== null) {
          modelAccEl.innerText = `${Number(acc).toFixed(1)}%`;
        } else {
          modelAccEl.innerText = 'Calibrating...';
        }
      }
      if (dbTicksEl && db.session_ticks !== undefined) {
        dbTicksEl.innerText = Number(db.session_ticks).toLocaleString();
      }
      if (retrainCountEl && db.next_retrain_in !== undefined) {
        retrainCountEl.innerText = `${db.next_retrain_in}s`;
      }

      // Dividend Vault Stats
      const divIncomeEl = document.getElementById('divIncomeDisplay');
      const vaultTag = document.getElementById('vaultStatusTag');
      const universeEl = document.getElementById('universeCount');
      const totalDivEl = document.getElementById('totalDividendsDisplay');

      if (divIncomeEl && db.dividend_income_per_min !== undefined) {
        divIncomeEl.innerText = `+$${Number(db.dividend_income_per_min).toFixed(2)} / min`;
      }
      if (vaultTag && db.dividend_vault_active !== undefined) {
        vaultTag.innerText = `Vault: ${db.dividend_vault_active ? 'ACTIVE' : 'Inactive'}`;
        vaultTag.className = db.dividend_vault_active ? 'text-emerald-500 font-bold' : 'text-dim';
      }
      if (universeEl && data.unlocked_stocks) {
        universeEl.innerText = `${data.unlocked_stocks.length} Stocks`;
      }
      if (totalDivEl && data.total_dividends !== undefined) {
        totalDivEl.innerText = `Harvested: $${Number(data.total_dividends).toFixed(2)}`;
      }

      // 4. Scheduled Resets Arbitrage Banner
      if (data.scheduled_events) {
        renderScheduledEvents(data.scheduled_events);
      }

      // 5. Auto Rules Table Update
      if (data.auto_rules) {
        renderAutoRulesTable(data.auto_rules);
      }

      // 6. Stocks Table Population
      const stocks = data.stocks || [];
      const tb = document.getElementById('stocksTableBody');
      const chartSelect = document.getElementById('chartStockSelect');

      if (stocks.length > 0 && tb) {
        if (chartSelect && chartSelect.options.length <= 1) {
          stocks.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.ticker;
            opt.innerText = `${s.ticker} - ${s.name || s.ticker}`;
            chartSelect.appendChild(opt);
          });
        }

        const prevPriceMap = {};
        lastRenderedStocks.forEach(s => { prevPriceMap[s.ticker] = s.price; });

        tb.innerHTML = stocks.map(s => {
          const oldP = prevPriceMap[s.ticker];
          let flashClass = '';
          if (oldP !== undefined && s.price > oldP) flashClass = 'flash-up';
          else if (oldP !== undefined && s.price < oldP) flashClass = 'flash-down';

          const hasPos = (s.holding && s.holding !== 'FLAT');
          const isLong = (s.holding && s.holding.includes('LONG'));
          const isShort = (s.holding && s.holding.includes('SHORT'));

          let pnlBadge = '<span class="text-dim">-</span>';
          if (hasPos && s.avg_price > 0) {
            const pnlVal = isLong ? ((s.price - s.avg_price) / s.avg_price) * 100 : ((s.avg_price - s.price) / s.avg_price) * 100;
            const pnlColor = pnlVal >= 0 ? 'text-emerald-500' : 'text-rose-500';
            pnlBadge = `<span class="${pnlColor} font-bold">${pnlVal >= 0 ? '+' : ''}${pnlVal.toFixed(1)}%</span>`;
          }

          let sigColor = 'badge-neutral';
          if (s.signal === 'STRONG_BUY') sigColor = 'badge-buy font-bold';
          else if (s.signal === 'BUY') sigColor = 'badge-buy';
          else if (s.signal === 'STRONG_SHORT') sigColor = 'badge-sell font-bold';
          else if (s.signal === 'SHORT') sigColor = 'badge-sell';

          const sparkSvg = renderSparklineSVG(s.sparkline, s.price >= (oldP || s.price));
          const profBadge = getProfileBadge(s.ticker, s.name);

          return `
            <tr data-ticker="${s.ticker}" data-has-holding="${hasPos}" class="${flashClass}">
              <td class="py-2 px-2.5">
                <div class="font-bold flex items-center gap-1.5 text-title">
                  <span>${s.ticker}</span>
                  ${profBadge}
                </div>
                <div class="text-[10px] text-dim">${s.name || s.ticker}</div>
              </td>
              <td class="py-2 px-2.5 font-bold tabular text-[13px] text-title">$${Number(s.price).toFixed(2)}</td>
              <td class="py-2 px-2.5">${sparkSvg}</td>
              <td class="py-2 px-2.5">
                <span class="px-1.5 py-0.5 rounded text-[10px] ${sigColor}">${s.signal}</span>
              </td>
              <td class="py-2 px-2.5 tabular text-muted">${s.confidence || 0}%</td>
              <td class="py-2 px-2.5 tabular ${s.expected_return >= 0 ? 'text-emerald-500' : 'text-rose-500'} font-semibold">${s.expected_return >= 0 ? '+' : ''}${s.expected_return || 0}%</td>
              <td class="py-2 px-2.5">
                <span class="px-1.5 py-0.5 rounded text-[10px] font-mono ${hasPos ? (isLong ? 'badge-buy' : 'badge-sell') : 'text-dim'}">
                  ${s.holding || 'FLAT'}
                </span>
              </td>
              <td class="py-2 px-2.5 tabular">${pnlBadge}</td>
              <td class="py-2 px-2.5 text-right space-x-1 whitespace-nowrap">
                <button onclick="executeStockAction('${s.ticker}', 'buy')" class="px-2 py-0.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-[11px] shadow-sm">BUY</button>
                <button onclick="executeStockAction('${s.ticker}', 'short')" class="px-2 py-0.5 rounded bg-rose-600 hover:bg-rose-500 text-white font-semibold text-[11px] shadow-sm">SHORT</button>
                ${hasPos ? `<button onclick="executeStockAction('${s.ticker}', 'close')" class="btn-secondary px-2 py-0.5 rounded text-[11px]">CLOSE</button>` : ''}
              </td>
            </tr>
          `;
        }).join('');

        lastRenderedStocks = stocks;
        applyTableFilter();
      }

      // 7. Live Technical Analysis Chart Update
      if (data.history) {
        lastHistoryData = data.history;
        renderChartData();
      }

      // 8. Execution Logs Stream Update
      const logContainer = document.getElementById('logsContainer');
      const logs = data.logs || [];
      if (logs.length > 0) {
        if (!window._renderedLogKeys) window._renderedLogKeys = new Set();
        logs.forEach(l => {
          const key = (l.id !== undefined) ? `id_${l.id}` : `${l.time}_${l.ticker}_${l.action}_${(l.reason || '').slice(0, 20)}`;
          if (!window._renderedLogKeys.has(key)) {
            window._renderedLogKeys.add(key);
            const div = document.createElement('div');
            const statusColor = (l.status === 'EXECUTED') ? 'text-emerald-500 font-bold' : (l.status === 'FAILED' ? 'text-rose-500' : 'text-blue-500');

            let srcBadge = '';
            const rLow = (l.reason || '').toLowerCase();
            if (rLow.includes('[event arb]')) srcBadge = '<span class="px-1 py-0.2 rounded text-[9px] font-bold" style="background-color: var(--accent-blue-bg); color: var(--accent-blue)">EVENT ARB</span>';
            else if (rLow.includes('[dip buyer]')) srcBadge = '<span class="px-1 py-0.2 rounded text-[9px] font-bold badge-buy">DIP BUY</span>';
            else if (rLow.includes('[auto rule]')) srcBadge = '<span class="px-1 py-0.2 rounded text-[9px] font-bold badge-blue">RULE</span>';
            else if (l.mode === 'MANUAL') srcBadge = '<span class="px-1 py-0.2 rounded text-[9px] font-bold badge-buy">MANUAL</span>';
            else if (rLow.includes('[alpha') || rLow.includes('quant')) srcBadge = '<span class="px-1 py-0.2 rounded text-[9px] font-bold badge-blue">QUANT AI</span>';

            div.className = 'border-b pb-1 flex items-start gap-1.5';
            div.style.borderColor = 'var(--border-subtle)';
            div.innerHTML = `
              <span class="text-dim font-mono">[${l.time}]</span>
              <strong class="font-mono text-title">${l.ticker}</strong>
              ${srcBadge}
              <span class="${statusColor}">${l.action}</span>
              <span class="text-muted flex-1 truncate" title="${l.reason || ''}">${l.reason || ''}</span>
              <span class="text-[10px] text-dim">${l.status}</span>
            `;
            if (logContainer.children.length > 0 && logContainer.children[0].classList.contains('italic')) {
              logContainer.innerHTML = '';
            }
            logContainer.prepend(div);
          }
        });
      }
    }

    function onStopLossSliderChange(v) {
      document.getElementById('stopLossVal').innerText = `${v}%`;
      saveSettings();
    }

    function onMinProfitSliderChange(v) {
      document.getElementById('minProfitVal').innerText = `${v}%`;
      saveSettings();
    }

    function onTechSliderChange(v) {
      document.getElementById('techTargetVal').innerText = `$${v}`;
      saveSettings();
    }

    function onMaxPosChange(v) {
      document.getElementById('maxPosVal').innerText = v;
      saveSettings();
    }

    function toggleStopLoss() {
      const btn = document.getElementById('stopLossToggleBtn');
      const isAct = (btn.innerText === 'ACTIVE');
      btn.innerText = isAct ? 'INACTIVE' : 'ACTIVE';
      btn.className = isAct ? 'text-[11px] font-mono px-1.5 py-0.2 rounded badge-neutral' : 'text-[11px] font-mono px-1.5 py-0.2 rounded badge-buy font-semibold';
      saveSettings();
    }

    function toggleMinProfit() {
      const btn = document.getElementById('minProfitToggleBtn');
      const isAct = (btn.innerText === 'ACTIVE');
      btn.innerText = isAct ? 'INACTIVE' : 'ACTIVE';
      btn.className = isAct ? 'text-[11px] font-mono px-1.5 py-0.2 rounded badge-neutral' : 'text-[11px] font-mono px-1.5 py-0.2 rounded badge-buy font-semibold';
      saveSettings();
    }

    function applySettingsToUI(s) {
      if (!s) return;
      if (s.stop_loss_pct !== undefined) {
        document.getElementById('stopLossSlider').value = s.stop_loss_pct;
        document.getElementById('stopLossVal').innerText = `${s.stop_loss_pct}%`;
      }
      if (s.min_profit_pct !== undefined) {
        document.getElementById('minProfitSlider').value = s.min_profit_pct;
        document.getElementById('minProfitVal').innerText = `${s.min_profit_pct}%`;
      }
      if (s.tech_target_x !== undefined) {
        document.getElementById('techTargetSlider').value = s.tech_target_x;
        document.getElementById('techTargetVal').innerText = `$${s.tech_target_x}`;
      }
      if (s.max_positions !== undefined) {
        document.getElementById('maxPosSlider').value = s.max_positions;
        document.getElementById('maxPosVal').innerText = s.max_positions;
      }
      if (s.auto_time_limit_hours !== undefined) {
        document.getElementById('autoTimeLimit').value = s.auto_time_limit_hours;
      }
      if (s.stop_loss_enabled !== undefined) {
        const btn = document.getElementById('stopLossToggleBtn');
        btn.innerText = s.stop_loss_enabled ? 'ACTIVE' : 'INACTIVE';
        btn.className = s.stop_loss_enabled ? 'text-[11px] font-mono px-1.5 py-0.2 rounded badge-buy font-semibold' : 'text-[11px] font-mono px-1.5 py-0.2 rounded badge-neutral';
      }
      if (s.take_profit_enabled !== undefined) {
        const btn = document.getElementById('minProfitToggleBtn');
        btn.innerText = s.take_profit_enabled ? 'ACTIVE' : 'INACTIVE';
        btn.className = s.take_profit_enabled ? 'text-[11px] font-mono px-1.5 py-0.2 rounded badge-buy font-semibold' : 'text-[11px] font-mono px-1.5 py-0.2 rounded badge-neutral';
      }
      if (s.background_tracking !== undefined) {
        document.getElementById('bgTrackingCheck').checked = Boolean(s.background_tracking);
      }
      if (s.close_to_tray !== undefined) {
        document.getElementById('closeToTrayCheck').checked = Boolean(s.close_to_tray);
      }
      if (s.theme) {
        applyTheme(s.theme);
      }
    }

    function saveSettings() {
      const payload = {
        max_positions: parseInt(document.getElementById('maxPosSlider').value, 10),
        stop_loss_enabled: (document.getElementById('stopLossToggleBtn').innerText === 'ACTIVE'),
        stop_loss_pct: parseFloat(document.getElementById('stopLossSlider').value),
        take_profit_enabled: (document.getElementById('minProfitToggleBtn').innerText === 'ACTIVE'),
        min_profit_pct: parseFloat(document.getElementById('minProfitSlider').value),
        auto_time_limit_hours: parseFloat(document.getElementById('autoTimeLimit').value),
        tech_target_x: parseFloat(document.getElementById('techTargetSlider').value),
        max_alloc_pct: globalTradeSizePct,
        background_tracking: document.getElementById('bgTrackingCheck').checked,
        close_to_tray: document.getElementById('closeToTrayCheck').checked,
        theme: currentTheme
      };

      fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') showTradeToast('Settings saved', 'info');
      })
      .catch(err => console.log('Settings save error:', err));
    }

    function toggleMode() {
      fetch('/api/toggle_mode', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        playAudioTone(data.mode === 'AUTO' ? 880 : 440, 0.15);
        showTradeToast(`Operating Mode: ${data.mode}`, 'info');
      });
    }

    function toggleAchievements() {
      fetch('/api/toggle_achievements', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        showTradeToast(`Achievements Hunter ${data.achievements_enabled ? 'ENGAGED' : 'DISENGAGED'}`, 'info');
      });
    }

    function liquidateAll() {
      if (confirm('CONFIRM IMMEDIATE LIQUIDATION: Liquidate all open positions to 100% Cash?')) {
        playAudioTone(300, 0.3, 'sawtooth');
        fetch('/api/liquidate', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
          showTradeToast(`Liquidated ${data.closed_positions || 0} open positions to 100% Cash`, 'success');
          refreshPortfolio();
        })
        .catch(err => showTradeToast(`Liquidation failed: ${err}`, 'error'));
      }
    }

    // Keyboard Hotkeys: M = Mode Toggle, A = Achievements, 1-7 = Switch Tab
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      if (e.key === 'm' || e.key === 'M') {
        e.preventDefault();
        toggleMode();
      } else if (e.key === 'a' || e.key === 'A') {
        e.preventDefault();
        toggleAchievements();
      } else if (e.key >= '1' && e.key <= '7') {
        const tabs = ['tab-main', 'tab-news', 'tab-auto', 'tab-portfolio', 'tab-stats', 'tab-skins', 'tab-settings'];
        const idx = parseInt(e.key, 10) - 1;
        if (tabs[idx]) switchTab(tabs[idx]);
      }
    });

    // Startup Initializer
    window.addEventListener('DOMContentLoaded', () => {
      applyTheme(currentTheme);
      initChart();
      connectWS();
      setCategoryFilter('ALL');

      // Immediate settings restoration from API
      fetch('/api/status')
        .then(res => res.json())
        .then(data => {
          if (data.settings) applySettingsToUI(data.settings);
          updateDashboard(data);
        })
        .catch(err => console.log('Init status fetch:', err));
    });
  </script>
</body>
</html>
"""
