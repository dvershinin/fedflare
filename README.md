## How this works

This script requests every repo's repomd.xml from Cloudflare and Fedora servers, and compares their 
`Last-Modified` response headers. 
Different values will mean that the `repomd.xml` will be added to the batch for
purging on Cloudflare.

As such, we have a highly-cacheable CDN of Fedora repositories, hosted on Cloudflare, with virtually
no stale data whatsoever.

### Running

```bash
fedflare domain.com
```

By default, it will work (and currently only supports) EPEL repositories by Fedora.

Live implementation can be found, and is much recommend for use: epel.cloud.# fedflare
