import { describe, expect, it } from 'vitest'

import { href, parse, type Route } from './route'

describe('routes', () => {
  const cases: [string, Route][] = [
    ['#/new', { page: 'new' }],
    ['#/tracker', { page: 'tracker' }],
    ['#/profile', { page: 'profile' }],
    ['#/applications/42', { page: 'application', id: 42, versionId: null }],
    ['#/applications/42/versions/7', { page: 'application', id: 42, versionId: 7 }],
  ]

  it.each(cases)('%s round-trips', (hash, route) => {
    expect(parse(hash)).toEqual(route)
    expect(href(route)).toBe(hash)
  })

  it('treats old and unknown URLs as a new job', () => {
    for (const hash of ['', '#', '#/', '#/applications/abc', '#/applications/', '#/nope']) {
      expect(parse(hash)).toEqual({ page: 'new' })
    }
  })

  it('ignores a trailing slash', () => {
    expect(parse('#/applications/3/')).toEqual({ page: 'application', id: 3, versionId: null })
  })
})
