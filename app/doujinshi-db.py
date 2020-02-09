#!/usr/bin/env python3
import os, sys, json, re, zipfile, rarfile, requests, xmltodict, atexit, hashlib, base64, code, threading, subprocess, shutil
from datetime import datetime
from PIL      import Image, ImageStat
from io       import BytesIO
from math     import floor
from calendar import timegm
from time     import time, strptime, sleep
from random   import choice
from pony.orm import *
from flask    import Flask, abort, request, render_template

app                = Flask(__name__)
config             = {}
rename_queue       = {}
info               = {'contents': [], 'character': [], 'convention': [], 'publisher': [], 'collections': [], 'type': [], 'circle': [], 'author': [], 'parody': [], 'imprint': [], 'genre': []}
valid_imgs_exts    = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
valid_archive_exts = ['.rar', '.zip', '.cbr', '.cbz', '.cbr', '.cbz', '.cbr', '.cbz']
conv_archive_dict  = dict(zip(valid_archive_exts[:4], valid_archive_exts[4:]))
title_langs        = ['NAME_EN', 'NAME_JP', 'NAME_R']
orders             = [[0, 1, 2], [1, 0, 2], [2, 1, 0]]
ignore_case        = ['【Needs Dupe Checking】']
log_types          = { 'ERROR':      '\x1b[1;37;41mERROR!\x1b[0m',
                       'NOTICE':     '\x1b[1;30;47mNOTICE:\x1b[0m',
                       'PROCESSING': '\x1b[1;37;45mPROCESSING:\x1b[0m',
                       'SUCCESS':    '\x1b[1;37;42mSUCCESS!\x1b[0m' }
default_insert     = { 'path':      'Unknown', 'title':       'Unknown',
                       'date':      0,         'pages':       0,
                       'contents':  'Unknown', 'convention':  'Unknown',
                       'publisher': 'Unknown', 'collections': 'Unknown',
                       'type':      'Unknown', 'circle':      'Unknown',
                       'author':    'Unknown', 'parody':      'Unknown',
                       'imprint':   'Unknown', 'genre':       'Unknown',
                       'character': 'Unknown', 'rating':      0,
                       'bid':       0 }
random_sample      = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
no_renamer         = False
open_arcs          = {}
keep_thread_going  = True
db                 = Database()
sql_debug(True)

class Doujins(db.Entity):
  id          = PrimaryKey(int, auto=True)
  bid         = Required(int, unique=True)
  path        = Required(unicode, unique=True)
  title       = Required(unicode)
  date        = Required(int)
  pages       = Required(int)
  contents    = Required(LongUnicode)
  convention  = Required(unicode)
  publisher   = Required(unicode)
  collections = Required(unicode)
  type        = Required(unicode)
  circle      = Required(unicode)
  author      = Required(unicode)
  parody      = Required(unicode)
  imprint     = Required(unicode)
  genre       = Required(unicode)
  character   = Required(unicode)
  rating      = Optional(int, default=0)

class Covers(db.Entity):
  id          = PrimaryKey(int, auto=False)
  cover       = Required(bytes)
  hash        = Required(str, 32, unique=True)

class Timer():
  def __init__(self):
    self.start = time()

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    print('The function took {} seconds to complete'.format(time() - self.start))

class Mutex():
  def __init__(self):
    self.lock = threading.Lock()

  def __enter__(self):
    self.lock.acquire()

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.lock.release()

open_arcs_lock = Mutex()
rename_queue_lock = Mutex()

def safe_rename(dir, path):
  basename = os.path.basename(path)
  head, tail = os.path.splitext(basename)
  dst = os.path.join(dir, basename)
  count = 2

  while os.path.exists(dst):
    dst = os.path.join(dir, '{} ({}){}'.format(head, count, tail))
    count += 1

  try:
    shutil.move(path, dst)
  except OSError as e:
    abort('\x1b[1;37;41mERROR!\x1b[0m Failed to move "{}": {}'.format(path, str(e)))

def random_string(len):
  return ''.join(choice(random_sample) for i in range(len))

def random_id():
  return "{}-{}-{}-{}".format(random_string(4), random_string(4), random_string(4), random_string(4))

