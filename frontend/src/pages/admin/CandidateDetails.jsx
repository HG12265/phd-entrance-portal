import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Sidebar from '../../components/Sidebar';
import { getCandidateById, getImageUrl } from '../../services/api';

export default function CandidateDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [candidate, setCandidate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchCandidateData = async () => {
      setLoading(true);
      setError('');
      try {
        const response = await getCandidateById(id);
        setCandidate(response.data);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to retrieve candidate information.');
      } finally {
        setLoading(false);
      }
    };
    fetchCandidateData();
  }, [id]);

  const handleBack = () => {
    navigate('/admin/candidates');
  };

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="page-container">
        <button 
          onClick={handleBack}
          className="btn btn-secondary mb-4"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
        >
          ← Back to List
        </button>

        <h1 className="mb-4">Candidate Details</h1>

        {error && <div className="alert alert-danger">{error}</div>}
        {loading && <p>Loading candidate details...</p>}

        {!loading && candidate && (
          <div className="card">
            <div className="grid grid-2" style={{ gap: '2rem', alignItems: 'start', gridTemplateColumns: '300px 1fr' }}>
              
              {/* Photo Box Section */}
              <div style={{ textAlign: 'center' }}>
                {candidate.photo_status === 'available' && candidate.photo_path ? (
                  <img
                    src={getImageUrl(candidate.photo_path)}
                    alt={`${candidate.name}'s photograph`}
                    style={{
                      width: '100%',
                      maxHeight: '350px',
                      borderRadius: '8px',
                      objectFit: 'cover',
                      border: '1px solid #cbd5e1',
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
                    }}
                    onError={(e) => {
                      e.target.onerror = null;
                      e.target.style.display = 'none';
                      // If image file loading fails on server side, show placeholder text instead
                      const placeholder = document.getElementById('photo-error-placeholder');
                      if (placeholder) placeholder.style.display = 'flex';
                    }}
                  />
                ) : null}

                {/* Backup error/missing placeholder */}
                <div
                  id="photo-error-placeholder"
                  style={{
                    display: candidate.photo_status === 'available' ? 'none' : 'flex',
                    width: '100%',
                    height: '300px',
                    borderRadius: '8px',
                    backgroundColor: '#f1f5f9',
                    border: '2px dashed #cbd5e1',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#64748b',
                    fontSize: '1rem',
                    flexDirection: 'column',
                    gap: '0.5rem'
                  }}
                >
                  <span style={{ fontSize: '2.5rem' }}>👤</span>
                  <strong>Photo Missing</strong>
                </div>

                <div style={{ marginTop: '1rem' }}>
                  <span className="user-badge" style={{
                    backgroundColor: candidate.photo_status === 'available' ? 'var(--success-bg)' : 'var(--danger-bg)',
                    color: candidate.photo_status === 'available' ? 'var(--success-color)' : 'var(--danger-color)',
                    fontSize: '0.85rem',
                    padding: '0.4rem 0.8rem'
                  }}>
                    {candidate.photo_status === 'available' ? 'Photo Available' : 'Photo Missing'}
                  </span>
                </div>
              </div>

              {/* Candidate Info Table Section */}
              <div>
                <h2 style={{ fontSize: '1.75rem', marginBottom: '1.5rem', borderBottom: '2px solid #f1f5f9', paddingBottom: '0.5rem' }}>
                  {candidate.applicant_name || candidate.name}
                </h2>

                <div className="table-container" style={{ margin: 0 }}>
                  <table className="table" style={{ minWidth: '100%' }}>
                    <tbody>
                      <tr>
                        <td style={{ fontWeight: 'bold', width: '200px', background: '#f8fafc' }}>Application ID</td>
                        <td><strong>{candidate.application_id || candidate.application_number}</strong></td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Applicant Name</td>
                        <td>{candidate.applicant_name || candidate.name}</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Initial</td>
                        <td>{candidate.initial || <span style={{ color: '#94a3b8' }}>-</span>}</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Full Name</td>
                        <td>{candidate.name}</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Date of Birth (DOB)</td>
                        <td>{candidate.dob}</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Category (FT/PT)</td>
                        <td>{candidate.category_ft_pt || <span style={{ color: '#94a3b8' }}>-</span>}</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Mobile Number</td>
                        <td>{candidate.mobile_number || <span style={{ color: '#94a3b8' }}>N/A</span>}</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Email Address (Mail ID)</td>
                        <td>{candidate.email || <span style={{ color: '#94a3b8' }}>N/A</span>}</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Mapped Department</td>
                        <td>{candidate.department_name}</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Programme Offered</td>
                        <td>{candidate.programme_offered || <span style={{ color: '#94a3b8' }}>-</span>}</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Subject</td>
                        <td>{candidate.subject || <span style={{ color: '#94a3b8' }}>-</span>}</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Original Department Text</td>
                        <td>{candidate.original_department_text || <span style={{ color: '#94a3b8' }}>-</span>}</td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Photo Filename</td>
                        <td><code>{candidate.photo_filename || 'N/A'}</code></td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>System Status</td>
                        <td>
                          <span className="user-badge" style={{
                            backgroundColor: candidate.is_active ? 'var(--success-bg)' : '#f1f5f9',
                            color: candidate.is_active ? 'var(--success-color)' : '#64748b'
                          }}>
                            {candidate.is_active ? 'Active / Enabled' : 'Disabled'}
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <td style={{ fontWeight: 'bold', background: '#f8fafc' }}>Record Created At</td>
                        <td>{new Date(candidate.created_at).toLocaleString()}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

            </div>
          </div>
        )}
      </div>
    </div>
  );
}
