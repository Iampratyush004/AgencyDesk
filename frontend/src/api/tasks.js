import { apiFetch } from './client';

export const getProjectTasks = (projectId) => {
  return apiFetch(`/projects/${projectId}/tasks`);
};

export const createTask = (projectId, payload) => {
  return apiFetch(`/projects/${projectId}/tasks`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
};

export const updateTask = (taskId, payload) => {
  return apiFetch(`/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  });
};
