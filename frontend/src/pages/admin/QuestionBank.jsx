import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Sidebar from '../../components/Sidebar';
import MathText from '../../components/MathText';
import api, { getQuestions, deleteQuestion, getImageUrl } from '../../services/api';

export default function QuestionBank() {
  const [departments, setDepartments] = useState([]);
  const [selectedDeptId, setSelectedDeptId] = useState('');
  
  const [questions, setQuestions] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit] = useState(25);
  const [pages, setPages] = useState(1);
  
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [selectedQuestionIds, setSelectedQuestionIds] = useState([]);
  const [deleting, setDeleting] = useState(false);

  // Toggle selection
  const toggleSelectQuestion = (id) => {
    setSelectedQuestionIds(prev =>
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  const toggleSelectAllQuestions = () => {
    const allVisibleIds = questions.map(q => q.id);
    const allSelected = allVisibleIds.every(id => selectedQuestionIds.includes(id));
    if (allSelected) {
      setSelectedQuestionIds(prev => prev.filter(id => !allVisibleIds.includes(id)));
    } else {
      const newSelection = [...selectedQuestionIds];
      allVisibleIds.forEach(id => {
        if (!newSelection.includes(id)) {
          newSelection.push(id);
        }
      });
      setSelectedQuestionIds(newSelection);
    }
  };

  // Fetch departments list
  useEffect(() => {
    const fetchDepts = async () => {
      try {
        const res = await api.get('/api/admin/departments');
        setDepartments(res.data.filter(d => d.is_active));
      } catch (err) {
        setError('Failed to fetch departments list.');
      }
    };
    fetchDepts();
  }, []);

  // Fetch questions based on search, filter, and page
  const fetchQuestions = async () => {
    setLoading(true);
    setError('');
    try {
      const params = {
        page,
        limit,
        is_active: true
      };
      if (selectedDeptId) params.department_id = selectedDeptId;
      if (search) params.search = search;
      
      const res = await getQuestions(params);
      setQuestions(res.data.items);
      setTotal(res.data.total);
      setPages(res.data.pages);
    } catch (err) {
      setError('Failed to fetch questions registry.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQuestions();
  }, [selectedDeptId, page]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    fetchQuestions();
  };

  const handleDelete = async (id) => {
    if (!window.confirm("WARNING: This will permanently delete question records from the database. Existing reports connected to these questions may lose question details. This cannot be undone.\n\nAre you sure you want to proceed?")) {
      return;
    }

    setDeleting(true);
    try {
      await api.delete(`/api/admin/questions/${id}`);
      setSuccess('Question permanently deleted successfully.');
      setSelectedQuestionIds(prev => prev.filter(item => item !== id));
      fetchQuestions();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete question.');
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteBulkQuestions = async () => {
    if (selectedQuestionIds.length === 0) return;
    if (!window.confirm(`WARNING: This will permanently delete ${selectedQuestionIds.length} selected question records from the database. Existing reports connected to these questions may lose question details. This cannot be undone.\n\nAre you sure you want to proceed?`)) {
      return;
    }

    setDeleting(true);
    try {
      await api.delete("/api/admin/questions/bulk-delete", {
        data: { question_ids: selectedQuestionIds }
      });
      setSuccess('Selected questions permanently deleted successfully.');
      setSelectedQuestionIds([]);
      fetchQuestions();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to bulk-delete questions.');
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteDepartmentQuestionBank = async () => {
    if (!selectedDeptId) {
      window.alert('Please select a department/subject first using the filter dropdown.');
      return;
    }
    const dept = departments.find(d => d.id === Number(selectedDeptId));
    const deptName = dept ? dept.department_name : 'selected department';

    if (!window.confirm(`WARNING: This will permanently delete the entire question bank for "${deptName}" from the database. Existing reports connected to these questions may lose question details. This cannot be undone.\n\nAre you sure you want to proceed?`)) {
      return;
    }

    setDeleting(true);
    try {
      await api.delete(`/api/admin/questions/department/${selectedDeptId}/hard-delete`);
      setSuccess(`Entire question bank for "${deptName}" permanently deleted successfully.`);
      setSelectedQuestionIds([]);
      setPage(1);
      fetchQuestions();
      setTimeout(() => setSuccess(''), 4000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete department question bank.');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="page-container">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <div>
            <h1 style={{ margin: 0 }}>Question Registry</h1>
            <p className="text-secondary" style={{ margin: 0 }}>
              Search, filter, and inspect uploaded question banks across all active academic departments.
            </p>
          </div>
          <Link to="/admin/questions/upload" className="btn btn-primary" style={{ textDecoration: 'none' }}>
            ➕ Upload New Bank
          </Link>
        </div>

        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        {/* Filter controls */}
        <div className="card mb-4">
          <form onSubmit={handleSearchSubmit} className="grid grid-3" style={{ gridTemplateColumns: '1fr 1fr 0.3fr', gap: '1rem', alignItems: 'end' }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Filter by Department</label>
              <select
                className="form-input"
                value={selectedDeptId}
                onChange={(e) => {
                  setSelectedDeptId(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All Departments</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>{d.department_name}</option>
                ))}
              </select>
            </div>

            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Search Keywords</label>
              <input
                type="text"
                className="form-input"
                placeholder="Search question text or options..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <button type="submit" className="btn btn-primary" style={{ height: '42px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              Search
            </button>
          </form>
        </div>

        {/* Question grid table */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
              {selectedQuestionIds.length > 0 && (
                <button
                  className="btn btn-danger"
                  style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                  onClick={handleDeleteBulkQuestions}
                  disabled={deleting}
                >
                  Delete Selected ({selectedQuestionIds.length})
                </button>
              )}
              {selectedDeptId && (
                <button
                  className="btn btn-danger"
                  style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem', border: '1px solid darkred' }}
                  onClick={handleDeleteDepartmentQuestionBank}
                  disabled={deleting}
                >
                  Delete Entire Department Question Bank
                </button>
              )}
            </div>
            <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              Total Questions: <strong>{total}</strong>
            </span>
          </div>

          {loading ? (
            <p>Loading questions list...</p>
          ) : questions.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center' }}>
              <p style={{ color: '#64748b', fontSize: '1.1rem' }}>No questions found.</p>
              <p style={{ fontSize: '0.9rem', color: '#94a3b8' }}>Ensure a department question bank of exactly 70 questions has been uploaded.</p>
            </div>
          ) : (
            <>
              <div className="table-container" style={{ margin: 0 }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th style={{ width: '40px', textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={questions.length > 0 && questions.every(q => selectedQuestionIds.includes(q.id))}
                          onChange={toggleSelectAllQuestions}
                        />
                      </th>
                      <th style={{ width: '60px' }}>S.No</th>
                      <th style={{ width: '150px' }}>Department</th>
                      <th style={{ width: '80px' }}>Q.No</th>
                      <th>Question Text Preview</th>
                      <th style={{ width: '120px' }}>Correct Option</th>
                      <th style={{ width: '80px' }}>Marks</th>
                      <th style={{ width: '90px' }}>Status</th>
                      <th style={{ width: '100px' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {questions.map((q, idx) => (
                      <tr key={q.id}>
                        <td style={{ textAlign: 'center', verticalAlign: 'top' }}>
                          <input
                            type="checkbox"
                            checked={selectedQuestionIds.includes(q.id)}
                            onChange={() => toggleSelectQuestion(q.id)}
                          />
                        </td>
                        <td style={{ verticalAlign: 'top', fontWeight: 'bold' }}>
                          {(page - 1) * limit + idx + 1}
                        </td>
                        <td style={{ verticalAlign: 'top' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{q.department_name}</span>
                        </td>
                        <td style={{ verticalAlign: 'top', fontWeight: 'bold' }}>{q.question_no}</td>
                        <td>
                          <div style={{ fontWeight: 500, marginBottom: '0.5rem', color: '#1e293b' }}>
                            <MathText text={q.question_text} />
                          </div>

                          <div className="grid grid-2" style={{ gap: '0.5rem', fontSize: '0.8rem', color: '#64748b' }}>
                            <div><strong style={{ color: q.correct_option === 'A' ? 'var(--success-color)' : 'inherit' }}>A:</strong> <MathText text={q.option_a} /></div>
                            <div><strong style={{ color: q.correct_option === 'B' ? 'var(--success-color)' : 'inherit' }}>B:</strong> <MathText text={q.option_b} /></div>
                            <div><strong style={{ color: q.correct_option === 'C' ? 'var(--success-color)' : 'inherit' }}>C:</strong> <MathText text={q.option_c} /></div>
                            <div><strong style={{ color: q.correct_option === 'D' ? 'var(--success-color)' : 'inherit' }}>D:</strong> <MathText text={q.option_d} /></div>
                          </div>
                        </td>
                        <td style={{ verticalAlign: 'top', textAlign: 'center' }}>
                          <span className="user-badge" style={{ backgroundColor: 'var(--success-bg)', color: 'var(--success-color)', fontWeight: 'bold' }}>
                            Option {q.correct_option}
                          </span>
                        </td>
                        <td style={{ verticalAlign: 'top', textAlign: 'center' }}>{q.marks}</td>
                        <td style={{ verticalAlign: 'top' }}>
                          <span className="user-badge" style={{ backgroundColor: '#ecfdf5', color: '#047857', fontWeight: 600 }}>
                            {q.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td style={{ verticalAlign: 'top' }}>
                          <button
                            className="btn btn-danger"
                            style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                            onClick={() => handleDelete(q.id)}
                            disabled={deleting}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination component */}
              {pages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.5rem', padding: '0 0.5rem' }}>
                  <span style={{ fontSize: '0.875rem', color: '#64748b' }}>
                    Showing page {page} of {pages} ({total} questions total)
                  </span>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      className="btn btn-secondary"
                      disabled={page === 1}
                      onClick={() => setPage(p => Math.max(p - 1, 1))}
                    >
                      Previous
                    </button>
                    <button
                      className="btn btn-secondary"
                      disabled={page === pages}
                      onClick={() => setPage(p => Math.min(p + 1, pages))}
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
