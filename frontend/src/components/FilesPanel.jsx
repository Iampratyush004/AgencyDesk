import React, { useState, useEffect } from 'react';
import { getTaskFiles, uploadTaskFile, downloadFile, approveFile } from '../api/files';

export default function FilesPanel({ task, userContext }) {
  const [files, setFiles] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Upload State
  const [selectedFile, setSelectedFile] = useState(null);
  const [visibility, setVisibility] = useState('internal');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  // Approval State
  const [reviewingFileId, setReviewingFileId] = useState(null);
  const [approvalStatus, setApprovalStatus] = useState('approved');
  const [approvalNote, setApprovalNote] = useState('');
  const [isApproving, setIsApproving] = useState(false);
  const [approvalError, setApprovalError] = useState(null);
  const [approvalSuccessMsg, setApprovalSuccessMsg] = useState('');

  const isAgencyStaff = userContext?.role === 'agency_admin' || userContext?.role === 'agency_member';
  const isClient = userContext?.role === 'client_user';

  const fetchFiles = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getTaskFiles(task.id);
      setFiles(data);
    } catch (err) {
      setError('Unable to load files.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (task && task.id) {
      fetchFiles();
      // Reset states
      setSelectedFile(null);
      setVisibility('internal');
      setUploadError(null);
      setReviewingFileId(null);
      setApprovalError(null);
    }
  }, [task?.id]);

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(false);

    try {
      await uploadTaskFile(task.id, selectedFile, visibility);
      setUploadSuccess(true);
      setSelectedFile(null);
      setVisibility('internal');
      fetchFiles();

      // Clear file input manually
      const fileInput = document.getElementById('file-upload');
      if (fileInput) fileInput.value = '';

      setTimeout(() => setUploadSuccess(false), 3000);
    } catch (err) {
      if (err.data && err.data.detail) {
        if (Array.isArray(err.data.detail)) {
          const messages = err.data.detail.map(d => `${d.loc.join('.')}: ${d.msg}`);
          setUploadError(messages.join(', '));
        } else if (typeof err.data.detail === 'object') {
          if (err.data.detail.error) {
            setUploadError(`${err.data.detail.error}${err.data.detail.blockers ? ` (${err.data.detail.blockers.join(', ')})` : ''}`);
          } else {
            setUploadError(JSON.stringify(err.data.detail));
          }
        } else {
          setUploadError(String(err.data.detail));
        }
      } else {
        setUploadError('An unexpected error occurred while uploading.');
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleDownload = async (file) => {
    try {
      const blob = await downloadFile(file.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to download file", err);
      alert('Unable to download file.');
    }
  };

  const handleApprovalSubmit = async (e, fileId) => {
    e.preventDefault();
    setIsApproving(true);
    setApprovalError(null);
    setApprovalSuccessMsg('');

    try {
      const payload = {
        status: approvalStatus,
        note: approvalNote.trim() || null
      };
      await approveFile(fileId, payload);
      setApprovalSuccessMsg('Review submitted successfully.');
      setReviewingFileId(null);
      setApprovalNote('');
      setApprovalStatus('approved');
      fetchFiles();

      setTimeout(() => setApprovalSuccessMsg(''), 3000);
    } catch (err) {
      if (err.data && err.data.detail) {
        setApprovalError(typeof err.data.detail === 'string' ? err.data.detail : JSON.stringify(err.data.detail));
      } else {
        setApprovalError('Failed to submit review.');
      }
    } finally {
      setIsApproving(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === null || bytes === undefined) return 'Unknown size';
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  return (
    <div className="files-panel" style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '1.5rem' }}>
      <h3 style={{ marginBottom: '1rem', fontSize: '1.125rem' }}>Files</h3>

      {/* Upload Form - Agency Staff Only */}
      {isAgencyStaff && (
        <form onSubmit={handleUploadSubmit} className="file-upload-form" style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: 'var(--bg-color)', borderRadius: '6px', border: '1px solid var(--border)' }}>
          <h4 style={{ marginBottom: '0.75rem', fontSize: '0.875rem', color: 'var(--text-main)' }}>Upload File</h4>

          {uploadError && (
            <div className="error-alert" style={{ marginBottom: '1rem', padding: '0.5rem', fontSize: '0.875rem' }}>
              {uploadError}
            </div>
          )}
          {uploadSuccess && (
            <div className="success-alert" style={{ marginBottom: '1rem', padding: '0.5rem', backgroundColor: '#e6fffa', color: '#234e52', border: '1px solid #b2f5ea', borderRadius: '4px', fontSize: '0.875rem' }}>
              File uploaded successfully.
            </div>
          )}

          <div className="form-group" style={{ marginBottom: '1rem' }}>
            <input
              id="file-upload"
              type="file"
              onChange={(e) => setSelectedFile(e.target.files[0])}
              disabled={isUploading}
              style={{ width: '100%', fontSize: '0.875rem' }}
            />
          </div>

          <div className="form-group" style={{ marginBottom: '1rem' }}>
            <label htmlFor="visibility" style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem' }}>Visibility</label>
            <select
              id="visibility"
              value={visibility}
              onChange={(e) => setVisibility(e.target.value)}
              disabled={isUploading}
              style={{ width: '100%', padding: '0.5rem', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '0.875rem' }}
            >
              <option value="internal">Internal — agency staff only</option>
              <option value="client">Client visible — visible in the client portal</option>
            </select>
          </div>

          <button type="submit" className="btn btn-primary btn-small" disabled={isUploading || !selectedFile}>
            {isUploading ? 'Uploading...' : 'Upload'}
          </button>
        </form>
      )}

      {/* Global Approval Success Message */}
      {approvalSuccessMsg && (
        <div className="success-alert" style={{ marginBottom: '1rem', padding: '0.5rem', backgroundColor: '#e6fffa', color: '#234e52', border: '1px solid #b2f5ea', borderRadius: '4px', fontSize: '0.875rem' }}>
          {approvalSuccessMsg}
        </div>
      )}

      {/* Files List */}
      {isLoading ? (
        <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Loading files...</div>
      ) : error ? (
        <div className="error-alert" style={{ padding: '0.5rem', fontSize: '0.875rem' }}>{error}</div>
      ) : files.length === 0 ? (
        <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>No files attached.</div>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {files.map(file => (
            <li key={file.id} style={{ padding: '0.75rem', borderBottom: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontWeight: '500', fontSize: '0.875rem', wordBreak: 'break-all' }}>{file.filename}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
                    <span>{formatFileSize(file.file_size_bytes)}</span>
                    <span>•</span>
                    <span>{new Date(file.created_at).toLocaleString()}</span>
                    {isAgencyStaff && (
                      <>
                        <span>•</span>
                        <span className={`visibility-badge visibility-${file.visibility}`} style={{ padding: '0 4px', fontSize: '0.7rem' }}>
                          {file.visibility === 'client' ? 'Client' : 'Internal'}
                        </span>
                      </>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    onClick={() => handleDownload(file)}
                    className="btn btn-secondary btn-small"
                    style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                  >
                    Download
                  </button>
                  {isClient && file.visibility === 'client' && reviewingFileId !== file.id && (
                    <button
                      onClick={() => setReviewingFileId(file.id)}
                      className="btn btn-primary btn-small"
                      style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                    >
                      Review
                    </button>
                  )}
                </div>
              </div>

              {/* Approval Status Display */}
              {file.visibility === 'client' && isAgencyStaff && (
                <div style={{ marginTop: '0.5rem', padding: '0.5rem', backgroundColor: 'var(--bg-color)', borderRadius: '4px', border: '1px solid var(--border)', fontSize: '0.75rem' }}>
                  {file.approvals && file.approvals.length > 0 ? (
                    file.approvals.map(appr => (
                      <div key={appr.id} style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', marginTop: appr !== file.approvals[0] ? '0.5rem' : 0 }}>
                        <div>
                          <span style={{ fontWeight: '600', color: appr.status === 'approved' ? 'var(--text-main)' : 'var(--error-color)' }}>
                            {appr.status === 'approved' ? 'Approved' : 'Needs Changes'}
                          </span>
                        </div>
                        {appr.note && (
                          <div style={{ color: 'var(--text-muted)' }}>Note: {appr.note}</div>
                        )}
                      </div>
                    ))
                  ) : (
                    <div style={{ color: 'var(--text-muted)' }}>Awaiting client review</div>
                  )}
                </div>
              )}

              {/* Client Review Form Inline */}
              {isClient && reviewingFileId === file.id && (
                <form
                  onSubmit={(e) => handleApprovalSubmit(e, file.id)}
                  style={{ marginTop: '0.5rem', padding: '0.75rem', backgroundColor: 'var(--bg-color)', borderRadius: '4px', border: '1px solid var(--border)' }}
                >
                  <h5 style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem' }}>Review File</h5>

                  {approvalError && (
                    <div className="error-alert" style={{ marginBottom: '0.5rem', padding: '0.5rem', fontSize: '0.75rem' }}>
                      {approvalError}
                    </div>
                  )}

                  <div className="form-group" style={{ marginBottom: '0.5rem' }}>
                    <select
                      value={approvalStatus}
                      onChange={(e) => setApprovalStatus(e.target.value)}
                      disabled={isApproving}
                      style={{ width: '100%', padding: '0.25rem', fontSize: '0.875rem', border: '1px solid var(--border)', borderRadius: '4px' }}
                    >
                      <option value="approved">Approve</option>
                      <option value="needs_changes">Needs Changes</option>
                    </select>
                  </div>

                  <div className="form-group" style={{ marginBottom: '0.5rem' }}>
                    <input
                      type="text"
                      placeholder="Note (optional)"
                      value={approvalNote}
                      onChange={(e) => setApprovalNote(e.target.value)}
                      disabled={isApproving}
                      style={{ width: '100%', padding: '0.25rem', fontSize: '0.875rem', border: '1px solid var(--border)', borderRadius: '4px' }}
                    />
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button type="submit" className="btn btn-primary btn-small" disabled={isApproving} style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}>
                      {isApproving ? 'Submitting...' : 'Submit'}
                    </button>
                    <button type="button" onClick={() => setReviewingFileId(null)} className="btn btn-secondary btn-small" disabled={isApproving} style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}>
                      Cancel
                    </button>
                  </div>
                </form>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
