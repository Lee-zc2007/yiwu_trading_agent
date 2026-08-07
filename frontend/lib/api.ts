const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export class ApiError extends Error { constructor(message: string, public status = 500) { super(message) } }

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', 'X-Merchant-ID': '1', ...(init?.headers || {}) },
    cache: 'no-store',
  })
  const payload = await response.json().catch(() => ({ message: '服务器返回了无效响应' }))
  if (!response.ok || payload.success === false) throw new ApiError(payload.message || '请求失败', response.status)
  return payload.data as T
}

export async function upload<T>(path: string, file: File): Promise<T> {
  const body = new FormData(); body.append('file', file)
  const response = await fetch(`${API_BASE}${path}`, { method: 'POST', headers: { 'X-Merchant-ID': '1' }, body })
  const payload = await response.json()
  if (!response.ok || payload.success === false) throw new ApiError(payload.message || '上传失败', response.status)
  return payload.data as T
}
