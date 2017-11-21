#!/usr/bin/env python
# -*- coding: utf-8 -*-

# A script to download full soundtracks from The Hylia.

# __future__ import for forwards compatibility with Python 3
from __future__ import print_function
from __future__ import unicode_literals

import os
import re # For the syntax error in the HTML.
import sys
from functools import wraps

try:
    from urllib.parse import unquote, urljoin
except ImportError: # Python 2
    from urlparse import unquote, urljoin

# --- Install prerequisites---

# (This section in `if __name__ == '__main__':` is entirely unrelated to the
# rest of the module, and doesn't even run if the module isn't run by itself.)

if __name__ == '__main__':
    import imp # To check modules without importing them.

    # User-friendly name, import name, pip specification.
    requiredModules = [
        ['requests', 'requests', 'requests >= 2.0.0, < 3.0.0'],
        ['Beautiful Soup 4', 'bs4', 'beautifulsoup4 >= 4.4.0, < 5.0.0']
    ]

    class Silence(object):
        def __enter__(self):
            self._stdout = sys.stdout
            self._stderr = sys.stderr
            sys.stdout = open(os.devnull, 'w')
            sys.stderr = open(os.devnull, 'w')
        
        def __exit__(self, *_):
            sys.stdout = self._stdout
            sys.stderr = self._stderr

    def moduleExists(module):
        try:
            imp.find_module(module[1])
        except ImportError:
            return False
        return True
    def neededInstalls(requiredModules=requiredModules):
        uninstalledModules = []
        for module in requiredModules:
            if not moduleExists(module):
                uninstalledModules.append(module)
        return uninstalledModules

    def install(package):
        with Silence(): # To silence pip's errors.
            exitStatus = pip.main(['install', '--quiet', package])
        if exitStatus != 0:
            raise OSError("Failed to install package.")
    def installModules(modules, verbose=True):
        for module in modules:
            if verbose:
                print("Installing {}...".format(module[0]))
            
            try:
                install(module[2])
            except OSError as e:
                if verbose:
                    print("Failed to install {}. "
                          "You may need to run the script as an administrator "
                          "or superuser.".format(module[0]))
                    print ("You can also try to install the package manually "
                           "(pip install \"{}\")".format(module[2]))
                raise e
    def installRequiredModules(needed=None, verbose=True):
        needed = neededInstalls() if needed is None else needed
        installModules(neededInstalls(), verbose)

    needed = neededInstalls()
    if needed: # Only import pip if modules are actually missing.
        try:
            import pip # To install modules if they're not there.
        except ImportError:
            print("You don't seem to have pip installed!")
            print("Get it from https://pip.readthedocs.org/en/latest/installing.html")
            sys.exit()

    try:
        installRequiredModules(needed)
    except OSError:
        sys.exit()

# ------

import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://anime.thehylia.com/'

# Different printin' for different Pythons.
normalPrint = print
def print(*args, **kwargs):
    encoding = sys.stdout.encoding or 'utf-8'
    if sys.version_info[0] > 2: # Python 3 can't print bytes properly (!?)
        # This lambda is ACTUALLY a "reasonable"
        # way to print Unicode in Python 3. What.
        printEncode = lambda s: s.encode(encoding, 'replace').decode(encoding)
        unicodeType = str
    else:
        printEncode = lambda s: s.encode(encoding, 'replace')
        unicodeType = unicode
    
    args = [
        printEncode(arg)
        if isinstance(arg, unicodeType) else arg
        for arg in args
    ]
    normalPrint(*args, **kwargs)


def lazy_property(func):
    attr_name = '_lazy_' + func.__name__
    @property
    @wraps(func)
    def lazy_version(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, func(self))
        return getattr(self, attr_name)
    return lazy_version


def getSoup(*args, **kwargs):
    r = requests.get(*args, **kwargs)
    content = r.content

    # Fix errors in The Hylia's HTML
    removeRe = re.compile(br"^</td>\s*$", re.MULTILINE)
    content = removeRe.sub(b'', content)
    
    badDivTag = b'<div style="padding: 7px; float: left;">'
    badDivLength = len(badDivTag)
    badDivStart = content.find(badDivTag)
    while badDivStart != -1:
        badAEnd = content.find(b'</a>', badDivStart)
        content = content[:badAEnd] + content[badAEnd + 4:]
        
        badDivEnd = content.find(b'</div>', badDivStart)
        content = content[:badDivEnd + 6] + b'</a>' + content[badDivEnd + 6:]
        
        badDivStart = content.find(badDivTag, badDivStart + badDivLength)
    
    return BeautifulSoup(content, 'html.parser')


def strictSplitext(filename):
    try:
        dotIndex = filename.rindex('.')
    except ValueError:
        return [filename, '']
    if re.match(r'^[A-Za-z0-9]+$', filename[dotIndex + 1:]):
        return [filename[:dotIndex], filename[dotIndex:]]
    else:
        return [filename, '']


