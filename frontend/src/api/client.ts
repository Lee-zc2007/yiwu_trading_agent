import axios from 'axios'
import { fallbackMap } from '../data/fallback'

export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

export const client = axios.create({ baseURL: API_BASE, timeout: 7000 })

export async function safeGet<T>(path: string, fallback?: T): Promise<{ data: T; live: boolean }> {
  try {
    const response = await client.get<T>(path)
    return { data: response.data, live: true }
  } catch {
    return { data: (fallback ?? fallbackMap[path]) as T, live: false }
  }
}

export async function safePost<T>(path: string, payload: unknown, fallback: T): Promise<{ data: T; live: boolean }> {
  try {
    const response = await client.post<T>(path, payload)
    return { data: response.data, live: true }
  } catch {
    return { data: fallback, live: false }
  }
}

