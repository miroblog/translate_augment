"""Run a local proxy server that distributes
   incoming requests to external proxies."""

import asyncio
import aiohttp
from textblob.compat import PY2, request, urlencode
from textblob.exceptions import TranslatorError, NotTranslated
from proxybroker import Broker
import urllib
import codecs
import ctypes
import json
import re

headers = {
    'Accept': '*/*',
    'Connection': 'keep-alive',
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) '
        'AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.168 Safari/535.19')
}

async def get_pages(urls, proxy_url):
    tasks = [fetch(url, proxy_url) for url in urls]
    contents = []
    for task in asyncio.as_completed(tasks):
        url, content = await task
        # print('Done! url: %s; content: %.100s' % (url, content))
        contents.append(content)
    return contents

async def get_translates(proxy_url, objs):
    n_requests = len(objs)
    sources, from_langs, to_langs = zip(*objs)
    # url, proxy_url, source, from_lang='auto', to_lang='en'
    tasks = [translate(proxy_url=proxy_url, source=sources[idx], from_lang=from_langs[idx], to_lang=to_langs[idx]) for idx in range(n_requests)]
    contents = []
    for task in asyncio.as_completed(tasks):
        content = await task
        # print('Done! url: %s; content: %.100s' % (url, content))
        contents.append(content)
    return contents


def _calculate_tk(source):
    """Reverse engineered cross-site request protection."""
    # Source: https://github.com/soimort/translate-shell/issues/94#issuecomment-165433715
    # Source: http://www.liuxiatool.com/t.php

    tkk = [406398, 561666268 + 1526272306]
    b = tkk[0]

    if PY2:
        d = map(ord, source)
    else:
        d = source.encode('utf-8')

    def RL(a, b):
        for c in range(0, len(b) - 2, 3):
            d = b[c + 2]
            d = ord(d) - 87 if d >= 'a' else int(d)
            xa = ctypes.c_uint32(a).value
            d = xa >> d if b[c + 1] == '+' else xa << d
            a = a + d & 4294967295 if b[c] == '+' else a ^ d
        return ctypes.c_int32(a).value

    a = b

    for di in d:
        a = RL(a + di, "+-a^+6")

    a = RL(a, "+-3^+b+-f")
    a ^= tkk[1]
    a = a if a >= 0 else ((a & 2147483647) + 2147483648)
    a %= pow(10, 6)

    tk = '{0:d}.{1:d}'.format(a, a ^ b)
    return tk

def _validate_translation(source, result):
    """Validate API returned expected schema, and that the translated text
    is different than the original string.
    """
    if not result:
        raise NotTranslated('Translation API returned and empty response.')
    if PY2:
        result = result.encode('utf-8')
    if result.strip() == source.strip():
        raise NotTranslated('Translation API returned the input string unchanged.')


def normal_translate(proxy_url, source, from_lang='auto', to_lang='en', host=None, type_=None):
    data = {"q": source}
    base_url = "http://translate.google.com/translate_a/t?client=webapp&dt=bd&dt=ex&dt=ld&dt=md&dt=qca&dt=rw&dt=rm&dt=ss&dt=t&dt=at&ie=UTF-8&oe=UTF-8&otf=2&ssel=0&tsel=0&kc=1"
    url = u'{url}&sl={from_lang}&tl={to_lang}&hl={to_lang}&tk={tk}'.format(
        url=base_url,
        from_lang=from_lang,
        to_lang=to_lang,
        tk=_calculate_tk(source),
    )
    resp = None
    try:
        encoded_data = urlencode(data).encode('utf-8')
        req = request.Request(url=url, headers=headers, data=encoded_data)

        proxies = {'http': proxy_url}
        print("Using HTTP proxy %s" % proxies['http'])

        authinfo = urllib.request.HTTPBasicAuthHandler()
        proxy_support = urllib.request.ProxyHandler({"http": proxy_url})
        # build a new opener that adds authentication and caching FTP handlers
        opener = urllib.request.build_opener(proxy_support, authinfo,
                                             urllib.request.CacheFTPHandler)
        # install it
        urllib.request.install_opener(opener)
        # f = urllib.request.urlopen('http://www.google.com/')
        # resp = urllib.request.urlopen(req, data=data, headers=headers)
        resp = request.urlopen(req)
        content = resp.read()
        return content.decode('utf-8')
    except Exception as e:
        print(e)
        return None


