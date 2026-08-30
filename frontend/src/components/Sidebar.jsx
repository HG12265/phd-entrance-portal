import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Building2, 
  Calendar, 
  Users, 
  Upload, 
  FileUp, 
  BookOpen, 
  TrendingUp, 
  Lock,
  LogOut
} from 'lucide-react';

export default function Sidebar() {
  const navigate = useNavigate();
  const adminUser = JSON.parse(localStorage.getItem('admin_user') || '{}');
  const isSuperAdmin = adminUser.role === 'super_admin';

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_user');
    localStorage.removeItem('userRole');
    navigate('/admin/login');
  };

  return (
    <aside className="sidebar">
      <div style={{ marginBottom: '1.5rem', paddingLeft: '1rem' }}>
        <h4 style={{ color: 'var(--text-secondary)', textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.05em' }}>
          Admin Panel
        </h4>
      </div>
      
      <NavLink 
        to="/admin/dashboard" 
        className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}
      >
        <LayoutDashboard size={18} />
        <span>Dashboard</span>
      </NavLink>

      <NavLink 
        to="/admin/departments" 
        className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}
      >
        <Building2 size={18} />
        <span>Departments</span>
      </NavLink>

      <NavLink 
        to="/admin/exam-sessions" 
        className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}
      >
        <Calendar size={18} />
        <span>Exam Sessions</span>
      </NavLink>

      <NavLink 
        to="/admin/candidates" 
        end
        className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}
      >
        <Users size={18} />
        <span>Candidate List</span>
      </NavLink>

      <NavLink 
        to="/admin/candidates/upload" 
        className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}
      >
        <Upload size={18} />
        <span>Upload Candidates</span>
      </NavLink>
      
      {isSuperAdmin && (
        <>
          <NavLink 
            to="/admin/questions" 
            end
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}
          >
            <FileUp size={18} />
            <span>Question Upload</span>
          </NavLink>

          <NavLink 
            to="/admin/questions/bank" 
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}
          >
            <BookOpen size={18} />
            <span>Question Bank</span>
          </NavLink>
        </>
      )}
      
      <NavLink 
        to="/admin/reports" 
        className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}
      >
        <TrendingUp size={18} />
        <span>Reports</span>
      </NavLink>

      <NavLink 
        to="/admin/exam-control" 
        className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
        style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}
      >
        <Lock size={18} />
        <span>Exam Control</span>
      </NavLink>

      <button 
        onClick={handleLogout}
        className="sidebar-link"
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '0.75rem', 
          width: '100%', 
          background: 'none', 
          border: 'none', 
          font: 'inherit',
          textAlign: 'left', 
          cursor: 'pointer',
          marginTop: 'auto',
          color: '#ef4444',
          transition: 'var(--transition-all)'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = '#fee2e2';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'transparent';
        }}
      >
        <LogOut size={18} />
        <span>Logout</span>
      </button>
    </aside>
  );
}