def doujin_to_dict(d, with_cover=False):
  return { 'path':      d.path,      'title':       d.title,
           'date':      d.date,      'pages':       d.pages,
           'contents':  d.contents,  'convention':  d.convention,
           'publisher': d.publisher, 'collections': d.collections,
           'type':      d.type,      'circle':      d.circle,
           'author':    d.author,    'parody':      d.parody,
           'imprint':   d.imprint,   'genre':       d.genre,
           'character': d.character, 'rating':      d.rating,
           'bid':       d.bid,       'cover': base64.b64encode(Covers.get(id=d.bid).cover).decode("utf-8") if with_cover else '' }

def open_archive(path):
  try:
    return zipfile.ZipFile(path) if valid_archive_exts.index(os.path.splitext(path)[-1]) % 2 else rarfile.RarFile(path)
  except (zipfile.BadZipfile, zipfile.LargeZipFile, rarfile.Error) as e:
    return 'Archive "{}" extraction failed: {}'.format(path, str(e))
  except:
    import traceback
    return 'Archive extraction failed "{}": Unknown error ({})'.format(path, traceback.format_exc().splitlines()[-1])

def get_archive_cover(path):
  arc = open_archive(path)
  if isinstance(arc, str):
    return { 'status': 'ERROR', 'message': arc }

  try:
    cover = [name for name in sorted(arc.namelist()) if os.path.splitext(name)[-1].lower() in valid_imgs_exts][0]
  except Exception as e:
    return { 'status': 'ERROR', 'message': 'Archive "{}" extraction failed: No valid cover images found'.format(path) }

  try:
    cover = Image.open(BytesIO(arc.read(cover))).convert('RGB')
    if config['ignore_grayscale'] or config['ignore_greyscale']:
      stat = ImageStat.Stat(cover)
      if sum(stat.sum) / 3 == stat.sum[0]:
        return { 'status': 'NOTICE', 'message': 'Archive {} cover greyscale, ignoring'.format(path) }
    ret = cover
  except Exception as e:
    return { 'status': 'ERROR', 'message': 'Archive "{}" failed to process cover: {}'.format(path, str(e)) }
  finally:
    arc.close()

  return { 'status': 'SUCCESS', 'cover': ret }

@app.route('/', methods=['GET', 'POST'])
def root():
  with db_session:
    if request.method == 'POST':
      data = json.loads(request.form['data']);
      data['search'] = data['search'].lower()
      if request.form['one'] == 'yes':
        return render_template('index.html', doujins=[doujin_to_dict(Doujins.get(title=data['search']))])
      else:
        ret = []
        for d in select(d for d in Doujins if data['search'] in d.title.lower())[:]:
          valid = True
          for t, v in data['tags'].items():
            x = getattr(d, t)
            if '|' in x:
              xx = x.split('|')
              for vv in v:
                if not vv in xx:
                  valid = False
                  break
              if not valid:
                break
            else:
              if not x in v:
                valid = False
                break
          if valid:
            ret.append(doujin_to_dict(d))          
        return render_template('index.html', doujins=ret)
    else:
      return render_template('index.html', doujins=[doujin_to_dict(d) for d in Doujins.select_random(9)])

@app.route('/<path:path>')
def static_proxy(path):
  return app.send_static_file(path)

@app.errorhandler(404)
def page_not_found(e):
  return render_template('error.html', error_code=404, error_message="Page not found"), 404

@app.errorhandler(500)
def internal_server_error(e):
  return render_template('error.html', error_code=500, error_message="Internal server error"), 500

@app.route('/<path:a>/<path:b>')
def tag_search(a, b):
  with db_session:
    ret = None
    if a == 'contents':
      ret = [doujin_to_dict(x) for x in select(d for d in Doujins if b in d.contents)[:]]
    elif a == 'character':
      ret = [doujin_to_dict(x) for x in select(d for d in Doujins if b in d.character)[:]]
    elif a == 'convention':
      ret = [doujin_to_dict(x) for x in select(d for d in Doujins if b == d.convention)[:]]
    elif a == 'publisher':
      ret = [doujin_to_dict(x) for x in select(d for d in Doujins if b == d.publisher)[:]]
    elif a == 'collections':
      ret = [doujin_to_dict(x) for x in select(d for d in Doujins if b == d.collections)[:]]
    elif a == 'type':
      ret = [doujin_to_dict(x) for x in select(d for d in Doujins if b == d.type)[:]]
    elif a == 'circle':
      ret = [doujin_to_dict(x) for x in select(d for d in Doujins if b == d.circle)[:]]
    elif a == 'author':
      ret = [doujin_to_dict(x) for x in select(d for d in Doujins if b in d.author)[:]]
    elif a == 'parody':
      ret = [doujin_to_dict(x) for x in select(d for d in Doujins if b in d.parody)[:]]
    elif a == 'imprint':
      ret = [doujin_to_dict(x) for x in select(d for d in Doujins if b == d.imprint)[:]]
    elif a == 'genre':
      ret = [doujin_to_dict(x) for x in select(d for d in Doujins if b == d.genre)[:]]
    elif a == 'rating':
      b = int(b)
      if b < 0 or b > 5:
        abort(404)
      else:
        ret = [doujin_to_dict(x) for x in select(d for d in Doujins if b == d.rating)[:]]
    else:
      abort(404)
    return render_template('index.html', doujins=ret, option=a, tag=b, tags=[1, 2, 3, 4, 5] if a == 'rating' else info[a])

