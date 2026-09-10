// @vitest-environment happy-dom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { SpecBadges } from './SpecBadges'

/** §3.8's acceptance, rendered and counted. */
afterEach(cleanup)

describe('SpecBadges', () => {
  it('shows three distinct badges for a 4K Dolby Vision Atmos disc', () => {
    // **§3.8's acceptance criterion, stated exactly.**
    const { container } = render(
      <SpecBadges
        videoSpecs={{ resolution: '2160p', hdr: ['Dolby Vision'] }}
        audioSpecs={[{ format: 'Dolby Atmos', language: 'English' }]}
        regionCode={null}
      />,
    )

    expect(screen.getByText('4K')).toBeTruthy()
    expect(screen.getByText('DV')).toBeTruthy()
    expect(screen.getByText('Atmos')).toBeTruthy()
    // Distinct, not merely three: each badge carries a different colour class.
    const classes = Array.from(container.querySelectorAll('span[title]')).map(
      (node) => node.className,
    )
    expect(new Set(classes).size).toBe(3)
  })

  it('shows both HDR formats when a disc carries two', () => {
    render(
      <SpecBadges
        videoSpecs={{ resolution: '2160p', hdr: ['Dolby Vision', 'HDR10+'] }}
        audioSpecs={null}
      />,
    )

    expect(screen.getByText('DV')).toBeTruthy()
    expect(screen.getByText('HDR10+')).toBeTruthy()
  })

  it('shows the best audio track rather than all of them', () => {
    // A disc lists Atmos, TrueHD and Dolby Digital; three audio badges would be noise.
    render(
      <SpecBadges
        videoSpecs={null}
        audioSpecs={[
          { format: 'Dolby Digital' },
          { format: 'Dolby Atmos' },
          { format: 'Dolby TrueHD' },
        ]}
      />,
    )

    expect(screen.getByText('Atmos')).toBeTruthy()
    expect(screen.queryByText('Dolby Digital')).toBeNull()
  })

  it('renders nothing at all when the specs are unknown', () => {
    // **Not a grey "unknown" pill.** Until Blu-ray.com has been asked the app does not
    // know, and a placeholder that looks like data is how a catalogue starts lying.
    const { container } = render(<SpecBadges videoSpecs={null} audioSpecs={null} />)

    expect(container.firstChild).toBeNull()
  })

  it('names the abbreviations for anybody who does not know them', () => {
    render(<SpecBadges videoSpecs={{ resolution: '2160p', hdr: ['Dolby Vision'] }} audioSpecs={null} />)

    expect(screen.getByTitle('High dynamic range: Dolby Vision')).toBeTruthy()
    expect(screen.getByTitle('Resolution: 2160p')).toBeTruthy()
  })

  it('labels a region-free disc in words', () => {
    render(<SpecBadges videoSpecs={null} audioSpecs={null} regionCode="Free" />)

    expect(screen.getByText('Region free')).toBeTruthy()
  })
})
