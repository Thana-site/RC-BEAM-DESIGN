"""
RC Section Visualizer — Styling & Configurations
Streamlit CSS Styles, Headers, and Markup Configurations
"""

# Custom CSS for Streamlit App Styling
CUSTOM_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;500;600;700;800&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .stApp { background: #0b0d14; color: #e8eaf0; }

  /* ─── Scrollbar ───────────────────────────────────────────────────────── */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: #0b0d14; }
  ::-webkit-scrollbar-thumb { background: #2a3050; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #3a4a70; }

  /* ─── App Header — Glassmorphism ──────────────────────────────────────── */
  .app-header {
    background: linear-gradient(135deg, rgba(26,29,46,0.85) 0%, rgba(22,33,62,0.85) 100%);
    backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(96,165,250,0.15);
    border-radius: 12px;
    padding: 12px 22px; margin-bottom: 14px;
    display: flex; align-items: center; gap: 14px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04);
    position: relative; overflow: hidden;
  }
  .app-header::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(96,165,250,0.3), rgba(167,139,250,0.3), transparent);
  }
  .app-header h1 {
    font-size: 1.35rem; font-weight: 800; letter-spacing: -0.02em;
    background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #f472b6 100%);
    background-size: 200% 200%;
    animation: gradientShift 4s ease infinite;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0;
  }
  @keyframes gradientShift {
    0%, 100% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
  }
  .app-header p { color: #7c8db5; margin: 2px 0 0; font-size: 0.78rem; font-weight: 400; letter-spacing: 0.02em; }
  .app-header .version-tag {
    position: absolute; top: 10px; right: 16px;
    font-size: 0.62rem; color: #4a5580; letter-spacing: 1px; font-weight: 600;
  }

  /* ─── Metric Cards — Glass + Hover ────────────────────────────────────── */
  .metric-card {
    background: linear-gradient(145deg, rgba(26,29,46,0.8) 0%, rgba(19,21,31,0.9) 100%);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(42,48,80,0.6); border-radius: 10px;
    padding: 10px 14px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative; overflow: hidden;
  }
  .metric-card::after {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, rgba(96,165,250,0.4), transparent);
    opacity: 0; transition: opacity 0.3s ease;
  }
  .metric-card:hover {
    transform: translateY(-2px);
    border-color: rgba(96,165,250,0.3);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3), 0 0 0 1px rgba(96,165,250,0.1);
  }
  .metric-card:hover::after { opacity: 1; }
  .metric-label {
    font-size: 0.62rem; color: #5a6a8a; text-transform: uppercase;
    letter-spacing: 1px; margin-bottom: 4px; font-weight: 700;
  }
  .metric-value {
    font-family: 'JetBrains Mono', monospace; font-size: 1.05rem;
    font-weight: 700; color: #e8eaf0;
  }
  .metric-unit { font-size: 0.62rem; color: #5a6a8a; margin-left: 4px; font-weight: 500; }

  /* ─── Section Tags — Animated ─────────────────────────────────────────── */
  .section-tag {
    display: inline-flex; align-items: center; gap: 4px;
    max-width: 100%; white-space: normal; overflow-wrap: anywhere;
    background: linear-gradient(135deg, rgba(30,45,74,0.7) 0%, rgba(26,29,46,0.7) 100%);
    backdrop-filter: blur(4px);
    color: #60a5fa;
    border: 1px solid rgba(42,74,127,0.4); border-radius: 6px;
    padding: 3px 10px; font-size: 0.65rem; font-weight: 700;
    letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 6px;
    transition: all 0.2s ease;
    border-left: 3px solid #60a5fa;
  }
  .section-tag:hover {
    border-color: rgba(96,165,250,0.6);
    background: linear-gradient(135deg, rgba(30,45,74,0.9) 0%, rgba(26,29,46,0.9) 100%);
    transform: translateX(2px);
  }

  /* ─── Sidebar — Premium Dark ──────────────────────────────────────────── */
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d0f18 0%, #111320 100%) !important;
    border-right: 1px solid rgba(42,48,80,0.4) !important;
  }
  [data-testid="stSidebar"] label {
    color: #8a9bc0 !important; font-size: 0.78rem !important;
    font-weight: 500 !important; letter-spacing: 0.02em !important;
  }
  [data-testid="stSidebar"] .stNumberInput input {
    font-size: 0.82rem !important; padding: 4px 10px !important;
    background: rgba(19,21,31,0.6) !important;
    border: 1px solid rgba(42,48,80,0.5) !important;
    border-radius: 6px !important;
    transition: border-color 0.2s ease !important;
  }
  [data-testid="stSidebar"] .stNumberInput input:focus {
    border-color: rgba(96,165,250,0.5) !important;
    box-shadow: 0 0 0 2px rgba(96,165,250,0.1) !important;
  }
  [data-testid="stSidebar"] .stSelectbox > div > div {
    background: rgba(19,21,31,0.6) !important;
    border: 1px solid rgba(42,48,80,0.5) !important;
    border-radius: 6px !important;
  }

  /* ─── Sidebar Section Cards ───────────────────────────────────────────── */
  .sidebar-section {
    background: linear-gradient(145deg, rgba(19,21,31,0.5) 0%, rgba(13,15,24,0.5) 100%);
    border: 1px solid rgba(42,48,80,0.3); border-radius: 8px;
    padding: 10px 12px; margin-bottom: 8px;
  }
  .sidebar-section-title {
    font-size: 0.68rem; font-weight: 700; color: #60a5fa;
    text-transform: uppercase; letter-spacing: 1.2px;
    margin-bottom: 8px; padding-bottom: 4px;
    border-bottom: 1px solid rgba(42,48,80,0.3);
    display: flex; align-items: center; gap: 6px;
  }
  .sidebar-section-title .icon { font-size: 0.85rem; }

  /* ─── Slider Styling ──────────────────────────────────────────────────── */
  .stSlider > div > div > div { background: #2a3050 !important; }

  /* ─── Data Editor ─────────────────────────────────────────────────────── */
  [data-testid="stDataEditor"] {
    border: 1px solid rgba(42,48,80,0.5) !important;
    border-radius: 10px; overflow: hidden;
    box-shadow: 0 2px 12px rgba(0,0,0,0.2);
  }

  /* ─── Buttons — Gradient + Glow ───────────────────────────────────────── */
  .stButton > button {
    background: linear-gradient(135deg, #3b4fd8 0%, #6c40cc 100%);
    color: white; border: none; border-radius: 8px;
    padding: 0.35rem 0.9rem; font-weight: 600; font-size: 0.78rem;
    letter-spacing: 0.4px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    width: 100%; position: relative; overflow: hidden;
    box-shadow: 0 2px 8px rgba(59,79,216,0.25);
  }
  .stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(59,79,216,0.4), 0 0 0 1px rgba(108,64,204,0.3);
    background: linear-gradient(135deg, #4a5ee8 0%, #7c50dc 100%);
  }
  .stButton > button:active { transform: translateY(0); }

  /* ─── Tabs — Glow Underline ───────────────────────────────────────────── */
  .stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: rgba(13,15,24,0.5);
    border-radius: 10px;
    padding: 4px;
    border: 1px solid rgba(42,48,80,0.3);
  }
  .stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    padding: 6px 16px !important;
    font-weight: 500 !important;
    font-size: 0.82rem !important;
    color: #7c8db5 !important;
    transition: all 0.3s ease !important;
    border: none !important;
  }
  .stTabs [data-baseweb="tab"]:hover {
    color: #c8d0e8 !important;
    background: rgba(42,48,80,0.3) !important;
  }
  .stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(59,79,216,0.15) 0%, rgba(108,64,204,0.15) 100%) !important;
    color: #e8eaf0 !important;
    font-weight: 600 !important;
    box-shadow: 0 0 12px rgba(96,165,250,0.1) !important;
  }
  .stTabs [data-baseweb="tab-highlight"] {
    background: linear-gradient(90deg, #3b4fd8, #a78bfa) !important;
    height: 2px !important;
    border-radius: 2px !important;
  }
  .stTabs [data-baseweb="tab-border"] {
    display: none !important;
  }

  /* ─── Info Box — Glass ────────────────────────────────────────────────── */
  .info-box {
    background: linear-gradient(135deg, rgba(26,29,46,0.7) 0%, rgba(19,21,31,0.7) 100%);
    backdrop-filter: blur(4px);
    border-left: 3px solid #60a5fa;
    border-radius: 0 8px 8px 0; padding: 8px 12px;
    font-size: 0.76rem; color: #a0aec0; margin-top: 6px;
    border: 1px solid rgba(42,48,80,0.3);
    border-left: 3px solid #60a5fa;
    overflow-wrap: anywhere;
  }
  .info-box b { color: #60a5fa; }

  .warn-box, .tmpl-box, .metric-card, .glass-card {
    overflow-wrap: anywhere;
  }
  [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
    margin-bottom: 12px;
  }
  [data-testid="stPlotlyChart"] {
    margin: 8px 0 14px;
    overflow: hidden;
  }
  [data-testid="stDataFrame"] {
    margin: 6px 0 12px;
  }

  /* ─── Warning Box ─────────────────────────────────────────────────────── */
  .warn-box {
    background: linear-gradient(135deg, rgba(30,26,16,0.7) 0%, rgba(26,22,12,0.7) 100%);
    backdrop-filter: blur(4px);
    border-left: 3px solid #f59e0b;
    border-radius: 0 8px 8px 0; padding: 8px 12px;
    font-size: 0.76rem; color: #d4a017; margin: 4px 0;
    border: 1px solid rgba(42,48,80,0.3);
    border-left: 3px solid #f59e0b;
  }

  /* ─── Template Box ────────────────────────────────────────────────────── */
  .tmpl-box {
    background: linear-gradient(135deg, rgba(26,29,46,0.7) 0%, rgba(19,21,31,0.7) 100%);
    backdrop-filter: blur(4px);
    border-left: 3px solid #a78bfa;
    border-radius: 0 8px 8px 0; padding: 8px 12px;
    font-size: 0.76rem; color: #c4b5fd; margin-top: 6px;
    border: 1px solid rgba(42,48,80,0.3);
    border-left: 3px solid #a78bfa;
  }
  .tmpl-box b { color: #a78bfa; }

  /* ─── Capacity Status Badges ──────────────────────────────────────────── */
  .capacity-badge {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 16px; border-radius: 8px;
    font-family: 'JetBrains Mono', monospace; font-size: 0.88rem;
    font-weight: 700; letter-spacing: 0.02em;
    backdrop-filter: blur(8px);
  }
  .capacity-badge.tension-controlled {
    background: linear-gradient(135deg, rgba(74,222,128,0.12) 0%, rgba(52,211,153,0.08) 100%);
    color: #4ade80; border: 1px solid rgba(74,222,128,0.3);
  }
  .capacity-badge.transition {
    background: linear-gradient(135deg, rgba(251,191,36,0.12) 0%, rgba(245,158,11,0.08) 100%);
    color: #fbbf24; border: 1px solid rgba(251,191,36,0.3);
  }
  .capacity-badge.compression-controlled {
    background: linear-gradient(135deg, rgba(248,113,113,0.12) 0%, rgba(239,68,68,0.08) 100%);
    color: #f87171; border: 1px solid rgba(248,113,113,0.3);
  }

  /* ─── Phi Factor Bar ──────────────────────────────────────────────────── */
  .phi-bar-container {
    background: rgba(19,21,31,0.6); border-radius: 8px;
    padding: 8px 14px; margin: 6px 0;
    border: 1px solid rgba(42,48,80,0.3);
  }
  .phi-bar-track {
    width: 100%; height: 6px; border-radius: 3px;
    background: linear-gradient(90deg, #f87171 0%, #fbbf24 40%, #4ade80 100%);
    position: relative; margin: 8px 0 4px;
  }
  .phi-bar-marker {
    position: absolute; top: -5px;
    width: 3px; height: 16px; border-radius: 2px;
    background: #e8eaf0; transform: translateX(-50%);
    box-shadow: 0 0 6px rgba(232,234,240,0.5);
  }
  .phi-bar-labels {
    display: flex; justify-content: space-between;
    font-size: 0.62rem; color: #5a6a8a;
    font-family: 'JetBrains Mono', monospace;
  }

  /* ─── Glass Card (generic) ────────────────────────────────────────────── */
  .glass-card {
    background: linear-gradient(145deg, rgba(26,29,46,0.7) 0%, rgba(19,21,31,0.8) 100%);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(42,48,80,0.4); border-radius: 10px;
    padding: 12px 16px; margin-bottom: 8px;
    transition: border-color 0.3s ease;
  }
  .glass-card:hover { border-color: rgba(96,165,250,0.25); }
  .glass-card-title {
    font-size: 0.68rem; font-weight: 700; color: #7c8db5;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;
  }

  /* ─── Status Dot ──────────────────────────────────────────────────────── */
  .status-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: #4ade80; display: inline-block;
    animation: pulse 2s ease-in-out infinite;
    margin-right: 4px;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(74,222,128,0.4); }
    50% { opacity: 0.7; box-shadow: 0 0 0 4px rgba(74,222,128,0); }
  }

  /* ─── Divider Override ────────────────────────────────────────────────── */
  hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, rgba(42,48,80,0.5), transparent) !important;
    margin: 10px 0 !important;
  }

  /* ─── Expander Styling ────────────────────────────────────────────────── */
  .streamlit-expanderHeader {
    background: rgba(19,21,31,0.4) !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: #a0aec0 !important;
  }

  /* ─── Preset Chip Buttons ─────────────────────────────────────────────── */
  .preset-chip {
    display: inline-block;
    background: rgba(42,48,80,0.3); border: 1px solid rgba(42,48,80,0.4);
    border-radius: 20px; padding: 2px 10px;
    font-size: 0.68rem; color: #8a9bc0; font-weight: 500;
    cursor: pointer; transition: all 0.2s ease; margin: 2px;
  }
  .preset-chip:hover {
    background: rgba(96,165,250,0.15); border-color: rgba(96,165,250,0.3);
    color: #60a5fa;
  }

  /* ─── Unit Pill Badge ─────────────────────────────────────────────────── */
  .unit-pill {
    display: inline-block; padding: 1px 8px;
    border-radius: 12px; font-size: 0.68rem;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600; margin-left: 2px;
  }
  .unit-pill.ksc { background: rgba(251,146,60,0.15); color: #fb923c; border: 1px solid rgba(251,146,60,0.25); }
  .unit-pill.mpa { background: rgba(96,165,250,0.15); color: #60a5fa; border: 1px solid rgba(96,165,250,0.25); }

  /* ─── Conditional Color Helpers ───────────────────────────────────────── */
  .val-green { color: #4ade80 !important; }
  .val-yellow { color: #fbbf24 !important; }
  .val-red { color: #f87171 !important; }
  .val-blue { color: #60a5fa !important; }
  .val-purple { color: #a78bfa !important; }
</style>
"""

# Header HTML Component
HEADER_HTML = """
<div class="app-header">
  <span style="font-size:1.7rem">🏗️</span>
  <div>
    <h1>RC Section Visualizer</h1>
    <p><span class="status-dot"></span>Int · Mid · Ext Section Manager — MKS (kgf · ksc · mm)</p>
  </div>
  <span class="version-tag">ACI 318 / TIS</span>
</div>
"""

# Footer HTML Component
FOOTER_HTML = """
<div style="text-align:center;margin-top:20px;padding:14px 0 10px;
  border-top:1px solid rgba(42,48,80,0.3);
  background: linear-gradient(180deg, transparent, rgba(13,15,24,0.5));">
  <span style="font-size:0.72rem;color:#3a4060;letter-spacing:0.5px;">
    RC Section Visualizer — ACI 318-19 / TIS 1008
    &nbsp;·&nbsp;
    <span style="color:#4a5580">MKS: kgf · ksc · mm</span>
  </span>
</div>
"""

# Style for Tab 2 Analysis Method Expander
ANALYSIS_METHOD_STYLE = """
<style>
.am { font-size:0.82rem; color:#c8d0e8; line-height:1.75; }
.am b { color:#60a5fa; }
.am code { background:rgba(26,29,46,0.8); color:#fbbf24; padding:2px 7px;
            border-radius:4px; font-family:'JetBrains Mono',monospace; font-size:0.78rem;
            border: 1px solid rgba(42,48,80,0.3); }
.am h4 { color:#a78bfa; font-size:0.80rem; letter-spacing:0.8px;
          text-transform:uppercase; margin:14px 0 6px;
          border-bottom:1px solid rgba(42,48,80,0.4); padding-bottom:4px;
          display: flex; align-items: center; gap: 6px; }
.am h4::before {
  content: ''; display: inline-block; width: 3px; height: 14px;
  background: linear-gradient(180deg, #a78bfa, #60a5fa); border-radius: 2px;
}
.am ul { padding-left: 16px; }
.am li { margin: 3px 0; }
.am li::marker { color: #4a5580; }
</style>
"""

# Style for Tab 4 Notation View
NOTATION_STYLE = """
<style>
.nt { display:grid; grid-template-columns:140px 1fr; gap:4px 16px; margin-bottom:8px; }
.nt-sym { font-family:'JetBrains Mono',monospace; color:#60a5fa; font-size:0.92rem;
          font-weight:700; padding:6px 10px;
          background: linear-gradient(135deg, rgba(26,29,46,0.8) 0%, rgba(19,21,31,0.8) 100%);
          border:1px solid rgba(42,48,80,0.4); border-radius:6px;
          transition: all 0.2s ease; }
.nt-sym:hover {
  border-color: rgba(96,165,250,0.4);
  background: linear-gradient(135deg, rgba(26,29,46,1) 0%, rgba(19,21,31,1) 100%);
}
.nt-def { color:#c8d0e8; font-size:0.85rem; padding:6px 0; align-self:center; }
.nt-head { grid-column:1/-1; color:#a78bfa; font-size:0.72rem; font-weight:700;
           letter-spacing:1.2px; text-transform:uppercase;
           border-bottom:1px solid rgba(42,48,80,0.4); padding-bottom:4px; margin:14px 0 6px;
           display: flex; align-items: center; gap: 6px; }
.nt-head::before {
  content: ''; display: inline-block; width: 3px; height: 12px;
  background: linear-gradient(180deg, #a78bfa, #60a5fa); border-radius: 2px;
}
</style>
"""

# Style for Tab 4 Variable Reference View
VARIABLE_REF_STYLE = """
<style>
.vr { width:100%; border-collapse:collapse; font-size:0.82rem; margin-bottom:18px; }
.vr th { background: linear-gradient(135deg, rgba(26,29,46,0.9) 0%, rgba(19,21,31,0.9) 100%);
         color:#5a6a8a; text-align:left; padding:8px 12px;
         font-size:0.70rem; text-transform:uppercase; letter-spacing:0.8px;
         border-bottom:2px solid rgba(42,48,80,0.5); position: sticky; top: 0; }
.vr td { padding:6px 12px; border-bottom:1px solid rgba(30,34,53,0.6); vertical-align:top;
         transition: background 0.2s ease; }
.vr tr:hover td { background: rgba(26,29,46,0.5); }
.vr .vname { font-family:'JetBrains Mono',monospace; color:#60a5fa; white-space:nowrap; }
.vr .vval  { font-family:'JetBrains Mono',monospace; color:#fbbf24; font-size:0.75rem; }
.vr .vdesc { color:#c8d0e8; }
.vr .vunit { color:#5a6a8a; font-size:0.75rem; }
.vr-head { color:#a78bfa; font-size:0.72rem; font-weight:700; letter-spacing:1.2px;
           text-transform:uppercase; padding:12px 0 6px;
           border-bottom:1px solid rgba(42,48,80,0.4); margin:12px 0 8px; }
</style>
"""