@app.route('/api/cover/<int:id>')
def get_cover(id):
  with db_session:
    c = Covers.get(id=id)
    if not c:
      abort(404)
    return base64.b64encode(c.cover).decode("utf-8") 

@app.route('/api/info/<path:path>')
def get_info(path):
  if path in info:
    return json.dumps(info[path])
  else:
    abort(404)

@app.route('/api/open/remote/<int:id>')
def open_remote(id):
  with db_session:
    p = select(d.path for d in Doujins if d.bid == id)[:]
    if not p:
      abort(404)
    path =  config['paths']['out'] + p[0]
    if not os.path.exists(path) or not "open_cmd" in config:
      abort(404)
    try:
      subprocess.check_call([config['open_cmd'], path])
      return 'SUCCESS'
    except Exception as e:
      abort(500)

@app.route('/api/open/web/<int:id>')
def open_web(id):
  with db_session:
    p = select(d.path for d in Doujins if d.bid == id)[:]
    if not p:
      abort(404)
    path =  config['paths']['out'] + p[0]
    if not os.path.exists(path):
      abort(404)
    with open_arcs_lock:
      if id in open_arcs:
        return open_arcs[id]['guid']
      arc = None
      try:
        arc = open_archive(path)
      except Exception as e:
        abort(500)
      pages = [name for name in sorted(arc.namelist()) if os.path.splitext(name)[-1].lower() in valid_imgs_exts]
      open_arcs[str(id)] = { 'arc': arc, 'pages': pages, 'last_access': int(time()) }
      return json.dumps({ 'id': id, 'pages': len(pages) })

@app.route('/api/page/<path:id>/<int:page>')
def get_page(id, page):
  with open_arcs_lock:
    if not id in open_arcs:
      open_web(id)
    if page < 0 or page > len(open_arcs[id]['pages']):
      abort(404)
    open_arcs[id]['last_access'] = time()
    return base64.b64encode(BytesIO(open_arcs[id]['arc'].read(open_arcs[id]['pages'][page])).getvalue()).decode("utf-8")

@app.route('/api/close/<path:id>')
def close_doujin(id):
  with open_arcs_lock:
    if not id in open_arcs:
      abort(404)
    open_arcs[id]['arc'].close()
    del open_arcs[id]
    return str(id)

@app.route('/api/rate/<path:id>/<int:rating>')
def rate_doujin(id, rating):
  with db_session:
    d = Doujins.get(bid=id)
    if not d or rating < 0 or rating > 5:
      abort(404)
    d.rating = rating
    commit()
    return id

@app.route('/api/delete/<path:id>')
def delete_doujin(id):
  with open_arcs_lock:
    if id in open_arcs:
      try:
        open_arcs[id]['arc'].close()
        del open_arcs[id]
      except Exception as e:
        abort(500)
  with db_session:
    d = Doujins.get(bid=id)
    c = Covers.get(id=id)
    if not d or not c:
      abort(404)
    path = config['paths']['out'] + d.path
    if not os.path.exists(path):
      abort(404)
    safe_rename(config['paths']['fail'], path)
    d.delete()
    c.delete()
  return id

@app.route('/api/autocomplete/tag/<path:a>/<path:b>')
def autocomplete_tag(a, b):
  a = a.lower()
  if not len(a) or not a in info.keys() or not len(b):
    return '[]'
  b = b.lower()
  ret = []
  for x in info[a]:
    if b in x.lower():
      ret.append(x)
  return json.dumps(ret)

