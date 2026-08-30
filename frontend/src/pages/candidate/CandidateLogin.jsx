import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { getPublicSetting } from '../../services/api';

export default function CandidateLogin() {
  const [appNumber, setAppNumber] = useState('');
  const [dob, setDob] = useState('');
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
    if (!appNumber || !dob) {
      setError('Please fill in all fields.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await api.post('/api/candidate/auth/login', {
        application_number: appNumber,
        dob: dob
      });

      const { access_token, candidate } = response.data;

      // Save credentials in localStorage
      localStorage.setItem('candidate_token', access_token);
      localStorage.setItem('candidate_user', JSON.stringify(candidate));
      localStorage.setItem('userRole', 'candidate');

      setLoading(false);
      navigate('/candidate/profile');
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
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Candidate Portal</p>
          </div>

          {error && <div className="alert alert-danger">{error}</div>}

          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label className="form-label" htmlFor="appNumber">Application ID</label>
              <input
                id="appNumber"
                type="text"
                className="form-input"
                placeholder="e.g. CETPHD/J26/0128"
                value={appNumber}
                onChange={(e) => setAppNumber(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="dob">Date of Birth</label>
              <input
                id="dob"
                type="date"
                className="form-input"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                max={new Date().toISOString().split('T')[0]}
                required
              />
            </div>

            <button type="submit" className="btn btn-primary w-full mt-4" disabled={loading}>
              {loading ? 'Verifying...' : 'Sign In as Candidate'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
