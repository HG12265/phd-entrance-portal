import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { getPublicSetting } from '../../services/api';

export default function AdminLogin() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [portalTitle, setPortalTitle] = useState('PhD Admission Entrance');
  const navigate = useNavigate();

  useEffect(() => {
    getPublicSetting('portal_title')
      .then(res => {
        if (res.data && res.data.value) {
          setPortalTitle(res.data.value);
        }
      })
      .catch(err => console.error('Failed to load portal title:', err));
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please fill in all fields.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await api.post('/api/admin/auth/login', {
        email: email,
        password: password
      });

      const { access_token, admin } = response.data;

      // Save credentials to localStorage as requested
      localStorage.setItem('admin_token', access_token);
      localStorage.setItem('admin_user', JSON.stringify(admin));
      localStorage.setItem('userRole', 'admin'); // Keep general userRole for backward compatibility

      setLoading(false);
      navigate('/admin/dashboard');
    } catch (err) {
      setLoading(false);
      const detail = err.response?.data?.detail || 'Authentication failed. Please check credentials.';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
  };

  return (
    <div className="page-container" style={{ maxWidth: '1100px', margin: '0 auto', padding: '1rem' }}>
      {/* Periyar University Redesigned Header Banner */}
      <div className="periyar-header">
        <div className="header-logo-container">
          <img src="/periyar_logo.png" alt="Periyar University Logo" className="periyar-logo" />
        </div>
        <div className="header-text-container">
          <h1 className="header-title-ta">பெரியார் பல்கலைக்கழகம்</h1>
          <p className="header-subtitle-ta">அரசு பல்கலைக்கழகம், சேலம்.</p>
          <h2 className="header-title-en">PERIYAR UNIVERSITY</h2>
          <p className="header-meta-en">
            State University - NAAC 'A++' Grade - NIRF Rank 94 <br />
            State Public University Rank 40 - SDG Institutions Rank Band: 11-50 <br />
            Salem - 636 011, Tamil Nadu, India.
          </p>
        </div>
        <div className="header-sketch-container">
          <img src="/periyar_sketch.png" alt="Thanthai Periyar Sketch" className="periyar-sketch" />
        </div>
      </div>

      <div className="login-container" style={{ minHeight: 'auto', padding: '2rem 0' }}>
        <div className="card login-card" style={{ borderTop: '4px solid var(--primary-color)', margin: '0 auto' }}>
          <div className="login-logo">
            <h2 style={{ color: 'var(--primary-color)', fontSize: '1.5rem', marginBottom: '0.25rem' }}>{portalTitle}</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Admin Console</p>
          </div>

          {error && <div className="alert alert-danger">{error}</div>}

          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label className="form-label" htmlFor="email">Administrator Email</label>
              <input
                id="email"
                type="email"
                className="form-input"
                placeholder="admin@phdportal.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="password">Security Password</label>
              <input
                id="password"
                type="password"
                className="form-input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="btn btn-primary w-full mt-4" disabled={loading}>
              {loading ? 'Authenticating...' : 'Sign In to Dashboard'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
