content = """import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE = 'http://localhost:8000';

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
    return <div className="loading"><h2>Loading ENSO Platform...</h2></div>;
  }

  const phase = status ? status.phase : 'Unknown';
  const phaseColor = phase === 'El Nino' ? '#F44336' : phase === 'La Nina' ? '#2196F3' : '#9E9E9E';
  const riskColor = (r) => r === 'High' || r === 'Extreme' ? '#F44336' : r === 'Medium' ? '#FF9800' : '#4CAF50';
  const market = report ? report.market_risks : {};

  return (
    <div className="app">
      <header className="header">
        <h1>ENSO Intelligence Platform</h1>
        <p>AI-powered climate risk intelligence by Vansh Rana</p>
      </header>
      <div className="card">
        <h3>Current ENSO Status</h3>
        <div className="phase-badge" style={{background: phaseColor}}>{phase}</div>
        <div className="status-details">
          <div className="stat">
            <span className="label">MEI Index</span>
            <span className="value">{status ? status.mei_value : ''}</span>
          </div>
          <div className="stat">
            <span className="label">Trend</span>
            <span className="value">{status ? status.trend : ''}</span>
          </div>
          <div className="stat">
            <span className="label">Risk Score</span>
            <span className="value" style={{color: '#F44336'}}>{status ? status.risk_score + '/10' : ''}</span>
          </div>
        </div>
        <p className="outlook">{status ? status.outlook : ''}</p>
      </div>
      <div className="card">
        <h3>Executive Summary</h3>
        <p className="outlook" style={{fontStyle: 'normal', color: '#cfd8dc'}}>{report ? report.executive_summary : ''}</p>
      </div>
      <div className="card">
        <h3>Commodity Market Risks</h3>
        <table className="risk-table">
          <thead>
            <tr>
              <th>Commodity</th>
              <th>Risk Level</th>
              <th>Price Outlook</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(market).map(([commodity, info]) => (
              <tr key={commodity}>
                <td>{commodity.replace('_', ' ').toUpperCase()}</td>
                <td><span className="risk-badge" style={{background: riskColor(info.risk_level)}}>{info.risk_level}</span></td>
                <td style={{color: '#90a4ae'}}>{info.outlook}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h3>Key Recommendations</h3>
        <ul className="recommendations">
          {report && report.key_recommendations ? report.key_recommendations.map((rec, i) => (
            <li key={i}>{rec}</li>
          )) : null}
        </ul>
      </div>
      <footer className="footer">
        <p>ENSO Intelligence Platform - Vansh Rana - B.Tech Computer Science</p>
      </footer>
    </div>
  );
}

export default App;
"""

with open('src/App.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("App.js written successfully!")