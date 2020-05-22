# translator = Translator()
# res = translator.translate('이 문장은 한글로 쓰여졌습니다.')
# print(res)

import argparse
import requests
from proxybroker import Broker
import asyncio
import random
import nltk
from textblob import TextBlob
import subprocess
from translation_script.modified_google_tran_obj import Translator


class SimpleProxyManager():
    def __init__(self, n_proxies=10):
        self.n_proxies = n_proxies
        self.valid_proxies = {}.fromkeys(self.cacheProxies(self.n_proxies))
        # self.check_proxies()
        print('done initializing proxy manager!')

    # get n proxies from proxybroker
    def cacheProxies(self, n):
        '''
        cmd = ['curl', '-sSf' 'https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt']
        curl https://${URL} &> /dev/stdout
        '''
        temp = ['curl', '-vs', 'https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt']
        res = subprocess.check_output(temp)
        return res.decode('utf-8').split("\n")
        # temp = []
        # for i in range(n):
        #     cmd = ['curl', 'http://pubproxy.com/api/proxy?limit=2&format=txt&http=true&country=US&type=http']
        #     temp.append(subprocess.check_output(cmd))
        #     time.sleep(1.2)
        # return temp

    def check_proxies(self, site_url):
        proxy_lists = list(self.valid_proxies.keys())
        for proxy in proxy_lists:
            proxies = {"https": proxy}
            try:
                with requests.get(site_url, proxies=proxies, timeout=7) as response:
                    if response.status_code == 200:
                        return proxy
                    else:
                        print(f"remove {proxy} with {response.status_code}")
                        self.remove_proxy(proxy)
            except Exception as e:
                if e == KeyboardInterrupt:
                    import sys
                    sys.exit()
                else:
                    print(e)
                    self.remove_proxy(proxy)

    def update_proxy(self):
        if len(self.valid_proxies.keys()) < self.n_proxies:
            self.valid_proxies.update({}.fromkeys(self.cacheProxies(self.n_proxies)))

    def remove_proxy(self, proxy):
        if proxy in self.valid_proxies:
            del self.valid_proxies[proxy]
            print("proxies left...", len(self.valid_proxies))

    def get_proxy(self):
        proxy = random.choice(list(self.valid_proxies.keys()))
        return proxy
        # while True:
        #     if len(self.valid_proxies) > 0:
        #         proxy = random.choice(list(self.valid_proxies.keys()))
        #         # test if the proxy works
        #         # proxies = {"http":proxy} if proxy.startswith("http") else {'https':proxy}
        #         proxies = {"https":proxy}
        #         try:
        #             with requests.get("http://google.com/", proxies=proxies, timeout=2) as response:
        #                 if response.status_code == 200:
        #                     print("using ...", proxy)
        #                     return proxy
        #                 else:
        #                     print(response.status_code)
        #                     self.remove_proxy(proxy)
        #         except Exception as e:
        #             if e == KeyboardInterrupt:
        #                 import sys
        #                 sys.exit()
        #             else:
        #                 print(e)
        #                 self.remove_proxy(proxy)
        #     else:
        #         self.valid_proxies.update({}.fromkeys(self.cacheProxies(self.n_proxies)))

class ProxyManager():
    def __init__(self, n_proxies=10):
        self.n_proxies = n_proxies
        self.valid_proxies = {}.fromkeys(self.cacheProxies(self.n_proxies))
        print('done initializing proxy manager!')

    # get n proxies from proxybroker
    def cacheProxies(self, n):
        print('caching proxies')
        async def show(proxies):
            p = []
            while True:
                proxy = await proxies.get()
                if proxy is None: break
                p.append("{}://{}:{}".format(proxy.schemes[0].lower(), proxy.host, proxy.port))
            return p

        proxies = asyncio.Queue()
        broker = Broker(proxies)
        tasks = asyncio.gather(broker.find(types=['HTTP', 'HTTPS'], limit=n), show(proxies))
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(tasks)[1]

    def update_proxy(self):
        if len(self.valid_proxies.keys()) < self.n_proxies:
            self.valid_proxies.update({}.fromkeys(self.cacheProxies(self.n_proxies)))

    def remove_proxy(self, proxy):
        if proxy in self.valid_proxies:
            del self.valid_proxies[proxy]

    def get_proxy(self):
        while True:
            if len(self.valid_proxies) > 0:
                proxy = random.choice(list(self.valid_proxies.keys()))
                # test if the proxy works
                proxies = {"http":proxy} if proxy.startswith("http") else {'https':proxy}
                try:
                    with requests.get("http://google.com/", proxies=proxies, timeout=2) as response:
                        if response.status_code == 200:
                            return proxy
                        else:
                            print(response.status_code)
                            self.remove_proxy(proxy)
                except Exception as e:
                    if e == KeyboardInterrupt:
                        import sys
                        sys.exit()
                    else:
                        print(e)
                        self.remove_proxy(proxy)
            else:
                self.valid_proxies.update({}.fromkeys(self.cacheProxies(self.n_proxies)))

def translate(comments, language, proxy_url):
    nltk.set_proxy(proxy_url)
    def fetch_translate_with_delay(comment, delay=0.5):
        if hasattr(comment, "decode"):
            comment = comment.decode("utf-8")
        text = TextBlob(comment)
        try:
            text = text.translate(to=language)
            print("intermediate translation: ", text)
            text = text.translate(to="en")
            return text
        except Exception as e:
            print(e)
            if e == KeyboardInterrupt:
                return None
    res = []
    for comment in comments:
        res.append(fetch_translate_with_delay(comment))
    if len(res) == 0: # for single comment
        return res[0]
    else: # for multiple comments
        return res

def translate_api(comment, language, proxy_url):
    nltk.set_proxy(proxy_url)
    translation = translator.translate(comment, dest=language)
    return translation.text

def main():
    parser = argparse.ArgumentParser("Script for translating")
    parser.add_argument("--languages", type=str, default='es')
    parser.add_argument("--comments", type=str, default="i like you")
    parser.add_argument("--language", default="extended_data")
    opt = parser.parse_args()
    proxyManager = SimpleProxyManager(n_proxies=5)
    # comments, language, proxy_url
    for i in range(5):
        t = translate_api(f'Does everybody have to be so mean?{i}', 'ko', proxyManager.get_proxy())
        print(t)
    # res = translate([opt.comments], opt.language, proxyManager.get_proxy())

if __name__ == '__main__':
    translator = Translator()
    main()