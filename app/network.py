import hashlib
import ipaddress
import socket
import threading
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

USER_AGENT = 'SignalStack/1.0 (+local company research; respects robots.txt)'
MAX_BYTES = 3_000_000


def canonical_url(value):
    parts = urlsplit(value.strip())
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('Use a public http(s) URL without embedded credentials')
    if parts.port not in (None, 80, 443):
        raise ValueError('Only standard web ports are supported')
    host = parts.hostname.lower()
    netloc = f'[{host}]' if ':' in host else host
    return urlunsplit((parts.scheme.lower(), netloc, parts.path.rstrip('/') or '/', parts.query, ''))


def public_url(value):
    value = canonical_url(value)
    host = urlsplit(value).hostname
    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ValueError(f'Could not resolve public host: {host}') from None
    if not addresses or any(not ipaddress.ip_address(r[4][0]).is_global for r in addresses):
        raise ValueError('Private, loopback, link-local, and reserved addresses cannot be crawled')
    return value


def digest(text):
    return hashlib.sha256(' '.join(text.split()).encode()).hexdigest()


@dataclass
class Page:
    url: str
    text: str
    content_type: str
    status: int = 200


class Fetcher:
    def __init__(self):
        self.robots = {}
        self.last_request = {}
        self.lock = threading.Lock()

    def _raw(self, url, delay=1):
        for _ in range(6):
            url = public_url(url)
            origin = '{0.scheme}://{0.netloc}'.format(urlsplit(url))
            with self.lock:
                wait = max(0, self.last_request.get(origin, 0) + delay - time.monotonic())
                if wait:
                    time.sleep(wait)
                self.last_request[origin] = time.monotonic()
            with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
                with client.stream('GET', url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,application/rss+xml,application/atom+xml,application/xml,text/plain;q=0.9'}) as response:
                    if response.is_redirect:
                        target = urljoin(url, response.headers.get('location', ''))
                        # Every redirected resource has its own robots policy.
                        self._check_robots(target, delay)
                        url = target
                        continue
                    if response.status_code in (401, 403):
                        raise ValueError('Access restricted; authentication and paywalls are not bypassed')
                    response.raise_for_status()
                    size, chunks = 0, []
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise ValueError('Response exceeds 3 MB limit')
                        chunks.append(chunk)
                    content_type = response.headers.get('content-type', '').lower()
                    return Page(url, b''.join(chunks).decode('utf-8', errors='replace'), content_type)
        raise ValueError('Too many redirects')

    def _check_robots(self, url, delay):
        url = public_url(url)
        origin = '{0.scheme}://{0.netloc}'.format(urlsplit(url))
        cached = self.robots.get(origin)
        if not cached or time.monotonic() - cached[0] > 3600:
            parser = RobotFileParser()
            try:
                # Follow canonical-host robots redirects without recursively
                # requesting a policy for the policy itself. Validate every hop.
                robots_url = origin + '/robots.txt'
                seen = set()
                with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
                    for _ in range(6):
                        robots_url = public_url(robots_url)
                        if robots_url in seen:
                            raise ValueError('robots.txt redirect loop; crawl deferred')
                        seen.add(robots_url)
                        policy_origin = '{0.scheme}://{0.netloc}'.format(urlsplit(robots_url))
                        with self.lock:
                            wait = max(0, self.last_request.get(policy_origin, 0) + delay - time.monotonic())
                            if wait:
                                time.sleep(wait)
                            self.last_request[policy_origin] = time.monotonic()
                        result = client.get(robots_url, headers={'User-Agent': USER_AGENT})
                        if not result.is_redirect:
                            break
                        robots_url = urljoin(robots_url, result.headers.get('location', ''))
                    else:
                        raise ValueError('Too many robots.txt redirects; crawl deferred')
                if result.status_code == 404:
                    parser.parse([])
                elif result.status_code == 200 and len(result.content) <= MAX_BYTES:
                    parser.parse(result.text.splitlines())
                else:
                    raise ValueError('robots.txt unavailable or restricted; crawl deferred')
            except httpx.HTTPError:
                raise ValueError('robots.txt could not be checked; crawl deferred') from None
            self.robots[origin] = (time.monotonic(), parser)
        parser = self.robots[origin][1]
        if not parser.can_fetch(USER_AGENT, url):
            raise ValueError('Disallowed by robots.txt')
        crawl_delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay('*') or delay
        if crawl_delay > 60:
            raise ValueError('robots.txt requires a delay over 60 seconds; crawl deferred')
        return max(delay, crawl_delay)

    def get(self, url, delay=1):
        delay = self._check_robots(url, delay)
        return self._raw(url, delay)

    def search(self, query):
        page = self.get('https://html.duckduckgo.com/html/?' + urlencode({'q': query}))
        soup = BeautifulSoup(page.text, 'html.parser')
        results = []
        for anchor in soup.select('.result__a')[:8]:
            raw = urljoin(page.url, anchor.get('href', ''))
            url = parse_qs(urlsplit(raw).query).get('uddg', [raw])[0]
            try:
                url = canonical_url(url)
            except ValueError:
                continue
            parent = anchor.find_parent(class_='result')
            snippet = parent.select_one('.result__snippet') if parent else None
            results.append({'url': url, 'title': anchor.get_text(' ', strip=True),
                            'snippet': snippet.get_text(' ', strip=True) if snippet else ''})
        if not results:
            raise ValueError('Free search returned no usable results or was blocked. Add sources manually or retry later.')
        return results


def html_content(page):
    soup = BeautifulSoup(page.text, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else urlsplit(page.url).hostname
    for item in soup(['script', 'style', 'nav', 'footer', 'noscript', 'header']):
        item.decompose()
    text = ' '.join(soup.get_text(' ', strip=True).split())[:50000]
    return title, text, soup
