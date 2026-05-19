import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { ComposedChart, BarChart, LineChart, Bar, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import './App.css';

const API_BASE =
  process.env.REACT_APP_API_URL ||
  'https://enso-intelligence-platform.onrender.com';

const mockChartData = [
  { month: 'Oct 25', mei: -1.19 },
  { month: 'Nov 25', mei: -1.06 },
  { month: 'Dec 25', mei: -0.77 },
  { month: 'Jan 26', mei: -0.76 },
  { month: 'Feb 26', mei: -0.95 },
  { month: 'Mar 26', mei: -1.03 },
];

const COMMODITY_META = {
  wheat:       { icon: '🌾', label: 'Wheat' },
  crude_oil:   { icon: '🛢️', label: 'Crude Oil' },
  soybean:     { icon: '🫘', label: 'Soybean' },
  corn:        { icon: '🌽', label: 'Corn' },
  natural_gas: { icon: '🔥', label: 'Natural Gas' },
  coffee:      { icon: '☕', label: 'Coffee' },
  sugar:       { icon: '🍬', label: 'Sugar' },
  cotton:      { icon: '🤍', label: 'Cotton' },
};

// ── Count-up animation hook ───────────────────────────────────────────────────
function useCountUp(target, duration = 1100) {
  const [val, setVal] = useState(0);
  const rafRef = useRef(null);
  useEffect(() => {
    if (typeof target !== 'number') return;
    const start = performance.now();
    const from = 0;
    const tick = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setVal(+(from + (target - from) * eased).toFixed(2));
      if (progress < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);
  return val;
}

// ── Ocean particle background ─────────────────────────────────────────────────
function OceanBackground({ phase }) {
  const canvasRef = useRef(null);
  const mouseRef = useRef({ x: -9999, y: -9999 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;

    const isLaNina = phase?.toLowerCase().includes('nina');
    const isElNino = phase?.toLowerCase().includes('nino') || phase?.toLowerCase().includes('niño');
    // La Niña → cool ocean blue, El Niño → warm amber, Neutral → sea green
    const base = isLaNina ? [30, 160, 255] : isElNino ? [255, 110, 30] : [0, 210, 180];

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();

    const count = Math.min(Math.floor((canvas.width * canvas.height) / 14000), 140);
    const particles = Array.from({ length: count }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 2.2 + 0.4,
      vx: (Math.random() - 0.5) * 0.4,
      vy: -(Math.random() * 0.35 + 0.05),
      opacity: Math.random() * 0.35 + 0.05,
      phase: Math.random() * Math.PI * 2,
    }));

    let frame = 0;
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      frame++;
      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;

      for (const p of particles) {
        const wobble = Math.sin(frame * 0.008 + p.phase) * 0.25;
        const dx = p.x - mx, dy = p.y - my;
        const dist = Math.sqrt(dx * dx + dy * dy);
        let pushX = 0, pushY = 0;
        if (dist < 100 && dist > 0) {
          const f = ((100 - dist) / 100) * 0.9;
          pushX = (dx / dist) * f;
          pushY = (dy / dist) * f;
        }
        p.x += p.vx + wobble + pushX;
        p.y += p.vy + pushY;
        if (p.y < -6)               { p.y = canvas.height + 6; p.x = Math.random() * canvas.width; }
        if (p.x < -6)                p.x = canvas.width + 6;
        if (p.x > canvas.width + 6)  p.x = -6;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${base[0]},${base[1]},${base[2]},${p.opacity})`;
        ctx.fill();
      }
      animId = requestAnimationFrame(draw);
    };
    draw();

    const onMouse = (e) => { mouseRef.current = { x: e.clientX, y: e.clientY }; };
    const onLeave = ()  => { mouseRef.current = { x: -9999, y: -9999 }; };
    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', onMouse);
    window.addEventListener('mouseleave', onLeave);
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', onMouse);
      window.removeEventListener('mouseleave', onLeave);
    };
  }, [phase]);

  return <canvas ref={canvasRef} style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }} />;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function getTimeAgo(date) {
  if (!date) return null;
  const mins = Math.floor((Date.now() - date.getTime()) / 60000);
  if (mins < 1) return 'Just now';
  if (mins === 1) return '1 min ago';
  if (mins < 60) return `${mins} min ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

function getDomain(url) {
  try { return new URL(url).hostname.replace('www.', ''); }
  catch { return null; }
}

function getRelativeDate(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  if (isNaN(d)) return null;
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function polarPoint(cx, cy, r, angleDeg) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

// ── Risk Gauge ────────────────────────────────────────────────────────────────
function RiskGauge({ score, max = 10 }) {
  const CX = 80, CY = 76, R = 56;
  const pct = Math.min(Math.max(score / max, 0), 1);
  const safeAngle = pct > 0.999 ? 359.4 : 180 + pct * 180;
  const ep = polarPoint(CX, CY, R, safeAngle);
  const np = polarPoint(CX, CY, R * 0.2, safeAngle);
  const color = score >= 7 ? '#ff4466' : score >= 4 ? '#f59e0b' : '#00e5a0';
  const trackD = `M ${CX - R},${CY} A ${R},${R} 0 0,1 ${CX + R},${CY}`;
  const fillD = pct < 0.001
    ? null
    : `M ${CX - R},${CY} A ${R},${R} 0 0,1 ${ep.x.toFixed(2)},${ep.y.toFixed(2)}`;

  return (
    <svg viewBox="0 0 160 98" style={{ width: '100%', maxWidth: 190, display: 'block', margin: '0 auto' }}>
      <defs>
        <filter id="gg" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="3" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      {/* Track */}
      <path d={trackD} fill="none" stroke="rgba(100,116,139,0.15)" strokeWidth="10" strokeLinecap="round"/>
      {/* Zone ticks */}
      {[0,1,2,3,4,5,6,7,8,9,10].map(v => {
        const a = 180 + (v / 10) * 180;
        const p1 = polarPoint(CX, CY, R + 5, a);
        const p2 = polarPoint(CX, CY, R + 11, a);
        const c = v <= 3 ? '#00e5a0' : v <= 6 ? '#f59e0b' : '#ff4466';
        return <line key={v} x1={p1.x.toFixed(1)} y1={p1.y.toFixed(1)} x2={p2.x.toFixed(1)} y2={p2.y.toFixed(1)} stroke={c} strokeWidth="1.5" opacity="0.55" strokeLinecap="round"/>;
      })}
      {/* Fill arc */}
      {fillD && <path d={fillD} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round" filter="url(#gg)"/>}
      {/* Needle */}
      {pct > 0 && <line x1={np.x.toFixed(2)} y1={np.y.toFixed(2)} x2={ep.x.toFixed(2)} y2={ep.y.toFixed(2)} stroke="white" strokeWidth="2" strokeLinecap="round" opacity="0.85"/>}
      {/* Hub */}
      <circle cx={CX} cy={CY} r="4" fill="#0a0e27" stroke="rgba(100,116,139,0.5)" strokeWidth="1.5"/>
      {/* Text */}
      <text x={CX} y={CY + 18} textAnchor="middle" fill={color} fontSize="28" fontWeight="800" fontFamily="-apple-system,sans-serif">{score}</text>
      <text x={CX} y={CY + 30} textAnchor="middle" fill="#475569" fontSize="9" letterSpacing="1.5" fontFamily="-apple-system,sans-serif">/ 10 RISK</text>
      <text x={CX - R - 4} y={CY + 14} textAnchor="middle" fill="#475569" fontSize="8">0</text>
      <text x={CX + R + 4} y={CY + 14} textAnchor="middle" fill="#475569" fontSize="8">10</text>
    </svg>
  );
}

// ── Mini Sparkline ────────────────────────────────────────────────────────────
function MiniSparkline({ data, color = '#0ea5e9' }) {
  if (!data || data.length < 2) return null;
  const W = 76, H = 26;
  const vals = data.map(d => (typeof d.mei === 'number' ? d.mei : 0));
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 0.1;
  const pts = vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * W;
    const y = H - 4 - ((v - min) / range) * (H - 8);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const last = pts[pts.length - 1].split(',');
  const delta = vals[vals.length - 1] - vals[vals.length - 2];
  const dc = delta >= 0 ? '#ef4444' : '#10b981';
  return (
    <div className="stat-sparkline">
      <svg width={W} height={H} style={{ overflow: 'visible', opacity: 0.8 }}>
        <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round"/>
        <circle cx={last[0]} cy={last[1]} r="2.5" fill={color}/>
      </svg>
      <span className="stat-delta" style={{ color: dc }}>
        {delta >= 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(2)}
      </span>
    </div>
  );
}

// ── Phase Timeline ────────────────────────────────────────────────────────────
function PhaseTimeline({ data, forecast }) {
  const hist = data || [];
  const fcast = forecast?.forecast?.slice(0, 9) || [];
  const all = [...hist, ...fcast];
  if (all.length === 0) return null;
  const histLen = hist.length;

  const segBg = (mei, isFc) => {
    const c = mei < -0.5 ? '59,130,246' : mei > 0.5 ? '239,68,68' : '107,114,128';
    const intensity = Math.min(0.9, 0.35 + Math.abs(mei) * 0.35);
    return `rgba(${c}, ${isFc ? intensity * 0.45 : intensity})`;
  };

  return (
    <div className="phase-timeline-card">
      <div className="phase-tl-header">
        <span className="phase-tl-title">PHASE HISTORY &amp; OUTLOOK</span>
        <div className="phase-tl-legend">
          <span className="tl-legend-item"><span className="tl-dot" style={{ background: '#3b82f6' }}/> La Niña</span>
          <span className="tl-legend-item"><span className="tl-dot" style={{ background: '#6b7280' }}/> Neutral</span>
          <span className="tl-legend-item"><span className="tl-dot" style={{ background: '#ef4444' }}/> El Niño</span>
          <span className="tl-legend-item tl-forecast-label">— Forecast</span>
        </div>
      </div>
      <div className="phase-tl-track">
        {all.map((d, i) => {
          const isFc = i >= histLen;
          const isNow = i === histLen - 1;
          return (
            <div
              key={i}
              className={`phase-tl-seg${isFc ? ' is-forecast' : ''}`}
              style={{ background: segBg(d.mei ?? 0, isFc) }}
              title={`${d.month}: MEI ${typeof d.mei === 'number' ? d.mei.toFixed(2) : '?'}`}
            >
              {isNow && <div className="tl-now-pin">▼</div>}
            </div>
          );
        })}
      </div>
      <div className="phase-tl-months">
        {all.map((d, i) => {
          const show = i === 0 || i % 4 === 0 || i === all.length - 1;
          return (
            <span key={i} className="phase-tl-month" style={{ opacity: show ? 1 : 0 }}>
              {show ? d.month : ''}
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ── App ───────────────────────────────────────────────────────────────────────
function App() {
  const [status,      setStatus]      = useState(null);
  const [report,      setReport]      = useState(null);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);
  const [running,     setRunning]     = useState(false);
  const [noData,      setNoData]      = useState(false);
  const [chartData,   setChartData]   = useState(mockChartData);
  const [forecast,    setForecast]    = useState(null);
  const [analytics,   setAnalytics]   = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchData = useCallback(() => {
    setLoading(true);
    setError(null);
    setNoData(false);

    Promise.all([
      axios.get(API_BASE + '/status'),
      axios.get(API_BASE + '/latest-report'),
      axios.get(API_BASE + '/mei-history').catch(() => null),
      axios.get(API_BASE + '/forecast').catch(() => null),
      axios.get(API_BASE + '/analytics').catch(() => null),
    ])
      .then(([s, r, h, f, a]) => {
        if (s.data?.status === 'no_data') {
          setNoData(true);
        } else {
          setStatus(s.data);
          setReport(r.data);
          if (h?.data && Array.isArray(h.data)) setChartData(h.data);
          else setChartData(mockChartData);
          if (f?.data && f.data.forecast) setForecast(f.data);
          if (a?.data && (a.data.status === 'success' || a.data.phase_probabilities)) setAnalytics(a.data);
          setLastUpdated(new Date());
        }
        setLoading(false);
      })
      .catch((err) => {
        if (err.response?.data?.status === 'no_data') setNoData(true);
        else setError(err.message || 'Could not reach backend');
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const triggerRunNow = async () => {
    setRunning(true);
    try {
      await axios.post(API_BASE + '/trigger');
      setTimeout(() => { fetchData(); setRunning(false); }, 3000);
    } catch (e) {
      console.error('trigger failed:', e);
      setRunning(false);
    }
  };

  // Hooks must be called before any early return (Rules of Hooks)
  const _rawRiskForHook = status?.risk_score ?? 0;
  const _riskForHook = _rawRiskForHook > 10 ? Math.round(_rawRiskForHook / 10) : _rawRiskForHook;
  const animatedMei  = useCountUp(typeof status?.mei_value === 'number' ? status.mei_value : 0);
  const animatedRisk = useCountUp(_riskForHook);

  // ── Loading ─────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="loading">
        <OceanBackground phase="neutral" />
        <div className="loading-inner">
          <div className="spinner"></div>
          <h2>Loading ENSO Intelligence Platform...</h2>
          <p style={{ color: '#64748b', fontSize: '0.85rem', marginTop: '0.5rem' }}>
            Connecting to {API_BASE}
          </p>
        </div>
      </div>
    );
  }

  if (noData) {
    return (
      <div className="loading">
        <div className="loading-inner">
          <h2 style={{ color: '#f59e0b' }}>No Report Yet</h2>
          <p style={{ color: '#94a3b8', margin: '1rem 0' }}>
            The pipeline hasn't run on this server instance.<br/>
            Click below to generate your first report.
          </p>
          <button onClick={triggerRunNow} disabled={running} className="download-btn"
            style={{ display: 'inline-block', cursor: running ? 'not-allowed' : 'pointer' }}>
            {running ? '⏳ Running pipeline…' : '▶ Run Pipeline Now'}
          </button>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="loading">
        <div className="loading-inner">
          <h2 style={{ color: '#ef4444' }}>Connection Error</h2>
          <p style={{ color: '#94a3b8', margin: '1rem 0', fontFamily: 'monospace', fontSize: '0.85rem' }}>{error}</p>
          <p style={{ color: '#64748b', fontSize: '0.8rem' }}>Backend: <code>{API_BASE}</code></p>
          <button onClick={fetchData} className="download-btn" style={{ display: 'inline-block', marginTop: '1rem' }}>Retry</button>
        </div>
      </div>
    );
  }

  // ── Derived values ───────────────────────────────────────────────────────────
  const phase      = status?.phase ?? 'Unknown';
  const phaseColor = phase.toLowerCase().includes('nina') ? '#00d4ff'
    : phase.toLowerCase().includes('nino') || phase.toLowerCase().includes('niño') ? '#ff4466'
    : '#6b7280';

  const phasePillStyle = phase.toLowerCase().includes('nina')
    ? { background: 'linear-gradient(135deg, #0369a1 0%, #0284c7 50%, #0ea5e9 100%)' }
    : phase.toLowerCase().includes('nino') || phase.toLowerCase().includes('niño')
      ? { background: 'linear-gradient(135deg, #7f1d1d 0%, #dc2626 50%, #ef4444 100%)' }
      : { background: 'linear-gradient(135deg, #374151 0%, #4b5563 50%, #6b7280 100%)' };

  // Normalize: LLM sometimes returns 0-100 scale instead of 0-10
  const rawRisk = status?.risk_score ?? 0;
  const riskScore = rawRisk > 10 ? Math.round(rawRisk / 10) : rawRisk;

  const market = report?.market_risks ?? {};

  const newsItems = report?.news_items?.length
    ? report.news_items
    : report?.news?.length
      ? report.news
      : [
          { title: 'El Niño may return by mid-2026 amid warming seas, says global weather body', source: 'BusinessLine' },
          { title: 'Brace yourself for a SUPER El Niño: Likelihood skyrockets', source: 'Daily Mail' },
          { title: 'How El Niño could impact world weather in 2026/27', source: 'Times of India' },
          { title: 'El Niño, Iran conflict heighten crude oil supply concerns', source: 'Crypto Briefing' },
        ];

  const forecastColor = forecast?.predicted_phase
    ? forecast.predicted_phase.toLowerCase().includes('nina') ? '#00d4ff'
      : forecast.predicted_phase.toLowerCase().includes('nino') ? '#ff4466'
      : '#64748b'
    : '#64748b';

  const riskChipClass = (level) => {
    const l = (level || '').toLowerCase();
    if (l === 'extreme') return 'extreme';
    if (l === 'high') return 'high';
    if (l === 'medium') return 'medium';
    if (l === 'low') return 'low';
    return 'unknown';
  };

  // ── Main dashboard ───────────────────────────────────────────────────────────
  return (
    <div className="app">
      <OceanBackground phase={phase} />

      {/* ── Ocean wave bottom strip ── */}
      <div className="ocean-wave-wrap">
        <svg viewBox="0 0 1200 90" preserveAspectRatio="none">
          <path d="M0,45 C200,80 400,10 600,45 C800,80 1000,10 1200,45 L1200,90 L0,90 Z" fill="rgba(0,200,255,0.12)"/>
        </svg>
        <svg viewBox="0 0 1200 90" preserveAspectRatio="none">
          <path d="M0,55 C300,15 500,75 750,40 C950,10 1100,65 1200,50 L1200,90 L0,90 Z" fill="rgba(0,180,235,0.08)"/>
        </svg>
      </div>

      {/* ── Header ── */}
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <span className="logo-icon">🌊</span>
            <div>
              <h1>ENSO INTELLIGENCE</h1>
              <p>AI-Powered Climate Risk Platform</p>
            </div>
          </div>
          <div className="header-right">
            {lastUpdated && (
              <span className="header-updated">SYS {getTimeAgo(lastUpdated)}</span>
            )}
            <button onClick={triggerRunNow} disabled={running} className="run-btn">
              {running ? '⏳ RUNNING…' : '▶ RUN NOW'}
            </button>
            <div className="live-badge">
              <span className="live-dot"></span>LIVE
            </div>
            <div className="phase-pill" style={phasePillStyle}>
              {phase}
            </div>
          </div>
        </div>
      </header>

      {/* ── Mission status strip ── */}
      <div className="mission-strip">
        <div className="ms-item">
          <span className="ms-label">Phase</span>
          <span className="ms-value" style={{ color: phaseColor === '#6b7280' ? '#64748b' : phaseColor }}>{phase.toUpperCase()}</span>
        </div>
        <div className="ms-divider"/>
        <div className="ms-item">
          <span className="ms-label">MEI Index</span>
          <span className="ms-value">{status?.mei_value != null ? (animatedMei >= 0 ? '+' : '') + animatedMei.toFixed(2) : '—'}</span>
        </div>
        <div className="ms-divider"/>
        <div className="ms-item">
          <span className="ms-label">Risk Level</span>
          <span className="ms-value" style={{ color: riskScore >= 7 ? '#ff4466' : riskScore >= 4 ? '#f59e0b' : '#00e5a0' }}>
            {riskScore >= 7 ? 'ELEVATED' : riskScore >= 4 ? 'MODERATE' : 'NOMINAL'} [{riskScore}/10]
          </span>
        </div>
        <div className="ms-divider"/>
        <div className="ms-item">
          <span className="ms-label">Trend</span>
          <span className="ms-value" style={{ color: '#64748b' }}>{status?.trend?.toUpperCase() ?? '—'}</span>
        </div>
        <div className="ms-divider"/>
        <div className="ms-item">
          <span className="ms-label">6M Forecast</span>
          <span className="ms-value" style={{ color: forecastColor }}>
            {forecast?.predicted_phase ? `${forecast.predicted_phase.toUpperCase()} ${forecast.confidence_pct}%` : '—'}
          </span>
        </div>
        <div className="ms-divider"/>
        <div className="ms-item">
          <span className="ms-label">Report Date</span>
          <span className="ms-value" style={{ color: '#64748b' }}>{status?.report_date ?? '—'}</span>
        </div>
      </div>

      {/* ── Stats row (5 cards) ── */}
      <div className="stats-row">
        <div className="stat-card">
          <span className="stat-label">MEI Index</span>
          <span className="stat-value glow-cyan">
            {status?.mei_value != null ? (animatedMei >= 0 ? '+' : '') + animatedMei.toFixed(2) : '-'}
          </span>
          <span className="stat-sub">Multivariate ENSO Index</span>
          <MiniSparkline data={chartData.slice(-8)} color="#00d4ff" />
        </div>

        <div className="stat-card">
          <span className="stat-label">Trend</span>
          <span className="stat-value sm" style={{ color: '#64748b', fontSize: '1.2rem' }}>
            {status?.trend ?? '-'}
          </span>
          <span className="stat-sub">Current direction</span>
        </div>

        <div className="stat-card">
          <span className="stat-label">Risk Score</span>
          <span className={`stat-value ${riskScore >= 7 ? 'glow-red' : riskScore >= 4 ? 'glow-amber' : 'glow-green'}`}>
            {status ? Math.round(animatedRisk) : '-'}
            <span style={{ fontSize: '1.1rem', fontWeight: 400, color: '#1e3a5f' }}>/10</span>
          </span>
          <span className="stat-sub">{riskScore >= 7 ? 'ELEVATED' : riskScore >= 4 ? 'MODERATE' : 'NOMINAL'}</span>
          <div className="stat-risk-bar">
            <div className="stat-risk-fill" style={{
              width: `${(riskScore / 10) * 100}%`,
              background: riskScore >= 7 ? '#ff4466' : riskScore >= 4 ? '#f59e0b' : '#00e5a0',
              boxShadow: `0 0 6px ${riskScore >= 7 ? '#ff4466' : riskScore >= 4 ? '#f59e0b' : '#00e5a0'}`
            }}/>
          </div>
        </div>

        <div className="stat-card">
          <span className="stat-label">Report Date</span>
          <span className="stat-value sm" style={{ color: '#334155' }}>
            {status?.report_date ?? '-'}
          </span>
          <span className="stat-sub">Last generated</span>
        </div>

        {forecast?.predicted_phase ? (
          <div className="stat-card">
            <span className="stat-label">6M Forecast</span>
            <span className="stat-value sm" style={{ color: forecastColor, fontSize: '1.1rem' }}>
              {forecast.predicted_phase}
            </span>
            <span className="stat-sub">{forecast.confidence_pct}% confidence</span>
            <div className="stat-risk-bar">
              <div className="stat-risk-fill" style={{ width: `${forecast.confidence_pct ?? 0}%`, background: forecastColor, boxShadow: `0 0 6px ${forecastColor}` }}/>
            </div>
          </div>
        ) : (
          <div className="stat-card" style={{ opacity: 0.35 }}>
            <span className="stat-label">6M Forecast</span>
            <span className="stat-value sm" style={{ color: '#334155' }}>—</span>
            <span className="stat-sub">No forecast yet</span>
          </div>
        )}
      </div>

      {/* ── Phase Timeline ── */}
      <PhaseTimeline data={chartData} forecast={forecast} />

      {/* ── MEI Chart (60%) + Commodity Risk Table (40%) ── */}
      <div className="grid-60-40">
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <h3>MEI Index Trend &amp; Forecast</h3>
            <span className="card-badge">{forecast ? '12MO HIST + 9MO FCST' : 'LAST 12 MONTHS'}</span>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart
              data={forecast ? [...(forecast.historical || []), ...(forecast.forecast || [])] : chartData}
              margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id="meiGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#00d4ff" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#00d4ff" stopOpacity={0.02}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="1 6" stroke="rgba(0,212,255,0.06)" vertical={false}/>
              <XAxis dataKey="month" stroke="#1e3a5f" fontSize={10} tick={{ fill: '#334155', fontFamily: 'Space Mono, monospace' }} axisLine={false} tickLine={false}/>
              <YAxis stroke="#1e3a5f" fontSize={10} domain={['auto', 'auto']} width={36} tick={{ fill: '#334155', fontFamily: 'Space Mono, monospace' }} axisLine={false} tickLine={false}/>
              <ReferenceLine y={0.5}  stroke="rgba(255,68,102,0.5)"  strokeDasharray="4 4" strokeWidth={1} label={{ value: 'EL NIÑO', fill: 'rgba(255,68,102,0.5)', fontSize: 8, fontFamily: 'Space Mono' }}/>
              <ReferenceLine y={-0.5} stroke="rgba(0,212,255,0.5)"  strokeDasharray="4 4" strokeWidth={1} label={{ value: 'LA NIÑA', fill: 'rgba(0,212,255,0.5)', fontSize: 8, fontFamily: 'Space Mono' }}/>
              <Tooltip
                contentStyle={{ background: 'rgba(6,9,18,0.97)', border: '1px solid rgba(0,212,255,0.2)', borderRadius: '6px', color: '#e2f4ff', padding: '10px 14px', fontSize: '0.78rem', fontFamily: 'Space Mono, monospace' }}
                cursor={{ stroke: 'rgba(0,212,255,0.15)', strokeWidth: 1 }}
                formatter={(value, name) => {
                  if (name === 'lower' || name === 'upper') return ['', ''];
                  if (typeof value === 'number') return [value.toFixed(2), 'MEI'];
                  return [value, name];
                }}
              />
              <Area type="monotone" dataKey="mei" fill="url(#meiGrad)" stroke="none" isAnimationActive={true} animationDuration={900}/>
              <Line
                type="monotone" dataKey="mei" stroke="#00d4ff" strokeWidth={2}
                isAnimationActive={true} animationDuration={900}
                dot={(props) => {
                  const { cx, cy, payload } = props;
                  if (payload.is_forecast) return <circle key={cx} cx={cx} cy={cy} r={2.5} fill="#334155" stroke="#1e3a5f" strokeWidth={1}/>;
                  return <circle key={cx} cx={cx} cy={cy} r={3.5} fill="#00d4ff" stroke="rgba(6,9,18,0.9)" strokeWidth={2}/>;
                }}
                activeDot={{ r: 5, strokeWidth: 2, stroke: '#ffffff', fill: '#00d4ff' }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <h3>Commodity Risk Matrix</h3>
            <span className="card-badge">LIVE ANALYSIS</span>
          </div>
          <div className="risk-table-header">
            <span>COMMODITY</span>
            <span>STATUS</span>
            <span>OUTLOOK</span>
          </div>
          {Object.entries(market).map(([commodity, info]) => {
            const meta = COMMODITY_META[commodity] || { icon: '📊', label: commodity.replace(/_/g, ' ') };
            const chipClass = riskChipClass(info.risk_level);
            const rowColor = chipClass === 'high' || chipClass === 'extreme' ? 'rgba(255,68,102,0.06)' : chipClass === 'medium' ? 'rgba(245,158,11,0.04)' : 'transparent';
            const borderColor = chipClass === 'high' || chipClass === 'extreme' ? '#ff4466' : chipClass === 'medium' ? '#f59e0b' : '#00e5a0';
            return (
              <div className="risk-row" key={commodity} style={{ background: rowColor, borderLeftColor: borderColor }}>
                <div className="risk-row-commodity">
                  <span className="commodity-icon">{meta.icon}</span>
                  <span className="commodity-name">{meta.label}</span>
                </div>
                <div className="risk-level-cell">
                  <span className={`risk-chip ${chipClass}`}>{info.risk_level || 'N/A'}</span>
                </div>
                <div className="risk-outlook-cell">{info.outlook}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Executive Summary + Risk Gauge ── */}
      <div className="grid-2" style={{ marginTop: 12 }}>
        <div className="card">
          <div className="card-header">
            <h3>Executive Summary</h3>
            <span className="card-badge">AI GENERATED</span>
          </div>
          <p className="summary-text">{report?.executive_summary ?? ''}</p>
          <a href={API_BASE + '/latest-report/download'} className="download-btn" target="_blank" rel="noreferrer">
            ↓ DOWNLOAD PDF REPORT
          </a>
        </div>
        <div className="card">
          <div className="card-header">
            <h3>Risk Assessment</h3>
          </div>
          <div className="risk-gauge-wrap">
            <div className="risk-gauge-label">Overall Risk Level</div>
            <RiskGauge score={riskScore} />
          </div>
          {status?.outlook && (
            <p style={{ fontSize: '0.82rem', color: '#64748b', lineHeight: 1.7, marginTop: 8, padding: '10px 12px', background: 'rgba(0,212,255,0.03)', borderRadius: 6, borderLeft: '2px solid rgba(0,212,255,0.3)' }}>
              {status.outlook}
            </p>
          )}
        </div>
      </div>

      {/* ── Recommendations + News ── */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <h3>Key Recommendations</h3>
            <span className="card-badge">AI Generated</span>
          </div>
          <div className="recommendations">
            {report?.key_recommendations?.length ? (
              report.key_recommendations.map((rec, i) => (
                <div className="rec-item" key={i}>
                  <span className="rec-number">{i + 1}</span>
                  <p>{rec}</p>
                </div>
              ))
            ) : (
              <div style={{ padding: '12px', color: '#64748b', fontSize: '0.85rem' }}>
                Run the pipeline to generate AI recommendations
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3>Latest Climate News</h3>
            <span className="card-badge">Live feed</span>
          </div>
          <div className="news-feed">
            {newsItems.map((item, i) => {
              const domain = item.url ? getDomain(item.url) : null;
              const dateStr = getRelativeDate(item.published_at || item.date);
              return (
                <div className="news-item" key={i}>
                  <div className="news-meta">
                    <span className="news-source">{item.source}</span>
                    {domain && <span className="news-domain">· {domain}</span>}
                    {dateStr && <span className="news-date">{dateStr}</span>}
                  </div>
                  {item.url
                    ? <a href={item.url} className="news-title news-link" target="_blank" rel="noreferrer">{item.title}</a>
                    : <p className="news-title">{item.title}</p>
                  }
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Analytics ── */}
      {analytics && (
        <>
          <div className="grid-2">
            <div className="card">
              <div className="card-header"><h3>Phase Probability Distribution</h3></div>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={[
                  { name: 'El Niño', value: analytics.phase_probabilities.el_nino },
                  { name: 'La Niña', value: analytics.phase_probabilities.la_nina },
                  { name: 'Neutral', value: analytics.phase_probabilities.neutral }
                ]} margin={{ top: 5, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,31,53,0.6)"/>
                  <XAxis dataKey="name" stroke="#64748b" fontSize={11}/>
                  <YAxis stroke="#64748b" fontSize={11} domain={[0, 100]}/>
                  <Tooltip contentStyle={{ background: 'rgba(13,21,32,0.95)', border: '1px solid rgba(59,130,246,0.3)', borderRadius: '8px', color: '#e2e8f0' }} formatter={(v) => `${v}%`}/>
                  <Bar dataKey="value" fill="#00d4ff" radius={[4, 4, 0, 0]}/>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="card">
              <div className="card-header"><h3>Forecast Accuracy</h3></div>
              <div className="analytics-metrics">
                <div className="metric-row">
                  <span className="metric-label">Mean Absolute Error</span>
                  <span className="metric-value">{analytics.forecast_accuracy.mae}</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Accuracy (±0.3)</span>
                  <span className="metric-value">{analytics.forecast_accuracy.accuracy_pct}%</span>
                </div>
                <div className="metric-row">
                  <span className="metric-label">Direction Accuracy</span>
                  <span className="metric-value">{analytics.forecast_accuracy.direction_accuracy}%</span>
                </div>
              </div>
            </div>
          </div>

          <div className="grid-2">
            <div className="card">
              <div className="card-header"><h3>Anomaly Detection</h3></div>
              <div style={{ padding: '20px', textAlign: 'center' }}>
                <div style={{ fontSize: '3rem', marginBottom: '12px', color: analytics.anomaly.is_anomaly ? '#ef4444' : '#10b981' }}>
                  {analytics.anomaly.is_anomaly ? '⚠' : '✓'}
                </div>
                <div style={{ color: '#e2e8f0', fontSize: '0.95rem', marginBottom: '8px' }}>
                  {analytics.anomaly.is_anomaly ? 'Unusual activity detected' : 'Normal activity'}
                </div>
                <div style={{ color: '#64748b', fontSize: '0.8rem' }}>Z-Score: {analytics.anomaly.z_score}</div>
                <div style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: '12px' }}>{analytics.anomaly.message}</div>
              </div>
            </div>

            <div className="card">
              <div className="card-header"><h3>Commodity Sensitivity</h3></div>
              <div className="commodity-sensitivity">
                {Object.entries(analytics.commodity_sensitivity).map(([commodity, correlation]) => {
                  const absCorr = Math.abs(correlation);
                  const barColor = correlation > 0 ? '#10b981' : '#ef4444';
                  return (
                    <div key={commodity} className="sensitivity-row">
                      <span className="sensitivity-label">{commodity.replace(/_/g, ' ').toUpperCase()}</span>
                      <div className="sensitivity-bar-wrapper">
                        <div className="sensitivity-bar" style={{ width: `${absCorr * 100}%`, background: barColor, height: '6px', borderRadius: '3px' }}/>
                      </div>
                      <span className="sensitivity-value">{correlation.toFixed(2)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {analytics.similar_events?.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h3>Similar Historical Events</h3>
                <span className="card-badge">Cosine similarity search</span>
              </div>
              <div className="similar-events-grid">
                {analytics.similar_events.map((event, i) => (
                  <div className="event-card" key={i}>
                    <div className="event-header">
                      <div className="event-period">{event.period}</div>
                      <div className="event-similarity">{event.similarity_pct}% similar</div>
                    </div>
                    <div className="event-outcome">
                      <span style={{ fontSize: '0.75rem', color: '#64748b' }}>What happened:</span>
                      <p>{event.outcome}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {analytics.seasonal?.trend?.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h3>Seasonal Decomposition</h3>
                <span className="card-badge">Trend · Seasonal · Residual</span>
              </div>
              <div className="decomposition-grid">
                {[
                  { key: 'trend', label: 'Trend', color: '#0ea5e9' },
                  { key: 'seasonal', label: 'Seasonal', color: '#8b5cf6' },
                  { key: 'residual', label: 'Residual', color: '#f59e0b' },
                ].map(({ key, label, color }) => (
                  <div className="decomposition-chart" key={key}>
                    <h4 style={{ marginBottom: '12px', fontSize: '0.95rem' }}>{label}</h4>
                    <ResponsiveContainer width="100%" height={120}>
                      <LineChart
                        data={analytics.seasonal[key].slice(-12).map((val, idx) => ({ idx, value: val }))}
                        margin={{ top: 5, right: 10, left: -25, bottom: 0 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,31,53,0.6)"/>
                        <XAxis dataKey="idx" stroke="#64748b" fontSize={10}/>
                        <YAxis stroke="#64748b" fontSize={10}/>
                        <Tooltip contentStyle={{ background: 'rgba(13,21,32,0.95)', border: '1px solid rgba(59,130,246,0.3)', borderRadius: '4px', color: '#e2e8f0', fontSize: '0.75rem' }}/>
                        <Line type="monotone" dataKey="value" stroke={color} isAnimationActive={false} strokeWidth={2} dot={false}/>
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Footer ── */}
      <footer className="footer">
        <div className="footer-content">
          <p className="footer-main">
            ENSO Intelligence Platform — Built by <span style={{ color: '#60a5fa' }}>Vansh Rana</span> — B.Tech Computer Science
          </p>
          <p className="footer-sub">
            Powered by NOAA MEI Index · Yahoo Finance · NewsAPI · Groq LLM · LangGraph Multi-Agent AI
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
