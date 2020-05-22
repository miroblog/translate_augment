from joblib import Parallel, delayed
import argparse
from translation_script.proxyManager import SimpleProxyManager
from tqdm import tqdm
from translation_script.modified_google_tran_obj import Translator

def proxy_google_translate(comments, language):
    res = []
    for comment in comments:
        org_comment = comment
        while True:
            proxy = proxyManager.get_proxy()
            translator = Translator(proxies={'http': proxy})
            translation = translator.translate(comment,dest=language, src='en')
            if translation is None:
                print(org_comment)
                return org_comment + "+unchanged"

            translation = translator.translate(comment, dest='en', src=language)
            if translation is None:
                print(org_comment)
                return org_comment + "+unchanged"
            res.append(comment)
            break
    return res

def process_dataset(args, comments):
    parallel = Parallel(args.thread_count, backend="threading")
    for language in args.languages:
        translated_responses = parallel(delayed(proxy_google_translate)([comment], language) for comment in tqdm(comments))
    return translated_responses

def main():
    parser = argparse.ArgumentParser("Script for extending train dataset")
    parser.add_argument("--languages", nargs="+", default=["es", "de", "fr"])
    parser.add_argument("--thread-count", type=int, default=100)
    args = parser.parse_args()
    comments = ['This is a dog', 'This is a frog']
    translated_comments = process_dataset(args, comments)

if __name__ == "__main__":
    proxyManager = SimpleProxyManager(10)
    main()