import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import './App.css';

const API_BASE = 'http://localhost:8000';

const mockChartData = [
  { month: 'Oct 25', mei: -1.19 },
  { month: 'Nov 25', mei: -1.06 },
  { month: 'Dec 25', mei: -0.77 },
  { month: 'Jan 26', mei: -0.76 },
  { month: 'Feb 26', mei: -0.95 },
  { month: 'Mar 26', mei: -1.03 },
];

const mockNews = [
  { title: 'El Nino may return by mid-2026 amid warming seas, says global weather body', source: 'BusinessLine' },
  { title: 'Brace yourself for a SUPER El Nino: Likelihood skyrockets as scientists warn of record highs', source: 'Daily Mail' },
  { title: 'How El Nino could impact the world weather in 2026/27', source: 'Times of India' },
  { title: 'El Nino, Iran conflict heighten crude oil supply concerns', source: 'Crypto Briefing' },
];

function App() {
  const [status, setStatus] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      axios.get(API_BASE + '/status'),
      axios.get(API_BASE + '/latest-report')
    ]).then(([s, r]) => {
      setStatus(s.data);
      setReport(r.data);
      setLoading(false);
    }).catch((err) => {
      console.error('API Error:', err);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-inner">
          <div className="spinner"></div>
          <h2>Loading ENSO Intelligence Platform...</h2>
        </div>
      </div>
    );
  }

  const phase = status ? status.phase : 'Unknown';
  const phaseColor = phase === 'El Nino' ? '#ef4444' : phase === 'La Nina' ? '#3b82f6' : '#6b7280';
  const riskColor = (r) => r === 'High' || r === 'Extreme' ? '#ef4444' : r === 'Medium' ? '#f59e0b' : '#10b981';
  const market = report ? report.market_risks : {};
  const riskScore = status ? status.risk_score : 0;
  const riskWidth = (riskScore / 10) * 100;

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
            <div className="live-badge">
              <span className="live-dot"></span>
              LIVE
            </div>
            <div className="phase-pill" style={{background: phaseColor}}>
              {phase}
            </div>
          </div>
        </div>
      </header>

      <div className="stats-row">
        <div className="stat-card">
          <span className="stat-label">MEI Index</span>
          <span className="stat-value" style={{color: phaseColor}}>{status ? status.mei_value : '-'}</span>
          <span className="stat-sub">Multivariate ENSO Index</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Trend</span>
          <span className="stat-value">{status ? status.trend : '-'}</span>
          <span className="stat-sub">Current direction</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Risk Score</span>
          <span className="stat-value" style={{color: '#ef4444'}}>{status ? status.risk_score + '/10' : '-'}</span>
          <span className="stat-sub">Overall risk level</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Report Date</span>
          <span className="stat-value" style={{fontSize: '1.1rem'}}>{status ? status.report_date : '-'}</span>
          <span className="stat-sub">Last generated</span>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <h3>MEI Index Trend</h3>
            <span className="card-badge">Last 6 months</span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={mockChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#0f1f35" />
              <XAxis dataKey="month" stroke="#475569" fontSize={11} />
              <YAxis stroke="#475569" fontSize={11} reversed={false} domain={[-1.5, 0.5]} />
              <ReferenceLine y={0.5} stroke="#ef4444" strokeDasharray="4 4" label={{value: 'El Nino', fill: '#ef4444', fontSize: 10}} />
              <ReferenceLine y={-0.5} stroke="#3b82f6" strokeDasharray="4 4" label={{value: 'La Nina', fill: '#3b82f6', fontSize: 10}} />
              <Tooltip
                contentStyle={{background: '#0d1520', border: '1px solid #0f1f35', borderRadius: '8px', color: '#e2e8f0'}}
              />
              <Line type="monotone" dataKey="mei" stroke={phaseColor} strokeWidth={2.5} dot={{fill: phaseColor, r: 4}} activeDot={{r: 6}} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-header">
            <h3>Executive Summary</h3>
          </div>
          <p className="summary-text">{report ? report.executive_summary : ''}</p>
          <div className="risk-meter">
            <div className="risk-meter-label">
              <span>Overall Risk Level</span>
              <span style={{color: '#ef4444', fontWeight: 'bold'}}>{riskScore}/10</span>
            </div>
            <div className="risk-bar">
              <div className="risk-fill" style={{width: riskWidth + '%', background: riskScore >= 7 ? '#ef4444' : riskScore >= 4 ? '#f59e0b' : '#10b981'}}></div>
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
                <span className="risk-badge" style={{background: riskColor(info.risk_level)}}>{info.risk_level}</span>
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
            {report && report.key_recommendations ? report.key_recommendations.map((rec, i) => (
              <div className="rec-item" key={i}>
                <span className="rec-number">{i + 1}</span>
                <p>{rec}</p>
              </div>
            )) : null}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3>Latest Climate News</h3>
            <span className="card-badge">Live feed</span>
          </div>
          <div className="news-feed">
            {mockNews.map((item, i) => (
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
          <p className="footer-main">ENSO Intelligence Platform — Built by <span style={{color: '#60a5fa'}}>Vansh Rana</span> — B.Tech Computer Science</p>
          <p className="footer-sub">Powered by NASA Satellite Data • NOAA MEI Index • Groq LLM • LangGraph Multi-Agent AI</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
