import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import './App.css';

// ── Single source of truth for the backend URL ────────────────────────────────
// In Vercel: add REACT_APP_API_URL=https://enso-intelligence-platform.onrender.com
// to Project → Settings → Environment Variables, then redeploy.
// Falls back to the hardcoded Render URL so it works even without the env var.
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

function App() {
  const [status, setStatus]   = useState(null);
  const [report, setReport]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [running, setRunning] = useState(false);
  const [noData, setNoData]   = useState(false);
  const [chartData, setChartData] = useState(mockChartData);
  const [forecast, setForecast] = useState(null);

  const fetchData = useCallback(() => {
    setLoading(true);
    setError(null);
    setNoData(false);

    Promise.all([
      axios.get(API_BASE + '/status'),
      axios.get(API_BASE + '/latest-report'),
      axios.get(API_BASE + '/mei-history').catch(() => null),
      axios.get(API_BASE + '/forecast').catch(() => null),
    ])
      .then(([s, r, h, f]) => {
        // /status returns 503 + {status:"no_data"} when pipeline hasn't run yet
        if (s.data?.status === 'no_data') {
          setNoData(true);
        } else {
          setStatus(s.data);
          setReport(r.data);
          // Use MEI history from backend if available, otherwise use mock data
          if (h?.data && Array.isArray(h.data)) {
            setChartData(h.data);
          } else {
            setChartData(mockChartData);
          }
          // Set forecast if available
          if (f?.data && f.data.forecast) {
            setForecast(f.data);
          }
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error('API Error:', err);
        // Axios throws on 503 — check the response body
        if (err.response?.data?.status === 'no_data') {
          setNoData(true);
        } else {
          setError(err.message || 'Could not reach backend');
        }
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchData();
    // Auto-refresh every 60 s
    const interval = setInterval(fetchData, 60_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const triggerRunNow = async () => {
    setRunning(true);
    try {
      await axios.post(API_BASE + '/run-now');
      // Give the backend 3 s to finish writing, then re-fetch
      setTimeout(() => {
        fetchData();
        setRunning(false);
      }, 3000);
    } catch (e) {
      console.error('run-now failed:', e);
      setRunning(false);
    }
  };

  // ── Loading state ───────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="loading">
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

  // ── Pipeline hasn't run yet ─────────────────────────────────────────────────
  if (noData) {
    return (
      <div className="loading">
        <div className="loading-inner">
          <h2 style={{ color: '#f59e0b' }}>No Report Yet</h2>
          <p style={{ color: '#94a3b8', margin: '1rem 0' }}>
            The pipeline hasn't run on this server instance.<br />
            Click below to generate your first report.
          </p>
          <button
            onClick={triggerRunNow}
            disabled={running}
            className="download-btn"
            style={{ display: 'inline-block', cursor: running ? 'not-allowed' : 'pointer' }}
          >
            {running ? '⏳ Running pipeline…' : '▶ Run Pipeline Now'}
          </button>
        </div>
      </div>
    );
  }

  // ── Network / CORS error ────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="loading">
        <div className="loading-inner">
          <h2 style={{ color: '#ef4444' }}>Connection Error</h2>
          <p style={{ color: '#94a3b8', margin: '1rem 0', fontFamily: 'monospace', fontSize: '0.85rem' }}>
            {error}
          </p>
          <p style={{ color: '#64748b', fontSize: '0.8rem' }}>
            Backend: <code>{API_BASE}</code>
          </p>
          <button onClick={fetchData} className="download-btn" style={{ display: 'inline-block', marginTop: '1rem' }}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  // ── Derive display values ───────────────────────────────────────────────────
  const phase      = status?.phase ?? 'Unknown';
  const phaseColor = phase.toLowerCase().includes('nina')
    ? '#3b82f6'
    : phase.toLowerCase().includes('nino') || phase.toLowerCase().includes('niño')
      ? '#ef4444'
      : '#6b7280';

  const phasePillStyle = phase.toLowerCase().includes('nina')
    ? { background: 'linear-gradient(135deg, #0369a1 0%, #0284c7 50%, #0ea5e9 100%)' }
    : phase.toLowerCase().includes('nino') || phase.toLowerCase().includes('niño')
      ? { background: 'linear-gradient(135deg, #7f1d1d 0%, #dc2626 50%, #ef4444 100%)' }
      : { background: 'linear-gradient(135deg, #374151 0%, #4b5563 50%, #6b7280 100%)' };

  const riskScore = status?.risk_score ?? 0;
  const riskWidth = (riskScore / 10) * 100;
  const riskFill  = riskScore >= 7 ? '#ef4444' : riskScore >= 4 ? '#f59e0b' : '#10b981';
  const riskColor = (r) =>
    r === 'High' || r === 'Extreme' ? '#ef4444' : r === 'Medium' ? '#f59e0b' : '#10b981';

  const market = report?.market_risks ?? {};

  // Live news from the report, or fall back to the static mock
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

  // ── Main dashboard ──────────────────────────────────────────────────────────
  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <span className="logo-icon">🌊</span>
            <div>
              <h1>ENSO Intelligence Platform</h1>
              <p>AI-powered climate risk intelligence</p>
            </div>
          </div>
          <div className="header-right">
            <button
              onClick={triggerRunNow}
              disabled={running}
              style={{
                background: 'transparent',
                border: '1px solid #334155',
                color: '#94a3b8',
                borderRadius: '6px',
                padding: '5px 12px',
                fontSize: '0.75rem',
                cursor: running ? 'not-allowed' : 'pointer',
                marginRight: '0.75rem',
              }}
            >
              {running ? '⏳ Running…' : '▶ Run Now'}
            </button>
            <div className="live-badge">
              <span className="live-dot"></span>
              LIVE
            </div>
            <div className="phase-pill" style={phasePillStyle}>
              {phase}
            </div>
          </div>
        </div>
      </header>

      <div className="stats-row">
        <div className="stat-card">
          <span className="stat-label">MEI Index</span>
          <span className="stat-value" style={{ color: phaseColor }}>
            {status?.mei_value ?? '-'}
          </span>
          <span className="stat-sub">Multivariate ENSO Index</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Trend</span>
          <span className="stat-value">{status?.trend ?? '-'}</span>
          <span className="stat-sub">Current direction</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Risk Score</span>
          <span className="stat-value" style={{ color: '#ef4444' }}>
            {status ? status.risk_score + '/10' : '-'}
          </span>
          <span className="stat-sub">Overall risk level</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Report Date</span>
          <span className="stat-value" style={{ fontSize: '1.1rem' }}>
            {status?.report_date ?? '-'}
          </span>
          <span className="stat-sub">Last generated</span>
        </div>
      </div>

      {forecast && forecast.predicted_phase && (
        <div className="stat-card" style={{ gridColumn: 'span 1', marginBottom: '20px' }}>
          <span className="stat-label">6-Month Forecast</span>
          <span className="stat-value" style={{
            color: forecast.predicted_phase.toLowerCase().includes('nina') ? '#3b82f6'
              : forecast.predicted_phase.toLowerCase().includes('nino') ? '#ef4444'
              : '#6b7280'
          }}>
            {forecast.predicted_phase}
          </span>
          <span className="stat-sub">{forecast.confidence_pct}% confidence</span>
        </div>
      )}

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <h3>MEI Index Trend & Forecast</h3>
            <span className="card-badge">{forecast ? '12mo history + 6mo forecast' : 'Last 12 months'}</span>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart
              data={forecast ? [
                ...(forecast.historical || []),
                ...(forecast.forecast || [])
              ] : chartData}
              margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(15, 31, 53, 0.6)" verticalPoints={[0]} />
              <XAxis dataKey="month" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} domain={[-1.5, 0.5]} width={40} />
              <ReferenceLine
                y={0.5}
                stroke="#ef4444"
                strokeDasharray="5 5"
                strokeWidth={2}
                label={{ value: 'El Niño (>0.5)', fill: '#ef4444', fontSize: 11, offset: 10 }}
              />
              <ReferenceLine
                y={-0.5}
                stroke="#3b82f6"
                strokeDasharray="5 5"
                strokeWidth={2}
                label={{ value: 'La Niña (<-0.5)', fill: '#3b82f6', fontSize: 11, offset: 10 }}
              />
              {forecast && forecast.forecast && forecast.forecast.length > 0 && (
                <Area
                  type="monotone"
                  dataKey="lower"
                  fill="rgba(59, 130, 246, 0.1)"
                  stroke="none"
                  isAnimationActive={false}
                  className="forecast-band"
                />
              )}
              <Tooltip
                contentStyle={{
                  background: 'rgba(13, 21, 32, 0.95)',
                  border: '1px solid rgba(59, 130, 246, 0.3)',
                  borderRadius: '8px',
                  color: '#e2e8f0',
                  padding: '10px'
                }}
                formatter={(value, name) => {
                  if (name === 'lower' || name === 'upper') return ['', ''];
                  if (typeof value === 'number') return [value.toFixed(2), name === 'mei' ? 'MEI Index' : name];
                  return [value, name];
                }}
              />
              <Line
                type="monotone"
                dataKey="mei"
                stroke="#0ea5e9"
                strokeWidth={3}
                isAnimationActive={true}
                animationDuration={800}
                dot={(props) => {
                  const { cx, cy, payload } = props;
                  if (payload.is_forecast) {
                    return <circle cx={cx} cy={cy} r={4} fill="#64748b" stroke="#64748b" strokeWidth={2} />;
                  }
                  return <circle cx={cx} cy={cy} r={5} fill="#0ea5e9" stroke="rgba(14, 165, 233, 0.3)" strokeWidth={2} />;
                }}
                strokeDasharray={(props) => props.is_forecast ? '5 5' : '0'}
                activeDot={{ r: 7, strokeWidth: 2, stroke: '#ffffff' }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-header">
            <h3>Executive Summary</h3>
          </div>
          <p className="summary-text">{report?.executive_summary ?? ''}</p>
          <div className="risk-meter">
            <div className="risk-meter-label">
              <span>Overall Risk Level</span>
              <span style={{ color: '#ef4444', fontWeight: 'bold' }}>{riskScore}/10</span>
            </div>
            <div className="risk-bar">
              <div className="risk-fill" style={{ width: riskWidth + '%', background: riskFill }}></div>
            </div>
          </div>
          <a href={API_BASE + '/latest-report/download'} className="download-btn" target="_blank" rel="noreferrer">
            📄 Download PDF Report
          </a>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>Commodity Market Risks</h3>
          <span className="card-badge">Real-time analysis</span>
        </div>
        <div className="commodity-grid">
          {Object.entries(market).map(([commodity, info]) => (
            <div className="commodity-card" key={commodity}>
              <div className="commodity-top">
                <span className="commodity-name">{commodity.replace('_', ' ').toUpperCase()}</span>
                <span className="risk-badge" style={{ background: riskColor(info.risk_level) }}>{info.risk_level}</span>
              </div>
              <p className="commodity-outlook">{info.outlook}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <h3>Key Recommendations</h3>
            <span className="card-badge">AI Generated</span>
          </div>
          <div className="recommendations">
            {report?.key_recommendations?.map((rec, i) => (
              <div className="rec-item" key={i}>
                <span className="rec-number">{i + 1}</span>
                <p>{rec}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3>Latest Climate News</h3>
            <span className="card-badge">Live feed</span>
          </div>
          <div className="news-feed">
            {newsItems.map((item, i) => (
              <div className="news-item" key={i}>
                <div className="news-source">{item.source}</div>
                <p className="news-title">{item.title}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <footer className="footer">
        <div className="footer-content">
          <p className="footer-main">
            ENSO Intelligence Platform — Built by <span style={{ color: '#60a5fa' }}>Vansh Rana</span> — B.Tech Computer Science
          </p>
          <p className="footer-sub">
            Powered by NASA Satellite Data • NOAA MEI Index • Groq LLM • LangGraph Multi-Agent AI
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;