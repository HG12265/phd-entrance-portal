import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../../components/Sidebar';
import { FileSpreadsheet, FileText, ChevronDown, Download } from 'lucide-react';
import api, {
  getOverallResult,
  getDepartmentWiseReport,
  getDepartmentDetail,
  downloadOverallResultExcel,
  downloadDepartmentWiseExcel,
  downloadDepartmentWiseDetailsExcel,
  downloadDepartmentReportExcel,
  downloadOverallResultPdf,
  downloadDepartmentWisePdf,
  downloadDepartmentReportPdf
} from '../../services/api';

function ResultBadge({ value }) {
  if (!value) return <span style={{ color: '#94a3b8' }}>--</span>;
  const isPass = value === 'PASS' || value === 'QUALIFIED';
  return (
    <span style={{
      padding: '0.2rem 0.6rem', borderRadius: '20px', fontSize: '0.72rem',
      fontWeight: 700, letterSpacing: '0.04em',
      backgroundColor: isPass ? '#d1fae5' : '#fee2e2',
      color: isPass ? '#065f46' : '#991b1b'
    }}>{value}</span>
  );
}

function QBankBadge({ status }) {
  const isReady = status && status.includes('Ready');
  return (
    <span style={{
      padding: '0.2rem 0.6rem', borderRadius: '20px', fontSize: '0.72rem', fontWeight: 700,
      backgroundColor: isReady ? '#d1fae5' : '#fff7ed',
      color: isReady ? '#065f46' : '#9a3412'
    }}>{status || '--'}</span>
  );
}

function SummaryCard({ label, value, accent, sub }) {
  return (
    <div style={{
      background: '#fff', border: '1px solid #e2e8f0',
      borderTop: '4px solid ' + (accent || '#6366f1'),
      borderRadius: '10px', padding: '1rem 1.2rem', textAlign: 'center', minWidth: 0
    }}>
      <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#0f172a', margin: '0.3rem 0 0.1rem' }}>{value !== null && value !== undefined ? value : '--'}</div>
      {sub && <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>{sub}</div>}
    </div>
  );
}

function Pagination({ page, pages, total, onChange }) {
  if (pages <= 1) return null;
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem', marginTop: '1.25rem' }}>
      <button className="btn btn-secondary" disabled={page === 1} onClick={() => onChange(page - 1)}>Prev</button>
      <span style={{ fontSize: '0.85rem', color: '#64748b' }}>Page <strong>{page}</strong> of {pages} ({total} total)</span>
      <button className="btn btn-secondary" disabled={page === pages} onClick={() => onChange(page + 1)}>Next</button>
    </div>
  );
}

function SectionHeader({ title, sub }) {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#0f172a' }}>{title}</h2>
      {sub && <p style={{ margin: '0.2rem 0 0', fontSize: '0.8rem', color: '#64748b' }}>{sub}</p>}
    </div>
  );
}