def friendlyDownloadFile(file, path, name, index, total, verbose=False):
    numberStr = "{}/{}".format(
        str(index).zfill(len(str(total))),
        str(total)
    )

    if not os.path.exists(path):
        if verbose:
            print("Downloading {}: {}...".format(numberStr, name))
        for triesElapsed in range(3):
            if verbose and triesElapsed:
                print("Couldn't download {}. Trying again...".format(name))
            try:
                file.download(path)
            except requests.ConnectionError:
                pass
            else:
                break
        else:
            if verbose:
                print("Couldn't download {}. Skipping over.".format(name))
    else:
        if verbose:
            print("Skipping over {}: {}. Already exists.".format(numberStr, name))


class NonexistentSoundtrackError(Exception):
    def __init__(self, soundtrackId=""):
        super(NonexistentSoundtrackError, self).__init__(soundtrackId)
        self.soundtrackId = soundtrackId
    def __str__(self):
        if not self.soundtrackId or len(self.soundtrackId) > 80:
            s = "The soundtrack does not exist."
        else:
            s = "The soundtrack \"{ost}\" does not exist.".format(ost=self.soundtrackId)
        return s


class Soundtrack(object):
    def __init__(self, soundtrackId):
        self.id = soundtrackId
        self.url = urljoin(BASE_URL, 'soundtracks/album/' + self.id)
    
    def __repr__(self):
        return "<{}: {}>".format(self.__class__.__name__, self.id)

    def _isLoaded(self, property):
        return hasattr(self, '_lazy_' + property)

    @lazy_property
    def _contentSoup(self):
        soup = getSoup(self.url)
        contentSoup = soup.find(id='content_container')('div')[1].find('div')
        if contentSoup.find('p', string="No such album"):
            raise NonexistentSoundtrackError(self.id)
        return contentSoup

    @lazy_property
    def songs(self):
        table = self._contentSoup.find('table')
        anchors = table('a')
        urls = [a['href'] for a in anchors]
        songs = [Song(urljoin(self.url, url)) for url in urls]
        return songs
    
    @lazy_property
    def images(self):
        anchors = self._contentSoup('a', target='_blank')
        urls = [a['href'] for a in anchors]
        images = [File(urljoin(self.url, url)) for url in urls]
        return images

    def download(self, path='', makeDirs=True, verbose=False):
        path = os.path.join(os.getcwd(), path)
        path = os.path.abspath(os.path.realpath(path))

        if verbose and not self._isLoaded('songs'):
            print("Getting song list...")
        files = []
        for song in self.songs:
            file = song.files[0]
            files.append(file)
        files.extend(self.images)
        totalFiles = len(files)

        if makeDirs and not os.path.isdir(path):
            os.makedirs(os.path.abspath(os.path.realpath(path)))

        for fileNumber, file in enumerate(files, 1):
            filePath = os.path.join(path, file.filename)
            friendlyDownloadFile(file, filePath, file.filename, fileNumber, totalFiles, verbose)


class Song(object):
    def __init__(self, url):
        self.url = url
    
    def __repr__(self):
        return "<{}: {}>".format(self.__class__.__name__, self.url)
    
    @lazy_property
    def _soup(self):
        return getSoup(self.url)

    @lazy_property
    def name(self):
        infoParagraph = self._soup.find(id='content_container').find(
            lambda tag: tag.name == 'p' and next(tag.stripped_strings) == 'Album name:')
        strippedStrings = infoParagraph.stripped_strings
        for s in strippedStrings:
            if s == 'Song name:':
                break
        return next(strippedStrings)

    @lazy_property
    def files(self):
        table = self._soup.find(id='content_container').find('table', class_='blog')
        anchors = [b.find('a') for b in table('b', string=re.compile(r'^\s*Download to Computer'))]
        files = [File(urljoin(self.url, a['href'])) for a in anchors]
        for file in files:
            file.filename = strictSplitext(self.name)[0] + os.path.splitext(file.filename)[1]
        return files


class File(object):
    def __init__(self, url):
        self.url = url
        self.filename = unquote(url.rsplit('/', 1)[-1])

    def __repr__(self):
        return "<{}: {}>".format(self.__class__.__name__, self.url)
    
    def download(self, path):
        response = requests.get(self.url, timeout=10)
        with open(path, 'wb') as outFile:
            outFile.write(response.content)


def download(soundtrackId, path='', makeDirs=True, verbose=False):
    Soundtrack(soundtrackId).download(path, makeDirs, verbose)


