import { apiFetch } from './client';

export const getComments = (taskId, options = {}) => {
  const { skip = 0, limit = 50 } = options;
  return apiFetch(`/tasks/${taskId}/comments?skip=${skip}&limit=${limit}`);
};

export const createComment = (taskId, payload) => {
  return apiFetch(`/tasks/${taskId}/comments`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
};
