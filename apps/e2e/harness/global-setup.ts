import http from 'node:http'
import { CONTROL_PORT, RUN_DB } from './env.ts'
import { buildTemplate } from './template.ts'
import { ApiProcess, WebProcess, assertPortFree, buildWeb, dbtool, resetWorld, templateName } from './stack.ts'

/**
 * One run: build the bundle for the cross-origin API, seed (or reuse) the template, clone it
 * into this run's database, start the API on it and serve the bundle, and open a small control
 * port so a case can stop and start the API (the offline case needs it gone, not mocked).
 */
export default async function globalSetup(): Promise<() => Promise<void>> {
  buildWeb()

  const template = templateName()
  if (process.env.E2E_RESEED || dbtool('exists', template) !== '0') await buildTemplate(template)
  dbtool('clone', template, RUN_DB)
  resetWorld()

  await assertPortFree(CONTROL_PORT, '127.0.0.1')
  const api = new ApiProcess(RUN_DB)
  const web = new WebProcess()
  await api.start()
  await web.start()

  const control = http.createServer((request, response) => {
    const done = (status: number, text: string) => {
      response.writeHead(status, { 'content-type': 'text/plain' })
      response.end(text)
    }
    const action = request.url ?? ''
    if (request.method !== 'POST') return done(405, 'POST only')
    if (action === '/api/stop') api.stop().then(() => done(200, 'stopped'), (e) => done(500, String(e)))
    else if (action === '/api/start') api.start().then(() => done(200, 'started'), (e) => done(500, String(e)))
    else done(404, 'unknown')
  })
  await new Promise<void>((resolve) => control.listen(CONTROL_PORT, '127.0.0.1', resolve))

  return async () => {
    control.close()
    await web.stop()
    await api.stop()
  }
}
