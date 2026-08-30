import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';

export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();

  const isAdmin = location.pathname.startsWith('/admin');
  const hasAdminToken = !!localStorage.getItem('admin_token');
  const isCandidate = location.pathname.startsWith('/candidate');
  const hasCandidateToken = !!localStorage.getItem('authToken');

  const showUserBadge = (isAdmin && hasAdminToken) || (isCandidate && hasCandidateToken);

  const handleLogout = () => {
    if (isAdmin) {
      localStorage.removeItem('admin_token');
      localStorage.removeItem('admin_user');
      localStorage.removeItem('userRole');
      navigate('/admin/login');
    } else {
      localStorage.removeItem('authToken');
      localStorage.removeItem('userRole');
      localStorage.removeItem('userEmail');
      navigate('/');
    }
  };

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">
        🎓 PhD Entrance Portal
      </Link>

      <div className="navbar-actions">
        {showUserBadge && (
          <>
            <span className="user-badge">
              {isAdmin ? '🛡️ Admin Mode' : '📝 Candidate Mode'}
            </span>
            <button className="btn btn-secondary" onClick={handleLogout}>
              Logout
            </button>
          </>
        )}
        {!showUserBadge && (
          <>
            <Link to="/candidate/login" className="btn btn-secondary">Candidate Login</Link>
            <Link to="/admin/login" className="btn btn-primary">Admin Login</Link>
          </>
        )}
      </div>
    </nav>
  );
}