function triggerDownload(blobData, filename, mime) {
  const blob = new Blob([blobData], { type: mime });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

const EXCEL_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

const labelStyle = {
  display: 'block', fontSize: '0.72rem', fontWeight: 700, color: '#64748b',
  textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.3rem'
};

const selectStyle = {
  padding: '0 0.6rem', height: '36px', borderRadius: '6px',
  border: '1px solid #cbd5e1', fontSize: '0.82rem', color: '#0f172a',
  background: '#fff', width: '100%', boxSizing: 'border-box', cursor: 'pointer'
};

const loadingStyle = { textAlign: 'center', padding: '3rem', color: '#94a3b8', fontSize: '0.9rem' };

export default function Reports() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [selectedSession, setSelectedSession] = useState('');
  const [selectedDept, setSelectedDept] = useState('');
  const [resultStatus, setResultStatus] = useState('');
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [overallLoading, setOverallLoading] = useState(true);
  const [overallData, setOverallData] = useState(null);
  const [overallPage, setOverallPage] = useState(1);
  const [deptWiseLoading, setDeptWiseLoading] = useState(true);
  const [deptWiseData, setDeptWiseData] = useState(null);
  const [detailDeptId, setDetailDeptId] = useState(null);
  const [detailDeptName, setDetailDeptName] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [detailResultStatus, setDetailResultStatus] = useState('');
  const [detailSearch, setDetailSearch] = useState('');
  const [detailSearchInput, setDetailSearchInput] = useState('');
  const [showAbsentees, setShowAbsentees] = useState(false);
  const [exporting, setExporting] = useState('');
  const [showExcelDropdown, setShowExcelDropdown] = useState(false);
  const [showPdfDropdown, setShowPdfDropdown] = useState(false);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (!e.target.closest('.export-dropdown-container')) {
        setShowExcelDropdown(false);
        setShowPdfDropdown(false);
      }
    };
    document.addEventListener('click', handleOutsideClick);
    return () => document.removeEventListener('click', handleOutsideClick);
  }, []);

  useEffect(() => {
    const load = async () => {
      try {
        const [sessRes, deptRes] = await Promise.all([
          api.get('/api/admin/exam-sessions/'),
          api.get('/api/admin/departments')
        ]);
        setSessions(sessRes.data);
        setDepartments(deptRes.data);
        if (sessRes.data.length > 0) setSelectedSession(sessRes.data[0].id);
      } catch (err) { console.error('Failed to load filters:', err); }
    };
    load();
  }, []);

  const fetchOverall = useCallback(async () => {
    setOverallLoading(true);
    try {
      const res = await getOverallResult({
        exam_session_id: selectedSession || undefined,
        department_id: selectedDept || undefined,
        result_status: resultStatus || undefined,
        search: search || undefined,
        page: overallPage, limit: 50
      });
      setOverallData(res.data);
    } catch (err) { console.error('Failed to load overall result:', err); }
    finally { setOverallLoading(false); }
  }, [selectedSession, selectedDept, resultStatus, search, overallPage]);

  useEffect(() => { fetchOverall(); }, [fetchOverall]);

  const fetchDeptWise = useCallback(async () => {
    setDeptWiseLoading(true);
    try {
      const res = await getDepartmentWiseReport({ exam_session_id: selectedSession || undefined });
      setDeptWiseData(res.data);
    } catch (err) { console.error('Failed to load dept-wise:', err); }
    finally { setDeptWiseLoading(false); }
  }, [selectedSession]);

  useEffect(() => { fetchDeptWise(); }, [fetchDeptWise]);

  const fetchDeptDetail = useCallback(async () => {
    if (!detailDeptId) return;
    setDetailLoading(true);
    try {
      const res = await getDepartmentDetail(detailDeptId, {
        exam_session_id: selectedSession || undefined,
        result_status: detailResultStatus || undefined,
        search: detailSearch || undefined
      });
      setDetailData(res.data);
      setShowAbsentees(false);
    } catch (err) { console.error('Failed to load dept detail:', err); }
    finally { setDetailLoading(false); }
  }, [detailDeptId, selectedSession, detailResultStatus, detailSearch]);

  useEffect(() => { fetchDeptDetail(); }, [fetchDeptDetail]);
  useEffect(() => { setOverallPage(1); }, [selectedSession, selectedDept, resultStatus, search]);

  // Debounce search inputs to avoid triggering queries on every key stroke
  useEffect(() => {
    const handler = setTimeout(() => {
      setSearch(searchInput);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchInput]);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDetailSearch(detailSearchInput);
    }, 300);
    return () => clearTimeout(handler);
  }, [detailSearchInput]);

  const handleSearchSubmit = (e) => { e.preventDefault(); };
  const handleDetailSearchSubmit = (e) => { e.preventDefault(); };

  const openDeptDetail = (dept) => {
    setDetailDeptId(dept.department_id);
    setDetailDeptName(dept.department_name);
    setDetailResultStatus('');
    setDetailSearch('');
    setDetailSearchInput('');
    setDetailData(null);
    setTimeout(() => {
      const el = document.getElementById('dept-detail-section');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 120);
  };

  const closeDeptDetail = () => { setDetailDeptId(null); setDetailData(null); };

  const handleExportOverall = async () => {
    setExporting('overall');
    try {
      const res = await downloadOverallResultExcel({
        exam_session_id: selectedSession || undefined,
        department_id: selectedDept || undefined,
        result_status: resultStatus || undefined
      });
      triggerDownload(res.data, 'overall_result.xlsx', EXCEL_MIME);
    } catch { alert('Failed to export Overall Result Excel.'); }
    finally { setExporting(''); }
  };

  const handleExportOverallPdf = async () => {
    setExporting('overall_pdf');
    try {
      const res = await downloadOverallResultPdf({
        exam_session_id: selectedSession || undefined,
        department_id: selectedDept || undefined,
        result_status: resultStatus || undefined
      });
      triggerDownload(res.data, 'overall_result.pdf', 'application/pdf');
    } catch { alert('Failed to export Overall Result PDF.'); }
    finally { setExporting(''); }
  };

  const handleExportDeptWise = async () => {
    setExporting('deptwise');
    try {
      const res = await downloadDepartmentWiseExcel({ exam_session_id: selectedSession || undefined });
      triggerDownload(res.data, 'department_wise_summary.xlsx', EXCEL_MIME);
    } catch { alert('Failed to export Department-wise Summary Excel.'); }
    finally { setExporting(''); }
  };

  const handleExportDeptWiseDetails = async () => {
    setExporting('deptwise_details');
    try {
      const res = await downloadDepartmentWiseDetailsExcel({ exam_session_id: selectedSession || undefined });
      triggerDownload(res.data, 'department_wise_details.xlsx', EXCEL_MIME);
    } catch { alert('Failed to export Department-wise Details Excel.'); }
    finally { setExporting(''); }
  };

  const handleExportDeptWisePdf = async () => {
    setExporting('deptwise_pdf');
    try {
      const res = await downloadDepartmentWisePdf({ exam_session_id: selectedSession || undefined });
      triggerDownload(res.data, 'department_wise_summary.pdf', 'application/pdf');
    } catch { alert('Failed to export Department-wise Summary PDF.'); }
    finally { setExporting(''); }
  };

  const handleExportDeptReport = async () => {
    const deptId = detailDeptId || selectedDept;
    if (!deptId) { alert('Please select a department first.'); return; }
    setExporting('deptreport');
    try {
      const res = await downloadDepartmentReportExcel(deptId, {
        exam_session_id: selectedSession || undefined,
        result_status: detailResultStatus || resultStatus || undefined
      });
      triggerDownload(res.data, 'department_' + deptId + '_result.xlsx', EXCEL_MIME);
    } catch { alert('Failed to export Selected Department Excel.'); }
    finally { setExporting(''); }
  };

  const handleExportDeptReportPdf = async () => {
    const deptId = detailDeptId || selectedDept;
    if (!deptId) { alert('Please select a department first.'); return; }
    setExporting('deptreport_pdf');
    try {
      const res = await downloadDepartmentReportPdf(deptId, {
        exam_session_id: selectedSession || undefined,
        result_status: detailResultStatus || resultStatus || undefined
      });
      triggerDownload(res.data, 'department_' + deptId + '_result.pdf', 'application/pdf');
    } catch { alert('Failed to export Selected Department PDF.'); }
    finally { setExporting(''); }
  };

  const activeDeptForExport = detailDeptId || selectedDept;
  const summary = overallData ? overallData.summary : null;

  return (
    <div className="dashboard-layout">
      <style>{`
        .reports-dropdown-item {
          display: flex;
          align-items: center;
          gap: 0.65rem;
          width: 100%;
          padding: 0.75rem 1.25rem;
          border: none;
          background: none;
          text-align: left;
          font-size: 0.82rem;
          color: #334155;
          cursor: pointer;
          transition: all 0.15s ease;
          font-weight: 500;
        }
        .reports-dropdown-item:hover {
          background-color: #f1f5f9;
          color: #0f172a;
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      <Sidebar />
      <div className="page-container" style={{ maxWidth: '1400px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '1.5rem' }}>
          <div>
            <h1 style={{ margin: 0, color: 'var(--text-primary)', fontSize: '1.6rem', fontWeight: 800 }}>Reports &amp; Exam Results</h1>
            <p style={{ margin: '0.3rem 0 0', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Overall results and department-wise exam reports. Summary reflects current filters.</p>
          </div>
          
          {/* Dropdown Restructuring with Icons */}
          <div className="export-dropdown-container" style={{ display: 'flex', gap: '0.8rem', alignItems: 'center' }}>
            
            {/* Excel Dropdown Button */}
            <div style={{ position: 'relative' }}>
              <button 
                className="btn"
                onClick={() => {
                  setShowExcelDropdown(prev => !prev);
                  setShowPdfDropdown(false);
                }}
                disabled={exporting !== ''}
                style={{ 
                  display: 'inline-flex', 
                  alignItems: 'center', 
                  gap: '0.5rem',
                  padding: '0.55rem 1.1rem',
                  backgroundColor: '#10b981',
                  borderColor: '#059669',
                  color: '#fff',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  borderRadius: '6px',
                  cursor: 'pointer',
                  border: '1px solid transparent',
                  boxShadow: '0 4px 6px -1px rgba(16, 185, 129, 0.15)',
                  transition: 'all 0.2s'
                }}
              >
                <FileSpreadsheet size={16} />
                <span>Export Excel</span>
                <ChevronDown size={14} style={{ transform: showExcelDropdown ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
              </button>

              {showExcelDropdown && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  right: 0,
                  marginTop: '0.5rem',
                  backgroundColor: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '8px',
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                  zIndex: 100,
                  minWidth: '280px',
                  padding: '0.4rem 0',
                  animation: 'fadeIn 0.2s ease-out'
                }}>
                  <button
                    onClick={() => { handleExportOverall(); setShowExcelDropdown(false); }}
                    className="reports-dropdown-item"
                  >
                    <Download size={14} style={{ color: '#10b981' }} />
                    <span>Export Overall Result</span>
                  </button>
                  <button
                    onClick={() => { handleExportDeptWise(); setShowExcelDropdown(false); }}
                    className="reports-dropdown-item"
                  >
                    <Download size={14} style={{ color: '#10b981' }} />
                    <span>Export Dept-wise Summary</span>
                  </button>
                  <button
                    onClick={() => { handleExportDeptWiseDetails(); setShowExcelDropdown(false); }}
                    className="reports-dropdown-item"
                  >
                    <Download size={14} style={{ color: '#10b981' }} />
                    <span>Export Dept-wise Details</span>
                  </button>
                  <div style={{ borderTop: '1px solid #f1f5f9', margin: '0.4rem 0' }}></div>
                  <button
                    disabled={!activeDeptForExport}
                    onClick={() => { handleExportDeptReport(); setShowExcelDropdown(false); }}
                    className={activeDeptForExport ? "reports-dropdown-item" : ""}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.65rem',
                      width: '100%',
                      padding: '0.75rem 1.25rem',
                      border: 'none',
                      background: 'none',
                      textAlign: 'left',
                      fontSize: '0.82rem',
                      color: activeDeptForExport ? '#334155' : '#94a3b8',
                      cursor: activeDeptForExport ? 'pointer' : 'not-allowed',
                      opacity: activeDeptForExport ? 1 : 0.6,
                      fontWeight: 500
                    }}
                  >
                    <Download size={14} style={{ color: activeDeptForExport ? '#10b981' : '#94a3b8' }} />
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span>Export Selected Dept</span>
                      {!activeDeptForExport && <span style={{ fontSize: '0.65rem', color: '#94a3b8', marginTop: '2px' }}>Choose a department first</span>}
                    </div>
                  </button>
                </div>
              )}
            </div>

            {/* PDF Dropdown Button */}
            <div style={{ position: 'relative' }}>
              <button 
                className="btn"
                onClick={() => {
                  setShowPdfDropdown(prev => !prev);
                  setShowExcelDropdown(false);
                }}
                disabled={exporting !== ''}
                style={{ 
                  display: 'inline-flex', 
                  alignItems: 'center', 
                  gap: '0.5rem',
                  padding: '0.55rem 1.1rem',
                  backgroundColor: '#ef4444',
                  borderColor: '#dc2626',
                  color: '#fff',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  borderRadius: '6px',
                  cursor: 'pointer',
                  border: '1px solid transparent',
                  boxShadow: '0 4px 6px -1px rgba(239, 68, 68, 0.15)',
                  transition: 'all 0.2s'
                }}
              >
                <FileText size={16} />
                <span>Export PDF</span>
                <ChevronDown size={14} style={{ transform: showPdfDropdown ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
              </button>

              {showPdfDropdown && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  right: 0,
                  marginTop: '0.5rem',
                  backgroundColor: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '8px',
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                  zIndex: 100,
                  minWidth: '260px',
                  padding: '0.4rem 0',
                  animation: 'fadeIn 0.2s ease-out'
                }}>
                  <button
                    onClick={() => { handleExportOverallPdf(); setShowPdfDropdown(false); }}
                    className="reports-dropdown-item"
                  >
                    <Download size={14} style={{ color: '#ef4444' }} />
                    <span>Export Overall Result</span>
                  </button>
                  <button
                    onClick={() => { handleExportDeptWisePdf(); setShowPdfDropdown(false); }}
                    className="reports-dropdown-item"
                  >
                    <Download size={14} style={{ color: '#ef4444' }} />
                    <span>Export Dept-wise Summary</span>
                  </button>
                  <div style={{ borderTop: '1px solid #f1f5f9', margin: '0.4rem 0' }}></div>
                  <button
                    disabled={!activeDeptForExport}
                    onClick={() => { handleExportDeptReportPdf(); setShowPdfDropdown(false); }}
                    className={activeDeptForExport ? "reports-dropdown-item" : ""}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.65rem',
                      width: '100%',
                      padding: '0.75rem 1.25rem',
                      border: 'none',
                      background: 'none',
                      textAlign: 'left',
                      fontSize: '0.82rem',
                      color: activeDeptForExport ? '#334155' : '#94a3b8',
                      cursor: activeDeptForExport ? 'pointer' : 'not-allowed',
                      opacity: activeDeptForExport ? 1 : 0.6,
                      fontWeight: 500
                    }}
                  >
                    <Download size={14} style={{ color: activeDeptForExport ? '#ef4444' : '#94a3b8' }} />
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span>Export Selected Dept</span>
                      {!activeDeptForExport && <span style={{ fontSize: '0.65rem', color: '#94a3b8', marginTop: '2px' }}>Choose a department first</span>}
                    </div>
                  </button>
                </div>
              )}
            </div>

          </div>
        </div>

        <div className="card" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.8rem', alignItems: 'end' }}>
            <div>
              <label style={labelStyle}>Exam Session</label>
              <select style={selectStyle} value={selectedSession} onChange={(e) => setSelectedSession(e.target.value)}>
                <option value="">All Sessions</option>
                {sessions.map(s => <option key={s.id} value={s.id}>{s.session_name}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Department Filter</label>
              <select style={selectStyle} value={selectedDept} onChange={(e) => setSelectedDept(e.target.value)}>
                <option value="">All Departments</option>
                {departments.map(d => <option key={d.id} value={d.id}>{d.department_name}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Result Status</label>
              <select style={selectStyle} value={resultStatus} onChange={(e) => setResultStatus(e.target.value)}>
                <option value="">All (QUALIFIED &amp; NOT QUALIFIED)</option>
                <option value="QUALIFIED">QUALIFIED (Score &gt;= 28)</option>
                <option value="NOT QUALIFIED">NOT QUALIFIED (Score &lt; 28)</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Search Overall Table</label>
              <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '0.4rem' }}>
                <input type="text" placeholder="Type to search..." style={{ ...selectStyle, flex: 1 }} value={searchInput} onChange={(e) => setSearchInput(e.target.value)} />
              </form>
            </div>
          </div>
          {search && (
            <div style={{ marginTop: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.78rem', color: '#64748b' }}>Searching: <strong>"{search}"</strong></span>
              <button onClick={() => { setSearch(''); setSearchInput(''); }} style={{ background: 'none', border: '1px solid #cbd5e1', borderRadius: '4px', padding: '0 0.5rem', fontSize: '0.72rem', cursor: 'pointer', color: '#64748b' }}>Clear</button>
            </div>
          )}
        </div>

        <div className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
          <SectionHeader title="Overall Exam Result" sub="Official attempts only. Excludes in-progress and force-reopened attempts. Summary reflects current filters." />
          {overallLoading ? <div style={loadingStyle}>Loading results...</div> : summary ? (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
                <SummaryCard label="Total Registered" value={summary.total_registered} accent="#6366f1" />
                <SummaryCard label="Appeared" value={summary.appeared} accent="#10b981" />
                <SummaryCard label="Absent" value={summary.absent} accent="#f59e0b" />
                <SummaryCard label="Qualified" value={summary.passed} accent="#22c55e" sub={summary.appeared > 0 ? summary.pass_percentage + '%' : null} />
                <SummaryCard label="Not Qualified" value={summary.failed} accent="#ef4444" />
                <SummaryCard label="Qualified %" value={summary.pass_percentage + '%'} accent="#8b5cf6" />
                <SummaryCard label="Avg Score" value={summary.average_score} accent="#0ea5e9" sub="out of 70" />
                <SummaryCard label="Lowest" value={summary.lowest_score} accent="#f97316" sub="out of 70" />
                <SummaryCard label="Highest" value={summary.highest_score} accent="#14b8a6" sub="out of 70" />
              </div>
              {overallData.total === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>No candidates match the current filters.</div>
              ) : (
                <>
                  <div style={{ overflowX: 'auto', maxHeight: '650px', overflowY: 'auto', position: 'relative' }}>
                    <table className="table" style={{ fontSize: '0.8rem' }}>
                      <thead>
                        <tr>
                          <th>#</th><th>Application ID</th><th style={{ textAlign: 'left' }}>Applicant Name</th>
                          <th>Initial</th><th style={{ textAlign: 'left' }}>Department</th>
                          <th style={{ textAlign: 'left' }}>Programme Offered</th><th style={{ textAlign: 'left' }}>Subject</th>
                          <th>Category (FT/PT)</th><th>Score</th><th>Correct</th><th>Incorrect</th><th>Unanswered</th>
                          <th>Result</th><th>Type</th><th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {overallData.results.map((row) => (
                          <tr key={row.candidate_id}>
                            <td><strong>{row.rank}</strong></td>
                            <td><span style={{ fontFamily: 'monospace', fontSize: '0.78rem', fontWeight: 600 }}>{row.application_id}</span></td>
                            <td style={{ textAlign: 'left' }}>{row.initial ? <span style={{ color: '#64748b' }}>{row.initial}. </span> : null}{row.applicant_name}</td>
                            <td>{row.initial || '--'}</td>
                            <td style={{ textAlign: 'left' }}>{row.department_name}</td>
                            <td style={{ textAlign: 'left' }}>{row.programme_offered || '--'}</td>
                            <td style={{ textAlign: 'left' }}>{row.subject || '--'}</td>
                            <td>{row.category_ft_pt || '--'}</td>
                            <td><strong style={{ color: '#2563eb' }}>{row.score}</strong><span style={{ color: '#94a3b8', fontSize: '0.68rem' }}>/70</span></td>
                            <td><span style={{ color: '#16a34a', fontWeight: 600 }}>{row.correct_count}</span></td>
                            <td><span style={{ color: '#dc2626', fontWeight: 600 }}>{row.wrong_count}</span></td>
                            <td><span style={{ color: '#64748b' }}>{row.unanswered_count}</span></td>
                            <td><ResultBadge value={row.result_status} /></td>
                            <td><span style={{ fontSize: '0.72rem', color: '#64748b' }}>{row.submission_type === 'manual' ? 'Manual' : 'Auto'}</span></td>
                            <td><button className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.72rem' }} onClick={() => navigate('/admin/reports/candidate/' + row.candidate_id)}>Review</button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <Pagination page={overallData.page} pages={overallData.pages} total={overallData.total} onChange={setOverallPage} />
                </>
              )}
            </>
          ) : <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>No data available.</div>}
        </div>

        <div className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
          <SectionHeader title="Department-wise Exam Report" sub="Grouped by department. Click View Report to see candidate details for that department." />
          {deptWiseLoading ? <div style={loadingStyle}>Loading department report...</div> : !deptWiseData || deptWiseData.departments.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>No departments found.</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="table" style={{ fontSize: '0.82rem' }}>
                <thead>
                  <tr>
                    <th>#</th><th style={{ textAlign: 'left' }}>Department</th><th>Registered</th><th>Appeared</th>
                    <th>Absent</th><th>Qualified</th><th>Not Qualified</th><th>Qualified %</th><th>Avg Score</th>
                    <th>Highest</th><th>Lowest</th><th>Q.Bank Status</th><th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {deptWiseData.departments.map((dept, idx) => {
                    const isActive = detailDeptId === dept.department_id;
                    return (
                      <tr key={dept.department_id} style={{ backgroundColor: isActive ? '#eff6ff' : undefined }}>
                        <td>{idx + 1}</td>
                        <td style={{ textAlign: 'left', fontWeight: 600 }}>{dept.department_name}</td>
                        <td>{dept.registered}</td>
                        <td><strong style={{ color: '#0284c7' }}>{dept.appeared}</strong></td>
                        <td style={{ color: '#f59e0b' }}>{dept.absent}</td>
                        <td><strong style={{ color: '#16a34a' }}>{dept.passed}</strong></td>
                        <td><strong style={{ color: '#dc2626' }}>{dept.failed}</strong></td>
                        <td>{dept.appeared > 0 ? dept.pass_percentage + '%' : '--'}</td>
                        <td>{dept.appeared > 0 ? dept.average_score : '--'}</td>
                        <td>{dept.appeared > 0 ? <strong>{dept.highest_score}</strong> : '--'}</td>
                        <td>{dept.appeared > 0 ? dept.lowest_score : '--'}</td>
                        <td><QBankBadge status={dept.question_bank_status} /></td>
                        <td>
                          {isActive ? <button className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.72rem' }} onClick={closeDeptDetail}>Close</button>
                            : <button className="btn btn-primary" style={{ padding: '0.25rem 0.6rem', fontSize: '0.72rem' }} onClick={() => openDeptDetail(dept)}>View Report</button>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {detailDeptId && (
          <div id="dept-detail-section" className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem', borderTop: '4px solid #6366f1' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <SectionHeader title={'Department Report -- ' + detailDeptName} sub="Detailed candidate results and absentee list for this department." />
              <button className="btn btn-secondary" style={{ fontSize: '0.8rem' }} onClick={closeDeptDetail}>Close Detail</button>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div>
                <label style={labelStyle}>Result Filter</label>
                <select style={{ ...selectStyle, width: '160px' }} value={detailResultStatus} onChange={(e) => setDetailResultStatus(e.target.value)}>
                  <option value="">All (QUALIFIED &amp; NOT QUALIFIED)</option>
                  <option value="QUALIFIED">QUALIFIED only</option>
                  <option value="NOT QUALIFIED">NOT QUALIFIED only</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Search</label>
                <form onSubmit={handleDetailSearchSubmit} style={{ display: 'flex', gap: '0.4rem' }}>
                  <input type="text" placeholder="Type to search..." style={{ ...selectStyle, width: '200px' }} value={detailSearchInput} onChange={(e) => setDetailSearchInput(e.target.value)} />
                </form>
              </div>
            </div>
            {detailLoading ? <div style={loadingStyle}>Loading department detail...</div> : detailData ? (
              <>
                {(() => {
                  const s = detailData.summary;
                  return (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
                      <SummaryCard label="Registered" value={s.registered} accent="#6366f1" />
                      <SummaryCard label="Appeared" value={s.appeared} accent="#10b981" />
                      <SummaryCard label="Absent" value={s.absent} accent="#f59e0b" />
                      <SummaryCard label="Qualified" value={s.passed} accent="#22c55e" />
                      <SummaryCard label="Not Qualified" value={s.failed} accent="#ef4444" />
                      <SummaryCard label="Qualified %" value={s.pass_percentage + '%'} accent="#8b5cf6" />
                      <SummaryCard label="Avg Score" value={s.average_score} accent="#0ea5e9" sub="out of 70" />
                      <SummaryCard label="Lowest" value={s.lowest_score} accent="#f97316" />
                      <SummaryCard label="Highest" value={s.highest_score} accent="#14b8a6" />
                    </div>
                  );
                })()}
                {detailData.results.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '1.5rem', color: '#94a3b8', background: '#f8fafc', borderRadius: '8px' }}>No appeared candidates match the filters.</div>
                ) : (
                  <div style={{ overflowX: 'auto', maxHeight: '650px', overflowY: 'auto', position: 'relative', marginBottom: '1rem' }}>
                    <table className="table" style={{ fontSize: '0.8rem' }}>
                      <thead>
                        <tr>
                          <th>#</th><th>Application ID</th><th style={{ textAlign: 'left' }}>Applicant Name</th>
                          <th>Initial</th><th style={{ textAlign: 'left' }}>Programme Offered</th>
                          <th style={{ textAlign: 'left' }}>Subject</th><th>Category (FT/PT)</th>
                          <th>Score</th><th>Correct</th><th>Incorrect</th><th>Unanswered</th><th>Result</th><th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detailData.results.map((row) => (
                          <tr key={row.candidate_id}>
                            <td><strong>{row.rank}</strong></td>
                            <td><span style={{ fontFamily: 'monospace', fontSize: '0.78rem', fontWeight: 600 }}>{row.application_id}</span></td>
                            <td style={{ textAlign: 'left' }}>{row.initial ? <span style={{ color: '#64748b' }}>{row.initial}. </span> : null}{row.applicant_name}</td>
                            <td>{row.initial || '--'}</td>
                            <td style={{ textAlign: 'left' }}>{row.programme_offered || '--'}</td>
                            <td style={{ textAlign: 'left' }}>{row.subject || '--'}</td>
                            <td>{row.category_ft_pt || '--'}</td>
                            <td><strong style={{ color: '#2563eb' }}>{row.score}</strong><span style={{ color: '#94a3b8', fontSize: '0.68rem' }}>/70</span></td>
                            <td><span style={{ color: '#16a34a', fontWeight: 600 }}>{row.correct_count}</span></td>
                            <td><span style={{ color: '#dc2626', fontWeight: 600 }}>{row.wrong_count}</span></td>
                            <td><span style={{ color: '#64748b' }}>{row.unanswered_count}</span></td>
                            <td><ResultBadge value={row.result_status} /></td>
                            <td><button className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.72rem' }} onClick={() => navigate('/admin/reports/candidate/' + row.candidate_id)}>Review</button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <div style={{ marginTop: '1rem' }}>
                  <button className="btn btn-secondary" style={{ fontSize: '0.8rem', marginBottom: '0.75rem' }} onClick={() => setShowAbsentees(prev => !prev)}>
                    {showAbsentees ? 'Hide' : 'Show'} Absent Candidates ({detailData.absentees.length})
                  </button>
                  {showAbsentees && (detailData.absentees.length === 0 ? (
                    <div style={{ padding: '1rem', color: '#94a3b8', textAlign: 'center', background: '#f8fafc', borderRadius: '8px' }}>No absent candidates for this department.</div>
                  ) : (
                    <div style={{ overflowX: 'auto' }}>
                      <table className="table" style={{ fontSize: '0.8rem' }}>
                        <thead>
                          <tr>
                            <th>#</th><th>Application ID</th><th style={{ textAlign: 'left' }}>Applicant Name</th>
                            <th>Initial</th><th>Mobile</th><th>Email</th><th>Category (FT/PT)</th>
                            <th style={{ textAlign: 'left' }}>Programme Offered</th><th style={{ textAlign: 'left' }}>Subject</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detailData.absentees.map((ab, idx) => (
                            <tr key={idx}>
                              <td>{idx + 1}</td>
                              <td><span style={{ fontFamily: 'monospace', fontSize: '0.78rem', fontWeight: 600 }}>{ab.application_id}</span></td>
                              <td style={{ textAlign: 'left' }}>{ab.initial ? <span style={{ color: '#64748b' }}>{ab.initial}. </span> : null}{ab.applicant_name}</td>
                              <td>{ab.initial || '--'}</td>
                              <td>{ab.mobile_number || '--'}</td>
                              <td>{ab.email || '--'}</td>
                              <td>{ab.category_ft_pt || '--'}</td>
                              <td style={{ textAlign: 'left' }}>{ab.programme_offered || '--'}</td>
                              <td style={{ textAlign: 'left' }}>{ab.subject || '--'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>
              </>
            ) : null}
          </div>
        )}

      </div>
    </div>
  );
}