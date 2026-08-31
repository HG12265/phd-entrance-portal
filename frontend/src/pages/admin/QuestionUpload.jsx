import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Sidebar from '../../components/Sidebar';
import api, { getDepartmentQuestionSummary, uploadQuestionExcel } from '../../services/api';

export default function QuestionUpload() {
  const [departments, setDepartments] = useState([]);
  const [selectedDeptId, setSelectedDeptId] = useState('');
  const [deptSummary, setDeptSummary] = useState(null);
  
  const [file, setFile] = useState(null);
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [uploadResult, setUploadResult] = useState(null);

  // Fetch departments
  useEffect(() => {
    const fetchDepts = async () => {
      try {
        const res = await api.get('/api/admin/departments');
        // Only list active departments
        setDepartments(res.data.filter(d => d.is_active));
      } catch (err) {
        setError('Failed to fetch departments list.');
      }
    };
    fetchDepts();
  }, []);

  // Fetch department question summary when selection changes
  useEffect(() => {
    if (!selectedDeptId) {
      setDeptSummary(null);
      return;
    }
    
    const fetchSummary = async () => {
      setSummaryLoading(true);
      setError('');
      try {
        const res = await getDepartmentQuestionSummary(selectedDeptId);
        setDeptSummary(res.data);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to fetch department summary.');
      } finally {
        setSummaryLoading(false);
      }
    };
    fetchSummary();
  }, [selectedDeptId]);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setUploadResult(null);
    setSuccess('');
    setError('');
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!selectedDeptId) {
      setError('Please select a department.');
      return;
    }
    if (!file) {
      setError('Please select an Excel file to upload.');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');
    setUploadResult(null);

    try {
      const res = await uploadQuestionExcel(selectedDeptId, file, replaceExisting);
      const data = res.data;
      
      if (data.success_count === 70) {
        setSuccess('Question bank uploaded successfully!');
        setUploadResult(data);
        // Refresh department summary
        const summaryRes = await getDepartmentQuestionSummary(selectedDeptId);
        setDeptSummary(summaryRes.data);
        setFile(null);
        // Reset file input
        document.getElementById('question-file-input').value = '';
      } else {
        setError(data.message || 'Validation failed. Check error details below.');
        setUploadResult(data);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred during file upload.');
      if (err.response?.data?.errors) {
        setUploadResult({
          message: err.response.data.detail,
          errors: err.response.data.errors,
          success_count: 0,
          failed_count: err.response.data.errors.length,
          total_rows: err.response.data.errors.length
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadTemplate = async () => {
    setError('');
    try {
      const response = await api.get('/api/admin/questions/template', {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'Question_Upload_Template.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download template', err);
      setError('Failed to download questions excel template.');
    }
  };

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="page-container">
        <h1 className="mb-2">Question Bank Management</h1>
        <p className="mb-4 text-secondary">
          Upload and validate department-wise MCQ question papers (exactly 70 questions per department) with full support for Tamil translation, LaTeX math equations, and formatting symbols.
        </p>

        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <div className="grid grid-2" style={{ gridTemplateColumns: '1.2fr 0.8fr', alignItems: 'start', gap: '2rem' }}>
          {/* Upload panel */}
          <div className="card">
            <h3 className="card-title">Upload Excel Spreadsheet</h3>
            <form onSubmit={handleUploadSubmit}>
              <div className="form-group">
                <label className="form-label" htmlFor="dept-select">Academic Department</label>
                <select
                  id="dept-select"
                  className="form-input"
                  value={selectedDeptId}
                  onChange={(e) => setSelectedDeptId(e.target.value)}
                  required
                >
                  <option value="">-- Choose Department --</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.department_name} ({d.department_code})
                    </option>
                  ))}
                </select>
              </div>

              {selectedDeptId && deptSummary && (
                <div style={{
                  padding: '1rem',
                  backgroundColor: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '6px',
                  marginBottom: '1.5rem',
                  fontSize: '0.9rem'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <strong>Active Questions:</strong>
                    <span style={{
                      fontWeight: 'bold',
                      color: deptSummary.is_ready ? 'var(--success-color)' : 'var(--danger-color)'
                    }}>
                      {deptSummary.active_questions} / 70
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <strong>Status:</strong>
                    <span className="user-badge" style={{
                      backgroundColor: deptSummary.is_ready ? 'var(--success-bg)' : 'var(--danger-bg)',
                      color: deptSummary.is_ready ? 'var(--success-color)' : 'var(--danger-color)'
                    }}>
                      {deptSummary.is_ready ? 'Ready (70 Questions)' : 'Pending Upload'}
                    </span>
                  </div>
                  {deptSummary.last_uploaded_at && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#64748b', marginTop: '0.5rem' }}>
                      <span>Last Uploaded:</span>
                      <span>{new Date(deptSummary.last_uploaded_at).toLocaleString()}</span>
                    </div>
                  )}
                  {deptSummary.is_ready && (
                    <Link
                      to={`/admin/questions/preview/${selectedDeptId}`}
                      className="btn btn-secondary w-full mt-3"
                      style={{ textAlign: 'center', display: 'block', textDecoration: 'none' }}
                    >
                      👁️ Preview Current Questions
                    </Link>
                  )}
                </div>
              )}

              <div className="form-group">
                <label className="form-label" htmlFor="question-file-input">Select Spreadsheet (.xlsx, .xls)</label>
                <input
                  id="question-file-input"
                  type="file"
                  accept=".xlsx, .xls"
                  className="form-input"
                  onChange={handleFileChange}
                  required
                  disabled={!selectedDeptId}
                />
              </div>

              {deptSummary && deptSummary.active_questions > 0 && (
                <div style={{
                  padding: '0.75rem',
                  backgroundColor: '#fffbeb',
                  border: '1px solid #fef3c7',
                  borderRadius: '6px',
                  marginBottom: '1.25rem'
                }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={replaceExisting}
                      onChange={(e) => setReplaceExisting(e.target.checked)}
                      style={{ width: '18px', height: '18px' }}
                    />
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#b45309' }}>
                      Replace existing question bank (Soft deactivates old questions)
                    </span>
                  </label>
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary w-full mt-2"
                disabled={loading || !selectedDeptId}
              >
                {loading ? 'Uploading & Validating...' : 'Upload Question Bank'}
              </button>
            </form>
          </div>

          {/* Guidelines / Template download card */}
          <div className="card">
            <h3 className="card-title">Spreadsheet Guidelines</h3>
            <p style={{ fontSize: '0.85rem', lineHeight: '1.4', marginBottom: '1rem' }}>
              Upload exactly <strong>70 MCQ questions</strong> in an Excel spreadsheet. The system automatically maps matching subjects, parses custom LaTeX/formulas, and preserves UTF-8 characters for Tamil syntax.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem' }}>
              <button onClick={handleDownloadTemplate} className="btn btn-secondary w-full" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                <span>📥</span> Download Excel Template
              </button>
            </div>

            <h4 style={{ fontSize: '0.9rem', marginBottom: '0.5rem', fontWeight: 600 }}>Header Requirements:</h4>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', fontSize: '0.75rem' }}>
              <span className="user-badge" style={{ backgroundColor: '#f1f5f9', color: '#1e293b' }}>Question No</span>
              <span className="user-badge" style={{ backgroundColor: '#f1f5f9', color: '#1e293b' }}>Question Text</span>
              <span className="user-badge" style={{ backgroundColor: '#f1f5f9', color: '#1e293b' }}>Option A</span>
              <span className="user-badge" style={{ backgroundColor: '#f1f5f9', color: '#1e293b' }}>Option B</span>
              <span className="user-badge" style={{ backgroundColor: '#f1f5f9', color: '#1e293b' }}>Option C</span>
              <span className="user-badge" style={{ backgroundColor: '#f1f5f9', color: '#1e293b' }}>Option D</span>
              <span className="user-badge" style={{ backgroundColor: '#f1f5f9', color: '#1e293b' }}>Correct Option</span>
              <span className="user-badge" style={{ backgroundColor: '#e2e8f0', color: '#0f172a', fontWeight: 'bold' }}>Marks</span>
            </div>
            <div style={{ marginTop: '1rem', fontSize: '0.8rem', color: '#64748b' }}>
              <strong>Formula example:</strong> <code>{"( E = mc^2 )"}</code>, <code>{"( \\frac{x}{y} )"}</code>
            </div>
          </div>
        </div>

        {/* Upload summary / errors display */}
        {uploadResult && (
          <div className="card mt-4" style={{ borderLeft: uploadResult.errors?.length > 0 ? '4px solid var(--danger-color)' : '4px solid var(--success-color)' }}>
            <h3 className="card-title">Processing Results Summary</h3>
            <div className="grid grid-4" style={{ gap: '1rem', marginBottom: '1.5rem' }}>
              <div style={{ padding: '0.75rem', backgroundColor: '#f8fafc', borderRadius: '4px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Total Rows</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{uploadResult.total_rows}</div>
              </div>
              <div style={{ padding: '0.75rem', backgroundColor: '#ecfdf5', borderRadius: '4px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.8rem', color: '#047857' }}>Valid Rows</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#047857' }}>{uploadResult.success_count}</div>
              </div>
              <div style={{ padding: '0.75rem', backgroundColor: '#fef2f2', borderRadius: '4px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.8rem', color: '#b91c1c' }}>Failed Rows</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#b91c1c' }}>{uploadResult.failed_count}</div>
              </div>
              <div style={{ padding: '0.75rem', backgroundColor: '#f0f9ff', borderRadius: '4px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.8rem', color: '#0369a1' }}>Replaced Old</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#0369a1' }}>{uploadResult.replaced_existing ? 'Yes' : 'No'}</div>
              </div>
            </div>

            {uploadResult.errors && uploadResult.errors.length > 0 && (
              <div>
                <h4 style={{ color: '#b91c1c', marginBottom: '0.75rem' }}>Validation Error Logs</h4>
                <div className="table-container" style={{ margin: 0, maxHeight: '300px', overflowY: 'auto' }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th style={{ width: '80px' }}>Row No</th>
                        <th style={{ width: '100px' }}>Q.No</th>
                        <th>Error Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {uploadResult.errors.map((err, i) => (
                        <tr key={i} style={{ backgroundColor: '#fff5f5' }}>
                          <td><strong>{err.row}</strong></td>
                          <td>{err.question_no || <span style={{ color: '#94a3b8' }}>-</span>}</td>
                          <td style={{ color: '#b91c1c', fontSize: '0.85rem' }}>{err.error}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
