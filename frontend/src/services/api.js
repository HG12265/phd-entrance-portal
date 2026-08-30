import axios from 'axios';
import { getExamClientId } from '../utils/examClient';

const api = axios.create({
  baseURL: window.location.port === '5173'
    ? 'http://127.0.0.1:8000'
    : window.location.origin,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    if (config.url.startsWith('/api/admin') || config.url.startsWith('/api/settings/admin')) {
      const adminToken = localStorage.getItem('admin_token');
      if (adminToken) {
        config.headers.Authorization = `Bearer ${adminToken}`;
      }
    } else if (config.url.startsWith('/api/candidate')) {
      const candidateToken = localStorage.getItem('candidate_token');
      if (candidateToken) {
        config.headers.Authorization = `Bearer ${candidateToken}`;
      }
      config.headers['X-Exam-Client-Id'] = getExamClientId();
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Candidate API helpers
export const getCandidates = (params) => {
  return api.get('/api/admin/candidates', { params });
};

export const getCandidateById = (id) => {
  return api.get(`/api/admin/candidates/${id}`);
};

export const uploadCandidateExcel = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/api/admin/candidates/upload-excel', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

export const uploadCandidatePhotos = (files) => {
  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i]);
  }
  return api.post('/api/admin/candidates/upload-photos', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

export const remapCandidatePhotos = () => {
  return api.post('/api/admin/candidates/remap-photos');
};

// Question API helpers
export const getQuestions = (params) => {
  return api.get('/api/admin/questions', { params });
};

export const getQuestionById = (id) => {
  return api.get(`/api/admin/questions/${id}`);
};

export const uploadQuestionExcel = (departmentId, file, replaceExisting = false) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/api/admin/questions/upload-excel/${departmentId}?replace_existing=${replaceExisting}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

export const getDepartmentQuestionSummary = (departmentId) => {
  return api.get(`/api/admin/questions/department/${departmentId}/summary`);
};

export const deleteQuestion = (id) => {
  return api.delete(`/api/admin/questions/${id}`);
};

export const deleteDepartmentQuestions = (departmentId) => {
  return api.delete(`/api/admin/questions/department/${departmentId}`);
};

export const getDashboardQuestionSummary = () => {
  return api.get('/api/admin/questions/summary/all');
};

// Candidate Exam Phase 6 API Helpers
export const startExam = () => {
  return api.post('/api/candidate/exam/start');
};

export const getCurrentExam = () => {
  return api.get('/api/candidate/exam/current');
};

export const saveAnswer = (payload) => {
  return api.post('/api/candidate/exam/save-answer', payload);
};

export const markQuestionStatus = (payload) => {
  return api.post('/api/candidate/exam/mark-status', payload);
};

export const getExamTimer = (attemptId) => {
  return api.get(`/api/candidate/exam/timer/${attemptId}`);
};

export const submitExam = (payload) => {
  return api.post('/api/candidate/exam/submit', payload);
};

export const getCandidateResult = () => {
  return api.get('/api/candidate/exam/result');
};

// Phase 8 Admin Reports API functions
export const getReportSummary = (params) => {
  return api.get('/api/admin/reports/summary', { params });
};

export const getSubjectSummary = (params) => {
  return api.get('/api/admin/reports/subject-summary', { params });
};

export const getOverallLeaderboard = (params) => {
  return api.get('/api/admin/reports/leaderboard/overall', { params });
};

export const getSubjectLeaderboard = (departmentId, params) => {
  return api.get(`/api/admin/reports/leaderboard/subject/${departmentId}`, { params });
};

export const getAbsentees = (params) => {
  return api.get('/api/admin/reports/absentees', { params });
};

export const getCandidateReport = (candidateId, params) => {
  return api.get(`/api/admin/reports/candidate/${candidateId}`, { params });
};

export const getAttemptReport = (attemptId) => {
  return api.get(`/api/admin/reports/attempt/${attemptId}`);
};

export const downloadOverallExcel = (params) => {
  return api.get('/api/admin/reports/export/overall-excel', { params, responseType: 'blob' });
};

export const downloadSubjectExcel = (departmentId, params) => {
  return api.get(`/api/admin/reports/export/subject-excel/${departmentId}`, { params, responseType: 'blob' });
};

export const downloadAbsenteesExcel = (params) => {
  return api.get('/api/admin/reports/export/absentees-excel', { params, responseType: 'blob' });
};

export const downloadCandidatePdf = (candidateId, params) => {
  return api.get(`/api/admin/reports/export/candidate-pdf/${candidateId}`, { params, responseType: 'blob' });
};

// Phase 11 Exam Control helpers
export const getAdminExamControlCandidate = (appNo) => {
  return api.get(`/api/admin/exam-control/candidate/${encodeURIComponent(appNo)}`);
};

export const reopenCandidateExam = (payload) => {
  return api.post('/api/admin/exam-control/reopen', payload);
};

// Phase 15 Reports API helpers
export const getOverallResult = (params) => {
  return api.get('/api/admin/reports/overall-result', { params });
};

export const getDepartmentWiseReport = (params) => {
  return api.get('/api/admin/reports/department-wise', { params });
};

export const getDepartmentDetail = (departmentId, params) => {
  return api.get(`/api/admin/reports/department/${departmentId}`, { params });
};

export const downloadOverallResultExcel = (params) => {
  return api.get('/api/admin/reports/export/overall-result-excel', { params, responseType: 'blob' });
};

export const downloadDepartmentWiseExcel = (params) => {
  return api.get('/api/admin/reports/export/department-wise-excel', { params, responseType: 'blob' });
};

export const downloadDepartmentReportExcel = (departmentId, params) => {
  return api.get(`/api/admin/reports/export/department-report-excel/${departmentId}`, { params, responseType: 'blob' });
};

export const downloadOverallResultPdf = (params) => {
  return api.get('/api/admin/reports/export/overall-result-pdf', { params, responseType: 'blob' });
};

export const downloadDepartmentWisePdf = (params) => {
  return api.get('/api/admin/reports/export/department-wise-pdf', { params, responseType: 'blob' });
};

export const downloadDepartmentReportPdf = (departmentId, params) => {
  return api.get(`/api/admin/reports/export/department-report-pdf/${departmentId}`, { params, responseType: 'blob' });
};

export const downloadDepartmentWiseDetailsExcel = (params) => {
  return api.get('/api/admin/reports/export/department-wise-details-excel', { params, responseType: 'blob' });
};


export const forceReopenSubmittedExam = (payload) => {
  return api.post('/api/admin/exam-control/force-reopen-submitted', payload);
};

export const addExtraTime = (payload) => {
  return api.post('/api/admin/exam-control/add-extra-time', payload);
};

export const logFullscreenEvent = (payload) => {
  return api.post('/api/candidate/exam/fullscreen-event', payload);
};

export const getImageUrl = (path) => {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  const base = api.defaults.baseURL || `${window.location.protocol}//${window.location.hostname}:8000`;
  // Clean potential double slashes
  const cleanBase = base.endsWith('/') ? base.slice(0, -1) : base;
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${cleanBase}${cleanPath}`;
};

export const getPublicSetting = (key) => {
  return api.get(`/api/settings/public/${key}`);
};

export const updateSetting = (key, payload) => {
  return api.put(`/api/settings/admin/${key}`, payload);
};

export const getAdminCredentialsInfo = () => {
  return api.get('/api/admin/auth/credentials-info');
};

export const updateAdminCredentials = (payload) => {
  return api.put('/api/admin/auth/credentials', payload);
};

export const purgeAllData = (confirmPhrase) => {
  return api.post('/api/admin/auth/system/purge-all-data', { confirm_phrase: confirmPhrase });
};

export const downloadFullBackup = () => {
  return api.get('/api/admin/auth/system/download-full-backup', {
    responseType: 'blob'
  });
};

export default api;
