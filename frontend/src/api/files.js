import { apiFetch, apiDownload } from './client';

export const getTaskFiles = (taskId) => {
  return apiFetch(`/tasks/${taskId}/files`);
};

export const uploadTaskFile = (taskId, file, visibility) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('visibility', visibility);

  return apiFetch(`/tasks/${taskId}/files`, {
    method: 'POST',
    body: formData
  });
};

export const downloadFile = (fileId) => {
  return apiDownload(`/files/${fileId}/download`);
};

export const approveFile = (fileId, payload) => {
  return apiFetch(`/files/${fileId}/approvals`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
};
