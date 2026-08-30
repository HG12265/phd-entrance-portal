import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../../components/Sidebar';
import api, { getCandidates } from '../../services/api';

export default function CandidateList() {
  const navigate = useNavigate();

  const [candidates, setCandidates] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [limit] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedIds, setSelectedIds] = useState([]);
  const [deleting, setDeleting] = useState(false);

  // Filter States
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [photoFilter, setPhotoFilter] = useState('');

  // Toggle selection
  const toggleSelect = (id) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  // Toggle select all visible on the page
  const toggleSelectAll = () => {
    const allVisibleIds = candidates.map(c => c.id);
    const allSelected = allVisibleIds.every(id => selectedIds.includes(id));
    if (allSelected) {
      setSelectedIds(prev => prev.filter(id => !allVisibleIds.includes(id)));
    } else {
      const newSelection = [...selectedIds];
      allVisibleIds.forEach(id => {
        if (!newSelection.includes(id)) {
          newSelection.push(id);
        }
      });
      setSelectedIds(newSelection);
    }
  };

  // Delete single candidate
  const handleDeleteSingle = async (id) => {
    if (!window.confirm("WARNING: This will permanently delete selected candidate(s), attempts, answers, and result data. This cannot be undone.\n\nAre you sure you want to proceed?")) {
      return;
    }

    setDeleting(true);
    setError('');
    try {
      await api.delete(`/api/admin/candidates/${id}`);
      setSelectedIds(prev => prev.filter(item => item !== id));
      fetchCandidates();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete candidate.');
    } finally {
      setDeleting(false);
    }
  };

  // Delete bulk selected candidates
  const handleDeleteBulk = async () => {
    if (selectedIds.length === 0) return;
    if (!window.confirm(`WARNING: This will permanently delete selected candidate(s), attempts, answers, and result data. This cannot be undone.\n\nAre you sure you want to proceed with deleting ${selectedIds.length} candidate(s)?`)) {
      return;
    }

    setDeleting(true);
    setError('');
    try {
      await api.delete("/api/admin/candidates/bulk-delete", {
        data: { candidate_ids: selectedIds }
      });
      setSelectedIds([]);
      fetchCandidates();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete candidates.');
    } finally {
      setDeleting(false);
    }
  };

  // Fetch Departments for Filter
  const fetchDepartments = async () => {
    try {
      const response = await api.get('/api/admin/departments');
      setDepartments(response.data);
    } catch (err) {
      console.error('Failed to load departments', err);
    }
  };

  // Fetch Candidates List
  const fetchCandidates = async () => {
    setLoading(true);
    setError('');
    try {
      const params = {
        page,
        limit,
        search: search || undefined,
        department_id: deptFilter || undefined,
        photo_status: photoFilter || undefined,
        category_ft_pt: categoryFilter || undefined,
        exam_session_id: sessionFilter || undefined
      };
      const response = await getCandidates(params);
      setCandidates(response.data.items);
      setTotal(response.data.total);
      setPages(response.data.pages);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch candidates list.');
    } finally {
      setLoading(false);
    }
  };

  const [sessions, setSessions] = useState([]);
  const [categoryFilter, setCategoryFilter] = useState('');
  const [sessionFilter, setSessionFilter] = useState('');

  // Fetch Sessions for Filter
  const fetchSessions = async () => {
    try {
      const response = await api.get('/api/admin/exam-sessions/');
      setSessions(response.data);
    } catch (err) {
      console.error('Failed to load exam sessions', err);
    }
  };

  useEffect(() => {
    fetchDepartments();
    fetchSessions();
  }, []);

  useEffect(() => {
    fetchCandidates();
  }, [page, deptFilter, photoFilter, categoryFilter, sessionFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    fetchCandidates();
  };

  const handleClearFilters = () => {
    setSearch('');
    setDeptFilter('');
    setPhotoFilter('');
    setCategoryFilter('');
    setSessionFilter('');
    setPage(1);
  };

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="page-container">
        <h1 className="mb-4">Candidate Registry</h1>
        <p className="mb-4">Search, filter, and inspect registered candidates and their photograph mapping details.</p>

        {error && <div className="alert alert-danger">{error}</div>}

        {/* Filters Panel Card */}
        <div className="card mb-4">
          <form onSubmit={handleSearchSubmit} style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'end' }}>
            <div className="form-group" style={{ margin: 0, minWidth: '200px', flex: 1 }}>
              <label className="form-label" htmlFor="search-input">Search Candidates</label>
              <input
                id="search-input"
                type="text"
                className="form-input"
                placeholder="Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <div className="form-group" style={{ margin: 0, minWidth: '150px' }}>
              <label className="form-label" htmlFor="dept-select">Department</label>
              <select
                id="dept-select"
                className="form-input"
                value={deptFilter}
                onChange={(e) => { setDeptFilter(e.target.value); setPage(1); }}
              >
                <option value="">All Departments</option>
                {departments.map((dept) => (
                  <option key={dept.id} value={dept.id}>
                    {dept.department_name} ({dept.department_code})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group" style={{ margin: 0, minWidth: '150px' }}>
              <label className="form-label" htmlFor="category-select">Category (FT/PT)</label>
              <select
                id="category-select"
                className="form-input"
                value={categoryFilter}
                onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
              >
                <option value="">All Categories</option>
                <option value="FT">Full-Time (FT)</option>
                <option value="PT">Part-Time (PT)</option>
              </select>
            </div>

            <div className="form-group" style={{ margin: 0, minWidth: '150px' }}>
              <label className="form-label" htmlFor="session-select">Exam Session</label>
              <select
                id="session-select"
                className="form-input"
                value={sessionFilter}
                onChange={(e) => { setSessionFilter(e.target.value); setPage(1); }}
              >
                <option value="">All Sessions</option>
                {sessions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.session_name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group" style={{ margin: 0, minWidth: '150px' }}>
              <label className="form-label" htmlFor="photo-select">Photo Status</label>
              <select
                id="photo-select"
                className="form-input"
                value={photoFilter}
                onChange={(e) => { setPhotoFilter(e.target.value); setPage(1); }}
              >
                <option value="">All Statuses</option>
                <option value="available">Available</option>
                <option value="missing">Missing</option>
              </select>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', minWidth: '150px' }}>
              <button type="submit" className="btn btn-primary" style={{ flex: 1 }}>Search</button>
              <button type="button" className="btn btn-secondary" onClick={handleClearFilters}>Clear</button>
            </div>
          </form>
        </div>

        {/* List Table Card */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <h3 className="card-title" style={{ margin: 0 }}>Candidate List</h3>
              {selectedIds.length > 0 && (
                <button
                  className="btn btn-danger"
                  style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                  onClick={handleDeleteBulk}
                  disabled={deleting}
                >
                  Delete Selected ({selectedIds.length})
                </button>
              )}
            </div>
            <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              Total Candidates found: <strong>{total}</strong>
            </span>
          </div>

          {loading ? (
            <p>Loading candidate list...</p>
          ) : candidates.length === 0 ? (
            <p>No candidates found matching the selected parameters.</p>
          ) : (
            <>
              <div className="table-container" style={{ margin: 0 }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th style={{ width: '40px', textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={candidates.length > 0 && candidates.every(c => selectedIds.includes(c.id))}
                          onChange={toggleSelectAll}
                        />
                      </th>
                      <th style={{ width: '60px' }}>S.No</th>
                      <th>Application ID</th>
                      <th>Applicant Name</th>
                      <th>Initial</th>
                      <th>DOB</th>
                      <th>Category (FT/PT)</th>
                      <th>Mobile</th>
                      <th>Email</th>
                      <th>Department</th>
                      <th>Programme Offered</th>
                      <th>Subject</th>
                      <th>Photo Status</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((c, index) => (
                      <tr key={c.id}>
                        <td style={{ textAlign: 'center' }}>
                          <input
                            type="checkbox"
                            checked={selectedIds.includes(c.id)}
                            onChange={() => toggleSelect(c.id)}
                          />
                        </td>
                        <td>{(page - 1) * limit + index + 1}</td>
                        <td><strong>{c.application_id || c.application_number}</strong></td>
                        <td>{c.applicant_name || c.name}</td>
                        <td>{c.initial || <span style={{ color: '#94a3b8' }}>-</span>}</td>
                        <td>{c.dob}</td>
                        <td>{c.category_ft_pt || <span style={{ color: '#94a3b8' }}>-</span>}</td>
                        <td>{c.mobile_number || <span style={{ color: '#94a3b8' }}>N/A</span>}</td>
                        <td>{c.email || <span style={{ color: '#94a3b8' }}>N/A</span>}</td>
                        <td>{c.department_name}</td>
                        <td>{c.programme_offered || <span style={{ color: '#94a3b8' }}>-</span>}</td>
                        <td>{c.subject || <span style={{ color: '#94a3b8' }}>-</span>}</td>
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
                            {c.is_active ? 'Enabled' : 'Disabled'}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '0.4rem' }}>
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                              onClick={() => navigate(`/admin/candidates/${c.id}`)}
                            >
                              View Details
                            </button>
                            <button
                              className="btn btn-danger"
                              style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                              onClick={() => handleDeleteSingle(c.id)}
                              disabled={deleting}
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

              {/* Pagination controls */}
              {pages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem', marginTop: '1.5rem' }}>
                  <button
                    className="btn btn-secondary"
                    disabled={page === 1}
                    onClick={() => setPage(p => Math.max(p - 1, 1))}
                  >
                    Previous
                  </button>
                  <span style={{ fontSize: '0.9rem' }}>
                    Page <strong>{page}</strong> of <strong>{pages}</strong>
                  </span>
                  <button
                    className="btn btn-secondary"
                    disabled={page === pages}
                    onClick={() => setPage(p => Math.min(p + 1, pages))}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
