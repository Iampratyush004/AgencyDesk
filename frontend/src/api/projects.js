import { apiFetch } from './client';

export const getProjects = () => {
  return apiFetch('/projects');
};

export const getProject = (projectId) => {
  return apiFetch(`/projects/${projectId}`);
};

export const getProjectDashboard = (projectId) => {
  return apiFetch(`/projects/${projectId}/dashboard`);
};
