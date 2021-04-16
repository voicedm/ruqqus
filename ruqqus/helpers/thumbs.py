import requests
from os import environ, remove
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from PIL import Image as PILimage
from flask import g
from io import BytesIO
import time

from .get import *
from ruqqus.__main__ import app, db_session

def expand_url(post_url, fragment_url):

    # convert src into full url
    if fragment_url.startswith("https://"):
        return fragment_url
    elif fragment_url.startswith("http://"):
        return f"https://{fragment_url.split('http://')[1]}"
    elif fragment_url.startswith('//'):
        return f"https:{fragment_url}"
    elif src.startswith('/'):
        parsed_url = urlparse(post_url)
        return f"https://{parsed_url.netloc}{fragment_url}"
    else:
        return f"{post_url}{'/' if not post_url.endswith('/') else ''}{fragment_url}"

def thumbnail_thread(pid, debug=False):

    #define debug print function
    def print_(x):
        if debug:
            try:
                print(x)
            except:
                pass

    db = db_session()

    post = get_post(pid, graceful=True, session=db)
    if not post:
        # account for possible follower lag
        time.sleep(60)
        post = get_post(pid, session=db)


    #First, determine the url to go off of
    #This is the embed url, if the post is allowed to be embedded, and the embedded url starts with http

    if post.domain_obj and post.domain_obj.show_thumbnail:
        print_("Post is likely hosted image")
        fetch_url=post.url
    elif post.embed_url and post.embed_url.startswith("https://"):
        print_("Post is likely embedded content")
        fetch_url=post.embed_url
    else:
        print_("Post is article content")
        fetch_url=post.url



    #get the content

    #mimic chrome browser agent
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.72 Safari/537.36"}

    try:
        print(f"loading {fetch_url}")
        x=requests.get(fetch_url, headers=headers)
    except:
        print_(f"unable to connect to {fetch_url}")
        return False, "Unable to connect to source"

    if x.status_code != 200:
        return False, f"Source returned status {x.status_code}."

    #if content is image, stick with that. Otherwise, parse html.

    if x.headers.get("Content-Type","")=="text/html":
        #parse html, find image, load image
        soup=BeautifulSoup(x.content, 'html.parser')
        #parse html

        #first, set metadata
        try:
            meta_title=soup.find('title')
            if meta_title:
                post.submission_aux.meta_title=str(meta_title.string)

            meta_desc = soup.find('meta', attrs={"name":"description"})
            if meta_desc:
                post.submission_aux.meta_description=meta_desc['content']

            if meta_title or meta_desc:
                db.add(post.submission_aux)
                db.commit()

        except Exception as e:
            print(f"Error while parsing for metadata: {e}")
            pass

        #create list of urls to check
        thumb_candidate_urls=[]

        #iterate through desired meta tags
        meta_tags = [
            "ruqqus:thumbnail",
            "twitter:image",
            "og:image",
            "thumbnail"
            ]

        for tag_name in meta_tags:
            
            print_(f"Looking for meta tag: {meta}")


            tag = soup.find(
                'meta', 
                attrs={
                    "name": tag_name, 
                    "content": True
                    }
                )
            if not tag:
                tag = soup.find(
                    'meta',
                    attrs={
                        'property': meta,
                        'content': True
                        }
                    )
            if tag:
                thumb_candidate_urls.append(expand_url(post.url, tag['content']))

        #parse html doc for <img> elements
        for tag in soup.find_all("img", attrs={'src':True}):
            thumb_candidate_urls.append(expand_url(post.url, tag['src']))


        #now we have a list of candidate urls to try
        for url in thumb_candidate_urls:
            print_(f"Trying url {url}")

            try:
                image_req=requests.get(url, headers=headers)
                break
            except:
                print_(f"Unable to connect to candidate url {url}")
                continue

            if image_req.status_code >= 400:
                print_(f"status code {x.status_code}")
                continue

            if not image_req.headers.get("Content-Type","").startswith("image/"):
                print_(f"bad type {image_req.headers.get("Content-Type","")}, try next")
                continue

            if image_req.headers.get("Content-Type","").startswith("image/svg"):
                print_("svg, try next")
                continue

            image = PILimage.open(BytesIO(x.content))
            if image.width < 30 or image.height < 30:
                print_("image too small, next")
                continue

            if image
            image = PILimage.open(BytesIO(image_req.content))
            break


        #getting here means we are out of candidate urls (or there never were any)
        print_("Unable to find image")
        return False, "No usable images"




    elif x.headers.get("Content-Type","").startswith("image/"):
        #image is originally loaded fetch_url
        print_("post url is direct image")
        image = PILimage.open(BytesIO(x.content))

    else:

        print_(f"Unknown content type {x.headers.get("Content-Type")}")
        return False, f"Unknown content type {x.headers.get("Content-Type")} for submitted content"


    print_(f"Have image, uploading")

    name = f"posts/{post.base36id}/thumb.png"
    tempname = name.replace("/", "_")

    with open(tempname, "wb") as file:
        for chunk in x.iter_content(1024):
            file.write(chunk)

    aws.upload_from_file(name, tempname, resize=(375, 227))
    post.has_thumb = True
    db.add(post)

    db.commit()

    db.close()

    try:
        remove(tempname)
    except FileNotFoundError:
        pass

    return True, "Success"





