def normal_google(proxy_url):
    base_url = "http://google.com"
    resp = None
    try:
        req = request.Request(url=base_url, headers=headers)
        proxies = {'http': proxy_url}
        print("Using HTTP proxy %s" % proxies['http'])
        authinfo = urllib.request.HTTPBasicAuthHandler()
        proxy_support = urllib.request.ProxyHandler({"http": proxy_url})
        # build a new opener that adds authentication and caching FTP handlers
        opener = urllib.request.build_opener(proxy_support, authinfo,
                                             urllib.request.CacheFTPHandler)
        # install it
        urllib.request.install_opener(opener)
        # f = urllib.request.urlopen('http://www.google.com/')
        # resp = urllib.request.urlopen(req, data=data, headers=headers)
        resp = request.urlopen(req)
        content = resp.read()
        return content.decode('utf-8')
    except Exception as e:
        print(e)
        return None


def build_params(query, src, dest, token):
    params = {
        'client': 't',
        'sl': src,
        'tl': dest,
        'hl': dest,
        'dt': ['at', 'bd', 'ex', 'ld', 'md', 'qca', 'rw', 'rm', 'ss', 't'],
        'ie': 'UTF-8',
        'oe': 'UTF-8',
        'otf': 1,
        'ssel': 0,
        'tsel': 0,
        'tk': token,
        'q': query,
    }
    return params

async def translate(proxy_url, source, from_lang='auto', to_lang='en', host=None, type_=None):
    params = build_params(query=source,src=from_lang, dest=to_lang, token=_calculate_tk(source))
    base_url = 'https://translate.google.com/translate_a/single'
    # base_url = "http://translate.google.com/translate_a/t?client=webapp&dt=bd&dt=ex&dt=ld&dt=md&dt=qca&dt=rw&dt=rm&dt=ss&dt=t&dt=at&ie=UTF-8&oe=UTF-8&otf=2&ssel=0&tsel=0&kc=1"
    # url = u'{url}&sl={from_lang}&tl={to_lang}&hl={to_lang}&tk={tk}'.format(
    #     url=base_url,
    #     from_lang=from_lang,
    #     to_lang=to_lang,
    #     tk=_calculate_tk(source),
    # )
    resp = None
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            # session.verify = False
            # async with session.get(url, proxy=proxy_url, type=type_, data=data, host=None) as response:
            # encoded_data = urlencode(data).encode('utf-8')
            async with session.get(base_url, data=params) as response:
                resp = await response.read()

                # if isinstance(resp, list):
                #     try:
                #         resp = resp[0]  # ignore detected language
                #     except IndexError:
                #         pass
                # _validate_translation(source, resp)
                return resp
    except Exception as e:
        print(e)
        return None

    # except (aiohttp.errors.ClientOSError, aiohttp.errors.ClientResponseError,
    #         aiohttp.errors.ServerDisconnectedError) as e:
    #     print('Error. url: %s; error: %r' % (url, e))
    # finally:
    #     return resp

async def fetch(url, proxy_url):
    resp = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=proxy_url) as response:
                resp = await response.read()
    except (aiohttp.errors.ClientOSError, aiohttp.errors.ClientResponseError,
            aiohttp.errors.ServerDisconnectedError) as e:
        print('Error. url: %s; error: %r' % (url, e))
    finally:
        return (url, resp)

def main():
    host, port = '127.0.0.1', 30003  # by default

    loop = asyncio.get_event_loop()

    types = ['HTTP', 'HTTPS']
    codes = [200]

    broker = Broker(max_tries=1, loop=loop)

    # Broker.serve() also supports all arguments that are accepted
    # Broker.find() method: data, countries, post, strict, dnsbl.
    broker.serve(host=host, port=port, types=types, limit=1000, max_tries=2,
                 prefer_connect=True, min_req_proxy=4, max_error_rate=0.25,
                 max_resp_time=4, http_allowed_codes=codes, backlog=100)


    # urls = ['https://translate.google.com/', 'https://google.com']
    #
    # proxy_url = 'http://%s:%d' % (host, port)
    #
    # # source, from_lang='auto', to_lang='en'
    # objs = [('i love my father', 'en', 'es'), ('so does my mother', 'en', 'es')]
    #
    # # res = translate(proxy_url=proxy_url, source=objs[0][0], from_lang='en', to_lang='es')
    #
    # # res = normal_google(proxy_url)
    # # print(res)
    #
    # sth = loop.run_until_complete(get_translates(proxy_url, objs))
    # # sth = loop.run_until_complete(get_pages(urls, proxy_url))
    # for fut in sth:
    #     print("return value is {}".format(fut.result()))
    broker.stop()


if __name__ == '__main__':
    main()