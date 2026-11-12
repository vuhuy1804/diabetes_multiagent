export class ApiError extends Error {
  constructor(message, { status = 0, data = null, kind = 'api' } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
    this.kind = kind;
  }
}

export function apiUrl(path, baseUrl = '') {
  if (typeof path !== 'string' || !/^\/api\/[a-z0-9/-]+$/.test(path)) {
    throw new TypeError('Unsupported API path');
  }
  const normalizedBase = (baseUrl || '').replace(/\/+$/, '');
  return normalizedBase + path;
}

export async function requestJson(path, { payload, timeoutMs = 90000, baseUrl, fetchImpl = fetch } = {}) {
  // Vite's proxy handles same-origin /api calls while developing.
  const configBase = baseUrl ?? import.meta.env?.VITE_API_BASE_URL ?? '';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(apiUrl(path, configBase), {
      method: payload === undefined ? 'GET' : 'POST',
      headers: {
        Accept: 'application/json',
        ...(payload !== undefined ? { 'Content-Type': 'application/json; charset=utf-8' } : {}),
      },
      ...(payload !== undefined ? { body: JSON.stringify(payload) } : {}),
      signal: controller.signal,
      cache: 'no-store',
    });
    const raw = await response.text();
    let data;
    try {
      data = JSON.parse(raw);
    } catch {
      throw new ApiError('API không trả JSON hợp lệ. Kiểm tra Flask hoặc cấu hình proxy.', {
        status: response.status, kind: 'invalid_json',
      });
    }
    if (!response.ok || data?.status === 'error') {
      throw new ApiError(
        response.status === 503
          ? 'Một thành phần Backend chưa sẵn sàng (model hoặc Neo4j).'
          : response.status === 400
            ? 'Dữ liệu đầu vào không hợp lệ. Vui lòng kiểm tra lại các trường.'
            : `Yêu cầu thất bại (HTTP ${response.status}).`,
        { status: response.status, data, kind: 'http' },
      );
    }
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error?.name === 'AbortError') {
      throw new ApiError('Yêu cầu quá thời gian 90 giây. Kiểm tra mô hình và Neo4j.', { kind: 'timeout' });
    }
    throw new ApiError('Không kết nối được API. Kiểm tra Flask ở cổng 5000 và Vite proxy.', { kind: 'network' });
  } finally {
    clearTimeout(timer);
  }
}

export const fetchHealth = (options) => requestJson('/api/health', { timeoutMs: 10000, ...options });
export const fetchAgents = (options) => requestJson('/api/agents/status', { timeoutMs: 10000, ...options });
export const generateReport = (payload, options) => requestJson('/api/report/generate', { payload, ...options });

export const queryKnowledge = (question, options) => requestJson('/api/knowledge/query', { payload: {question}, ...options });
