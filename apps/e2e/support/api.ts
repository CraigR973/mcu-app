import { API_ORIGIN, PINS, type Person } from '../harness/env.ts'

export interface Tokens {
  accessToken: string
  refreshToken: string
}

export async function login(person: Person, pin: string = PINS[person]): Promise<Tokens> {
  const response = await fetch(`${API_ORIGIN}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ displayName: person, pin }),
  })
  if (!response.ok) throw new Error(`login as ${person} answered ${response.status}`)
  return (await response.json()) as Tokens
}

export class Api {
  constructor(private readonly token: string) {}

  static async as(person: Person): Promise<Api> {
    return new Api((await login(person)).accessToken)
  }

  async call<T = unknown>(method: string, path: string, body?: unknown, expect: number[] = [200, 201, 204]): Promise<T> {
    const response = await fetch(`${API_ORIGIN}/api/v1${path}`, {
      method,
      headers: {
        authorization: `Bearer ${this.token}`,
        ...(body === undefined ? {} : { 'content-type': 'application/json' }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    const text = await response.text()
    if (!expect.includes(response.status)) {
      throw new Error(`${method} ${path} answered ${response.status}: ${text.slice(0, 400)}`)
    }
    return (text ? JSON.parse(text) : undefined) as T
  }

  get<T = unknown>(path: string): Promise<T> {
    return this.call<T>('GET', path)
  }
  post<T = unknown>(path: string, body?: unknown, expect?: number[]): Promise<T> {
    return this.call<T>('POST', path, body, expect)
  }
  put<T = unknown>(path: string, body?: unknown): Promise<T> {
    return this.call<T>('PUT', path, body)
  }
  patch<T = unknown>(path: string, body?: unknown): Promise<T> {
    return this.call<T>('PATCH', path, body)
  }
  delete<T = unknown>(path: string): Promise<T> {
    return this.call<T>('DELETE', path)
  }
}
