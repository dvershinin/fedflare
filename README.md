# fedflare

Python-based CLI app for cache invalidation and warm up for a Cloudflare mirror of Fedora repositories.

The `fedflare` CLI program:

* invalidates *changed* `repomd.xml` files, ensuring that Cloudflare mirror is always fresh
* warms up Cloudflare's `repomd.xml` copy (currently limited feature, because it warms up from a single location only)

## Use epel.cloud

Install epel-release with CDN base URLs in lieu of standard releases packages.

### CentOS/RHEL 7

    sudo yum -y install https://epel.cloud/pub/epel/epel-release-latest-7.noarch.rpm

### CentOS/RHEL 8

    sudo dnf -y install https://epel.cloud/pub/epel/epel-release-latest-8.noarch.rpm

## `fedflare` at its core

`fedflare` is what makes this simple yet fast CDN possible. It ensures that the Cloudflare CDN is
in sync with actual Fedora repositories.

## How this works

This script requests every repo's repomd.xml from Fedora servers, and then caches it locally. 
Changes in cache state for a repomd.xml will mean that the repomd.xml needs to be invalidated.

As such, we have a highly-cacheable CDN of Fedora repositories, hosted on Cloudflare, with virtually
no stale data whatsoever.

### Running

```bash
fedflare domain.com
```

By default, it will work (and currently only supports) EPEL repositories by Fedora.

Live implementation can be found, and is much recommend for use: [epel.cloud](https://www.getpagespeed.com/server-setup/nginx/epel-powered-by-cloudflare-cdn-fix-your-sanity).

### Example installation

```bash
cp /home/<username>/fedflare/fedflare.service /etc/systemd/system/fedflare.service
systemctl daemon-reload
systemctl enable --now fedflare
systemctl status fedflare
```
