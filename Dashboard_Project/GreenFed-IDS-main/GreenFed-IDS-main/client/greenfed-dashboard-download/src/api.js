import axios from "axios";

export const api = axios.create({ timeout: 15000 });

export async function get(path, config) {
  const response = await api.get(path, config);
  return response.data?.data ?? response.data;
}

export async function post(path, body, config) {
  const response = await api.post(path, body, config);
  return response.data?.data ?? response.data;
}

export function formatPercent(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "N/A";
  }
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

export function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "N/A";
  }
  return Number(value).toFixed(digits);
}

export function formatBytesMb(bytes) {
  if (bytes === null || bytes === undefined) return "N/A";
  return `${(Number(bytes) / (1024 * 1024)).toFixed(3)} MB`;
}
