import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Sidebar from '../../components/Sidebar';
import MathText from '../../components/MathText';
import { getCandidateReport, downloadCandidatePdf, getImageUrl } from '../../services/api';

export default function CandidateReport() {
  const { candidateId } = useParams();
  const navigate = useNavigate();
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const fetchReport = async () => {
    try {
      const res = await getCandidateReport(candidateId);
      setReportData(res.data);
      setError('');
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to load candidate report.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [candidateId]);

  const handleDownloadPdf = async () => {
    if (!reportData) return;
    setDownloadingPdf(true);
    try {
      const response = await downloadCandidatePdf(candidateId);
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      const safeAppNum = reportData.candidate.application_number.replace(/\//g, '-');
      link.setAttribute('download', `candidate_report_${safeAppNum}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      alert('Failed to download candidate PDF report.');
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="dashboard-layout">
        <Sidebar />
        <div className="page-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
          <p style={{ fontSize: '1.2rem', fontWeight: 500 }}>Loading report...</p>
        </div>
      </div>
    );
  }

  if (error || !reportData) {
    return (
      <div className="dashboard-layout">
        <Sidebar />
        <div className="page-container">
          <div className="card" style={{ maxWidth: '600px', margin: '3rem auto', textAlign: 'center', padding: '3rem 2rem' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⚠️</div>
            <h2>Error Loading Report</h2>
            <div className="alert alert-danger mb-4">{error || 'Record missing.'}</div>
            <button className="btn btn-secondary" onClick={() => navigate('/admin/reports')}>
              Back to Reports
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { candidate, exam, attempt, answers, message } = reportData;
  const hasAttempt = attempt !== null;
  const isPass = hasAttempt && attempt.result_status === 'PASS';

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="page-container printing-area">
        
        {/* Navigation / Header Buttons */}
        <div className="no-print" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <button className="btn btn-secondary" onClick={() => navigate('/admin/reports')}>
            ← Back to Reports
          </button>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button className="btn btn-secondary" onClick={handlePrint}>
              🖨️ Print Report
            </button>
            {hasAttempt && (
              <button className="btn btn-primary" onClick={handleDownloadPdf} disabled={downloadingPdf}>
                {downloadingPdf ? 'Generating PDF...' : '📄 Download PDF'}
              </button>
            )}
          </div>
        </div>

        {/* Report Card Header */}
        <div className="card" style={{ padding: '2rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', textAlign: 'left' }}>
              {candidate.photo_url ? (
                <img 
                  src={getImageUrl(candidate.photo_url)} 
                  alt={candidate.name} 
                  onError={(e) => { e.target.style.display = 'none'; }}
                  style={{ width: '80px', height: '100px', objectFit: 'cover', borderRadius: '4px', border: '1px solid var(--border-color)' }}
                />
              ) : (
                <div style={{ width: '80px', height: '100px', backgroundColor: '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '4px', border: '1px solid var(--border-color)', fontSize: '2rem' }}>
                  👤
                </div>
              )}
              <div>
                <h1 style={{ margin: 0, fontSize: '1.75rem', color: 'var(--text-primary)' }}>{candidate.name}</h1>
                <p style={{ margin: '0.25rem 0 0 0', color: 'var(--text-secondary)', fontWeight: 500 }}>
                  Application No: <span style={{ fontFamily: 'monospace', fontSize: '1rem' }}>{candidate.application_number}</span>
                </p>
                <p style={{ margin: '0.25rem 0 0 0', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  Subject Subject: <strong>{candidate.department_name}</strong>
                </p>
              </div>
            </div>
            
            {hasAttempt ? (
              <div style={{
                padding: '0.75rem 1.75rem',
                borderRadius: '0.375rem',
                textAlign: 'center',
                backgroundColor: isPass ? '#d1fae5' : '#fef2f2',
                border: `1px solid ${isPass ? '#34d399' : '#f87171'}`
              }}>
                <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Grading Status</span>
                <strong style={{ fontSize: '1.5rem', color: isPass ? '#065f46' : '#991b1b' }}>
                  {attempt.result_status}
                </strong>
              </div>
            ) : (
              <div style={{
                padding: '0.75rem 1.75rem',
                borderRadius: '0.375rem',
                textAlign: 'center',
                backgroundColor: '#fef3c7',
                border: '1px solid #fbbf24'
              }}>
                <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600 }}>Grading Status</span>
                <strong style={{ fontSize: '1.5rem', color: '#92400e' }}>ABSENT</strong>
              </div>
            )}
          </div>
        </div>

        {/* Details Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
          
          {/* Attempt Statistics */}
          <div className="card" style={{ padding: '1.5rem', textAlign: 'left' }}>
            <h3 className="card-title" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
              Performance Summary
            </h3>
            {hasAttempt ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', textAlign: 'center' }}>
                <div style={{ padding: '0.75rem', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '0.25rem' }}>
                  <span style={{ display: 'block', fontSize: '0.75rem', color: '#166534' }}>Total Score</span>
                  <strong style={{ fontSize: '1.4rem', color: '#166534' }}>{attempt.score} / 70 <span style={{ fontSize: '0.85rem', fontWeight: 'normal' }}>Marks</span></strong>
                </div>
                <div style={{ padding: '0.75rem', backgroundColor: 'var(--background-color)', border: '1px solid var(--border-color)', borderRadius: '0.25rem' }}>
                  <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--success-color)' }}>Correct Answers</span>
                  <strong style={{ fontSize: '1.4rem', color: 'var(--success-color)' }}>{attempt.correct_count} <span style={{ fontSize: '0.85rem', fontWeight: 'normal', color: 'var(--text-secondary)' }}>Qns</span></strong>
                </div>
                <div style={{ padding: '0.75rem', backgroundColor: 'var(--background-color)', border: '1px solid var(--border-color)', borderRadius: '0.25rem' }}>
                  <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--danger-color)' }}>Incorrect Answers</span>
                  <strong style={{ fontSize: '1.4rem', color: 'var(--danger-color)' }}>{attempt.wrong_count} <span style={{ fontSize: '0.85rem', fontWeight: 'normal', color: 'var(--text-secondary)' }}>Qns</span></strong>
                </div>
                <div style={{ padding: '0.75rem', backgroundColor: 'var(--background-color)', border: '1px solid var(--border-color)', borderRadius: '0.25rem' }}>
                  <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Unanswered</span>
                  <strong style={{ fontSize: '1.4rem', color: '#64748b' }}>{attempt.unanswered_count} <span style={{ fontSize: '0.85rem', fontWeight: 'normal', color: 'var(--text-secondary)' }}>Qns</span></strong>
                </div>
              </div>
            ) : (
              <div className="alert alert-warning" style={{ margin: 0 }}>
                {message || 'No attempt record generated for this session.'}
              </div>
            )}
          </div>

          {/* Exam Schedule */}
          <div className="card" style={{ padding: '1.5rem', textAlign: 'left' }}>
            <h3 className="card-title" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
              Exam Details
            </h3>
            <div style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div><span style={{ color: 'var(--text-secondary)' }}>Session:</span> <strong>{exam.session_name}</strong></div>
              <div><span style={{ color: 'var(--text-secondary)' }}>Title:</span> <strong>{exam.exam_title}</strong></div>
              <div><span style={{ color: 'var(--text-secondary)' }}>Duration:</span> <strong>{exam.duration_minutes} mins</strong></div>
              {hasAttempt && attempt.submitted_time && (
                <div>
                  <span style={{ color: 'var(--text-secondary)' }}>Submitted:</span>{' '}
                  <strong>{new Date(attempt.submitted_time).toLocaleString('en-IN')}</strong>
                </div>
              )}
            </div>
          </div>

        </div>

        {/* Question-Wise Table */}
        {hasAttempt && answers.length > 0 && (
          <div className="card" style={{ padding: '1.5rem' }}>
            <h3 className="card-title" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem', textAlign: 'left' }}>
              Question-Wise Evaluation Logs
            </h3>
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: '60px' }}>Q.No</th>
                    <th>Question Description</th>
                    <th style={{ width: '120px' }}>Candidate Answer</th>
                    <th style={{ width: '120px' }}>Correct Answer</th>
                    <th style={{ width: '100px' }}>Evaluation</th>
                    <th style={{ width: '60px' }}>Marks</th>
                  </tr>
                </thead>
                <tbody>
                  {answers.map((ans) => {
                    const isCorrect = ans.is_correct;
                    const isUnanswered = !ans.candidate_answer;
                    
                    let bgStatus = '#e2e8f0'; // Gray (Unanswered)
                    let textStatusColor = '#475569';
                    let statusLabel = 'Unanswered';
                    
                    if (!isUnanswered) {
                      bgStatus = isCorrect ? '#d1fae5' : '#fef2f2'; // Green or Red
                      textStatusColor = isCorrect ? '#065f46' : '#991b1b';
                      statusLabel = isCorrect ? 'Correct' : 'Incorrect';
                    }

                    return (
                      <tr key={ans.question_id}>
                        <td><strong>{ans.display_no}</strong></td>
                        <td style={{ textAlign: 'left' }}>
                          <div style={{ marginBottom: '0.25rem', fontWeight: 500 }}>
                            <MathText text={ans.question_text} />
                          </div>
                          {ans.question_tamil && (
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', borderLeft: '2px solid #cbd5e1', paddingLeft: '0.5rem', marginTop: '0.25rem' }}>
                              {ans.question_tamil}
                            </div>
                          )}
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginTop: '0.5rem', fontSize: '0.8rem' }}>
                            <div>A) <MathText text={ans.option_a} /></div>
                            <div>B) <MathText text={ans.option_b} /></div>
                            <div>C) <MathText text={ans.option_c} /></div>
                            <div>D) <MathText text={ans.option_d} /></div>
                          </div>
                        </td>
                        <td>
                          <span style={{ 
                            fontFamily: 'monospace', 
                            fontWeight: 700, 
                            fontSize: '1rem',
                            color: !isUnanswered ? (isCorrect ? 'var(--success-color)' : 'var(--danger-color)') : 'var(--text-secondary)'
                          }}>
                            {ans.candidate_answer ? ans.candidate_answer : '-'}
                          </span>
                        </td>
                        <td>
                          <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '1rem', color: 'var(--success-color)' }}>
                            {ans.correct_answer}
                          </span>
                        </td>
                        <td>
                          <span style={{
                            padding: '0.25rem 0.5rem',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            backgroundColor: bgStatus,
                            color: textStatusColor
                          }}>
                            {statusLabel}
                          </span>
                        </td>
                        <td>
                          <strong>{ans.mark_awarded}</strong>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
