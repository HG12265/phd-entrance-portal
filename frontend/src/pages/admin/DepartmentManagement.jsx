import React, { useEffect, useState } from 'react';
import Sidebar from '../../components/Sidebar';
import api from '../../services/api';

export default function DepartmentManagement() {
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Form states (Add Department)
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [description, setDescription] = useState('');

  // Editing states
  const [editingDept, setEditingDept] = useState(null);
  const [editName, setEditName] = useState('');
  const [editCode, setEditCode] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editIsActive, setEditIsActive] = useState(true);

  // Deletion modal states
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deptToDelete, setDeptToDelete] = useState(null);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');

  // Fetch departments list
  const fetchDepartments = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.get('/api/admin/departments');
      setDepartments(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch departments.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDepartments();
  }, []);

  // Handle Add Department
  const handleAddSubmit = async (e) => {
    e.preventDefault();
    if (!name || !code) {
      setError('Department Name and Code are required.');
      return;
    }

    setActionLoading(true);
    setError('');
    setSuccess('');

    try {
      await api.post('/api/admin/departments', {
        department_name: name,
        department_code: code,
        description: description
      });

      setSuccess('Department added successfully!');
      setName('');
      setCode('');
      setDescription('');
      fetchDepartments();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create department.');
    } finally {
      setActionLoading(false);
    }
  };

  // Start Editing a department
  const startEdit = (dept) => {
    setEditingDept(dept);
    setEditName(dept.department_name);
    setEditCode(dept.department_code);
    setEditDescription(dept.description || '');
    setEditIsActive(dept.is_active);
    setError('');
    setSuccess('');
  };

  // Cancel Editing
  const cancelEdit = () => {
    setEditingDept(null);
    setEditName('');
    setEditCode('');
    setEditDescription('');
    setEditIsActive(true);
  };

  // Handle Update Department
  const handleUpdateSubmit = async (e) => {
    e.preventDefault();
    if (!editName || !editCode) {
      setError('Department Name and Code are required.');
      return;
    }

    setActionLoading(true);
    setError('');
    setSuccess('');

    try {
      await api.put(`/api/admin/departments/${editingDept.id}`, {
        department_name: editName,
        department_code: editCode,
        description: editDescription,
        is_active: editIsActive
      });

      setSuccess('Department updated successfully!');
      cancelEdit();
      fetchDepartments();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update department.');
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Delete Button Click (Open Modal)
  const handleDeleteClick = (dept) => {
    setDeptToDelete(dept);
    setDeleteConfirmText('');
    setShowDeleteConfirm(true);
    setError('');
    setSuccess('');
  };

  // Confirm and Execute Delete
  const confirmDelete = async () => {
    if (deleteConfirmText !== 'DELETE') return;
    
    setShowDeleteConfirm(false);
    setActionLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await api.delete(`/api/admin/departments/${deptToDelete.id}`);
      const counts = response.data?.deleted_counts || {};
      setSuccess(
        `Department "${deptToDelete.department_name}" permanently deleted! Cleaned up: ${counts.candidates || 0} candidates, ${counts.questions || 0} questions, ${counts.exam_attempts || 0} attempts.`
      );
      fetchDepartments();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete department.');
    } finally {
      setActionLoading(false);
      setDeptToDelete(null);
    }
  };

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="page-container">
        <h1 className="mb-4">Department Management</h1>
        <p className="mb-4">Configure the institutional departments hosting the PhD Entrance examinations.</p>

        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <div className="grid grid-2" style={{ gridTemplateColumns: '1.7fr 1fr', alignItems: 'start' }}>
          
          {/* Left Column: Department List Table */}
          <div className="card">
            <h3 className="card-title">Active Departments Registry</h3>
            {loading ? (
              <p>Loading departments list...</p>
            ) : departments.length === 0 ? (
              <p>No departments found. Use the form to add one.</p>
            ) : (
              <div className="table-container" style={{ margin: 0 }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th style={{ width: '60px' }}>S.No</th>
                      <th>Department Name</th>
                      <th>Code</th>
                      <th>Description</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {departments.map((dept, index) => (
                      <tr key={dept.id}>
                        <td>{index + 1}</td>
                        <td><strong>{dept.department_name}</strong></td>
                        <td><span className="user-badge" style={{ backgroundColor: '#f1f5f9', color: '#334155' }}>{dept.department_code}</span></td>
                        <td>{dept.description || <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>No description</span>}</td>
                        <td>
                          <span className="user-badge" style={{
                            backgroundColor: dept.is_active ? 'var(--success-bg)' : 'var(--danger-bg)',
                            color: dept.is_active ? 'var(--success-color)' : 'var(--danger-color)'
                          }}>
                            {dept.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                              onClick={() => startEdit(dept)}
                            >
                              Edit
                            </button>
                            <button
                              className="btn btn-danger"
                              style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                              onClick={() => handleDeleteClick(dept)}
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

          {/* Right Column: Form Panel (Add / Edit Context) */}
          <div className="card" style={{ borderTop: editingDept ? '4px solid var(--warning-color)' : '4px solid var(--primary-color)' }}>
            <h3 className="card-title">
              {editingDept ? 'Edit Department' : 'Add New Department'}
            </h3>
            
            {editingDept ? (
              // Edit Form
              <form onSubmit={handleUpdateSubmit}>
                <div className="form-group">
                  <label className="form-label" htmlFor="edit-name">Department Name</label>
                  <input
                    id="edit-name"
                    type="text"
                    className="form-input"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    placeholder="e.g. Computer Science"
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="edit-code">Department Code</label>
                  <input
                    id="edit-code"
                    type="text"
                    className="form-input"
                    value={editCode}
                    onChange={(e) => setEditCode(e.target.value)}
                    placeholder="e.g. CS"
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="edit-desc">Description (Optional)</label>
                  <textarea
                    id="edit-desc"
                    className="form-input"
                    style={{ minHeight: '80px', fontFamily: 'inherit', resize: 'vertical' }}
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    placeholder="Enter short description..."
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
                  <label className="form-label" htmlFor="new-name">Department Name</label>
                  <input
                    id="new-name"
                    type="text"
                    className="form-input"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Mathematics"
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="new-code">Department Code</label>
                  <input
                    id="new-code"
                    type="text"
                    className="form-input"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="e.g. MATH"
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="new-desc">Description (Optional)</label>
                  <textarea
                    id="new-desc"
                    className="form-input"
                    style={{ minHeight: '80px', fontFamily: 'inherit', resize: 'vertical' }}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Enter short description..."
                  />
                </div>

                <button type="submit" className="btn btn-primary w-full mt-4" disabled={actionLoading}>
                  {actionLoading ? 'Creating...' : 'Create Department'}
                </button>
              </form>
            )}
          </div>
        </div>

        {/* Custom Delete Confirmation Modal */}
        {showDeleteConfirm && deptToDelete && (
          <div className="modal-backdrop">
            <div className="modal-content" style={{ maxWidth: '500px' }}>
              <h3 className="modal-title" style={{ color: 'var(--danger-color)' }}>Confirm Department Deletion</h3>
              <p className="mb-4">
                Are you sure you want to permanently delete the department <strong>{deptToDelete.department_name} ({deptToDelete.department_code})</strong>?
              </p>
              
              <div style={{ background: '#fff5f5', padding: '0.8rem', borderLeft: '4px solid var(--danger-color)', fontSize: '0.85rem' }} className="mb-4 text-secondary">
                <strong>WARNING:</strong> This action cannot be undone. It will permanently delete all associated:
                <ul style={{ margin: '0.5rem 0 0 1.2rem', padding: 0 }}>
                  <li>Candidates registered in this department</li>
                  <li>Questions uploaded for this department</li>
                  <li>Exam attempts and candidate answers</li>
                  <li>Evaluation results and reports</li>
                </ul>
              </div>

              <div className="form-group mb-4">
                <label className="form-label" htmlFor="delete-confirm-input" style={{ fontWeight: 600 }}>
                  Type <strong style={{ color: 'var(--danger-color)' }}>DELETE</strong> to confirm:
                </label>
                <input
                  id="delete-confirm-input"
                  type="text"
                  className="form-control"
                  placeholder="Type DELETE in capital letters"
                  value={deleteConfirmText}
                  onChange={(e) => setDeleteConfirmText(e.target.value)}
                  style={{ textTransform: 'uppercase' }}
                />
              </div>

              <div className="flex justify-end gap-2">
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={() => {
                    setShowDeleteConfirm(false);
                    setDeptToDelete(null);
                  }}
                >
                  Cancel
                </button>
                <button 
                  type="button" 
                  className="btn btn-danger" 
                  onClick={confirmDelete}
                  disabled={deleteConfirmText !== 'DELETE'}
                >
                  Permanently Delete
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
