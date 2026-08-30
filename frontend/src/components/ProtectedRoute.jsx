import React from 'react';
import { Navigate } from 'react-router-dom';

export default function ProtectedRoute({ children, requiredRole, superAdminOnly }) {
  if (requiredRole === 'admin') {
    const adminToken = localStorage.getItem('admin_token');
    if (!adminToken) {
      return <Navigate to="/admin/login" replace />;
    }
    if (superAdminOnly) {
      const adminUser = JSON.parse(localStorage.getItem('admin_user') || '{}');
      if (adminUser.role !== 'super_admin') {
        return <Navigate to="/admin/dashboard" replace />;
      }
    }
    return children;
  }

  if (requiredRole === 'candidate') {
    const candidateToken = localStorage.getItem('candidate_token');
    if (!candidateToken) {
      return <Navigate to="/candidate/login" replace />;
    }
    return children;
  }

  const candidateToken = localStorage.getItem('candidate_token');
  if (!candidateToken) {
    return <Navigate to="/candidate/login" replace />;
  }

  return children;
}