def search(term):
    """Return a list of OST IDs for the search term `term`."""
    soup = getSoup(urljoin(BASE_URL, 'search'), params={'search': term})
    
    headerParagraph = soup.find(id='content_container').find('p',
        string=re.compile(r"^Found [0-9]+ matching albums for \".*\"\.$"))
    anchors = headerParagraph.find_next_sibling('p')('a')
    soundtrackIds = [a['href'].split('/')[-1] for a in anchors]

    return [Soundtrack(id) for id in soundtrackIds]

# --- And now for the execution. ---

if __name__ == '__main__':
    import argparse

    # Tiny details!
    class ProperHelpFormatter(argparse.RawTextHelpFormatter):
        def add_usage(self, usage, actions, groups, prefix=None):
            if prefix is None:
                prefix = 'Usage: '
            return super(ProperHelpFormatter, self).add_usage(usage, actions, groups, prefix)

    def doIt(): # Only in a function to be able to stop after errors, really.
        script_name = os.path.split(sys.argv[0])[-1]
        if len(sys.argv) == 1:
            print("No soundtrack specified! As the first parameter, use the name the soundtrack uses in its URL.")
            print("If you want to, you can also specify an output directory as the second parameter.")
            print("You can also search for soundtracks by using your search term as parameter - as long as it's not an existing soundtrack.")
            print()
            print("For detailed help and more options, run \"{} --help\".".format(script_name))
            return

        parser = argparse.ArgumentParser(description="Download entire soundtracks from The Hylia.\n\n"
                                         "Examples:\n"
                                         "%(prog)s jumping-flash\n"
                                         "%(prog)s katamari-forever \"music{}Katamari Forever OST\"\n"
                                         "%(prog)s --search persona\n".format(os.sep),
                                         epilog="Hope you enjoy the script!",
                                         formatter_class=ProperHelpFormatter,
                                         add_help=False)
        
        try: # More tiny details!
            parser._positionals.title = "Positional arguments"
            parser._optionals.title = "Optional arguments"
        except AttributeError:
            pass

        parser.add_argument('soundtrack',
                            help="The ID of the soundtrack, used at the end of its URL (e.g. \"jumping-flash\").\n"
                            "If it doesn't exist (or --search is specified, orrrr too many arguments are supplied),\n"
                            "all the positional arguments together are used as a search term.")
        parser.add_argument('outPath', metavar='download directory', nargs='?',
                            help="The directory to download the soundtrack to.\n"
                            "Defaults to creating a new directory with the soundtrack ID as its name.")
        parser.add_argument('trailingArguments', nargs='*', help=argparse.SUPPRESS)
        
        parser.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS,
                            help="Show this help and exit.")
        parser.add_argument('-s', '--search', action='store_true',
                            help="Always search, regardless of whether the specified soundtrack ID exists or not.")

        arguments = parser.parse_args()

        try:
            soundtrack = arguments.soundtrack.decode(sys.getfilesystemencoding())
        except AttributeError: # Python 3's argv is in Unicode
            soundtrack = arguments.soundtrack

        outPath = arguments.outPath if arguments.outPath is not None else soundtrack

        # I think this makes the most sense for people who aren't used to the
        # command line - this'll yield useful results even if you just type
        # in an entire soundtrack name as arguments without quotation marks.
        onlySearch = arguments.search or len(arguments.trailingArguments) > 1
        searchTerm = [soundtrack] + ([outPath] if arguments.outPath is not None else [])
        searchTerm += arguments.trailingArguments
        try:
            searchTerm = ' '.join(arg.decode(sys.getfilesystemencoding()) for arg in searchTerm)
        except AttributeError: # Python 3, again
            searchTerm = ' '.join(searchTerm)
        searchTerm = searchTerm.replace('-', ' ')

        try:
            if onlySearch:
                searchResults = search(searchTerm)
                if searchResults:
                    print("Soundtracks found (to download, "
                          "run \"{} soundtrack-name\"):".format(script_name))
                    for soundtrack in searchResults:
                        print(soundtrack.id)
                else:
                    print("No soundtracks found.")
            else:
                try:
                    download(soundtrack, outPath, verbose=True)
                except NonexistentSoundtrackError:
                    searchResults = search(searchTerm)
                    print("\nThe soundtrack \"{}\" does not seem to exist.".format(soundtrack))

                    if searchResults: # aww yeah we gon' do some searchin'
                        print()
                        print("These exist, though:")
                        for soundtrack in searchResults:
                            print(soundtrack.id)
                except KeyboardInterrupt:
                    print("Stopped download.")
        except requests.ConnectionError:
            print("Could not connect to The Hylia.")
            print("Make sure you have a working internet connection.")
        except Exception as e:
            print()
            print("An unexpected error occurred! "
                  "If it isn't too much to ask, please report to "
                  "https://github.com/obskyr/thehylia/issues.")
            print("Attach the following error message:")
            print()
            raise e
    
    doIt()
