import React, { useState, useEffect } from 'react';
import Sidebar from '../../components/Sidebar';
import { 
  getAdminExamControlCandidate, 
  reopenCandidateExam, 
  forceReopenSubmittedExam, 
  addExtraTime,
  getPublicSetting,
  updateSetting
} from '../../services/api';

export default function ExamControl() {
  const [appNo, setAppNo] = useState('');
  const [loading, setLoading] = useState(false);
  const [reopenLoading, setReopenLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [data, setData] = useState(null);

  // System settings states
  const [portalTitle, setPortalTitle] = useState('PhD Admission Entrance');
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState('');
  const [saveError, setSaveError] = useState('');

  useEffect(() => {
    getPublicSetting('portal_title')
      .then(res => {
        if (res.data && res.data.value) {
          setPortalTitle(res.data.value);
        }
      })
      .catch(err => console.error('Failed to load portal title:', err));
  }, []);

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSaveLoading(true);
    setSaveSuccess('');
    setSaveError('');

    try {
      await updateSetting('portal_title', { value: portalTitle.trim() });
      setSaveSuccess('Portal title updated successfully.');
      setTimeout(() => setSaveSuccess(''), 3000);
    } catch (err) {
      setSaveError(err.response?.data?.detail || 'Failed to update portal title.');
    } finally {
      setSaveLoading(false);
    }
  };

  // Reopen inputs (normal device lock bypass)
  const [reason, setReason] = useState('');

  // Force Reopen inputs (submitted exams)
  const [forceReason, setForceReason] = useState('');
  const [forceConfirmText, setForceConfirmText] = useState('');
  const [extraMinutes, setExtraMinutes] = useState('');
  const [forceLoading, setForceLoading] = useState(false);
  const [showForceConfirm, setShowForceConfirm] = useState(false);

  // Add Extra Time inputs
  const [extraTimeMinutes, setExtraTimeMinutes] = useState('');
  const [extraTimeReason, setExtraTimeReason] = useState('');
  const [extraTimeLoading, setExtraTimeLoading] = useState(false);
  const [showExtraTimeConfirm, setShowExtraTimeConfirm] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!appNo.trim()) {
      setError('Please enter Application ID');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');
    setData(null);

    try {
      const response = await getAdminExamControlCandidate(appNo.trim());
      setData(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to find candidate exam status.');
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setAppNo('');
    setData(null);
    setError('');
    setSuccess('');
  };

  const handleDirectReopenExam = async () => {
    if (!data || !data.candidate) return;
    setReopenLoading(true);
    setError('');
    setSuccess('');

    try {
      let response;
      if (data.attempt && (data.attempt.status === 'submitted' || data.attempt.status === 'auto_submitted')) {
        response = await forceReopenSubmittedExam({
          application_number: data.candidate.application_number,
          reason: 'Administrative Reopen',
          confirm_text: 'REOPEN'
        });
      } else {
        response = await reopenCandidateExam({
          application_number: data.candidate.application_number,
          reason: 'Administrative Unlock'
        });
      }
      setSuccess(response.data.message || 'Exam reopened successfully!');
      // Refresh candidate state
      const refreshRes = await getAdminExamControlCandidate(data.candidate.application_number);
      setData(refreshRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reopen candidate exam.');
    } finally {
      setReopenLoading(false);
    }
  };

  const handleAddExtraTimeSubmit = (e) => {
    e.preventDefault();
    const mins = parseInt(extraTimeMinutes, 10);
    if (!mins || mins <= 0) {
      setError('Please enter a valid number of minutes.');
      return;
    }
    setShowExtraTimeConfirm(true);
  };

  const confirmAddExtraTime = async () => {
    setShowExtraTimeConfirm(false);
    setExtraTimeLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await addExtraTime({
        application_number: data.candidate.application_number,
        extra_minutes: parseInt(extraTimeMinutes, 10),
        reason: extraTimeReason.trim() || 'Administrative Extra Time'
      });
      setSuccess(response.data.message || 'Extra time added successfully.');
      setExtraTimeMinutes('');
      setExtraTimeReason('');
      // Refresh candidate state
      const refreshRes = await getAdminExamControlCandidate(data.candidate.application_number);
      setData(refreshRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add extra time.');
    } finally {
      setExtraTimeLoading(false);
    }
  };

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="page-container">
        <h1 className="mb-2">Candidate Exam Control</h1>
        <p className="mb-4 text-secondary">
          Search candidate registry records to view status and perform 1-click exam reopening.
        </p>

        {error && <div className="alert alert-danger mb-4">{error}</div>}
        {success && <div className="alert alert-success mb-4">{success}</div>}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
          {/* Modern Search Card Layout */}
          <div className="card" style={{ padding: '1.5rem', margin: 0 }}>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', fontWeight: 700 }}>Candidate Search</h3>
            <p className="text-secondary mb-4" style={{ fontSize: '0.85rem' }}>
              Enter Candidate Application ID or Application Number to manage exam access.
            </p>
            <form onSubmit={handleSearch}>
              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label" style={{ fontWeight: 600, fontSize: '0.9rem' }}>Application ID / Number *</label>
                <input
                  type="text"
                  className="form-control"
                  style={{
                    height: '46px',
                    borderRadius: '0.375rem',
                    fontSize: '1rem',
                    fontWeight: 600,
                    width: '100%'
                  }}
                  placeholder="e.g. CET/PHD/J26/0123 or CETPHD-J26-0123"
                  value={appNo}
                  onChange={(e) => setAppNo(e.target.value)}
                  required
                />
              </div>
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button 
                  type="submit" 
                  className="btn btn-primary" 
                  style={{ flex: 1, height: '46px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600 }}
                  disabled={loading}
                >
                  {loading ? 'Searching...' : '🔍 Search Candidate'}
                </button>
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  style={{ height: '46px', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 1.5rem' }} 
                  onClick={handleClear}
                  disabled={loading || reopenLoading}
                >
                  Clear
                </button>
              </div>
            </form>
          </div>

          {/* Portal settings card */}
          <div className="card" style={{ padding: '1.5rem', margin: 0 }}>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', fontWeight: 700 }}>System Configuration</h3>
            <p className="text-secondary mb-4" style={{ fontSize: '0.85rem' }}>
              Modify settings that apply globally to the candidate and admin portals.
            </p>
            {saveError && <div className="alert alert-danger mb-3" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>{saveError}</div>}
            {saveSuccess && <div className="alert alert-success mb-3" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>{saveSuccess}</div>}
            
            <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontWeight: 600, fontSize: '0.9rem' }}>Portal Login Title</label>
                <input
                  type="text"
                  className="form-control"
                  style={{
                    height: '42px',
                    borderRadius: '0.375rem',
                    fontSize: '0.9rem',
                    width: '100%'
                  }}
                  placeholder="e.g. PhD Admission Entrance"
                  value={portalTitle}
                  onChange={(e) => setPortalTitle(e.target.value)}
                  required
                />
              </div>
              <button 
                type="submit" 
                className="btn btn-primary"
                style={{ height: '42px', width: '100%', marginTop: '0.25rem', fontWeight: 600 }}
                disabled={saveLoading}
              >
                {saveLoading ? 'Saving...' : '💾 Save Settings'}
              </button>
            </form>
          </div>
        </div>

        {data && (
          <>
            <div className="grid grid-2" style={{ alignItems: 'start', gap: '2rem' }}>
            {/* Candidate Details & Attempt Status */}
            <div className="card">
              <h3 className="card-title">Exam Attempt & Status Card</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                <div>
                  <strong className="text-secondary">Name:</strong>
                  <div style={{ fontSize: '1.1rem', fontWeight: 'bold' }}>{data.candidate.name}</div>
                </div>
                <div>
                  <strong className="text-secondary">Application Number:</strong>
                  <div>{data.candidate.application_number}</div>
                </div>
                <div>
                  <strong className="text-secondary">Applied Subject:</strong>
                  <div>{data.candidate.department_name}</div>
                </div>

                <hr style={{ borderColor: '#eee', margin: '0.5rem 0' }} />

                {data.attempt ? (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong className="text-secondary">Attempt ID:</strong>
                      <span>#{data.attempt.id}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong className="text-secondary">Attempt Status:</strong>
                      <span className={`badge badge-${data.attempt.status === 'in_progress' ? 'success' : 'secondary'}`}>
                        {data.attempt.status.toUpperCase()}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong className="text-secondary">Device Lock Status:</strong>
                      <span className={`badge badge-${data.attempt.lock_status === 'locked' ? 'danger' : data.attempt.lock_status === 'reopened' ? 'warning' : 'info'}`}>
                        {data.attempt.lock_status.toUpperCase()}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong className="text-secondary">Reopen Count:</strong>
                      <span>{data.attempt.reopen_count}</span>
                    </div>

                    <hr style={{ borderColor: '#eee', margin: '0.5rem 0' }} />

                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span><strong>Answered:</strong> {data.attempt.answered_count}</span>
                      <span><strong>Not Answered:</strong> {data.attempt.not_answered_count}</span>
                      <span><strong>Review:</strong> {data.attempt.marked_for_review_count}</span>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem' }}>
                      <strong className="text-secondary">Time Remaining:</strong>
                      <span style={{ fontWeight: 'bold', color: data.attempt.remaining_seconds > 0 ? 'var(--text-primary)' : 'var(--danger-color)' }}>
                        {data.attempt.remaining_seconds > 0 
                          ? `${Math.floor(data.attempt.remaining_seconds / 60)}m ${data.attempt.remaining_seconds % 60}s`
                          : 'Time Over'}
                      </span>
                    </div>
                  </>
                ) : (
                  <div className="text-secondary" style={{ fontStyle: 'italic' }}>
                    Candidate has not started the exam session yet.
                  </div>
                )}
              </div>
            </div>

            {/* Reopen Action Form */}
            <div className="card">
              <h3 className="card-title">Reopen/Unlock Exam</h3>
              
              {!data.attempt ? (
                <div style={{ padding: '1rem', background: '#f9f9f9', borderRadius: '4px', fontStyle: 'italic' }} className="text-secondary">
                  No active attempt exists for this candidate. Candidate can log in and start the exam.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  <div style={{ padding: '1rem', backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '0.375rem', fontSize: '0.9rem', color: '#1e40af' }}>
                    <strong>Exam Status:</strong> {data.attempt.status.toUpperCase()} ({data.attempt.lock_status.toUpperCase()})
                    <p style={{ margin: '0.3rem 0 0 0', fontSize: '0.85rem', color: '#3b82f6' }}>
                      Clicking <strong>REOPEN EXAM</strong> will immediately restore the candidate's exam session, allowing them to log back in and resume.
                    </p>
                  </div>

                  <button 
                    onClick={handleDirectReopenExam} 
                    className="btn btn-danger w-full" 
                    style={{ fontWeight: 700, padding: '0.85rem 1.25rem', fontSize: '1.05rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', boxShadow: '0 4px 6px -1px rgba(239, 68, 68, 0.2)' }}
                    disabled={reopenLoading}
                  >
                    {reopenLoading ? 'Reopening Exam...' : '🔓 REOPEN EXAM NOW'}
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Add Extra Time Card */}
          {data.attempt && (data.attempt.status === 'in_progress' || data.attempt.status === 'expired') && (
            <div className="card" style={{ marginTop: '2rem', maxWidth: '600px', padding: '1.5rem' }}>
              <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                ⏱️ Add Extra Exam Time
              </h3>
              <p className="text-secondary mb-4" style={{ fontSize: '0.9rem' }}>
                Add extra minutes to this candidate's active exam session. If the candidate's time has already expired, this will restore their status to <strong>in_progress</strong> and grant them the extra minutes starting from now.
              </p>
              <form onSubmit={handleAddExtraTimeSubmit}>
                <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                  <label className="form-label" htmlFor="extra-time-minutes" style={{ fontWeight: 600 }}>Extra Minutes to Add *</label>
                  <input
                    id="extra-time-minutes"
                    type="number"
                    min="1"
                    className="form-control"
                    placeholder="e.g., 10, 15, 20"
                    value={extraTimeMinutes}
                    onChange={(e) => setExtraTimeMinutes(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                  <label className="form-label" htmlFor="extra-time-reason" style={{ fontWeight: 600 }}>Reason *</label>
                  <textarea
                    id="extra-time-reason"
                    rows="3"
                    className="form-control"
                    placeholder="Explain why extra time is being given (e.g. Server disconnection, client system crash)"
                    value={extraTimeReason}
                    onChange={(e) => setExtraTimeReason(e.target.value)}
                    required
                  ></textarea>
                </div>
                <button 
                  type="submit" 
                  className="btn btn-primary w-full"
                  style={{ height: '46px' }}
                  disabled={extraTimeLoading || !extraTimeMinutes || !extraTimeReason.trim()}
                >
                  {extraTimeLoading ? 'Adding Extra Time...' : 'Add Extra Minutes'}
                </button>
              </form>
            </div>
          )}
          </>
        )}



        {/* Force Reopen Confirmation Modal */}
        {showForceConfirm && (
          <div className="modal-backdrop">
            <div className="modal-content">
              <h3 className="modal-title" style={{ color: 'var(--danger-color)' }}>Confirm Force Reopen</h3>
              <p className="mb-4">
                This will revert the submitted exam attempt for <strong>{data.candidate.name}</strong> back to <strong>IN_PROGRESS</strong>.
              </p>
              <div style={{ padding: '0.8rem', background: '#f5f5f5', borderRadius: '4px', fontSize: '0.9rem' }} className="mb-4">
                <strong>Reason:</strong> {forceReason}
              </div>
              <div style={{ background: '#fff5f5', padding: '0.8rem', borderLeft: '4px solid var(--danger-color)' }} className="mb-4 text-secondary">
                Note: Existing answers and question order will be <strong>preserved</strong>. Old score and evaluation details will be cleared until the candidate submits again.
              </div>
              <div className="flex justify-end gap-2">
                <button type="button" className="btn btn-secondary" onClick={() => setShowForceConfirm(false)}>
                  Cancel
                </button>
                <button type="button" className="btn btn-danger" onClick={confirmForceReopen}>
                  Force Reopen & Resume Attempt
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Extra Time Confirmation Modal */}
        {showExtraTimeConfirm && (
          <div className="modal-backdrop">
            <div className="modal-content">
              <h3 className="modal-title" style={{ color: 'var(--primary-color)' }}>Confirm Extra Time Allocation</h3>
              <p className="mb-4">
                This will add <strong>{extraTimeMinutes} minutes</strong> to <strong>{data.candidate.name}'s</strong> exam attempt.
              </p>
              <div style={{ padding: '0.8rem', background: '#f5f5f5', borderRadius: '4px', fontSize: '0.9rem' }} className="mb-4">
                <strong>Reason:</strong> {extraTimeReason}
              </div>
              <div className="flex justify-end gap-2">
                <button type="button" className="btn btn-secondary" onClick={() => setShowExtraTimeConfirm(false)}>
                  Cancel
                </button>
                <button type="button" className="btn btn-primary" onClick={confirmAddExtraTime}>
                  Confirm & Add Time
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
