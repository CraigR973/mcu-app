import { describe, expect, it } from 'vitest'

import type { BidTrial, TrialFilm, TrialSummary } from '@/lib/api'

import { plural, summaryLines, trialStatus, wholePounds } from './bid-trial'

const SUMMARY: TrialSummary = {
  formatCode: 'blu_ray',
  films: 33,
  withBids: 5,
  withBidsEndingSoon: 1,
  auctionsCounted: 18,
  endingSoon: 6,
  compared: 5,
  bidToAskingPercent: 72,
  cut: 12,
  auctionOnlyPlaces: 85,
  askingSample: 512,
  storedSample: 604,
  askingLost: 2,
  stored: { total: '412.40', discs: 35 },
  asking: { total: '398.00', discs: 34 },
  bids: { total: '61.00', discs: 6 },
  blend: { total: '380.50', discs: 34, fromBids: 6, fromAsking: 28 },
}

const TRIAL: BidTrial = {
  id: '3f2504e0-4f89-41d3-9a0c-0305e82c3410',
  status: 'finished',
  startedAt: '2026-10-01T09:00:00Z',
  finishedAt: '2026-10-01T09:02:10Z',
  budget: 750,
  calls: 101,
  failed: 0,
  lastError: null,
  sampleSize: 100,
  minSample: 3,
  endingWindowHours: 24,
  dailyShare: 750,
  currency: 'GBP',
  report: null,
}

const SUMMARY_REPORT = { sampled: 100, films: [], formats: [SUMMARY], overall: { ...SUMMARY, formatCode: null } }

describe('the bid trial in words — Batch V6', () => {
  it('counts in words, and totals to the pound', () => {
    expect(plural(1, 'film')).toBe('1 film')
    expect(plural(1234, 'film')).toBe('1,234 films')
    expect(plural(2, 'search', 'searches')).toBe('2 searches')
    expect(wholePounds('412.40', 'GBP')).toBe('£412')
  })

  it('answers each question the trial was asked, by format', () => {
    expect(summaryLines(SUMMARY, 3, 24)).toEqual([
      { label: 'Bid prices', text: '5 of 33 films had 3 or more auctions with bids.' },
      { label: 'Bids against asking', text: 'Bids were 72% of the asking price (the median of 5 films).' },
      {
        label: 'Ending within 24 hours',
        text: '6 of their 18 auctions. Counting only those, 1 film would keep a bid price.',
      },
      {
        label: 'Sharing the 200 results',
        text: '12 searches had more than 200 results; auctions with no Buy It Now took 85 places in them.',
      },
      {
        label: 'Buy It Now listings',
        text: '512 matched today, 604 when the stored prices were taken. 2 films fell under 3 and could not be priced on asking.',
      },
    ])
  })

  it('says plainly when bids priced nothing and no search was full', () => {
    const quiet = { ...SUMMARY, withBids: 0, compared: 0, bidToAskingPercent: null, auctionsCounted: 0, cut: 0, askingLost: 0 }
    const lines = summaryLines(quiet, 3, 24)

    expect(lines.map((line) => line.label)).toEqual([
      'Bid prices',
      'Bids against asking',
      'Sharing the 200 results',
      'Buy It Now listings',
    ])
    expect(lines[1]?.text).toBe('No film had both a bid price and an asking price.')
    expect(lines[2]?.text).toBe('No search had more than 200 results, so auctions cost no Buy It Now listings.')
    expect(lines[3]?.text).toBe('512 matched today, 604 when the stored prices were taken.')
  })

  it('says where the trial got to', () => {
    const film: TrialFilm = {
      movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3401',
      title: 'Heat',
      formatCode: 'blu_ray',
      copies: 1,
      stored: { price: '9.99', sampleSize: 12 },
      results: { total: 40, returned: 40, buyItNow: 38, auctionOnly: 2 },
      asking: { price: '9.50', sampleSize: 11 },
      bids: { counted: 2, withoutBids: 0, rejected: 0, price: null, endingSoon: 0 },
      error: null,
    }
    const withFilms = (count: number): BidTrial => ({
      ...TRIAL,
      report: { ...SUMMARY_REPORT, films: Array.from({ length: count }, () => film) },
    })

    expect(trialStatus({ ...withFilms(37), status: 'running' })).toBe('Trying bid prices: 37 of 100 films looked up.')
    expect(trialStatus(withFilms(100))).toBe("Tried 1 Oct 2026: 100 films looked up, 101 eBay lookups of the day's 750.")
    expect(trialStatus({ ...withFilms(60), status: 'budget_spent', calls: 62 })).toBe(
      "Tried 1 Oct 2026: the day's share ran out after 60 of 100 films, 62 eBay lookups of the day's 750.",
    )
    expect(trialStatus({ ...withFilms(1), status: 'stopped', lastError: 'eBay search failed (HTTP 429)' })).toBe(
      'Tried 1 Oct 2026: it stopped early after 1 of 100 films (eBay search failed (HTTP 429)).',
    )
  })
})