def _thumbnail_thread(pid, debug=False):

    db = db_session()

    post = get_post(pid, graceful=True, session=db)
    if not post:
        # account for possible follower lag
        time.sleep(60)
        post = get_post(pid, session=db)

    # step 1: see if post is image

    #print("thumbnail thread")

    domain_obj = post.domain_obj

    #mimic chrome browser agent
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.72 Safari/537.36"}


    if debug:
        print(f"domain_obj {domain_obj}")
        if domain_obj:
            print(f"show thumb {domain_obj.show_thumbnail}")

    if domain_obj and domain_obj.show_thumbnail:

        if debug:
            print("trying direct url as image")

        if post.embed_url and post.embed_url.startswith("https://"):
            fetch_url=post.embed_url
        else:
            fetch_url=post.url

        try:
            x = requests.get(fetch_url, headers=headers)
        except:
            if debug:
                print("error connecting")
            return False, "Unable to connect to source"

        if x.status_code>=400:
            return False, f"Got status {x.status_code} from source"

        if x.headers.get("Content-Type", "/").split("/")[0] == "image":
            # image post, using submitted url

            name = f"posts/{post.base36id}/thumb.png"
            tempname = name.replace("/", "_")

            with open(tempname, "wb") as file:
                for chunk in x.iter_content(1024):
                    file.write(chunk)

            aws.upload_from_file(name, tempname, resize=(375, 227))
            post.has_thumb = True

            post.is_image = True
            db.add(post)

            db.commit()
            return True, x.status_code

    if debug:
        print("not direct image")
    try:
        x = requests.get(post.url, headers=headers)

    except:
        if debug:
            print("error connecting")
        return False, "Unable to connect to source"

    if x.status_code != 200 or not x.headers["Content-Type"].startswith(
            ("text/html", "image/")):
        if debug:
            print(f'not html post, status {x.status_code}')
        return False, "Unable to parse source"

    if x.headers["Content-Type"].startswith("image/"):

        if debug:
            print("submitted url is image, use that")
        pass
        # submitted url is image

    elif x.headers["Content-Type"].startswith("text/html"):


        if debug:
            print("parsing html doc")

        soup = BeautifulSoup(x.content, 'html.parser')

        #get meta title and description
        try:
            meta_title=soup.find('title')
            if meta_title:
                post.submission_aux.meta_title=str(meta_title.string)

            meta_desc = soup.find('meta', attrs={"name":"description"})
            if meta_desc:
                post.submission_aux.meta_description=meta_desc['content']

            if meta_title or meta_desc:
                db.add(post.submission_aux)
        except:
            pass

        metas = ["ruqqus:thumbnail",
                 "twitter:image",
                 "og:image",
                 "thumbnail"
                 ]

        for meta in metas:

            if debug:
                print(f"Looking for meta tag: {meta}")

            img = soup.find('meta', attrs={"name": meta, "content": True})
            if not img:
                img = soup.find(
                    'meta',
                    attrs={
                        'property': meta,
                        'content': True})
            if not img:
                continue
            try:
                if debug:
                    print(f"image load attempt from meta tag {meta}")
                x = requests.get(img['content'], headers=headers)
            except BaseException:
                if debug:
                    print("unable to connect")
                continue
            break

        if debug:
            print(img)
            print(x)

        if not img or not x or x.status_code != 200:

            if debug:
                print("no meta tags, looking for img")

            imgs = soup.find_all('img', src=True)
            if debug:
                print(f"found {len(imgs)} img elements")
            if imgs:
                #print("using <img> elements")
                pass
            else:
                #print('no image in doc')
                return False, "No images in source"

            # Loop through all images in document until we find one that works
            # (and isn't svg)
            for img in imgs:

                src = img["src"]

                #print("raw src: "+src)

                # convert src into full url
                if src.startswith("https://"):
                    pass
                elif src.startswith("http://"):
                    src = f"https://{src.split('http://')[1]}"
                elif src.startswith('//'):
                    src = f"https:{src}"
                elif src.startswith('/'):
                    parsed_url = urlparse(post.url)
                    src = f"https://{parsed_url.netloc}{src}"
                else:
                    src = f"{post.url}{'/' if not post.url.endswith('/') else ''}{src}"

                #print("full src: "+src)

                # load asset

                if debug:
                    print(f"attempting asset load {src}")
                x = requests.get(src, headers=headers)

                if x.status_code != 200:
                    if debug:
                        print(f"status code {x.status_code}, try next")
                    #print('not 200, next')
                    continue

                type = x.headers.get("Content-Type", "")

                if not type.startswith("image/"):
                    if debug:
                        print(f"bad type {type}, try next")
                    #print("not an image, next")
                    continue

                if type.startswith("image/svg"):
                    if debug:
                        print("svg, try next")
                    #print("svg image, next")
                    continue

                i = PILimage.open(BytesIO(x.content))
                if i.width < 30 or i.height < 30:
                    if debug:
                        print("image too small, next")
                    continue

                break
        else:
            if debug:
                print("meta tag found, no need to look for img tags")

    name = f"posts/{post.base36id}/thumb.png"
    tempname = name.replace("/", "_")

    with open(tempname, "wb") as file:
        for chunk in x.iter_content(1024):
            file.write(chunk)

    aws.upload_from_file(name, tempname, resize=(375, 227))
    post.has_thumb = True
    db.add(post)

    db.commit()

    db.close()

    try:
        remove(tempname)
    except FileNotFoundError:
        pass

    return True, "Success"
