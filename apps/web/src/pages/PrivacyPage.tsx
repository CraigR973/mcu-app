import { Link } from 'react-router-dom'

/**
 * The privacy policy — Batch T8b (`DECISIONS.md` #227, #245).
 *
 * **Public, because eBay links to it from its sign-in page** (the RuName's privacy policy
 * URL), where the person reading it is not signed in to this app. It says what "Connect
 * eBay" keeps and does, plainly, and nothing it does not do.
 */
export default function PrivacyPage() {
  return (
    <main className="mx-auto w-full max-w-2xl space-y-6 px-4 py-10 text-foreground sm:px-6">
      <header className="space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          The Real MCU
        </p>
        <h1 className="font-display text-3xl font-semibold">Privacy</h1>
        <p className="text-sm text-muted-foreground">
          A private film-collection app for two people. It is not open to sign-up.
        </p>
      </header>

      <section className="space-y-2" aria-labelledby="privacy-ebay">
        <h2 id="privacy-ebay" className="text-lg font-semibold">
          When you connect eBay
        </h2>
        <ul className="list-disc space-y-1.5 pl-5 text-sm leading-6">
          <li>You sign in on eBay&rsquo;s own page. This app never sees or stores your eBay password.</li>
          <li>
            The app keeps the sign-in eBay gives it (two tokens), encrypted, so it can read
            your watch list, your saved searches, what you are selling and what you sold in
            the last 60 days. It reads those lists from eBay when you open them, and does not
            keep them.
          </li>
          <li>Only you see your eBay lists in the app. The other person using it cannot.</li>
          <li>
            The app does not buy, bid, sell, message or change anything on eBay. It does not
            keep or show your buyers&rsquo; or sellers&rsquo; details.
          </li>
          <li>
            Your price alerts, if you set any from your lists, are kept until you remove them.
          </li>
        </ul>
      </section>

      <section className="space-y-2" aria-labelledby="privacy-ending">
        <h2 id="privacy-ending" className="text-lg font-semibold">
          Ending it
        </h2>
        <ul className="list-disc space-y-1.5 pl-5 text-sm leading-6">
          <li>Disconnect in the app&rsquo;s Settings, and the app deletes its copy of your eBay sign-in.</li>
          <li>
            If you remove the app&rsquo;s access in your eBay account, or close the account,
            the app deletes its copy the next time eBay refuses it.
          </li>
          <li>To ask about anything the app holds about you, ask the person who invited you.</li>
        </ul>
      </section>

      <p className="text-sm">
        <Link to="/" className="font-medium text-primary underline-offset-2 hover:underline">
          Back to the app
        </Link>
      </p>
    </main>
  )
}
