import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Printer, CheckCircle2, AlertCircle } from 'lucide-react';
import Sidebar from '../../components/Sidebar';
import MathText from '../../components/MathText';
import api, { getQuestions, getImageUrl } from '../../services/api';

export default function QuestionPreview() {
  const { departmentId } = useParams();
  const [departmentName, setDepartmentName] = useState('');
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchDeptAndQuestions = async () => {
      setLoading(true);
      setError('');
      try {
        // Fetch department details
        const deptRes = await api.get(`/api/admin/departments`);
        const dept = deptRes.data.find(d => d.id === parseInt(departmentId));
        if (dept) {
          setDepartmentName(dept.department_name);
        }

        // Fetch all active questions for this department (disable pagination by using a high limit like 100)
        const qRes = await getQuestions({
          department_id: departmentId,
          is_active: true,
          limit: 100
        });
        
        // Sort questions by question_no ascending
        const sortedQuestions = qRes.data.items.sort((a, b) => a.question_no - b.question_no);
        setQuestions(sortedQuestions);
      } catch (err) {
        setError('Failed to load question bank details for preview.');
      } finally {
        setLoading(false);
      }
    };

    if (departmentId) {
      fetchDeptAndQuestions();
    }
  }, [departmentId]);

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="dashboard-layout">
      {/* Hide sidebar when printing */}
      <div className="no-print">
        <Sidebar />
      </div>
      
      <div className="page-container print-full-width">
        {/* Breadcrumb controls - hidden during printing */}
        <div className="no-print" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <div>
            <Link to="/admin/questions" style={{ textDecoration: 'none', color: 'var(--primary-color)', fontSize: '0.9rem' }}>
              &larr; Back to Question Upload
            </Link>
            <h1 style={{ marginTop: '0.5rem', marginBottom: 0 }}>Question Bank Preview</h1>
            <p className="text-secondary" style={{ margin: 0 }}>
              Verify full translation and math layout correctness before releasing the exam.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button onClick={handlePrint} className="btn btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Printer size={16} /> Print Question Paper
            </button>
          </div>
        </div>

        {error && <div className="alert alert-danger no-print">{error}</div>}

        {loading ? (
          <p>Loading preview sheets...</p>
        ) : (
          <div className="card" style={{ borderTop: '4px solid var(--primary-color)', padding: '2.5rem' }}>
            {/* Header info sheet */}
            <div style={{ textAlign: 'center', borderBottom: '2px solid #e2e8f0', paddingBottom: '1.5rem', marginBottom: '2rem' }}>
              <h2 style={{ fontSize: '1.8rem', color: '#1e293b', marginBottom: '0.5rem' }}>
                PhD Entrance Examination Question Paper
              </h2>
              <h3 style={{ fontSize: '1.3rem', color: 'var(--primary-color)', fontWeight: 600, margin: 0 }}>
                Subject: {departmentName || `Department #${departmentId}`}
              </h3>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '2rem', marginTop: '1rem', fontSize: '0.9rem', color: '#64748b' }}>
                <span><strong>Total Questions:</strong> {questions.length}</span>
                <span><strong>Total Marks:</strong> {questions.reduce((sum, q) => sum + q.marks, 0)} Marks</span>
                <span><strong>Status:</strong> {questions.length === 70 ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: 'var(--success-color)', fontWeight: 600 }}>
                    <CheckCircle2 size={16} /> Ready for Exam
                  </span>
                ) : (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: 'var(--warning-color)', fontWeight: 600 }}>
                    <AlertCircle size={16} /> Pending (exactly 70 questions required)
                  </span>
                )}</span>
              </div>
            </div>

            {/* Questions List */}
            {questions.length === 0 ? (
              <p style={{ textAlign: 'center', color: '#64748b' }}>No active questions uploaded for this department.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                {questions.map((q, idx) => (
                  <div key={q.id} className="preview-question-block" style={{ pageBreakInside: 'avoid', borderBottom: '1px solid #f1f5f9', paddingBottom: '1.5rem' }}>
                    <div style={{ display: 'flex', gap: '0.75rem', fontSize: '1.05rem', fontWeight: 600, color: '#1e293b', marginBottom: '1rem' }}>
                      <span style={{ minWidth: '24px' }}>{q.question_no}.</span>
                      <div style={{ flex: 1, lineHeight: '1.5' }}>
                        <MathText text={q.question_text} />
                      </div>
                      <span className="no-print" style={{ fontSize: '0.8rem', fontWeight: 500, color: '#94a3b8', marginLeft: 'auto' }}>
                        ({q.marks} Mark)
                      </span>
                    </div>



                    {/* Options list */}
                    <div className="grid grid-2" style={{ gap: '1rem', paddingLeft: '2rem' }}>
                      {['option_a', 'option_b', 'option_c', 'option_d'].map((optKey, oIdx) => {
                        const optLetter = ['A', 'B', 'C', 'D'][oIdx];
                        const isCorrect = q.correct_option === optLetter;
                        return (
                          <div 
                            key={optKey} 
                            style={{
                              padding: '0.75rem 1rem',
                              border: isCorrect ? '1px solid #86efac' : '1px solid #e2e8f0',
                              borderRadius: '6px',
                              backgroundColor: isCorrect ? '#f0fdf4' : '#ffffff',
                              display: 'flex',
                              gap: '0.5rem',
                              alignItems: 'center'
                            }}
                          >
                            <span style={{
                              fontWeight: 'bold',
                              color: isCorrect ? 'var(--success-color)' : '#64748b',
                              fontSize: '0.9rem'
                            }}>
                              {optLetter}.
                            </span>
                            <div style={{ fontSize: '0.95rem', color: isCorrect ? '#166534' : '#334155' }}>
                              <MathText text={q[optKey]} />
                            </div>
                            {isCorrect && (
                              <span className="no-print" style={{
                                marginLeft: 'auto',
                                fontSize: '0.7rem',
                                backgroundColor: 'var(--success-bg)',
                                color: 'var(--success-color)',
                                padding: '0.1rem 0.4rem',
                                borderRadius: '4px',
                                fontWeight: 'bold'
                              }}>
                                Correct Answer
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>

                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Embedded print css overrides */}
      <style dangerouslySetInnerHTML={{__html: `
        @media print {
          .no-print {
            display: none !important;
          }
          .dashboard-layout {
            display: block !important;
            padding: 0 !important;
          }
          .page-container {
            margin: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
          }
          .card {
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
          }
          body {
            background-color: #fff !important;
            color: #000 !important;
          }
          .preview-question-block {
            border-bottom: 1px dashed #ccc !important;
          }
        }
      `}} />
    </div>
  );
}
