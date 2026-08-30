import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCandidateResult } from '../../services/api';

export default function ResultPage() {
  const navigate = useNavigate();
  const [resultData, setResultData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchResult = async () => {
    try {
      const response = await getCandidateResult();
      setResultData(response.data);
      setError('');
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Result not available yet.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResult();
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('candidate_token');
    localStorage.removeItem('candidate_user');
    navigate('/', { replace: true });
  };

  const formatTime = (isoStr) => {
    if (!isoStr) return 'N/A';
    try {
      const dt = new Date(isoStr);
      return dt.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: true, dateStyle: 'medium', timeStyle: 'short' }) + ' (IST)';
    } catch {
      return isoStr;
    }
  };

  if (loading) {
    return (
      <div className="page-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ fontSize: '1.2rem', fontWeight: 500 }}>Fetching exam results...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container">
        <div style={{ maxWidth: '600px', margin: '4rem auto', textAlign: 'center' }}>
          <div className="card" style={{ padding: '3rem 2rem' }}>
            <div style={{ fontSize: '4rem', marginBottom: '1.5rem' }}>⏳</div>
            <h2 className="mb-4" style={{ color: 'var(--text-primary)' }}>Result Not Available</h2>
            <div className="alert alert-warning mb-4">{error}</div>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
              <button className="btn btn-secondary" onClick={() => navigate('/candidate/profile')}>
                Back to Profile
              </button>
              <button className="btn btn-primary" onClick={handleLogout}>
                Logout
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const { candidate, exam, result } = resultData;
  const isPass = result.result_status === 'PASS';

  return (
    <div className="page-container">
      <div style={{ maxWidth: '750px', margin: '2rem auto', textAlign: 'center' }}>
        <div className="card" style={{ padding: '2.5rem', borderTop: `6px solid ${isPass ? 'var(--success-color)' : 'var(--danger-color)'}` }}>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '2px solid var(--border-color)', paddingBottom: '1rem' }}>
            <div style={{ textAlign: 'left' }}>
              <h1 style={{ fontSize: '1.6rem', color: 'var(--text-primary)', margin: 0 }}>Candidate Result Card</h1>
              <p style={{ margin: '0.25rem 0 0 0', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                PhD Entrance Examination
              </p>
            </div>
            <div style={{
              padding: '0.5rem 1.5rem',
              borderRadius: '2rem',
              fontWeight: 800,
              fontSize: '1.2rem',
              backgroundColor: isPass ? '#d1fae5' : '#fef2f2',
              color: isPass ? '#065f46' : '#991b1b',
              border: `1px solid ${isPass ? '#6ee7b7' : '#fca5a5'}`
            }}>
              {result.result_status}
            </div>
          </div>

          {/* Candidate Profile Details */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '1rem',
            backgroundColor: 'var(--background-color)',
            padding: '1.25rem',
            borderRadius: '0.5rem',
            marginBottom: '1.5rem',
            textAlign: 'left',
            fontSize: '0.9rem',
            border: '1px solid var(--border-color)'
          }}>
            <div>
              <span style={{ color: 'var(--text-secondary)', display: 'block', fontSize: '0.75rem', textTransform: 'uppercase' }}>Candidate Name</span>
              <strong>{candidate.name}</strong>
            </div>
            <div>
              <span style={{ color: 'var(--text-secondary)', display: 'block', fontSize: '0.75rem', textTransform: 'uppercase' }}>Application Number</span>
              <strong>{candidate.application_number}</strong>
            </div>
            <div>
              <span style={{ color: 'var(--text-secondary)', display: 'block', fontSize: '0.75rem', textTransform: 'uppercase' }}>Department</span>
              <strong>{candidate.department_name}</strong>
            </div>
            <div>
              <span style={{ color: 'var(--text-secondary)', display: 'block', fontSize: '0.75rem', textTransform: 'uppercase' }}>Exam Session</span>
              <strong>{exam.session_name}</strong>
            </div>
          </div>

          {/* Metrics & Score Summary Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '1rem',
            marginBottom: '2rem'
          }}>
            <div style={{ padding: '1rem', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '0.375rem' }}>
              <span style={{ display: 'block', fontSize: '0.75rem', color: '#166534', fontWeight: 600, textTransform: 'uppercase' }}>Obtained Score</span>
              <strong style={{ fontSize: '1.8rem', color: '#166534' }}>{result.score}</strong>
              <small style={{ display: 'block', fontSize: '0.75rem', color: '#166534' }}>Out of {exam.total_marks}</small>
            </div>
            <div style={{ padding: '1rem', backgroundColor: 'var(--background-color)', border: '1px solid var(--border-color)', borderRadius: '0.375rem' }}>
              <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Incorrect Answers</span>
              <strong style={{ fontSize: '1.8rem', color: 'var(--danger-color)' }}>{result.wrong_count}</strong>
              <small style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>No negative marks</small>
            </div>
            <div style={{ padding: '1rem', backgroundColor: 'var(--background-color)', border: '1px solid var(--border-color)', borderRadius: '0.375rem' }}>
              <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Unanswered</span>
              <strong style={{ fontSize: '1.8rem', color: '#64748b' }}>{result.unanswered_count}</strong>
              <small style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Not attempted</small>
            </div>
          </div>

          {/* Submission Info */}
          <table className="table mb-4" style={{ width: '100%', fontSize: '0.875rem' }}>
            <tbody>
              <tr>
                <td style={{ fontWeight: 600, width: '40%' }}>Submission Type</td>
                <td>
                  <span style={{
                    padding: '0.25rem 0.75rem',
                    borderRadius: '1rem',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    backgroundColor: result.submission_type === 'manual' ? '#e0f2fe' : '#fee2e2',
                    color: result.submission_type === 'manual' ? '#0369a1' : '#991b1b'
                  }}>
                    {result.submission_type === 'manual' ? 'Manual Submit' : 'Auto Submit'}
                  </span>
                </td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Submitted Time</td>
                <td>{formatTime(result.submitted_time)}</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Passing Criteria</td>
                <td>Minimum <strong>{exam.pass_mark} / {exam.total_marks} marks</strong> required to pass.</td>
              </tr>
            </tbody>
          </table>

          <div className="alert alert-warning" style={{ fontSize: '0.85rem', textAlign: 'left', lineHeight: 1.5 }}>
            <strong>Note:</strong> Question-wise detailed reports and answer keys are restricted on the candidate portal. For concerns, contact the exam administration.
          </div>

          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '1.5rem' }}>
            <button className="btn btn-secondary" onClick={() => navigate('/candidate/profile')}>
              Back to Profile
            </button>
            <button className="btn btn-primary" onClick={handleLogout}>
              Logout
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}
