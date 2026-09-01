import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../../components/Sidebar';
import api, { getDashboardQuestionSummary, purgeAllData, getAdminCredentialsInfo, updateAdminCredentials, downloadFullBackup } from '../../services/api';
import {
  Building2,
  Users,
  Camera,
  BookOpen,
  PenTool,
  CheckCircle2,
  XCircle,
  Hourglass,
  Trash2,
  AlertTriangle,
  RefreshCw,
  Key,
  ShieldCheck,
  Download
} from 'lucide-react';

export default function Dashboard() {
  const navigate = useNavigate();

  const [deptCount, setDeptCount] = useState(0);
  const [candidateCount, setCandidateCount] = useState(0);
  const [missingPhotoCount, setMissingPhotoCount] = useState(0);
  const [readyBanksCount, setReadyBanksCount] = useState(0);

  // Phase 8 Result stats
  const [appearedCount, setAppearedCount] = useState(0);
  const [passedCount, setPassedCount] = useState(0);
  const [failedCount, setFailedCount] = useState(0);
  const [absentCount, setAbsentCount] = useState(0);

  const [recentCandidates, setRecentCandidates] = useState([]);
  const [loading, setLoading] = useState(true);

  // System Purge Modal State
  const [showPurgeModal, setShowPurgeModal] = useState(false);
  const [confirmInput, setConfirmInput] = useState('');
  const [purging, setPurging] = useState(false);
  const [purgeError, setPurgeError] = useState('');
  const [purgeSuccess, setPurgeSuccess] = useState('');

  // Backup Download States
  const [downloadingBackup, setDownloadingBackup] = useState(false);
  const [backupError, setBackupError] = useState('');
  const [backupSuccess, setBackupSuccess] = useState('');

  const handleDownloadBackup = async () => {
    setDownloadingBackup(true);
    setBackupError('');
    setBackupSuccess('');
    try {
      const response = await downloadFullBackup();
      const blob = new Blob([response.data], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const timestamp = new Date().toISOString().replace(/[-:T.]/g, '').slice(0, 14);
      link.setAttribute('download', `phd_portal_full_backup_${timestamp}.zip`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
      setBackupSuccess('Complete System Backup (.ZIP) downloaded successfully!');
    } catch (err) {
      console.error('Failed to download backup:', err);
      setBackupError('Failed to generate complete backup package. Please check backend server.');
    } finally {
      setDownloadingBackup(false);
    }
  };

  // Credentials management states
  const [credRole, setCredRole] = useState('super_admin');
  const [adminEmailInput, setAdminEmailInput] = useState('');
  const [adminPasswordInput, setAdminPasswordInput] = useState('');
  const [credLoading, setCredLoading] = useState(false);
  const [credSuccess, setCredSuccess] = useState('');
  const [credError, setCredError] = useState('');
  const [credentialsInfo, setCredentialsInfo] = useState(null);

  const adminUser = JSON.parse(localStorage.getItem('admin_user') || '{}');

  const fetchCredentialsInfo = async () => {
    try {
      const res = await getAdminCredentialsInfo();
      setCredentialsInfo(res.data);
      setAdminEmailInput(res.data.my_account?.email || '');
    } catch (err) {
      console.error('Failed to load credentials info:', err);
    }
  };

  const fetchDashboardStats = async () => {
    setLoading(true);
    try {
      // 1. Fetch departments
      const deptsResponse = await api.get('/api/admin/departments');
      const activeDepts = deptsResponse.data.filter(d => d.is_active);
      setDeptCount(activeDepts.length);

      // 2. Fetch candidates total count
      const candResponse = await api.get('/api/admin/candidates?limit=5');
      setCandidateCount(candResponse.data.total);
      setRecentCandidates(candResponse.data.items);

      // 3. Fetch missing photos count
      const missingPhotoResponse = await api.get('/api/admin/candidates?photo_status=missing&limit=1');
      setMissingPhotoCount(missingPhotoResponse.data.total);

      // 4. Fetch question bank readiness counts
      const questionSummaryResponse = await getDashboardQuestionSummary();
      setReadyBanksCount(questionSummaryResponse.data.ready_departments);

      // 5. Fetch result statistics reports
      try {
        const reportsResponse = await api.get('/api/admin/reports/summary');
        setAppearedCount(reportsResponse.data.appeared || 0);
        setPassedCount(reportsResponse.data.passed || 0);
        setFailedCount(reportsResponse.data.failed || 0);
        setAbsentCount(reportsResponse.data.absent || 0);
      } catch (repErr) {
        console.error('Failed to load reports summary for dashboard, defaulting to 0:', repErr);
        setAppearedCount(0);
        setPassedCount(0);
        setFailedCount(0);
        setAbsentCount(0);
      }

    } catch (err) {
      console.error('Error fetching dashboard statistics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardStats();
    fetchCredentialsInfo();
  }, []);

  const handleUpdateCredentials = async (e) => {
    e.preventDefault();
    setCredLoading(true);
    setCredSuccess('');
    setCredError('');

    const targetRole = adminUser.role || 'super_admin';

    try {
      const res = await updateAdminCredentials({
        target_role: targetRole,
        email: adminEmailInput.trim(),
        password: adminPasswordInput.trim() || undefined
      });
      setCredSuccess(res.data.message || 'Account credentials updated successfully.');
      setAdminPasswordInput('');

      // Sync local storage if email changed
      if (res.data.admin && res.data.admin.email) {
        const updatedUser = { ...adminUser, email: res.data.admin.email };
        localStorage.setItem('admin_user', JSON.stringify(updatedUser));
      }

      fetchCredentialsInfo();
    } catch (err) {
      setCredError(err.response?.data?.detail || 'Failed to update account credentials.');
    } finally {
      setCredLoading(false);
    }
  };

  const handleExecutePurge = async () => {
    if (confirmInput !== 'DELETE ALL DATA') return;
    setPurging(true);
    setPurgeError('');
    try {
      const res = await purgeAllData('DELETE ALL DATA');
      setShowPurgeModal(false);
      setPurgeSuccess(res.data.message || 'All exam sessions, candidates, questions, and attempt reports have been wiped clean.');
      // Refresh dashboard counters
      setCandidateCount(0);
      setMissingPhotoCount(0);
      setReadyBanksCount(0);
      setAppearedCount(0);
      setPassedCount(0);
      setFailedCount(0);
      setAbsentCount(0);
      setRecentCandidates([]);
    } catch (err) {
      setPurgeError(err.response?.data?.detail || 'Failed to execute system purge. Please check backend server.');
    } finally {
      setPurging(false);
    }
  };

  const stats = [
    { label: 'Departments', value: loading ? '...' : deptCount, icon: <Building2 size={24} style={{ color: 'var(--primary-color)' }} /> },
    { label: 'Total Candidates', value: loading ? '...' : candidateCount, icon: <Users size={24} style={{ color: 'var(--primary-color)' }} /> },
    { label: 'Missing Photos', value: loading ? '...' : missingPhotoCount, icon: <Camera size={24} style={{ color: 'var(--danger-color)' }} />, highlight: missingPhotoCount > 0 },
    { label: 'Question Banks Ready', value: loading ? '...' : `${readyBanksCount} / ${deptCount}`, icon: <BookOpen size={24} style={{ color: 'var(--primary-color)' }} />, highlight: deptCount > 0 && readyBanksCount < deptCount },
    { label: 'Appeared Candidates', value: loading ? '...' : appearedCount, icon: <PenTool size={24} style={{ color: 'var(--primary-color)' }} /> },
    { label: 'Qualified Candidates', value: loading ? '...' : passedCount, icon: <CheckCircle2 size={24} style={{ color: 'var(--success-color)' }} /> },
    { label: 'Non-Qualified Candidates', value: loading ? '...' : failedCount, icon: <XCircle size={24} style={{ color: 'var(--danger-color)' }} /> },
    { label: 'Absent Candidates', value: loading ? '...' : absentCount, icon: <Hourglass size={24} style={{ color: 'var(--warning-color)' }} /> }
  ];

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="page-container">
        {/* Header section with DELETE ALL DATA button */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '2rem' }}>
          <div>
            <h1 style={{ margin: 0, marginBottom: '0.25rem' }}>Welcome back, {adminUser.name || 'Super Admin'}!</h1>
            <p style={{ margin: 0 }}>You are logged in as {adminUser.email} ({adminUser.role || 'Administrator'}).</p>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button
              onClick={handleDownloadBackup}
              disabled={downloadingBackup}
              className="btn btn-success"
              style={{
                backgroundColor: 'var(--success-color, #10b981)',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                fontWeight: 600,
                padding: '0.6rem 1.25rem',
                boxShadow: '0 2px 4px rgba(16, 185, 129, 0.2)',
                border: 'none',
                cursor: downloadingBackup ? 'not-allowed' : 'pointer'
              }}
            >
              {downloadingBackup ? (
                <>
                  <RefreshCw size={18} className="spin" /> Generating Backup ZIP...
                </>
              ) : (
                <>
                  <Download size={18} /> DOWNLOAD COMPLETE BACKUP (.ZIP)
                </>
              )}
            </button>

            <button
              onClick={() => {
                setShowPurgeModal(true);
                setConfirmInput('');
                setPurgeError('');
              }}
              className="btn btn-danger"
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, padding: '0.6rem 1.25rem', boxShadow: '0 2px 4px rgba(239, 68, 68, 0.2)' }}
            >
              <Trash2 size={18} />
              <span>DELETE ALL DATA</span>
            </button>
          </div>
        </div>

        {backupSuccess && (
          <div className="alert alert-success" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span><strong>Backup Exported:</strong> {backupSuccess}</span>
            <button className="btn btn-secondary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem' }} onClick={() => setBackupSuccess('')}>Dismiss</button>
          </div>
        )}

        {backupError && (
          <div className="alert alert-danger" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span><strong>Backup Error:</strong> {backupError}</span>
            <button className="btn btn-secondary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem' }} onClick={() => setBackupError('')}>Dismiss</button>
          </div>
        )}

        {purgeSuccess && (
          <div className="alert alert-success" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span><strong>System Reset Success:</strong> {purgeSuccess}</span>
            <button className="btn btn-secondary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem' }} onClick={() => setPurgeSuccess('')}>Dismiss</button>
          </div>
        )}

        {/* Stat cards grid */}
        <div className="grid grid-4 mb-4">
          {stats.map((stat, i) => (
            <div
              className="card stat-card"
              key={i}
              style={{
                borderLeft: stat.highlight ? '4px solid var(--danger-color)' : 'none'
              }}
            >
              <div className="stat-icon">{stat.icon}</div>
              <div className="stat-details">
                <p>{stat.label}</p>
                <h3 style={{ color: stat.highlight ? 'var(--danger-color)' : 'inherit' }}>{stat.value}</h3>
              </div>
            </div>
          ))}
        </div>

        {/* Action items alert */}
        <div className="alert alert-success">
          <strong>System Status:</strong> MySQL database connection active. Real-time department counts, candidates, and photograph mapping synchronized successfully.
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 className="card-title" style={{ margin: 0 }}>Recent Candidate Registrations</h3>
            <button
              className="btn btn-secondary"
              style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
              onClick={() => navigate('/admin/candidates')}
            >
              View All Candidates
            </button>
          </div>

          <div className="table-container">
            {recentCandidates.length === 0 ? (
              <p style={{ margin: '1rem 0', color: 'var(--text-secondary)' }}>No candidates registered in the system yet.</p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Application No</th>
                    <th>Name</th>
                    <th>Department</th>
                    <th>Photo Status</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recentCandidates.map((c) => (
                    <tr key={c.id}>
                      <td><strong>{c.application_number}</strong></td>
                      <td>{c.name}</td>
                      <td>{c.department_name}</td>
                      <td>
                        <span className="user-badge" style={{
                          backgroundColor: c.photo_status === 'available' ? 'var(--success-bg)' : 'var(--danger-bg)',
                          color: c.photo_status === 'available' ? 'var(--success-color)' : 'var(--danger-color)'
                        }}>
                          {c.photo_status === 'available' ? 'Available' : 'Missing'}
                        </span>
                      </td>
                      <td>
                        <span className="user-badge" style={{
                          backgroundColor: c.is_active ? 'var(--success-bg)' : '#f1f5f9',
                          color: c.is_active ? 'var(--success-color)' : '#64748b'
                        }}>
                          {c.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Change Admin & Staff Credentials Section */}
        <div className="card" style={{ marginTop: '2rem', borderTop: '4px solid var(--primary-color)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h3 className="card-title" style={{ margin: 0, border: 'none', padding: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Key size={20} style={{ color: 'var(--primary-color)' }} />
                <span>Account Credentials & Security Settings</span>
              </h3>
              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Modify custom login email and password for your account ({adminUser.role === 'super_admin' ? 'Super Admin' : 'Staff Account'}).
              </p>
            </div>

            {/* Account Role Badge Indicator */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', backgroundColor: '#e0f2fe', border: '1px solid #bae6fd', padding: '0.4rem 0.85rem', borderRadius: '0.375rem', fontWeight: 600, fontSize: '0.85rem', color: '#0369a1' }}>
              <ShieldCheck size={16} />
              <span>{adminUser.role === 'super_admin' ? 'Super Admin Account' : 'Staff Account'}</span>
            </div>
          </div>

          {credSuccess && <div className="alert alert-success mb-3">{credSuccess}</div>}
          {credError && <div className="alert alert-danger mb-3">{credError}</div>}

          <div className="grid grid-2" style={{ gap: '1.5rem', alignItems: 'start' }}>
            {/* Form */}
            <form onSubmit={handleUpdateCredentials} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--primary-color)', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
                Editing {adminUser.role === 'super_admin' ? 'Super Admin' : 'Staff Account'} Login Details
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontWeight: 600 }}>Login Email Address</label>
                <input
                  type="email"
                  className="form-input"
                  placeholder={adminUser.role === 'super_admin' ? 'admin@gmail.com' : 'staff@gmail.com'}
                  value={adminEmailInput}
                  onChange={(e) => setAdminEmailInput(e.target.value)}
                  required
                />
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontWeight: 600 }}>New Password (Leave blank to keep unchanged)</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="Enter new password (optional)"
                  value={adminPasswordInput}
                  onChange={(e) => setAdminPasswordInput(e.target.value)}
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                style={{ fontWeight: 600, padding: '0.65rem 1.25rem', marginTop: '0.5rem' }}
                disabled={credLoading}
              >
                {credLoading ? 'Updating Credentials...' : '💾 Save Account Credentials'}
              </button>
            </form>


          </div>
        </div>
      </div>

      {/* SYSTEM PURGE MODAL */}
      {showPurgeModal && (
        <div className="modal-backdrop">
          <div className="modal-content" style={{ maxWidth: '550px', borderTop: '5px solid var(--danger-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
              <div style={{ padding: '0.5rem', backgroundColor: '#fef2f2', borderRadius: '50%', color: 'var(--danger-color)' }}>
                <AlertTriangle size={28} />
              </div>
              <div>
                <h3 className="modal-title" style={{ margin: 0, color: '#991b1b' }}>DELETE ALL DATA (System Purge)</h3>
                <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b' }}>Permanently reset portal for the next examination cycle</p>
              </div>
            </div>

            <div style={{ backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.375rem', padding: '1rem', marginBottom: '1.25rem', fontSize: '0.9rem', color: '#991b1b', lineHeight: '1.5' }}>
              <strong>⚠️ Permanent Action Warning:</strong>
              <ul style={{ paddingLeft: '1.25rem', marginTop: '0.5rem', marginBottom: 0 }}>
                <li><strong>Exam Sessions:</strong> All scheduled sessions will be erased.</li>
                <li><strong>Candidate List & Photos:</strong> All student profiles and uploaded photographs will be permanently deleted.</li>
                <li><strong>Question Banks:</strong> All uploaded questions and Excel sheets will be deleted.</li>
                <li><strong>Reports & Results:</strong> All exam attempts, answers, and evaluation logs will be deleted.</li>
              </ul>
              <div style={{ marginTop: '0.75rem', paddingTop: '0.5rem', borderTop: '1px dashed #fca5a5', fontSize: '0.85rem', color: '#065f46' }}>
                ✅ <strong>Preserved:</strong> Academic Department list and Admin account logins will remain active.
              </div>
            </div>

            {purgeError && <div className="alert alert-danger mb-4">{purgeError}</div>}

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem', color: '#1e293b' }}>
                Type <span style={{ color: 'var(--danger-color)', userSelect: 'all', fontFamily: 'monospace', fontWeight: 'bold' }}>DELETE ALL DATA</span> below to confirm:
              </label>
              <input
                type="text"
                className="form-input"
                placeholder="DELETE ALL DATA"
                value={confirmInput}
                onChange={(e) => setConfirmInput(e.target.value)}
                style={{ borderColor: confirmInput === 'DELETE ALL DATA' ? 'var(--danger-color)' : 'var(--border-color)', fontWeight: 600, letterSpacing: '0.5px' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowPurgeModal(false)}
                disabled={purging}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={confirmInput !== 'DELETE ALL DATA' || purging}
                onClick={handleExecutePurge}
                style={{ opacity: confirmInput !== 'DELETE ALL DATA' || purging ? 0.6 : 1, display: 'flex', alignItems: 'center', gap: '0.5rem' }}
              >
                {purging ? (
                  <>
                    <RefreshCw size={16} className="spin" /> Purging All Data...
                  </>
                ) : (
                  <>
                    <Trash2 size={16} /> Permanently Wipe Data
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

