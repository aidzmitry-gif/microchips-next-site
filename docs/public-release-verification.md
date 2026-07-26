# Public release verification

Run this read-only gate only against a real staging or production HTTPS domain after deployment. It sends GET requests only and does not submit forms or use credentials.

```powershell
.\scripts\verify-public-release.ps1 `
  -BaseUrl "https://staging.example.by" `
  -ExpectedHost "staging.example.by" `
  -ExpectedSiteKey "microchips-by" `
  -RequiredPaths @('/', '/catalog') `
  -Expected404Paths @('/contacts')
```

The command rejects localhost, `.test`, HTTP, custom ports, paths, queries, and fragments. It writes a JSON evidence report under `docs/audits/generated/public-release/` and returns a non-zero exit code if HTTPS, canonical, robots, sitemap, required URLs, redirects, or expected 404 pages fail.

It cannot verify business facts, Bitrix24, Search Console, Yandex Webmaster, analytics, legal entity details, or delivery/payment terms. Those remain separate launch evidence requirements.

Validate the script implementation without a public host:

```powershell
.\scripts\verify-public-release.ps1 -RunSelfTest
```