@app.route('/api/autocomplete/unknown/<path:a>')
def autocomplete_unknown(a):
  a = a.lower()
  if not len(a):
    return '[]'
  ret = []
  for k, v in info.items():
    for vv in v:
      if a in vv.lower():
        ret.append("{}:{}".format(k, vv))
  return json.dumps(ret)

@app.route('/api/autocomplete/check/<path:a>/<path:b>')
def check_valid_tag(a, b):
  a = a.lower()
  if not len(a) or not a in info.keys() or not len(b):
    return 'no'
  b = b.lower()
  for x in info[a]:
    if b in x.lower():
      return 'yes'
  return 'no'

@app.route('/api/autocomplete/regular', methods=['POST'])
def autocomplete_regular():
  data = request.get_json(silent=True)
  with db_session:
    return json.dumps(list(select(d.title for d in Doujins if data['search'] in d.title.lower())[:]))

def get_files(input):
  for fd, subfds, fns in os.walk(input):
    for fn in fns:
      yield os.path.join(fd, fn)

def get_files_list(input):
  return [f for f in get_files(input) if os.path.splitext(f)[-1] in valid_archive_exts]

@db_session
def db_doctor():
  actions = { 'delete': [d for d in select((d.path, d.id) for d in Doujins)[:] if not os.path.exists(config['paths']['out'] + d[0])], 'move': [] }

  cut_len    = len(config['paths']['out'])
  valid_exts = ['.rar', '.zip', '.cbr', '.cbz']

  for fn in get_files(config['paths']['out']):
    new_fn = fn[cut_len:]
    if os.path.splitext(new_fn)[-1] in valid_exts:
      if not Doujins.get(path=new_fn):
        actions['move'].append(fn)

  if not len(actions['delete']) and not len(actions['move']):
    add_log('SUCCESS', 'Everything is fine! Nothing out of place')
  else:
    if len(actions['delete']):
      add_log('NOTICE', 'I want to delete {} row(s)'.format(len(actions['delete'])))
      for a in actions['delete']:
        print("\t-", a)
    if len(actions['move']):
      add_log('NOTICE', 'I want to move {} file(s)'.format(len(actions['move'])))
      for a in actions['move']:
        print("\t-", a)

    do_it = input('\nWould you like to perform these actions? [y/n]\n')
    if do_it.lower() == 'yes' or do_it.lower() == 'y':
      with db_session:
        for a in actions['delete']:
          try:
            a = Doujins[a[1]]
            Covers.get(id=a.bid).delete()
            a.delete()
          except Exception as e:
            add_log('ERROR', 'Failed to delete row - {}'.format(str(e)))
      for a in actions['move']:
        safe_rename(config['paths']['fail'], a)

      add_log('SUCCESS', 'All finished, {} row(s) deleted and {} file(s) moved'.format(len(actions['delete']), len(actions['move'])))
    else:
      add_log('NOTICE', 'No actions taken...')

def api_test(key):
  resp = requests.get('http://www.doujinshi.org/api/{}/'.format(key), timeout=10)
  try:
    resp.raise_for_status()
  except requests.exceptions.HTTPError as e:
    abort(str(e))

  root = xmltodict.parse(resp.content)['LIST']
  if 'USER' in root:
    return { 'status': 'OK', 'user': root['USER']['User'], 'id': root['USER']['@id'], 'queries': int(root['USER']['Queries']) }
  else:
    return { 'status': 'ERROR', 'code': root['ERROR']['CODE'], 'message': root['ERROR']['EXACT'] }

def get_preferred_lang_str(type):
  return (['NAME_' + config['langs']['preferred'].upper() if config['langs']['preferred'] else 'NAME_EN'] + ['NAME_' + l.upper() for l in ['en', 'jp', 'r'] if l in config['langs']['exceptions'] and type in config['langs']['exceptions'][l]])[-1]

def hash_replace(hash, hay):
  return re.compile('|'.join(map(re.escape, hash))).sub(lambda x: hash[x.group(0)], hay)

