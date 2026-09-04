import React, { useEffect, useState } from 'react';
import Sidebar from '../../components/Sidebar';
import api from '../../services/api';
import { AlertCircle, Search, Building2, CheckCheck, XCircle } from 'lucide-react';


export default function ExamSessions() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Department states
  const [allDepartments, setAllDepartments] = useState([]);
  const [selectedDepts, setSelectedDepts] = useState([]);
  const [addDeptSearch, setAddDeptSearch] = useState('');

  // Form states (Add Exam Session)
  const [sessionName, setSessionName] = useState('');
  const [examTitle, setExamTitle] = useState('PhD Entrance Examination');
  const [examDate, setExamDate] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [durationMinutes, setDurationMinutes] = useState(90);
  const [instructions, setInstructions] = useState('');

  // Editing states
  const [editingSession, setEditingSession] = useState(null);
  const [editSessionName, setEditSessionName] = useState('');
  const [editExamTitle, setEditExamTitle] = useState('');
  const [editExamDate, setEditExamDate] = useState('');
  const [editStartTime, setEditStartTime] = useState('');
  const [editEndTime, setEditEndTime] = useState('');
  const [editDurationMinutes, setEditDurationMinutes] = useState(90);
  const [editInstructions, setEditInstructions] = useState('');
  const [editIsActive, setEditIsActive] = useState(true);
  const [editSelectedDepts, setEditSelectedDepts] = useState([]);
  const [editDeptSearch, setEditDeptSearch] = useState('');

  // Fetch all sessions
  const fetchSessions = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.get('/api/admin/exam-sessions/');
      setSessions(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch exam sessions.');
    } finally {
      setLoading(false);
    }
  };

  // Fetch all active departments
  const fetchDepartments = async () => {
    try {
      const response = await api.get('/api/admin/departments');
      // Only show active departments for scheduling
      setAllDepartments(response.data.filter(d => d.is_active));
    } catch (err) {
      console.error('Failed to fetch departments:', err);
    }
  };

  useEffect(() => {
    fetchSessions();
    fetchDepartments();
  }, []);

  // Format date display
  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  // Format time display
  const formatTime = (timeStr) => {
    if (!timeStr) return '';
    try {
      const d = new Date(timeStr);
      return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
    } catch {
      return timeStr;
    }
  };

  // Pre-fill date fields to HTML datetime-local format (YYYY-MM-DDTHH:MM)
  const formatToLocalInput = (isoStr) => {
    if (!isoStr) return '';
    const d = new Date(isoStr);
    const pad = (num) => num.toString().padStart(2, '0');
    const yyyy = d.getFullYear();
    const mm = pad(d.getMonth() + 1);
    const dd = pad(d.getDate());
    const hh = pad(d.getHours());
    const min = pad(d.getMinutes());
    return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
  };

  // Department Filtering & Helpers for Add Form
  const filteredAddDepts = allDepartments.filter(d => 
    d.department_name.toLowerCase().includes(addDeptSearch.toLowerCase()) ||
    (d.department_code && d.department_code.toLowerCase().includes(addDeptSearch.toLowerCase()))
  );

  const toggleAddDept = (deptId) => {
    setSelectedDepts(prev => 
      prev.includes(deptId) ? prev.filter(id => id !== deptId) : [...prev, deptId]
    );
  };

  const handleSelectAllAdd = () => {
    const visibleIds = filteredAddDepts.map(d => d.id);
    setSelectedDepts(prev => Array.from(new Set([...prev, ...visibleIds])));
  };

  const handleDeselectAllAdd = () => {
    if (addDeptSearch.trim()) {
      const visibleIds = filteredAddDepts.map(d => d.id);
      setSelectedDepts(prev => prev.filter(id => !visibleIds.includes(id)));
    } else {
      setSelectedDepts([]);
    }
  };

  // Department Filtering & Helpers for Edit Form
  const filteredEditDepts = allDepartments.filter(d => 
    d.department_name.toLowerCase().includes(editDeptSearch.toLowerCase()) ||
    (d.department_code && d.department_code.toLowerCase().includes(editDeptSearch.toLowerCase()))
  );

  const toggleEditDept = (deptId) => {
    setEditSelectedDepts(prev => 
      prev.includes(deptId) ? prev.filter(id => id !== deptId) : [...prev, deptId]
    );
  };

  const handleSelectAllEdit = () => {
    const visibleIds = filteredEditDepts.map(d => d.id);
    setEditSelectedDepts(prev => Array.from(new Set([...prev, ...visibleIds])));
  };

  const handleDeselectAllEdit = () => {
    if (editDeptSearch.trim()) {
      const visibleIds = filteredEditDepts.map(d => d.id);
      setEditSelectedDepts(prev => prev.filter(id => !visibleIds.includes(id)));
    } else {
      setEditSelectedDepts([]);
    }
  };

  // Handle Add Session Submit
  const handleAddSubmit = async (e) => {
    e.preventDefault();
    if (!sessionName || !examDate || !startTime || !endTime) {
      setError('Please fill in all required fields.');
      return;
    }

    setActionLoading(true);
    setError('');
    setSuccess('');

    try {
      await api.post('/api/admin/exam-sessions/', {
        session_name: sessionName,
        exam_title: examTitle,
        exam_date: examDate,
        start_time: startTime,
        end_time: endTime,
        duration_minutes: Number(durationMinutes),
        instructions: instructions,
        department_ids: selectedDepts
      });

      setSuccess('Exam session created successfully!');
      setSessionName('');
      setExamTitle('PhD Entrance Examination');
      setExamDate('');
      setStartTime('');
      setEndTime('');
      setDurationMinutes(90);
      setInstructions('');
      setSelectedDepts([]);
      setAddDeptSearch('');
      fetchSessions();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create exam session.');
    } finally {
      setActionLoading(false);
    }
  };

  // Start edit
  const startEdit = (session) => {
    setEditingSession(session);
    setEditSessionName(session.session_name);
    setEditExamTitle(session.exam_title);
    setEditExamDate(session.exam_date);
    setEditStartTime(formatToLocalInput(session.start_time));
    setEditEndTime(formatToLocalInput(session.end_time));
    setEditDurationMinutes(session.duration_minutes);
    setEditInstructions(session.instructions || '');
    setEditIsActive(session.is_active);
    setEditSelectedDepts(session.departments ? session.departments.map(d => d.id) : []);
    setEditDeptSearch('');
    setError('');
    setSuccess('');
  };

  // Cancel edit
  const cancelEdit = () => {
    setEditingSession(null);
    setEditSessionName('');
    setEditExamTitle('');
    setEditExamDate('');
    setEditStartTime('');
    setEditEndTime('');
    setEditDurationMinutes(90);
    setEditInstructions('');
    setEditIsActive(true);
    setEditSelectedDepts([]);
    setEditDeptSearch('');
  };

  // Handle Update Session Submit
  const handleUpdateSubmit = async (e) => {
    e.preventDefault();
    if (!editSessionName || !editExamDate || !editStartTime || !editEndTime) {
      setError('Please fill in all required fields.');
      return;
    }

    setActionLoading(true);
    setError('');
    setSuccess('');

    try {
      await api.put(`/api/admin/exam-sessions/${editingSession.id}`, {
        session_name: editSessionName,
        exam_title: editExamTitle,
        exam_date: editExamDate,
        start_time: editStartTime,
        end_time: editEndTime,
        duration_minutes: Number(editDurationMinutes),
        instructions: editInstructions,
        is_active: editIsActive,
        department_ids: editSelectedDepts
      });

      setSuccess('Exam session updated successfully!');
      cancelEdit();
      fetchSessions();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update exam session.');
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Permanent Delete
  const handleDelete = async (id) => {
    if (!window.confirm("WARNING: This will permanently delete this exam session and related attempts/answers. Candidates assigned to this session will be unassigned.\n\nAre you sure you want to proceed?")) {
      return;
    }

    setActionLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await api.delete(`/api/admin/exam-sessions/${id}`);
      const counts = response.data?.deleted_counts || {};
      setSuccess(
        `Exam session permanently deleted! Cleaned up: ${counts.exam_attempts || 0} attempts, unassigned ${counts.candidates_unassigned || 0} candidates.`
      );
      fetchSessions();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete exam session.');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="page-container" style={{ maxWidth: '1400px' }}>
        <h1 className="mb-4">Exam Session Management</h1>
        <p className="mb-4">Configure multiple examination schedules, time frames, and candidate start time lock policies.</p>

        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <div className="grid grid-2" style={{ gridTemplateColumns: '1.8fr 1.2fr', alignItems: 'start', gap: '2rem' }}>
          
          {/* List of Sessions */}
          <div className="card">
            <h3 className="card-title">Configured Sessions Registry</h3>
            {loading ? (
              <p>Loading exam sessions...</p>
            ) : sessions.length === 0 ? (
              <p>No exam sessions defined yet. Use the panel on the right to create one.</p>
            ) : (
              <div className="table-container" style={{ margin: 0 }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th style={{ width: '50px' }}>S.No</th>
                      <th>Session Name</th>
                      <th>Date</th>
                      <th>Time Frame</th>
                      <th>Duration</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map((sess, index) => (
                      <tr key={sess.id}>
                        <td>{index + 1}</td>
                        <td>
                          <strong>{sess.session_name}</strong>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>{sess.exam_title}</div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem', marginTop: '0.25rem' }}>
                            {sess.departments && sess.departments.length > 0 ? (
                              sess.departments.map(dept => (
                                <span key={dept.id} className="user-badge" style={{
                                  backgroundColor: '#eff6ff',
                                  color: '#1d4ed8',
                                  border: '1px solid #bfdbfe',
                                  fontSize: '0.7rem',
                                  padding: '0.1rem 0.35rem',
                                  fontWeight: 500
                                }}>
                                  {dept.department_code}
                                </span>
                              ))
                            ) : (
                              <span className="user-badge" style={{
                                  backgroundColor: '#fffbeb',
                                  color: '#b45309',
                                  border: '1px solid #fde68a',
                                  fontSize: '0.7rem',
                                  padding: '0.1rem 0.35rem',
                                  fontWeight: 500,
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '0.2rem'
                              }}>
                                <AlertCircle size={12} />
                                No Depts Selected
                              </span>
                            )}
                          </div>
                        </td>
                        <td>{formatDate(sess.exam_date)}</td>
                        <td style={{ fontSize: '0.8rem' }}>
                          <div>Start: {formatTime(sess.start_time)}</div>
                          <div>End: {formatTime(sess.end_time)}</div>
                        </td>
                        <td>{sess.duration_minutes} mins</td>
                        <td>
                          <span className="user-badge" style={{
                            backgroundColor: sess.is_active ? 'var(--success-bg)' : 'var(--danger-bg)',
                            color: sess.is_active ? 'var(--success-color)' : 'var(--danger-color)'
                          }}>
                            {sess.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '0.35rem' }}>
                            <button 
                              className="btn btn-secondary" 
                              style={{ padding: '0.2rem 0.4rem', fontSize: '0.7rem' }}
                              onClick={() => startEdit(sess)}
                            >
                              Edit
                            </button>
                            <button 
                              className="btn btn-danger" 
                              style={{ padding: '0.2rem 0.4rem', fontSize: '0.7rem' }}
                              onClick={() => handleDelete(sess.id)}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Create/Edit Form Card */}
          <div className="card" style={{ borderTop: editingSession ? '4px solid var(--warning-color)' : '4px solid var(--primary-color)' }}>
            <h3 className="card-title">
              {editingSession ? `Edit Session: ${editingSession.session_name}` : 'Create New Exam Session'}
            </h3>

            {editingSession ? (
              // Edit Form
              <form onSubmit={handleUpdateSubmit}>
                <div className="form-group">
                  <label className="form-label" htmlFor="edit-sess-name">Session Name</label>
                  <input
                    id="edit-sess-name"
                    type="text"
                    className="form-input"
                    value={editSessionName}
                    onChange={(e) => setEditSessionName(e.target.value)}
                    placeholder="e.g. Session 1, Afternoon Batch"
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="edit-exam-title">Exam Title</label>
                  <input
                    id="edit-exam-title"
                    type="text"
                    className="form-input"
                    value={editExamTitle}
                    onChange={(e) => setEditExamTitle(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="edit-exam-date">Exam Date</label>
                  <input
                    id="edit-exam-date"
                    type="date"
                    className="form-input"
                    value={editExamDate}
                    onChange={(e) => setEditExamDate(e.target.value)}
                    required
                  />
                </div>

                <div className="grid grid-2" style={{ gap: '1rem', gridTemplateColumns: '1fr 1fr', marginBottom: '1rem' }}>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label" htmlFor="edit-start-time">Start Time (IST)</label>
                    <input
                      id="edit-start-time"
                      type="datetime-local"
                      className="form-input"
                      value={editStartTime}
                      onChange={(e) => setEditStartTime(e.target.value)}
                      required
                    />
                  </div>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label" htmlFor="edit-end-time">End Time (IST)</label>
                    <input
                      id="edit-end-time"
                      type="datetime-local"
                      className="form-input"
                      value={editEndTime}
                      onChange={(e) => setEditEndTime(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="edit-duration">Duration (Minutes)</label>
                  <input
                    id="edit-duration"
                    type="number"
                    className="form-input"
                    value={editDurationMinutes}
                    onChange={(e) => setEditDurationMinutes(e.target.value)}
                    required
                  />
                </div>

                {/* Enhanced Assign Departments Selector (EDIT FORM) */}
                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <label className="form-label" style={{ margin: 0, fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Building2 size={16} style={{ color: 'var(--primary-color)' }} />
                      Assign Departments for Exam
                    </label>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.15rem 0.5rem', borderRadius: '1rem', backgroundColor: editSelectedDepts.length > 0 ? '#e0e7ff' : '#f3f4f6', color: editSelectedDepts.length > 0 ? '#4338ca' : '#6b7280' }}>
                      {editSelectedDepts.length} of {allDepartments.length} Selected
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.6rem', alignItems: 'center' }}>
                    <div style={{ position: 'relative', flex: 1 }}>
                      <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
                      <input
                        type="text"
                        className="form-input"
                        placeholder="Search department name or code..."
                        value={editDeptSearch}
                        onChange={(e) => setEditDeptSearch(e.target.value)}
                        style={{ paddingLeft: '28px', paddingRight: '28px', height: '34px', fontSize: '0.825rem' }}
                      />
                      {editDeptSearch && (
                        <button
                          type="button"
                          onClick={() => setEditDeptSearch('')}
                          style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', padding: 0 }}
                        >
                          <XCircle size={14} />
                        </button>
                      )}
                    </div>

                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={handleSelectAllEdit}
                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', height: '34px', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                    >
                      <CheckCheck size={14} /> Select All
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={handleDeselectAllEdit}
                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', height: '34px', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                    >
                      Clear All
                    </button>
                  </div>

                  <div style={{
                    maxHeight: '220px',
                    overflowY: 'auto',
                    border: '1px solid var(--border-color)',
                    borderRadius: '0.5rem',
                    padding: '0.5rem',
                    backgroundColor: '#fafafa',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                    gap: '0.4rem'
                  }}>
                    {filteredEditDepts.length === 0 ? (
                      <div style={{ gridColumn: '1 / -1', padding: '1rem', textAlign: 'center', color: '#6b7280', fontSize: '0.85rem' }}>
                        {allDepartments.length === 0 ? "No active departments found." : `No department matching "${editDeptSearch}"`}
                      </div>
                    ) : (
                      filteredEditDepts.map(dept => {
                        const isChecked = editSelectedDepts.includes(dept.id);
                        return (
                          <label
                            key={dept.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justify: 'space-between',
                              gap: '0.4rem',
                              padding: '0.45rem 0.6rem',
                              borderRadius: '0.375rem',
                              border: isChecked ? '1px solid #6366f1' : '1px solid #e5e7eb',
                              backgroundColor: isChecked ? '#eef2ff' : '#ffffff',
                              cursor: 'pointer',
                              transition: 'all 0.15s ease',
                              userSelect: 'none'
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', overflow: 'hidden' }}>
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => toggleEditDept(dept.id)}
                                style={{ cursor: 'pointer', accentColor: '#4f46e5', width: '15px', height: '15px' }}
                              />
                              <span style={{
                                fontSize: '0.8rem',
                                fontWeight: isChecked ? 600 : 400,
                                color: isChecked ? '#312e81' : '#374151',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis'
                              }}>
                                {dept.department_name}
                              </span>
                            </div>
                            <span style={{
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              padding: '0.1rem 0.35rem',
                              borderRadius: '0.25rem',
                              backgroundColor: isChecked ? '#c7d2fe' : '#f3f4f6',
                              color: isChecked ? '#3730a3' : '#6b7280',
                              flexShrink: 0
                            }}>
                              {dept.department_code}
                            </span>
                          </label>
                        );
                      })
                    )}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="edit-instructions">Instructions Text (Optional)</label>
                  <textarea
                    id="edit-instructions"
                    className="form-input"
                    style={{ minHeight: '100px', resize: 'vertical', fontFamily: 'inherit' }}
                    value={editInstructions}
                    onChange={(e) => setEditInstructions(e.target.value)}
                    placeholder="Enter custom guidelines for this session..."
                  />
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={editIsActive}
                      onChange={(e) => setEditIsActive(e.target.checked)}
                      style={{ width: '18px', height: '18px' }}
                    />
                    <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>Is Active / Enabled</span>
                  </label>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1.5rem' }}>
                  <button type="button" className="btn btn-secondary w-full" onClick={cancelEdit} disabled={actionLoading}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary w-full" style={{ backgroundColor: 'var(--warning-color)' }} disabled={actionLoading}>
                    {actionLoading ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              </form>
            ) : (
              // Add Form
              <form onSubmit={handleAddSubmit}>
                <div className="form-group">
                  <label className="form-label" htmlFor="new-sess-name">Session Name</label>
                  <input
                    id="new-sess-name"
                    type="text"
                    className="form-input"
                    value={sessionName}
                    onChange={(e) => setSessionName(e.target.value)}
                    placeholder="e.g. Session 1"
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="new-exam-title">Exam Title</label>
                  <input
                    id="new-exam-title"
                    type="text"
                    className="form-input"
                    value={examTitle}
                    onChange={(e) => setExamTitle(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="new-exam-date">Exam Date</label>
                  <input
                    id="new-exam-date"
                    type="date"
                    className="form-input"
                    value={examDate}
                    onChange={(e) => setExamDate(e.target.value)}
                    required
                  />
                </div>

                <div className="grid grid-2" style={{ gap: '1rem', gridTemplateColumns: '1fr 1fr', marginBottom: '1rem' }}>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label" htmlFor="new-start-time">Start Time (IST)</label>
                    <input
                      id="new-start-time"
                      type="datetime-local"
                      className="form-input"
                      value={startTime}
                      onChange={(e) => setStartTime(e.target.value)}
                      required
                    />
                  </div>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label" htmlFor="new-end-time">End Time (IST)</label>
                    <input
                      id="new-end-time"
                      type="datetime-local"
                      className="form-input"
                      value={endTime}
                      onChange={(e) => setEndTime(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="new-duration">Duration (Minutes)</label>
                  <input
                    id="new-duration"
                    type="number"
                    className="form-input"
                    value={durationMinutes}
                    onChange={(e) => setDurationMinutes(e.target.value)}
                    required
                  />
                </div>

                {/* Enhanced Assign Departments Selector (ADD FORM) */}
                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <label className="form-label" style={{ margin: 0, fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Building2 size={16} style={{ color: 'var(--primary-color)' }} />
                      Assign Departments for Exam
                    </label>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.15rem 0.5rem', borderRadius: '1rem', backgroundColor: selectedDepts.length > 0 ? '#e0e7ff' : '#f3f4f6', color: selectedDepts.length > 0 ? '#4338ca' : '#6b7280' }}>
                      {selectedDepts.length} of {allDepartments.length} Selected
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.6rem', alignItems: 'center' }}>
                    <div style={{ position: 'relative', flex: 1 }}>
                      <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
                      <input
                        type="text"
                        className="form-input"
                        placeholder="Search department name or code..."
                        value={addDeptSearch}
                        onChange={(e) => setAddDeptSearch(e.target.value)}
                        style={{ paddingLeft: '28px', paddingRight: '28px', height: '34px', fontSize: '0.825rem' }}
                      />
                      {addDeptSearch && (
                        <button
                          type="button"
                          onClick={() => setAddDeptSearch('')}
                          style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', padding: 0 }}
                        >
                          <XCircle size={14} />
                        </button>
                      )}
                    </div>

                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={handleSelectAllAdd}
                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', height: '34px', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                    >
                      <CheckCheck size={14} /> Select All
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={handleDeselectAllAdd}
                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', height: '34px', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                    >
                      Clear All
                    </button>
                  </div>

                  <div style={{
                    maxHeight: '220px',
                    overflowY: 'auto',
                    border: '1px solid var(--border-color)',
                    borderRadius: '0.5rem',
                    padding: '0.5rem',
                    backgroundColor: '#fafafa',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                    gap: '0.4rem'
                  }}>
                    {filteredAddDepts.length === 0 ? (
                      <div style={{ gridColumn: '1 / -1', padding: '1rem', textAlign: 'center', color: '#6b7280', fontSize: '0.85rem' }}>
                        {allDepartments.length === 0 ? "No active departments found." : `No department matching "${addDeptSearch}"`}
                      </div>
                    ) : (
                      filteredAddDepts.map(dept => {
                        const isChecked = selectedDepts.includes(dept.id);
                        return (
                          <label
                            key={dept.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justify: 'space-between',
                              gap: '0.4rem',
                              padding: '0.45rem 0.6rem',
                              borderRadius: '0.375rem',
                              border: isChecked ? '1px solid #6366f1' : '1px solid #e5e7eb',
                              backgroundColor: isChecked ? '#eef2ff' : '#ffffff',
                              cursor: 'pointer',
                              transition: 'all 0.15s ease',
                              userSelect: 'none'
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', overflow: 'hidden' }}>
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => toggleAddDept(dept.id)}
                                style={{ cursor: 'pointer', accentColor: '#4f46e5', width: '15px', height: '15px' }}
                              />
                              <span style={{
                                fontSize: '0.8rem',
                                fontWeight: isChecked ? 600 : 400,
                                color: isChecked ? '#312e81' : '#374151',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis'
                              }}>
                                {dept.department_name}
                              </span>
                            </div>
                            <span style={{
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              padding: '0.1rem 0.35rem',
                              borderRadius: '0.25rem',
                              backgroundColor: isChecked ? '#c7d2fe' : '#f3f4f6',
                              color: isChecked ? '#3730a3' : '#6b7280',
                              flexShrink: 0
                            }}>
                              {dept.department_code}
                            </span>
                          </label>
                        );
                      })
                    )}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="new-instructions">Instructions Text (Optional)</label>
                  <textarea
                    id="new-instructions"
                    className="form-input"
                    style={{ minHeight: '100px', resize: 'vertical', fontFamily: 'inherit' }}
                    value={instructions}
                    onChange={(e) => setInstructions(e.target.value)}
                    placeholder="Enter custom guidelines for this session..."
                  />
                </div>

                <button type="submit" className="btn btn-primary w-full mt-4" disabled={actionLoading}>
                  {actionLoading ? 'Creating...' : 'Create Session'}
                </button>
              </form>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}

