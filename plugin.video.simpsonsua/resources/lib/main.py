# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re

import requests
from bs4 import BeautifulSoup
# noinspection PyUnresolvedReferences
from codequick import Route, Resolver, Listitem, Script, run
from codequick.script import Settings
from codequick.utils import urljoin_partial

BASE_URL = "https://simpsonsua.tv/"
url_constructor = urljoin_partial(BASE_URL)
session = None


# noinspection PyUnusedLocal
@Route.register
def root(plugin, content_type="video"):
    """
    :param Route plugin: The plugin parent object.
    :param str content_type: The type of content being listed e.g. video, music. This is passed in from kodi and
                             we have no use for it as of yet.
    """
    for item in list_tiles(plugin, url_constructor("/multserialy-ukrainskoyu/")):
        yield item


@Route.register
def list_tiles(_, url, list_type="root", prefix=""):
    tiles = load_tiles(url)
    for tile in tiles:
        item = Listitem()
        item.label = prefix + tile["label"]
        item.art["thumb"] = tile["thumbnail"]
        if len(tile["desc"]) > 0:
            item.info["plot"] = tile["desc"]
            item.info["plot"] += "\n\n"
            item.info["plot"] += tile["url"]
        else:
            item.info["plot"] = tile["url"]

        if tile['type'] == "list":
            item.set_callback(list_tiles, url=tile["url"])
        else:
            item.set_callback(episode_info, url=tile["url"])
        yield item


@Route.register
def episode_info(_, url):
    response = get_session().get(url)
    bs = BeautifulSoup(response.text, "html.parser")

    title = ""
    subtitle = ""
    description = ""
    title_nodes = bs.select('div.poster.pinktext')
    if not title_nodes:
        title_nodes = bs.select('div.poster > h2')

    description_nodes = bs.select('div.fullstory')
    if title_nodes and len(title_nodes) > 0:
        title = title_nodes[0].get_text().title()
    if description_nodes and len(description_nodes) > 0:
        subtitle = description_nodes[0].get_text()
        description = "\n".join(map(lambda x: x.get_text(), description_nodes[1:]))

    subscription_elements = bs.select('.fullnews center a[href*="subscribe.html"]')
    subscription_needed = subscription_elements and len(subscription_elements) > 0
    item = None

    for i in (1, 2):
        player = bs.select('#Player' + str(i) + ' iframe')
        if not player or len(player) == 0:
            continue
        item = Listitem()
        item.info['plot'] = subtitle + "\n" + description
        item.label = "Джерело " + str(i) + " - " + title
        item.set_callback(play_video, url=player[0]['src'])
        yield item
    if not item:
        yield None
        if subscription_needed:
            Script.notify("Доу!", "Серія доступна лише Vip користувачам!")


@Resolver.register
def play_video(plugin, url):
    """
    :type plugin: Resolver
    :type url: unicode
    """

    try:
        return plugin.extract_source(url)
    except RuntimeError as e:
        # Cut the error message to 50 characters to avoid long live notification
        raise RuntimeError(str(e)[0:50]+'...')


def load_tiles(url):
    response = get_session().get(url)
    bs = BeautifulSoup(response.text, "html.parser")
    figures = bs.find_all('figure')
    result = []
    for figure in figures:
        if len(figure.find('img')['src']) == 0:
            continue

        url = figure.find('a')['href']
        image = "https://simpsonsua.tv/" + figure.find('img')['src']
        season = None
        episode = None
        season_match = re.search(r'.*?(sezon|season)-([0-9]+)/$', url, re.IGNORECASE)
        if season_match:
            season = season_match.group(2)
        season_episode_match = re.search(r'.*?([0-9]+)-(sezon|season)-([0-9]+)-(seriya|episode)', url, re.IGNORECASE)
        if season_episode_match:
            season = season_episode_match.group(1)
            episode = season_episode_match.group(3)
        title_tags = figure.select("div.descr.nazva")
        title = ""
        if title_tags and len(title_tags) > 0:
            title = title_tags[0].get_text().capitalize()

        if episode and len(episode) > 0:
            title = ("S{:02d}E{:02d} - " + title).format(int(season), int(episode))
        elif season and len(season) > 0:
            title = ("Season {:02d} " + title).format(int(season))

        if len(title) == 0:
            title_search = re.search(r'.*/([0-9]+-)?(.+)(/|.html)', url, re.IGNORECASE)
            if title_search:
                title = title_search.group(2)
            else:
                title_search = re.search(r'.*/(.*)\.jpg', image, re.IGNORECASE)
                title = title_search.group(1)

            title = re.sub("([a-z])([A-Z])", "\g<1> \g<2>", title)
            title = title.replace('-', ' ').title()

        description = figure.find_all("div", class_="descr")
        if description:
            description = description[-1].get_text()

        result.append({
            "type": 'list' if url[-1] == '/' else "episode",
            "label": title,
            "url": url,
            "thumbnail": image,
            "desc": description,
            "season": season,
            "episode": episode,
        })
    return result


def get_session():
    global session

    if session is None:
        session = requests.Session()
        data = {
            "login_name": Settings.get_string("simpsons_login"),
            "login_password": Settings.get_string("simpsons_password"),
            "submit": "",
            "login": "submit"
        }
        session.post(url_constructor("/index.php?do=login"), data=data)
    return session
