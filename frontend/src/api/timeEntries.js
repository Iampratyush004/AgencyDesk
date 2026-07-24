import { apiFetch } from './client';

export const createTimeEntry = (taskId, payload) => {
  return apiFetch(`/tasks/${taskId}/time-entries`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
};