def image_search(cover):
  resp = requests.post('http://doujinshi.mugimugi.org/api/{}/?S=imageSearch'.format(config['api']), files={'img': cover.getvalue()}, timeout=100)
  try:
    resp.raise_for_status()
  except requests.exceptions.HTTPError as e:
    return { 'status': 'ERROR', 'message': str(e) }

  config['queries'] -= 1
  root = xmltodict.parse(resp.content)['LIST']
  if 'ERROR' in root:
    return { 'status': 'ERROR', 'message': root['ERROR']['EXACT'], 'code': int(root['ERROR']['CODE']) }

  highest_match = float(root['BOOK'][0]['@search'][:-1].replace(',', '.'))
  if highest_match < config['min_threshold']:
    return { 'status': 'NOTICE', 'message': 'Skipping, match % below minimum threshold' }

  ret = []
  for i, book in enumerate([root['BOOK'][0]] if highest_match > (config['threshold'] if 'threshold' in config else 75) else root['BOOK'][:3]):
    ret.append({
        'bid':        int(book['@ID'][1:]),
        'match':      floor(float(book['@search'][:-1].replace(',', '.'))),
        'pages':      int(book['DATA_PAGES']),
        'date':       0 if book['DATE_RELEASED'] == '0000-00-00' else int(timegm(strptime(book['DATE_RELEASED'], '%Y-%m-%d'))),
        'all_titles': [book[n] for n in title_langs if book[n]],
        'title':      [book[title_langs[n]] for n in orders[title_langs.index(get_preferred_lang_str('title'))] if book[title_langs[n]]][0],
        'magazine':   bool(book['DATA_MAGAZINE']),
        'anthology':  bool(book['DATA_ANTHOLOGY']),
        'copyshi':    bool(book['DATA_COPYSHI'])})
    ret[i]['cover_url'] = 'http://img.doujinshi.org/{}/{}/{}.jpg'.format('big' if i == 0 else 'tn', str(int(floor(ret[i]['bid'] / 2000))), str(ret[i]['bid']))

    for item in book['LINKS']['ITEM']:
      t = item['@TYPE']
      if t not in ret[i]:
        ret[i][t] = []

      test = [item[title_langs[n]] for n in orders[title_langs.index(get_preferred_lang_str(t))] if item[title_langs[n]]][0]
      if test not in ignore_case:
        ret[i][t].append(test)

    for key in ret[i].keys():
      if isinstance(ret[i][key], list) and len(ret[i][key]) == 1:
        ret[i][key] = ret[i][key][0]

  return { 'status': 'SUCCESS', 'matches': ret }

def rename_archive(path, data):
  data['date'] = 'Unknown' if not data['date'] else datetime.fromtimestamp(int(data['date'])).strftime('%Y-%m-%d')
  if not data['pages']:
    data['pages'] = 0

  to = "{}/{}{}".format(config['paths']['out'], hash_replace(config['replace'], hash_replace(config['replace'], hash_replace({'%' + k: v[0] if isinstance(v, list) else str(v) for k, v in data.items()}, config['patterns'][data['type']] if data['type'] in config['patterns'] else config['patterns']['default']))), conv_archive_dict[os.path.splitext(path)[-1]])
  if os.path.exists(to):
    return { 'status': 'ERROR', 'message': 'Archive already exists "{}"'.format(to) }
  else:
    try:
      to_dir = os.path.split(to)[0]
      if not os.path.exists(to_dir):
        try:
          os.makedirs(to_dir)
        except OSError as e:
          return { 'status': 'ERROR', 'message': str(e) }
      shutil.move(path, to)
      return { 'status': 'SUCCESS', 'path': to }
    except OSError as e:
      return { 'status': 'ERROR', 'message': str(e) }

def fix_invalid_chars(str):
  return str.translate({ord(i):None for i in '/\\?%*:|"<>.'})

