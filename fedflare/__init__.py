import argparse
import os
import signal
import logging

import CloudFlare
import requests
from cachecontrol import CacheControl
from cachecontrol.caches import FileCache
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
# Flag to control the loop
running = True


def divide_chunks(l, n):
    # looping till length l
    for i in range(0, len(l), n):
        yield l[i : i + n]


def signal_handler(signum, frame):
    global running
    logging.info(f"Received signal {signum}, shutting down...")
    running = False


def main():
    """The entrypoint to CLI app."""
    parser = argparse.ArgumentParser(
        description="Purge Cloudflare-cached repomd.xml URLs upon refresh of Fedora repositories.",
        prog="fedflare",
    )
    parser.add_argument("--project", default="epel", help="Repository group")
    parser.add_argument(
        "domain",
        metavar="<domain>",
        help="Domain hosted on Cloudflare with CNAME to dl.fedoraproject.org",
    )

    parser.add_argument("--service", help="Run as a service", action="store_true")

    args = parser.parse_args()

    cf = CloudFlare.CloudFlare()

    # grab the zone identifier
    try:
        zones = cf.zones.get(params={"name": args.domain, "per_page": 1})
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        exit("/zones %d %s - api call failed" % (e, e))
    except Exception as e:
        exit("/zones.get - %s - api call failed" % (e))

    zone_id = None
    # there should only be one zone
    for zone in sorted(zones, key=lambda v: v["name"]):
        zone_id = zone["id"]

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    global running

    while running:

        logging.info("Checking for changes in Fedora repositories. Iteration started.")
        invalidate_urls = []

        with requests.Session() as uncached_session:
            retry = Retry(
                connect=3,
                read=3,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry)
            uncached_session.mount("https://", adapter)
            # Use CacheControl to wrap the session
            # Create or ensure the cache directory exists
            cache_dir = os.path.expanduser("~/.cache/fedlare")
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            s = CacheControl(uncached_session, cache=FileCache(cache_dir))
            s.headers.update({"User-Agent": "libdnf"})

            dirs_url = "https://dl.fedoraproject.org/pub/DIRECTORY_SIZES.txt"
            dirs_r = s.get(dirs_url, timeout=30)
            # This response may be unchanged even though repodata actually changed, simply in cases where repodata remains
            # approximately the same size. So we need to check each repodata.xml file for freshness.

            all_repodata_uris = []
            for line in dirs_r.text.splitlines():
                if "repodata" in line:
                    repodata_uri = line.split()[-1].strip()
                    if repodata_uri.startswith("/pub/epel/"):
                        # Only EPEL repos
                        all_repodata_uris.append(repodata_uri)

            for repodata_uri in all_repodata_uris:
                repomd_uri = f"{repodata_uri}/repomd.xml"
                repomd_fedora_url = f"https://dl.fedoraproject.org{repomd_uri}"

                repomd_cloud_url = f"https://{args.domain}{repomd_uri}"
                r_live = s.get(repomd_fedora_url, timeout=30)
                time.sleep(0.1)  # Add a microsleep to reduce CPU usage

                # comparing to cloud URL's last-modified is wrong because maybe we hit one edge where it's cached with
                # proper date while on another edge it's outdated
                # that would result in not purging the cache when it should be purged,
                # so again we use CacheControl to detect changes
                if not r_live.from_cache:
                    invalidate_urls.append(repomd_cloud_url)
                    logging.info(f"{repomd_uri}: Detected change (uncached)")
                else:
                    logging.info(f"{repomd_uri}: No change")

            # split in batches of 30 URLs, as single purge request only allows up to 30 see here:
            # https://community.cloudflare.com/t/suddenly-cannot-purge-more-than-30-files-on-a-single-request/188756
            url_chunks = list(divide_chunks(invalidate_urls, 30))
            if not url_chunks:
                logging.info("All was synced already")
            else:
                for urls in url_chunks:
                    logging.info("Invalidating: " + str(urls))
                    r = cf.zones.purge_cache.post(zone_id, data={"files": urls})
                    logging.debug(r)

            # warm up job
            for repodata_uri in all_repodata_uris:
                url = f"https://{args.domain}{repodata_uri}/repomd.xml"
                logging.debug(f"Warming {url}")
                # python-requests on Keep-Alive:
                # Note that connections are only released back to the pool for reuse once all body data has been read;
                # be sure to either set stream to False or read the content property of the Response object.
                try:
                    warm_r = s.get(url, stream=False)
                    time.sleep(0.1)  # Add a microsleep to reduce CPU usage
                except requests.exceptions.ChunkedEncodingError:
                    # just repeat on a broken connection
                    time.sleep(1)
                    warm_r = s.get(url, stream=False)

                if "cf-cache-status" not in warm_r.headers:
                    logging.warning(
                        f"cf-cache-status not found in headers: {warm_r.headers}"
                    )
                    continue
                if warm_r.headers["cf-cache-status"] == "DYNAMIC":
                    logging.error(
                        f"Got DYNAMIC cache status at {url}. Is Cache Everything rule active?"
                    )
                    # TODO: this happens even when Cache Everything is set. So we should not exit
                    # Instead, we need to log response headers to Sentry or somewhere
                logging.info(
                    f"Warmed %s and received Cloudflare cache status: %s",
                    url,
                    warm_r.headers["cf-cache-status"],
                )
        if not args.service:
            break
        # Sleep 1 minute between checks
        logging.info("Sleeping for 60 seconds")
        time.sleep(60)
