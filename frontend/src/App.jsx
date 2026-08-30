import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';

// Pages
import CandidateLogin from './pages/candidate/CandidateLogin';
import CandidateProfile from './pages/candidate/CandidateProfile';
import Instructions from './pages/candidate/Instructions';
import ExamPage from './pages/candidate/ExamPage';
import ResultPage from './pages/candidate/ResultPage';

import AdminLogin from './pages/admin/AdminLogin';
import Dashboard from './pages/admin/Dashboard';
import DepartmentManagement from './pages/admin/DepartmentManagement';
import ExamSessions from './pages/admin/ExamSessions';
import CandidateList from './pages/admin/CandidateList';
import CandidateUpload from './pages/admin/CandidateUpload';
import CandidateDetails from './pages/admin/CandidateDetails';
import QuestionUpload from './pages/admin/QuestionUpload';
import QuestionBank from './pages/admin/QuestionBank';
import QuestionPreview from './pages/admin/QuestionPreview';
import Reports from './pages/admin/Reports';
import CandidateReport from './pages/admin/CandidateReport';
import ExamControl from './pages/admin/ExamControl';
import DeveloperInfo from './pages/DeveloperInfo';

export default function App() {
  return (
    <Router>
      <div className="app-container">
        <main className="main-content">
          <Routes>
            {/* Public Routes */}
            <Route path="/" element={<CandidateLogin />} />
            <Route path="/candidate/login" element={<CandidateLogin />} />
            <Route path="/admin" element={<AdminLogin />} />
            <Route path="/admin/login" element={<AdminLogin />} />
            <Route path="/dev" element={<DeveloperInfo />} />

            {/* Candidate Protected Routes */}
            <Route path="/candidate/profile" element={
              <ProtectedRoute requiredRole="candidate">
                <CandidateProfile />
              </ProtectedRoute>
            } />
            <Route path="/candidate/instructions" element={
              <ProtectedRoute requiredRole="candidate">
                <Instructions />
              </ProtectedRoute>
            } />
            <Route path="/candidate/exam" element={
              <ProtectedRoute requiredRole="candidate">
                <ExamPage />
              </ProtectedRoute>
            } />
            <Route path="/candidate/result" element={
              <ProtectedRoute requiredRole="candidate">
                <ResultPage />
              </ProtectedRoute>
            } />

            {/* Admin Protected Routes */}
            <Route path="/admin/dashboard" element={
              <ProtectedRoute requiredRole="admin">
                <Dashboard />
              </ProtectedRoute>
            } />
            <Route path="/admin/departments" element={
              <ProtectedRoute requiredRole="admin">
                <DepartmentManagement />
              </ProtectedRoute>
            } />
            <Route path="/admin/exam-sessions" element={
              <ProtectedRoute requiredRole="admin">
                <ExamSessions />
              </ProtectedRoute>
            } />
            <Route path="/admin/candidates" element={
              <ProtectedRoute requiredRole="admin">
                <CandidateList />
              </ProtectedRoute>
            } />
            <Route path="/admin/candidates/upload" element={
              <ProtectedRoute requiredRole="admin">
                <CandidateUpload />
              </ProtectedRoute>
            } />
            <Route path="/admin/candidates/:id" element={
              <ProtectedRoute requiredRole="admin">
                <CandidateDetails />
              </ProtectedRoute>
            } />
            <Route path="/admin/questions" element={
              <ProtectedRoute requiredRole="admin" superAdminOnly={true}>
                <QuestionUpload />
              </ProtectedRoute>
            } />
            <Route path="/admin/questions/upload" element={
              <ProtectedRoute requiredRole="admin" superAdminOnly={true}>
                <QuestionUpload />
              </ProtectedRoute>
            } />
            <Route path="/admin/questions/bank" element={
              <ProtectedRoute requiredRole="admin" superAdminOnly={true}>
                <QuestionBank />
              </ProtectedRoute>
            } />
            <Route path="/admin/questions/preview/:departmentId" element={
              <ProtectedRoute requiredRole="admin" superAdminOnly={true}>
                <QuestionPreview />
              </ProtectedRoute>
            } />
            <Route path="/admin/reports" element={
              <ProtectedRoute requiredRole="admin">
                <Reports />
              </ProtectedRoute>
            } />
            <Route path="/admin/reports/candidate/:candidateId" element={
              <ProtectedRoute requiredRole="admin">
                <CandidateReport />
              </ProtectedRoute>
            } />
            <Route path="/admin/exam-control" element={
              <ProtectedRoute requiredRole="admin">
                <ExamControl />
              </ProtectedRoute>
            } />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
