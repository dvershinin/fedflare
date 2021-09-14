import argparse
import CloudFlare
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from .fedora import projects


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
    print(args.domain)
    # grab the zone identifier
    try:
        zones = cf.zones.get(params={'name': args.domain, 'per_page' : 1})
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
        for name, dist in projects['epel'].items():
            for repo in dist['repos']:
                repomd_uri = f"pub/epel/{name}/{repo}/repodata/repomd.xml"
                alias_repomd_url = None
                if 'alias' in dist:
                    alias_repomd_url = f"https://{args.domain}/pub/epel/{dist['alias']}/{repo}/repodata/repomd.xml"
                repomd_fedora_url = f"https://dl.fedoraproject.org/{repomd_uri}"
                repomd_cloud_url = f"https://{args.domain}/{repomd_uri}"
                r_live = s.head(repomd_fedora_url)
                r_cloud = s.head(repomd_cloud_url)
                synced = r_live.headers['last-modified'] == r_cloud.headers['last-modified']
                if not synced:
                    invalidate_urls.append(repomd_cloud_url)
                    if alias_repomd_url:
                        invalidate_urls.append(alias_repomd_url)
                    print(f"Detected change on epel/{repomd_uri}")
                # simply request both and compare Last-Modified. If different, need to purge!
        # split in batches of 30 URLs, as single purge request only allows up to 30
        # see here: https://community.cloudflare.com/t/suddenly-cannot-purge-more-than-30-files-on-a-single-request/188756
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
