import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../../services/api';
import { Clock, PlayCircle, StopCircle, AlertCircle } from 'lucide-react';

export default function Instructions() {
  const [checked, setChecked] = useState(false);
  const [instructions, setInstructions] = useState(null);
  const [statusInfo, setStatusInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [enterError, setEnterError] = useState('');
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (location.state && location.state.error) {
      setEnterError(location.state.error);
      // Clear location state so the error message doesn't persist on page refresh
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location, navigate]);

  const fetchInstructionsAndStatus = async () => {
    try {
      const [instRes, statusRes] = await Promise.all([
        api.get('/api/candidate/instructions'),
        api.get('/api/candidate/exam-status')
      ]);
      setInstructions(instRes.data);
      setStatusInfo(statusRes.data);
      setError('');
    } catch (err) {
      console.error(err);
      const detail = err.response?.data?.detail || err.response?.data;
      if (detail?.redirect_to_result || detail?.exam_completed) {
        navigate('/candidate/result', { replace: true });
      } else {
        setError('Failed to fetch exam schedules or instructions from server.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInstructionsAndStatus();

    // Polling status every 10 seconds
    const interval = setInterval(async () => {
      try {
        const statusRes = await api.get('/api/candidate/exam-status');
        setStatusInfo(statusRes.data);
      } catch (err) {
        console.error('Polling status error:', err);
        const detail = err.response?.data?.detail || err.response?.data;
        if (detail?.redirect_to_result || detail?.exam_completed) {
          navigate('/candidate/result', { replace: true });
        }
      }
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  const handleStartExam = async () => {
    if (!checked || !statusInfo?.can_enter) return;
    setEnterError('');
    try {
      await api.post('/api/candidate/exam/enter');
      navigate('/candidate/exam');
    } catch (err) {
      const detail = err.response?.data?.detail || err.response?.data;
      if (detail && typeof detail === 'object') {
        if (detail.redirect_to_result || detail.exam_completed) {
          navigate('/candidate/result', { replace: true });
        } else {
          setEnterError(detail.message || 'Access Denied.');
        }
      } else {
        setEnterError(detail || 'Failed to start examination. Access Denied.');
      }
    }
  };

  if (loading) {
    return (
      <div className="page-container">
        <div style={{ textAlign: 'center', marginTop: '4rem' }}>
          <p>Loading exam instructions...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container">
        <div style={{ maxWidth: '600px', margin: '4rem auto', textAlign: 'center' }}>
          <div className="alert alert-danger mb-4">{error}</div>
          <button className="btn btn-primary" onClick={fetchInstructionsAndStatus}>Retry</button>
        </div>
      </div>
    );
  }

  // Determine banner styles
  let bannerStyle = { 
    padding: '0.85rem 1rem', 
    borderRadius: '0.5rem', 
    marginBottom: '1.5rem', 
    fontWeight: 600, 
    textAlign: 'center',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem'
  };
  const status = statusInfo?.status || 'no_session';

  if (status === 'waiting') {
    bannerStyle = { ...bannerStyle, backgroundColor: '#fef3c7', color: '#d97706', border: '1px solid #fde68a' };
  } else if (status === 'live') {
    bannerStyle = { ...bannerStyle, backgroundColor: '#ecfdf5', color: '#059669', border: '1px solid #a7f3d0' };
  } else if (status === 'ended') {
    bannerStyle = { ...bannerStyle, backgroundColor: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca' };
  } else {
    bannerStyle = { ...bannerStyle, backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1' };
  }

  const formatTime = (isoStr) => {
    if (!isoStr || isoStr === 'N/A') return 'N/A';
    try {
      const dt = new Date(isoStr);
      return dt.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: true, dateStyle: 'medium', timeStyle: 'short' }) + ' (IST)';
    } catch {
      return isoStr;
    }
  };

  const isCompleted = statusInfo?.redirect_to_result || statusInfo?.exam_completed || instructions?.redirect_to_result || instructions?.exam_completed;

  return (
    <div className="page-container">
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <h1 className="mb-4">Examination Instructions</h1>
        <p className="mb-4">Read the following guidelines carefully before starting the exam.</p>

        {/* Status banner */}
        <div style={bannerStyle}>
          {status === 'waiting' && <Clock size={18} />}
          {status === 'live' && <PlayCircle size={18} />}
          {status === 'ended' && <StopCircle size={18} />}
          {status !== 'waiting' && status !== 'live' && status !== 'ended' && <AlertCircle size={18} />}
          <span>
            {status === 'waiting' && 'Exam Status: Scheduled / Waiting for start time'}
            {status === 'live' && 'Exam Status: Live / Active Now'}
            {status === 'ended' && 'Exam Status: Concluded / Examination ended'}
            {status !== 'waiting' && status !== 'live' && status !== 'ended' && `Exam Status: ${statusInfo?.message || 'No active session assigned'}`}
          </span>
        </div>

        {enterError && <div className="alert alert-danger mb-4">{enterError}</div>}

        <div className="card" style={{ textAlign: 'left' }}>
          <h2 style={{ marginBottom: '1rem', borderBottom: '2px solid var(--border-color)', paddingBottom: '0.5rem', color: 'var(--primary-color)' }}>
            {instructions.exam_title}
          </h2>
          
          <table className="table mb-4" style={{ width: '100%', fontSize: '0.9rem' }}>
            <tbody>
              <tr>
                <td style={{ fontWeight: 600, width: '30%' }}>Exam Session</td>
                <td>{instructions.session_name}</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Scheduled Start</td>
                <td>{formatTime(instructions.start_time)}</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Scheduled End</td>
                <td>{formatTime(instructions.end_time)}</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Duration</td>
                <td>{instructions.duration} Minutes</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Applied Department</td>
                <td>{instructions.department}</td>
              </tr>
            </tbody>
          </table>

          <h3 className="card-title">Instructions & Guidelines</h3>
          <div style={{ whiteSpace: 'pre-line', padding: '1rem', backgroundColor: 'var(--background-color)', borderRadius: '0.375rem', marginBottom: '1.5rem', fontSize: '0.95rem', lineHeight: '1.6' }}>
            {instructions.instructions}
          </div>

          <h3 className="card-title">Interpreting the Question Palette</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.5rem', marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="palette-btn" style={{ width: '32px', height: '32px', cursor: 'default' }}>1</span>
              <span>Not Answered / Unvisited</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="palette-btn answered" style={{ width: '32px', height: '32px', cursor: 'default' }}>2</span>
              <span>Answered & Saved</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="palette-btn flagged" style={{ width: '32px', height: '32px', cursor: 'default' }}>3</span>
              <span>Flagged for Review</span>
            </div>
          </div>

          {isCompleted ? (
            <div className="alert alert-info mb-4" style={{ textAlign: 'center', fontWeight: 'bold' }}>
              Exam already completed. You can view your result.
            </div>
          ) : (
            <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1.5rem', marginTop: '1.5rem' }}>
              <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  style={{ width: '20px', height: '20px', marginTop: '2px' }}
                  checked={checked}
                  onChange={(e) => setChecked(e.target.checked)}
                />
                <span style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                  I have read and understood all the instructions. I declare that I am not carrying any prohibited electronic devices and will abide by the code of conduct of the examination.
                </span>
              </label>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1.5rem' }}>
          <button className="btn btn-secondary" onClick={() => navigate('/candidate/profile')}>
            Back to Profile
          </button>
          {isCompleted ? (
            <button
              className="btn btn-primary"
              onClick={() => navigate('/candidate/result')}
            >
              View Result
            </button>
          ) : (
            <button
              className="btn btn-primary animate-pulse"
              disabled={!checked || !statusInfo?.can_enter}
              onClick={handleStartExam}
            >
              Start Exam Now
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
