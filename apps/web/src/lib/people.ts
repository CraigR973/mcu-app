/** AE9 (#355): where a person's name or face leads: their page, or You for the reader. */
export function personPath(profileId: string, readerId: string | null | undefined): string {
  return profileId === readerId ? '/you' : `/people/${profileId}`
}
