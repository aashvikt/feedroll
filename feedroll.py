import fastfeedparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from shutil import rmtree
from os import makedirs
from datetime import date as d8
from string import Template
from html import escape

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <meta name="color-scheme" content="light dark">
        <title>feedroll: $title</title>
        <style>
            *, *::before, *::after { box-sizing: border-box; }
            :root {
                color-scheme: light dark;
                &:has(#light:checked) { color-scheme: light; };
                &:has(#dark:checked) { color-scheme: dark; };
            }
            input[name=theme] { position: absolute; opacity: 0; }
            input[name=theme]+label { cursor: pointer; }
            input[name=theme]:focus+label { outline: 1px solid; }
            input[name=theme]:checked+label { text-decoration: underline; }
            body {
                font: 14px "DejaVu Sans", sans-serif;
                color: light-dark(#1a1a1a, #eaeaea);
                background: light-dark(#fafafa, #121212);
                max-width: min(70ch, 100%);
                margin: 0 auto;
                padding: 0 1ch;
            }
            a { color: light-dark(blue, #0978db); }
        </style>
    </head>
    <body>
        <p>
            <strong><a href="/" title="main site">↩ ash</a></strong> ·
            <a href="/feedroll/sites">feed list</a> ·
            <a href="/posts/feedroll-py">about this feedroll</a> ·
            <input type=radio id=light name=theme aria-label="light mode"> <label for=light title="light mode">☼</label> /
            <input type=radio id=dark name=theme aria-label="dark mode"> <label for=dark title="dark mode">☾</label>
        </p>
        <h1>
            <a href="/feedroll">Feedroll</a>:
            $title
        </h1>
        <main>$content</main>
    </body>
</html>"""

def page(location, title, content):
    makedirs(f'public/{location}', exist_ok=True)

    with open(f"public/{location and location+'/'}index.html", 'w') as page_file:
        page_file.write(
            Template(
                PAGE_TEMPLATE
            ).substitute(
                title = title,
                content = content
            )
        )

def consume(feed_link): # insert "feed" joke
    print(feed_link)
    try: parsed = fastfeedparser.parse(feed_link)
    except Exception as exc:
        print(f'FAILED to parse {feed_link} due to {exc}')
        return

    slug = '-'.join(filter(None, feed_link.split('/')[2:-1]))
    ffp_link = escape(parsed.feed.get('link', feed_link))
    if not (feed_entries:=parsed.get('entries', [])): return

    polyauctorial = len({e.get('author', '') for e in feed_entries}) > 1

    page(
        slug,
        f"{slug}'s Feed",
        f"""<h2><a href="{ffp_link}">{escape(parsed.feed.get('title', slug))}</a></h2>
        <ul>{'\n'.join(
            f"<li>{e.get('published', '0000-01-01')[:10]}: <a href='{escape(e.get('link', ffp_link))}'>{escape(e.get('title', '?'))}</a>"
            + (' by ' + escape(e.get('author', '')) if polyauctorial else '')
            + '</li>'
            for e in feed_entries
        )}</ul>
        <p>End of feed.</p>"""
    )

    if info:=sorted(
        (
            (date[:10], e.get('link', feed_link), escape(title))
            for e in feed_entries
            if (date:=e.get('published')) and (title:=e.get('title'))
        ),
        key = lambda e: e[0],
        reverse = True
    ): return slug, info

rmtree('public', ignore_errors=True)
makedirs('public')

with open('feeds', 'r') as ffile:
    flinks = ffile.read().split()

FEED_ITEM_LIMIT, feeds, all_sites = 5, {}, ''

with ThreadPoolExecutor(max_workers=min(32, len(flinks))) as executor:
    for future in as_completed(executor.submit(consume, link) for link in flinks):
        if not (result:=future.result()): continue
        slug, info = result
        feeds[slug] = info[:FEED_ITEM_LIMIT]
        all_sites += f"<li><a href='/feedroll/{slug}'>{slug}</a></li>"

page('sites', "Site List", f"<ul>{all_sites}</ul>")

def days(date):
    y, m, d = map(int, date.split('-'))
    return d8(y, m, d).toordinal()

today, roll = days(max(e[0][0] for e in feeds.values())), []
CADENCE_WT = 1.2

for slug, entries in feeds.items():
    dates = [v[0] for v in entries if v[0][:3]!='0'*3]
    if len(dates)<2: continue
    timespan = max(days(max(dates))-days(min(dates)), 7)
    cadence = len(dates) / timespan

    for date, link, title in entries:
        age = today - days(date) + 1
        newness = 1 / age
        score = newness - (cadence*CADENCE_WT)
        roll.append((score, date, link, title, slug))

roll.sort(key = lambda e: e[0], reverse = True)

COUNT = 100

for batch in range(0, len(roll), COUNT):
    batch_li = '\n'.join(
        f"<li><a href='{link}'>{title}</a> "
        + f"<small>(<a style='color:inherit' href='/feedroll/{slug}'>{slug}</a>, {date})</small></li>"
        for _, date, link, title, slug in roll[batch:batch+COUNT]
    )

    page_number = int(1 + batch/COUNT)

    page(
        str(page_number) if page_number>1 else '',
        f"Page {page_number}",
        (
            f"<p><a href='/feedroll/{page_number-1 if page_number>2 else ''}'>← Previous page</a></p>" if page_number > 1 else '')
            + f"<ul>{batch_li}</ul>"
            + (f"<p><a href='/feedroll/{page_number+1}'>Next page →</a></p>" if batch+COUNT < len(roll) else ''
        )
    )