import React, { useState, useEffect } from 'react';
import Sidebar from '../../components/Sidebar';
import api, { uploadCandidateExcel, uploadCandidatePhotos, remapCandidatePhotos } from '../../services/api';

export default function CandidateUpload() {
  const [excelFile, setExcelFile] = useState(null);
  const [photosFiles, setPhotosFiles] = useState([]);
  const [excelSummary, setExcelSummary] = useState(null);
  const [photoSummary, setPhotoSummary] = useState(null);
  const [remapMessage, setRemapMessage] = useState('');

  const [excelLoading, setExcelLoading] = useState(false);
  const [photosLoading, setPhotosLoading] = useState(false);
  const [remapLoading, setRemapLoading] = useState(false);
  const [error, setError] = useState('');

  // Manual Candidate Form States
  const [sessions, setSessions] = useState([]);
  const [manualApplicantName, setManualApplicantName] = useState('');
  const [manualAppId, setManualAppId] = useState('');
  const [manualInitial, setManualInitial] = useState('');
  const [manualDob, setManualDob] = useState('');
  const [manualCategory, setManualCategory] = useState('');
  const [manualMobile, setManualMobile] = useState('');
  const [manualEmail, setManualEmail] = useState('');
  const [manualDept, setManualDept] = useState('');
  const [manualProg, setManualProg] = useState('');
  const [manualSubject, setManualSubject] = useState('');
  const [manualSessionId, setManualSessionId] = useState('');
  const [manualLoading, setManualLoading] = useState(false);
  const [manualSuccess, setManualSuccess] = useState('');

  const handleExcelChange = (e) => {
    setExcelFile(e.target.files[0]);
    setError('');
  };

  const handlePhotosChange = (e) => {
    setPhotosFiles(e.target.files);
    setError('');
  };

  // Upload Excel Handler
  const handleExcelUpload = async (e) => {
    e.preventDefault();
    if (!excelFile) {
      setError('Please choose an Excel file to upload.');
      return;
    }

    setExcelLoading(true);
    setError('');
    setExcelSummary(null);

    try {
      const response = await uploadCandidateExcel(excelFile);
      setExcelSummary(response.data);
      setExcelFile(null);
      // Reset input element
      document.getElementById('excel-file-input').value = '';
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to process Excel upload.');
    } finally {
      setExcelLoading(false);
    }
  };

  // Upload Photos Handler
  const handlePhotosUpload = async (e) => {
    e.preventDefault();
    if (photosFiles.length === 0) {
      setError('Please select one or more candidate photo files.');
      return;
    }

    setPhotosLoading(true);
    setError('');
    setPhotoSummary(null);

    try {
      const response = await uploadCandidatePhotos(photosFiles);
      setPhotoSummary(response.data);
      setPhotosFiles([]);
      // Reset input element
      document.getElementById('photos-file-input').value = '';
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload photo files.');
    } finally {
      setPhotosLoading(false);
    }
  };

  // Remap Photos Handler
  const handleRemap = async () => {
    setRemapLoading(true);
    setError('');
    setRemapMessage('');

    try {
      const response = await remapCandidatePhotos();
      setRemapMessage(response.data.message || 'Photos remapped successfully.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remap photos.');
    } finally {
      setRemapLoading(false);
    }
  };

  // Fetch active sessions on mount
  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const response = await api.get('/api/admin/exam-sessions/');
        setSessions(response.data.filter(s => s.is_active));
      } catch (err) {
        console.error('Failed to load active exam sessions', err);
      }
    };
    fetchSessions();
  }, []);

  const handleManualAddSubmit = async (e) => {
    e.preventDefault();
    if (!manualApplicantName || !manualAppId || !manualDept || !manualDob) {
      setError('Please fill in all required fields.');
      return;
    }

    setManualLoading(true);
    setError('');
    setManualSuccess('');

    try {
      const response = await api.post('/api/admin/candidates/manual', {
        application_id: manualAppId,
        applicant_name: manualApplicantName,
        initial: manualInitial || null,
        dob: manualDob,
        category_ft_pt: manualCategory || null,
        mobile_number: manualMobile || null,
        email: manualEmail || null,
        department: manualDept,
        programme_offered: manualProg || null,
        subject: manualSubject || null,
        exam_session_id: manualSessionId ? Number(manualSessionId) : null
      });

      setManualSuccess(response.data.message || 'Candidate added successfully!');
      // Reset form
      setManualApplicantName('');
      setManualAppId('');
      setManualInitial('');
      setManualDob('');
      setManualCategory('');
      setManualMobile('');
      setManualEmail('');
      setManualDept('');
      setManualProg('');
      setManualSubject('');
      setManualSessionId('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add candidate manually.');
    } finally {
      setManualLoading(false);
    }
  };

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="page-container">
        <h1 className="mb-4">Upload & Map Candidates</h1>
        <p className="mb-4">Upload student records via Excel files and upload candidate photos to map them automatically.</p>

        {error && <div className="alert alert-danger">{error}</div>}
        {remapMessage && <div className="alert alert-success">{remapMessage}</div>}

        <div className="grid grid-2 mb-4" style={{ alignItems: 'start' }}>
          {/* Section A: Excel Upload */}
          <div className="card">
            <h3 className="card-title">A. Candidate Excel Upload</h3>
            <form onSubmit={handleExcelUpload}>
              <div className="form-group">
                <label className="form-label" htmlFor="excel-file-input">Select Excel File (.xlsx, .xls)</label>
                <input
                  id="excel-file-input"
                  type="file"
                  accept=".xlsx, .xls"
                  className="form-input"
                  onChange={handleExcelChange}
                  required
                />
              </div>
              <button type="submit" className="btn btn-primary w-full mt-4" disabled={excelLoading}>
                {excelLoading ? 'Processing excel database...' : 'Upload Excel Sheet'}
              </button>
            </form>

            <div style={{ marginTop: '1.5rem', borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
              <h4 style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>B. Candidate Photos Folder Rescan</h4>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                If you have manually copied candidate photos into the `uploads/candidate_photos` folder, click the button below to rescan and remap them to the database.
              </p>
              <button type="button" className="btn btn-secondary w-full mt-2" onClick={handleRemap} disabled={remapLoading}>
                {remapLoading ? 'Scanning folder...' : 'Scan & Remap Photos'}
              </button>
            </div>
          </div>

          {/* Section B: Photo Upload */}
          <div className="card">
            <h3 className="card-title">C. Upload Candidate Photos</h3>
            <form onSubmit={handlePhotosUpload}>
              <div className="form-group">
                <label className="form-label" htmlFor="photos-file-input">Select Images (.jpg, .jpeg, .png)</label>
                <input
                  id="photos-file-input"
                  type="file"
                  accept=".jpg, .jpeg, .png, .JPG, .JPEG, .PNG"
                  multiple
                  className="form-input"
                  onChange={handlePhotosChange}
                  required
                />
              </div>
              <button type="submit" className="btn btn-primary w-full mt-4" disabled={photosLoading}>
                {photosLoading ? 'Uploading and mapping photos...' : 'Upload Photos'}
              </button>
            </form>

            <div style={{ marginTop: '1.5rem', borderTop: '1px solid #e2e8f0', paddingTop: '1rem', fontSize: '0.8rem' }}>
              <strong style={{ display: 'block', marginBottom: '0.5rem' }}>Excel Format Specifications:</strong>
              <p style={{ margin: '0 0 0.5rem 0', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                Periyar University's official PhD Application Report format is supported. The header row is automatically detected (typically on row 6). Extra metadata/university title rows at the top are automatically skipped and extra columns are ignored. Bulk uploading of 700+ records is supported.
              </p>
              <strong style={{ display: 'block', marginBottom: '0.25rem' }}>Required Excel Columns:</strong>
              <code style={{ display: 'block', background: '#f8fafc', padding: '0.5rem', borderRadius: '4px', wordBreak: 'break-all', marginBottom: '0.5rem' }}>
                Application ID | Applicant Name | Date of Birth | Department
              </code>
              <strong style={{ display: 'block', marginBottom: '0.25rem' }}>Optional Excel Columns:</strong>
              <code style={{ display: 'block', background: '#f8fafc', padding: '0.5rem', borderRadius: '4px', wordBreak: 'break-all', marginBottom: '0.75rem' }}>
                Initial | Category (FT/PT) | Mobile | Email | Programme Offered | Subject
              </code>
              <strong style={{ display: 'block', marginTop: '0.75rem', marginBottom: '0.25rem' }}>Photo Filename Mapping Rule:</strong>
              <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                Application ID <strong>CETPHD/J26/0128</strong> maps to image file <strong>CETPHD-J26-0128.JPG</strong> or <strong>CET-PHD-J26-0128.JPG</strong> (replacing '/' with '-').
              </p>
            </div>
          </div>
        </div>

        {/* Section D: Manual Candidate Add Form */}
        <div className="card mb-4" style={{ borderTop: '4px solid var(--primary-color)' }}>
          <h3 className="card-title">Add Candidate Manually</h3>
          {manualSuccess && <div className="alert alert-success">{manualSuccess}</div>}

          <form onSubmit={handleManualAddSubmit}>
            <div className="grid grid-3" style={{ gap: '1.5rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="manual-app-id">Application ID *</label>
                <input
                  id="manual-app-id"
                  type="text"
                  className="form-input"
                  placeholder="e.g. CETPHD/J26/0128"
                  value={manualAppId}
                  onChange={(e) => setManualAppId(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="manual-name">Applicant Name *</label>
                <input
                  id="manual-name"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Gowtham"
                  value={manualApplicantName}
                  onChange={(e) => setManualApplicantName(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="manual-initial">Initial</label>
                <input
                  id="manual-initial"
                  type="text"
                  className="form-input"
                  placeholder="e.g. G"
                  value={manualInitial}
                  onChange={(e) => setManualInitial(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="manual-dob">Date of Birth * (DD-MM-YYYY)</label>
                <input
                  id="manual-dob"
                  type="text"
                  className="form-input"
                  placeholder="DD-MM-YYYY"
                  value={manualDob}
                  onChange={(e) => setManualDob(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="manual-category">Category (FT/PT)</label>
                <input
                  id="manual-category"
                  type="text"
                  className="form-input"
                  placeholder="e.g. FT or PT"
                  value={manualCategory}
                  onChange={(e) => setManualCategory(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="manual-dept">Department *</label>
                <input
                  id="manual-dept"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Computer Science"
                  value={manualDept}
                  onChange={(e) => setManualDept(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="manual-subject">Subject</label>
                <input
                  id="manual-subject"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Computer Science"
                  value={manualSubject}
                  onChange={(e) => setManualSubject(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="manual-prog">Programme Offered</label>
                <input
                  id="manual-prog"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Ph.D. Computer Science"
                  value={manualProg}
                  onChange={(e) => setManualProg(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="manual-mobile">Mobile Number</label>
                <input
                  id="manual-mobile"
                  type="text"
                  className="form-input"
                  placeholder="9876543210"
                  value={manualMobile}
                  onChange={(e) => setManualMobile(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="manual-email">Mail ID</label>
                <input
                  id="manual-email"
                  type="email"
                  className="form-input"
                  placeholder="candidate@example.com"
                  value={manualEmail}
                  onChange={(e) => setManualEmail(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="manual-session">Exam Session (Optional)</label>
                <select
                  id="manual-session"
                  className="form-input"
                  value={manualSessionId}
                  onChange={(e) => setManualSessionId(e.target.value)}
                >
                  <option value="">No Session Assigned</option>
                  {sessions.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.session_name} ({s.exam_date})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
              <button type="submit" className="btn btn-primary" style={{ padding: '0.6rem 2.5rem' }} disabled={manualLoading}>
                {manualLoading ? 'Saving Candidate...' : 'Add Candidate'}
              </button>
            </div>
          </form>
        </div>

        {/* Section C: Excel Upload Summary Card */}
        {excelSummary && (
          <div className="card mb-4" style={{ borderTop: '4px solid var(--success-color)' }}>
            <h3 className="card-title">Excel Process Summary Result</h3>
            <div className="grid grid-4 mb-4">
              <div className="stat-card card" style={{ padding: '1rem' }}>
                <p style={{ fontSize: '0.8rem', margin: 0 }}>Total Rows</p>
                <h3 style={{ margin: '0.25rem 0 0' }}>{excelSummary.total_rows}</h3>
              </div>
              <div className="stat-card card" style={{ padding: '1rem', borderLeft: '3px solid var(--success-color)' }}>
                <p style={{ fontSize: '0.8rem', margin: 0 }}>Successful Imports</p>
                <h3 style={{ margin: '0.25rem 0 0', color: 'var(--success-color)' }}>{excelSummary.success_count}</h3>
              </div>
              <div className="stat-card card" style={{ padding: '1rem', borderLeft: '3px solid var(--danger-color)' }}>
                <p style={{ fontSize: '0.8rem', margin: 0 }}>Failed / Skipped Rows</p>
                <h3 style={{ margin: '0.25rem 0 0', color: 'var(--danger-color)' }}>{excelSummary.failed_count}</h3>
              </div>
              <div className="stat-card card" style={{ padding: '1rem' }}>
                <p style={{ fontSize: '0.8rem', margin: 0 }}>Photo Mapped</p>
                <h3 style={{ margin: '0.25rem 0 0', color: 'var(--primary-color)' }}>{excelSummary.photo_available_count}</h3>
              </div>
            </div>

            <div className="grid grid-3 mb-4" style={{ gap: '1rem' }}>
              <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px' }}>
                <span style={{ fontSize: '0.85rem', color: '#64748b' }}>Excel Duplicates:</span>
                <span style={{ fontWeight: 'bold', marginLeft: '0.5rem' }}>{excelSummary.duplicate_in_excel_count}</span>
              </div>
              <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px' }}>
                <span style={{ fontSize: '0.85rem', color: '#64748b' }}>Database Duplicates:</span>
                <span style={{ fontWeight: 'bold', marginLeft: '0.5rem' }}>{excelSummary.duplicate_in_database_count}</span>
              </div>
              <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px' }}>
                <span style={{ fontSize: '0.85rem', color: '#64748b' }}>Photo Missing:</span>
                <span style={{ fontWeight: 'bold', marginLeft: '0.5rem', color: 'var(--danger-color)' }}>{excelSummary.photo_missing_count}</span>
              </div>
            </div>

            {/* Section D: Error Rows Preview */}
            {excelSummary.errors && excelSummary.errors.length > 0 && (
              <div style={{ marginTop: '1.5rem' }}>
                <h4 style={{ color: 'var(--danger-color)', marginBottom: '0.75rem' }}>Failed Rows Description ({excelSummary.errors.length})</h4>
                <div className="table-container" style={{ margin: 0 }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th style={{ width: '80px' }}>Row No</th>
                        <th>Application ID</th>
                        <th>Error Explanation</th>
                      </tr>
                    </thead>
                    <tbody>
                      {excelSummary.errors.map((err, i) => (
                        <tr key={i}>
                          <td>{err.row}</td>
                          <td><strong>{err.application_id || 'N/A'}</strong></td>
                          <td style={{ color: 'var(--danger-color)', fontSize: '0.85rem' }}>{err.error}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Section E: Photo Upload Summary */}
        {photoSummary && (
          <div className="card" style={{ borderTop: '4px solid var(--primary-color)' }}>
            <h3 className="card-title">Photo File Upload Summary</h3>
            <div className="grid grid-3">
              <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: '6px', textAlign: 'center' }}>
                <p style={{ fontSize: '0.8rem', color: '#64748b', margin: 0 }}>Uploaded Images</p>
                <h3 style={{ margin: '0.5rem 0 0' }}>{photoSummary.uploaded_count}</h3>
              </div>
              <div style={{ background: '#f0fdf4', padding: '1rem', borderRadius: '6px', textAlign: 'center', borderLeft: '3px solid var(--success-color)' }}>
                <p style={{ fontSize: '0.8rem', color: 'var(--success-color)', margin: 0 }}>Mapped to Candidates</p>
                <h3 style={{ margin: '0.5rem 0 0', color: 'var(--success-color)' }}>{photoSummary.mapped_count}</h3>
              </div>
              <div style={{ background: '#fef2f2', padding: '1rem', borderRadius: '6px', textAlign: 'center', borderLeft: '3px solid var(--danger-color)' }}>
                <p style={{ fontSize: '0.8rem', color: 'var(--danger-color)', margin: 0 }}>Unmapped (No Candidate Found)</p>
                <h3 style={{ margin: '0.5rem 0 0', color: 'var(--danger-color)' }}>{photoSummary.unmapped_count}</h3>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
