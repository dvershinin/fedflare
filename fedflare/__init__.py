import argparse
import CloudFlare
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


def divide_chunks(l, n):
    # looping till length l
    for i in range(0, len(l), n):
        yield l[i:i + n]


def main():
    """The entrypoint to CLI app."""
    parser = argparse.ArgumentParser(
        description='Purge Cloudflare-cached repomd.xml URLs upon refresh of Fedora repositories.',
        prog='fedflare')
    parser.add_argument(
        '--project',
        default='epel',
        help='Repository group'
    )
    parser.add_argument(
        'domain',
        metavar='<domain>',
        help='Domain hosted on Cloudflare with CNAME to dl.fedoraproject.org'
    )
    args = parser.parse_args()

    cf = CloudFlare.CloudFlare()

    # grab the zone identifier
    try:
        zones = cf.zones.get(params={'name': args.domain, 'per_page': 1})
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        exit('/zones %d %s - api call failed' % (e, e))
    except Exception as e:
        exit('/zones.get - %s - api call failed' % (e))

    zone_id = None
    # there should only be one zone
    for zone in sorted(zones, key=lambda v: v['name']):
        zone_id = zone['id']

    invalidate_urls = []

    with requests.Session() as s:
        retry = Retry(connect=3, read=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        s.mount('https://', adapter)
        s.headers.update({'User-Agent': 'libdnf'})

        dirs_url = "https://dl.fedoraproject.org/pub/DIRECTORY_SIZES.txt"
        dirs_r = s.get(dirs_url, timeout=30)
        all_repodata_uris = []

        for line in dirs_r.text.splitlines():
            if 'repodata' in line:
                repodata_uri = line.split()[-1].strip()
                if repodata_uri.startswith('/pub/epel/'):
                    # Only EPEL repos
                    all_repodata_uris.append(repodata_uri)

        for repodata_uri in all_repodata_uris:
            print(f"Checking repomd.xml for freshness at repo {repodata_uri}", end=" ")
            repomd_uri = f"{repodata_uri}/repomd.xml"
            repomd_fedora_url = f"https://dl.fedoraproject.org{repomd_uri}"
            repomd_cloud_url = f"https://{args.domain}{repomd_uri}"
            r_live = s.head(repomd_fedora_url, timeout=5)
            r_cloud = s.head(repomd_cloud_url)

            # simply request both and compare Last-Modified. If different, need to purge!
            if 'last-modified' not in r_live.headers or 'last-modified' not in r_cloud.headers:
                invalidate_urls.append(repomd_cloud_url)
                print(f"Detected change (last-modified missing) on {repomd_uri}")
            elif r_live.headers['last-modified'] != r_cloud.headers['last-modified']:
                invalidate_urls.append(repomd_cloud_url)
                print(f"Detected change on {repomd_uri}")
            else:
                print(f"Fresh {r_live.headers['last-modified']}")
            s.get(repomd_cloud_url)

        # split in batches of 30 URLs, as single purge request only allows up to 30 see here:
        # https://community.cloudflare.com/t/suddenly-cannot-purge-more-than-30-files-on-a-single-request/188756
        url_chunks = list(divide_chunks(invalidate_urls, 30))
        if not url_chunks:
            print('All was synced already')
        else:
            for urls in url_chunks:
                print("Invalidating: " + str(urls))
                r = cf.zones.purge_cache.post(
                    zone_id,
                    data={'files': urls}
                )
                print(r)

        # warm up job
        for repodata_uri in all_repodata_uris:
            url = f"https://{args.domain}{repodata_uri}/repomd.xml"
            print(f"Warming {url}", end=" ")
            # python-requests on Keep-Alive:
            # Note that connections are only released back to the pool for reuse once all body data has been read;
            # be sure to either set stream to False or read the content property of the Response object.
            warm_r = s.get(url, stream=False)
            if 'cf-cache-status' not in warm_r.headers:
                print(f"cf-cache-status not found in headers: {warm_r.headers}")
                exit(1)
            if warm_r.headers['cf-cache-status'] == 'DYNAMIC':
                print('Got DYNAMIC cache status. Is Cache Everything rule active?')
                exit(2)
            print(warm_r.headers['cf-cache-status'])

