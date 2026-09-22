After you package the site as an Android app (e.g. with PWABuilder.com) and it
gives you a "Digital Asset Links" JSON snippet, paste it into
`assetlinks.json` in this folder and redeploy. It gets served automatically
at `https://yourdomain/.well-known/assetlinks.json`, which is what proves to
Android/Chrome that the app and this website are the same publisher (so the
app opens full-screen with no browser address bar).

Until then, `assetlinks.json` here is an empty array `[]`, which is a safe,
valid placeholder.