def finalize_rename(path, match, cover):
  match = {**default_insert, **match}
  for k, v in match.items():
    if isinstance(v, list):
      match[k] = [fix_invalid_chars(x.strip()) for x in v]
    elif isinstance(v, str):
      if k == 'cover_url':
        continue
      match[k] = fix_invalid_chars(v)

  rename_match = match.copy()  
  to = rename_archive(path, rename_match)
  if to['status'] != 'SUCCESS':
    add_log(to['status'], to['message'])
    safe_rename(config['paths']['fail'], path)
    return
  else:
    to = to['path']

  add_log('SUCCESS', '"{}" moved to "{}"'.format(os.path.basename(path), os.path.basename(to)))
  match['path'] = to[len(config['paths']['out']):]
  for k, v in match.items():
    if isinstance(v, list):
      match[k] = '|'.join(v)

  with db_session:
    if Doujins.get(bid=match['bid']):
      add_log('ERROR', "Archive '{}, {}' already in database!".format(match['path'], match['bid']))
      safe_rename(config['paths']['fail'], to)
      return
    else:
      try:
        Doujins(bid         = match['bid'],         path      = match['path'],
                title       = match['title'],       date      = match['date'],
                pages       = match['pages'],       contents  = match['contents'],
                convention  = match['convention'],  publisher = match['publisher'],
                collections = match['collections'], type      = match['type'],
                circle      = match['circle'],      author    = match['author'],
                parody      = match['parody'],      imprint   = match['imprint'],
                genre       = match['genre'],       character = match['character'],
                rating      = match['rating'] if 'rating' in match else 0)
      except:
        add_log('ERROR', 'Failed to put doujin into database! {}'.format(sys.exc_info()[0]))
        safe_rename(config['paths']['fail'], to)
      try:
        Covers(id=match['bid'], cover=cover.getvalue(), hash=hashlib.md5(cover.getvalue()).hexdigest())
        for k, v in match.items():
          if not k in info.keys():
            continue
          if '|' in v:
            vv = v.split('|')
            for vvv in vv:
              if not vvv in info[k]:
                info[k].append(vvv)
          else:
            if not v in info[k]:
              info[k].append(v)
      except Exception as e:
        Doujins.get(bid=mtach['bid']).delete()
        add_log('ERROR', 'Failed to put cover into database! {}'.format(sys.exc_info()[0]))
        safe_rename(config['paths']['fail'], to)

def add_log(type, msg):
  print("{} {}".format(log_types[type], msg))

@app.route('/api/queue')
def get_rename_queue():
  with rename_queue_lock:
    return json.dumps(rename_queue)

@app.route('/api/queue/<path:path>/<int:id>')
def rename_from_queue(path, id):
  with rename_queue_lock:
    id -= 1
    if not path in rename_queue or id >= len(rename_queue[path]['match']):
      abort(404)
    if id >= 0:
      cover = None
      if config['use_source']:
        cover = BytesIO(base64.b64decode(rename_queue[path]['cover']))
      else:
        resp = requests.get(rename_queue[path]['match'][id]['cover_url'], timeout=100)
        try:
          resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
          abort(500)
        cover = BytesIO(resp.content)
      finalize_rename(rename_queue[path]['path'], rename_queue[path]['match'][id], cover) 
    else:
      add_log('NOTICE', 'Archive "{}" skipped!'.format(rename_queue[path]['path']))
      safe_rename(config['paths']['fail'], rename_queue[path]['path'])
    del rename_queue[path]
    return path

def rename_worker():
  files = get_files_list(config['paths']['in'])
  while keep_thread_going:
    if files:
      for path in files:
        with rename_queue_lock:
          skip_this = False
          for k, v in rename_queue.items():
            if v['path'] == path:
              skip_this = True
              break
          if skip_this:
            continue

        add_log('PROCESSING', path)

        tmp_cover = get_archive_cover(path)
        if tmp_cover['status'] != 'SUCCESS':
          safe_rename(config['paths']['fail'], path)
          add_log(tmp_cover['status'], tmp_cover['message'])
          continue

        tmp_thumb_cover = tmp_cover['cover'].copy()
        tmp_thumb_cover.thumbnail((500, 500))
        thumb_cover = BytesIO()
        tmp_thumb_cover.save(thumb_cover, 'JPEG')
        cover = BytesIO()
        tmp_cover['cover'].save(cover, 'JPEG')

        match = image_search(thumb_cover)
        if match['status'] != 'SUCCESS':
          if match['code'] == 2:
            add_log(match['status'], match['message'])
            abort(2)
            continue
          if match['code'] in [1, 3, 6, 8]:
            print("\x1b[1;37;41mERROR!\x1b[0m {} (#{})".format(match['message'], match['code']))
            abort(match['code'])
          else:
            add_log(match['status'], match['message'])
            safe_rename(config['paths']['fail'], path)
            continue

        match = match['matches']
        if len(match) > 1:
          rid = random_id()
          add_log('NOTICE', 'Archive needs checking, (ID: {})'.format(rid))
          with rename_queue_lock:
            rename_queue[rid] = { 'path': path, 'cover': base64.b64encode(cover.getvalue()).decode("utf-8"), 'match': match }
        else:
          finalize_rename(path, match[0], cover)

    sleep(10)
    files = get_files_list(config['paths']['in'])

