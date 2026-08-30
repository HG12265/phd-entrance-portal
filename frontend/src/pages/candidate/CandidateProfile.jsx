import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { getImageUrl } from '../../services/api';

export default function CandidateProfile() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await api.get('/api/candidate/auth/me');
        setProfile(response.data);
      } catch (err) {
        setError('Failed to retrieve candidate profile. Please log in again.');
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('candidate_token');
    localStorage.removeItem('candidate_user');
    localStorage.removeItem('userRole');
    navigate('/candidate/login');
  };

  if (loading) {
    return (
      <div className="page-container">
        <div style={{ textAlign: 'center', marginTop: '4rem' }}>
          <p>Loading candidate profile...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container">
        <div style={{ maxWidth: '600px', margin: '4rem auto', textAlign: 'center' }}>
          <div className="alert alert-danger mb-4">{error}</div>
          <button className="btn btn-primary" onClick={handleLogout}>Go to Login</button>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <h1 className="mb-4">Candidate Profile Verification</h1>
        <p className="mb-4">Please verify your details carefully before starting the examination. Contact the invigilator if any information is incorrect.</p>

        <div className="card">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2rem', alignItems: 'center' }}>
            {profile.photo_status === 'available' && profile.photo_url ? (
              <img 
                src={getImageUrl(profile.photo_url)} 
                alt="Candidate Photograph" 
                style={{ width: '150px', height: '180px', objectFit: 'cover', borderRadius: '0.5rem', border: '1px solid var(--border-color)' }}
                onError={(e) => {
                  e.target.onerror = null; 
                  e.target.style.display = 'none';
                  e.target.parentNode.querySelector('.photo-placeholder').style.display = 'flex';
                }}
              />
            ) : null}
            
            <div 
              className="photo-placeholder"
              style={{ 
                display: profile.photo_status === 'available' && profile.photo_url ? 'none' : 'flex', 
                flex: '0 0 150px', 
                width: '150px',
                height: '180px', 
                backgroundColor: 'var(--background-color)', 
                borderRadius: '0.5rem', 
                alignItems: 'center', 
                justifyContent: 'center', 
                border: '1px solid var(--border-color)', 
                fontSize: '3rem' 
              }}
            >
              👤
            </div>

            <div style={{ flex: '1', minWidth: '250px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h2>{profile.applicant_name || profile.name}</h2>
                <span className="user-badge" style={{ backgroundColor: 'var(--success-bg)', color: 'var(--success-color)' }}>
                  ✓ Verified Profile
                </span>
              </div>

              <table className="table" style={{ width: '100%' }}>
                <tbody>
                  <tr>
                    <td style={{ fontWeight: 600, width: '40%' }}>Application ID</td>
                    <td>{profile.application_id || profile.application_number}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Applicant Name</td>
                    <td>{profile.applicant_name || profile.name}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Initial</td>
                    <td>{profile.initial || <span style={{ color: 'var(--text-secondary)' }}>-</span>}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Full Name</td>
                    <td>{profile.name}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Date of Birth</td>
                    <td>{profile.dob}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Category (FT/PT)</td>
                    <td>{profile.category_ft_pt || <span style={{ color: 'var(--text-secondary)' }}>-</span>}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Mobile Number</td>
                    <td>{profile.mobile_number || <span style={{ color: 'var(--text-secondary)' }}>N/A</span>}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Email Address</td>
                    <td>{profile.email || <span style={{ color: 'var(--text-secondary)' }}>N/A</span>}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Department</td>
                    <td>{profile.department_name}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Programme Offered</td>
                    <td>{profile.programme_offered || <span style={{ color: 'var(--text-secondary)' }}>-</span>}</td>
                  </tr>
                  <tr>
                    <td style={{ fontWeight: 600 }}>Subject</td>
                    <td>{profile.subject || <span style={{ color: 'var(--text-secondary)' }}>-</span>}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="alert alert-warning">
          <strong>Important Security Notice:</strong> By clicking "Proceed to Exam Instructions", you agree that your browser will enter an active exam session. Do not open other tabs or windows during the exam.
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '1.5rem' }}>
          <button className="btn btn-secondary" onClick={handleLogout}>
            Logout / Cancel
          </button>
          <button className="btn btn-primary" onClick={() => navigate('/candidate/instructions')}>
            Proceed to Exam Instructions
          </button>
        </div>
      </div>
    </div>
  );
}
