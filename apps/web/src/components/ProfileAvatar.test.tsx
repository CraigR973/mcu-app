// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ fetchProfilePhoto: vi.fn(), uploadProfilePhoto: vi.fn(), removeProfilePhoto: vi.fn() }))
vi.mock('@/lib/api', () => api)
import { ProfileAvatar } from './ProfileAvatar'
import { ProfilePhotoEditor } from './ProfilePhotoEditor'

beforeEach(() => {
  vi.resetAllMocks()
  api.fetchProfilePhoto.mockResolvedValue(null)
  api.uploadProfilePhoto.mockResolvedValue(undefined)
  api.removeProfilePhoto.mockResolvedValue(undefined)
  // Preserve URL's constructor: happy-dom uses it to validate an img's source.
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:private')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

function show(editor = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const rendered = render(<QueryClientProvider client={client}><ProfileAvatar profileId="mark" name="Mark" />{editor ? <ProfilePhotoEditor profileId="mark" /> : null}</QueryClientProvider>)
  return { client, ...rendered }
}

describe('private profile picture', () => {
  it('keeps the initial for no photo and a failed read', async () => {
    api.fetchProfilePhoto.mockRejectedValue(new Error('offline'))
    show()
    await waitFor(() => expect(api.fetchProfilePhoto).toHaveBeenCalledWith('mark'))
    expect(screen.getByText('M')).toBeTruthy()
  })
  it('shows private bytes, falls back on decode failure, and releases its object URL', async () => {
    api.fetchProfilePhoto.mockResolvedValue(new Blob(['jpeg'], { type: 'image/jpeg' }))
    const view = show()
    await waitFor(() => expect(view.client.getQueryState(['profile-photo', 'mark'])?.status).toBe('success'))
    await waitFor(() => expect(view.container.querySelector('img')?.src).toBe('blob:private'))
    fireEvent.error(view.container.querySelector('img')!)
    expect(screen.getByText('M')).toBeTruthy()
    view.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private')
  })
  it('uploads, re-reads all avatars, and allows returning to the initial', async () => {
    const view = show(true)
    const file = new File(['photo'], 'me.jpg', { type: 'image/jpeg' })
    fireEvent.change(screen.getByLabelText('Choose profile picture'), { target: { files: [file] } })
    await screen.findByText('Profile picture saved.')
    expect(api.uploadProfilePhoto).toHaveBeenCalledWith(file)
    expect(api.fetchProfilePhoto.mock.calls.length).toBeGreaterThan(1)
    fireEvent.click(screen.getByRole('button', { name: 'Use my initial' }))
    await waitFor(() => expect(api.removeProfilePhoto).toHaveBeenCalledOnce())
    expect(view.container.querySelector('img')).toBeNull()
  })
  it('reports a refused upload without hiding the existing photo', async () => {
    api.fetchProfilePhoto.mockResolvedValue(new Blob(['old']))
    api.uploadProfilePhoto.mockRejectedValue(new Error('That file was empty.'))
    const view = show(true)
    await waitFor(() => expect(view.container.querySelector('img')).not.toBeNull())
    fireEvent.change(screen.getByLabelText('Choose profile picture'), { target: { files: [new File([], 'empty.jpg')] } })
    await screen.findByRole('alert')
    expect(view.container.querySelector('img')?.src).toBe('blob:private')
  })
})