def open_arcs_worker():
  while True:
    to_del = []
    with open_arcs_lock:
      for k, v in open_arcs.items():
        if time() - v['last_access'] > 180:
          try:
            v['arc'].close()
          except Exception as e:
            pass
          to_del.append(k)
      for k in to_del:
        del open_arcs[k]
    sleep(60)

if __name__ == '__main__':
  config_path = [fh for fh in ['{}/.doujinshi.json'.format(os.environ['HOME']), '{}/.config/doujinshi.json'.format(os.environ['HOME']), '.doujinshi.json'] if os.path.exists(fh)]
  if config_path:
    with open(config_path[0]) as fh:
      config = {**{'api': '', 'threshold': 75, 'min_threshold': 0, 'use_source': False, 'ignore_grayscale': False, 'paths': {'in': '', 'out': '', 'fail': ''}, 'patterns': {'default': '%type/%parody/%title [%circle, %pages]'}, 'langs': {'preferred': 'en', 'exceptions': {}}, 'replace': {}}, **json.load(fh)}

    for k, v in config['paths'].items():
      if not os.path.exists(v):
        try:
          os.makedirs(v)
        except OSError as e:
          abort('Failed to create directory "{}": {}'.format(v, str(e)))
  else:
    abort('Failed to find valid config path')

  if not config['db_type']:
    abort('No database type in cofig! Set one or set no_db to true')

  if config['db_type'] == 'sqlite':
    db.bind(provider='sqlite', filename=config['db_path'], create_db=True)
  elif config['db_type'] == 'mysql':
    db.bind(provider='mysql', host=config['db_host'], user=config['db_user'], passwd=config['db_pass'], db=config['db_database'], charset='utf8mb4', use_unicode=True)
  elif config['db_type'] == 'postgres':
    db.bind(provider='postgres', user=config['db_user'], password=config['db_pass'], host=config['db_host'], database=config['db_database'])
  elif config['db_type'] == 'oracle':
    db.bind(provider='oracle', user=config['db_user'], password=config['db_pass'], dsn=config['db_dsn'])
  else:
    abort('Invalid database type "{}"'.format(config['db_type']))

  db.generate_mapping(create_tables=True)

  def exit_handler():
    global keep_thread_going
    keep_thread_going = False
    for k, v in open_arcs.items():
      try:
        v['arc'].close()
      except:
        pass
  atexit.register(exit_handler)

  if "break" in sys.argv:
    with db_session:
      code.interact(local=locals())

  if "check" in sys.argv:
    db_doctor()
    sys.exit(0)

  if "test" in sys.argv:
    with db_session:
      with Timer():
        select(d for d in Doujins)[:]
      with Timer():
        select(c for c in Covers)[:]
    sys.exit(0)

  with db_session:
    tmp = select(d for d in Doujins)[:]
    for d in tmp:
      for k, v in doujin_to_dict(d).items():
        if k in info:
          info[k].append(v.split('|') if '|' in v else [v])
    del tmp

  for k, v in info.items():
    info[k] = sorted(list(set(sum(v, []))))

  if not 'api' in config or not re.match(r'^[0-9a-f]{20}$', config['api'], re.IGNORECASE):
    add_log('ERROR', 'Invalid API key "{}"'.format(config['api']))
    add_log('NOTICE', 'Renamer is disabled!')
    no_renamer = True
  else:
    test = api_test(config['api'])
    if test['status'] == 'ERROR':
      add_log('ERROR', "{} (#{})".format(test['message'], test['code']))
      add_log('NOTICE', 'Renamer is disabled!')
      no_renamer = True
    else:
      config['queries'] = test['queries']
      if config['queries'] == 0:
        add_log('ERROR', "No queries left for today...")
        add_log('NOTICE', 'Renamer is disabled!')
        no_renamer = True
      else:
        add_log("SUCCESS", "Hello, {} (#{}), {} queries left".format(test['user'], test['id'], test['queries']))

  if not no_renamer:
    t = threading.Thread(target=rename_worker)
    t.daemon = True
    t.start()
  t2 = threading.Thread(target=open_arcs_worker)
  t2.daemon = True
  t2.start()

  app.run(host='0.0.0.0', debug=True, use_reloader=False)
