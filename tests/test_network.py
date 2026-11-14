import httpx
import pytest

from app.network import Fetcher


@pytest.fixture
def network(monkeypatch):
    import app.network as mod
    real_client=httpx.Client
    replies={}
    requests=[]
    def respond(request):
        url=str(request.url);requests.append(url)
        code,text,headers=replies.get(url,(200,'Public article body',{'content-type':'text/html'}))
        return httpx.Response(code,text=text,headers=headers)
    monkeypatch.setattr(mod,'public_url',lambda u:u)
    monkeypatch.setattr(mod.httpx,'Client',lambda **kwargs:real_client(transport=httpx.MockTransport(respond),**kwargs))
    monkeypatch.setattr(mod.time,'sleep',lambda s:None)
    replies['https://site.example/robots.txt']=(200,'User-agent: *\nDisallow: /private\nCrawl-delay: 3',{})
    return Fetcher(),replies,requests


def test_robots_disallow_prevents_resource_request(network):
    fetcher,replies,requests=network
    with pytest.raises(ValueError,match='Disallowed'):
        fetcher.get('https://site.example/private')
    assert requests==['https://site.example/robots.txt']


def test_robots_error_defers_and_missing_allows(network):
    fetcher,replies,requests=network
    replies['https://site.example/robots.txt']=(503,'Unavailable',{})
    with pytest.raises(ValueError,match='deferred'):fetcher.get('https://site.example/page')
    replies['https://site.example/robots.txt']=(404,'Not found',{})
    assert fetcher.get('https://site.example/page').status==200


def test_cross_origin_redirect_checks_new_robots(network):
    fetcher,replies,requests=network
    replies['https://site.example/page']=(302,'',{'location':'https://other.example/secret'})
    replies['https://other.example/robots.txt']=(200,'User-agent: *\nDisallow: /secret',{})
    with pytest.raises(ValueError,match='Disallowed'):fetcher.get('https://site.example/page')
    assert 'https://other.example/secret' not in requests


def test_response_size_and_auth_restrictions(network):
    fetcher,replies,requests=network
    replies['https://site.example/big']=(200,'X'*3_000_001,{})
    with pytest.raises(ValueError,match='3 MB'):fetcher.get('https://site.example/big')
    replies['https://site.example/login']=(403,'Restricted',{})
    with pytest.raises(ValueError,match='not bypassed'):fetcher.get('https://site.example/login')


def test_excessive_robot_delay_deferred(network):
    fetcher,replies,requests=network
    replies['https://site.example/robots.txt']=(200,'User-agent: *\nCrawl-delay: 120',{})
    with pytest.raises(ValueError,match='over 60 seconds'):fetcher.get('https://site.example/page')


def test_crawl_delay_respected_and_robot_cache_reused(network,monkeypatch):
    import app.network as mod
    fetcher,replies,requests=network
    waits=[]
    monkeypatch.setattr(mod.time,'sleep',lambda s:waits.append(s))
    fetcher.get('https://site.example/page')
    fetcher.get('https://site.example/another')
    assert requests.count('https://site.example/robots.txt')==1
    assert any(s>2 for s in waits)


def test_canonical_host_robots_redirect_is_followed_safely(network):
    fetcher,replies,requests=network
    replies['https://site.example/robots.txt']=(301,'',{'location':'https://canonical.example/robots.txt'})
    replies['https://canonical.example/robots.txt']=(200,'User-agent: *\nDisallow: /private',{})
    assert fetcher.get('https://site.example/page').status==200
    with pytest.raises(ValueError,match='Disallowed'):
        fetcher.get('https://site.example/private')
    assert 'https://canonical.example/robots.txt' in requests
