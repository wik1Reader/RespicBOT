# -*- coding: utf-8 -*
from __future__ import absolute_import, unicode_literals
from datetime import datetime, timezone, timedelta
import os
import requests
import pandas as pd
import pywikibot
from pywikibot import pagegenerators, Bot

i1 = 0.964
point = 0


def get_current_year_and_month():
  now = datetime.now()
  return now.year, now.month


def is_anonymous_user(self, username):
  """
  Check if the given user is an anonymous user (IP user).

  :param username: The username to check.
  :return: True if the user is anonymous, False otherwise.
  """
  user = pywikibot.User(self.site, username)
  return user.isAnonymous()


class RespiceBOT(Bot):
  """BOT que revierte desde ORES"""

  def __init__(self, generator, site=None, **kwargs):
    super(RespiceBOT, self).__init__(**kwargs)
    self.available_options.update({'gf': 0.085, 'dm': 0.970, 'wiki': 'kowiki'})

    self.generator = generator
    self.site = site
    if not self.site.logged_in():
      self.site.login()
    self.wiki = "{}{}".format(self.site.lang,
                              str(self.site.family).replace('pedia', ''))

  def run(self):
    global point
    print('run')
    for page in filter(self.valid, self.generator):
      try:
        revision, buena_fe, danina, resultado, algorithm = self.check_risk(
            page)
      except Exception as exp:
        print(exp)
        continue

      if revision is None:
        continue
      kst = timezone(timedelta(hours=9))
      data = [
          revision, buena_fe, danina, resultado,
          page._rcinfo.get('user'),
          page.title(),
          datetime.now(kst).strftime('%Y%m%d%H%M%S'),
          int(datetime.now(kst).timestamp()), algorithm
      ]
      i = i1
      self.do_log(data)
      if is_anonymous_user(self, page._rcinfo.get('user')):
        i = 0.977
      if point >= i:
        self.do_reverse(page, page._rcinfo.get('user'))
        if self.site.family.name == 'wikipedia' and self.site.lang == 'ko':
          ##self.check_user(page._rcinfo.get('user'), page.title())
          self.check_pagina(page.title())

  def valid(self, page):
    print('valid')
    """
        Check if we need to check the page from the LiveRCGenerator

        @param page: Page to check
        """
    return (
        # Solo lo que sea edicion
        page._rcinfo.get('type') == 'edit' and
        # que no sea bot
        not page._rcinfo.get('bot') and
        # que este en el espacio principal o anexo
        page._rcinfo.get('namespace') in {0, 104} and
        # que no sea yo mismo
        page._rcinfo.get('user') != self.site.username() and
        # que no sea una reversa (tag de reversa, los RV manual no los considera)
        'mw-rollback' not in list(page.revisions(total=10))[0]['tags'])

  def check_risk(self, page):
    print('check_risk')
    global point
    i = i1
    """Send a request to Wikimedia API to check the revert-risk of the page"""
    headers = {
        'User-Agent':
        'RespiceBOT - an ORES/revertrisk-language-agnostic counter vandalism tool'
    }
    revision = page._rcinfo.get('revision')
    revision_check = str(revision.get('new'))
    url = 'https://api.wikimedia.org/service/lw/inference/v1/models/revertrisk-language-agnostic:predict'

    try:
      data = requests.post(url=url,
                           headers=headers,
                           json={
                               "rev_id": revision_check,
                               "lang": self.site.lang
                           }).json()
    except requests.RequestException as e:
      print(f"Error in API request: {e}")
      # Handle the error or consider returning a default value
      return None, None, None, None, None

    if 'output' in data and 'probabilities' in data['output']:
      point = data['output']['probabilities']['true']
      return revision_check, data['output']['probabilities']['false'], data['output']['probabilities']['true'], \
          data['output']['probabilities']['true'] > i, 'revertrisk-language-agnostic'
    else:
      print("Unexpected API response format")
      # Handle the unexpected format or consider returning a default value
      return None, None, None, None, None

  def do_log(self, data):
    wiki = self.wiki
    general = os.path.join(os.path.dirname(os.path.realpath(__file__)), "log",
                           f"{wiki}-general.log")
    positivo = os.path.join(os.path.dirname(os.path.realpath(__file__)), "log",
                            f"{wiki}-positivo.log")
    print('loging')
    with open(general, encoding="utf-8", mode="a+") as archivo:
      archivo.write("\t".join(map(str, data)) + "\n")

    if data[3]:
      with open(positivo, encoding="utf-8", mode="a+") as archivo:
        archivo.write("\t".join(map(str, data)) + "\n")

  """def check_user(self, user, page):
        # Check for consecutive reversions by the same user
        wiki = self.wiki
        positive_log_path = os.path.join(os.path.dirname(
            os.path.realpath(__file__)), 'log', f"{wiki}-positivo.log")
        df_reversas = pd.read_csv(
            positive_log_path, header=None, delimiter='\t')
        user_reversions = df_reversas[(
            df_reversas[4] == user) & (df_reversas[5] == page)]

        # Handle two consecutive reversions by a registered user
         if len(user_reversions) == 2:
            if not pywikibot.User(self.site, user).isAnonymous():
                talk_page = pywikibot.Page(self.site, title=user, ns=3)
                talk_page.text += u"\n{{subst:Aviso prueba2|" + page + "}} ~~~~"
                summary = u'Aviso de pruebas a usuario tras reversiones consecutivas'
                try:
                    talk_page.save(summary=summary)
                except pywikibot.Error as e:
                    print(f"Error saving talk page: {e}")
                return

        # Handle four consecutive reversions by any user
        if len(user_reversions) == 4:
            vandalism_page = pywikibot.Page(
                self.site, title='Vandalismo en curso', ns=2)
            template = "\n" + u'{{subst:'
            template += 'ReportevandalismoIP' if pywikibot.User(
                self.site, user).isAnonymous() else 'Reportevandalismo'
            template += u'|1=' + user
            template += u'|2=Reversiones: ' + (', '.join(
                map(lambda x: u'[[Special:Diff/' + str(x) + '|diff: ' + str(x) + ']]', user_reversions[0])))
            template += u'}}'
            vandalism_page.text += "\n" + template
            summary = u'Reportando al usuario [[Special:Contributions/' + \
                user + '|' + user + ']] por posibles ediciones vándalicas'
            try:
                vandalism_page.save(summary=summary)
            except pywikibot.Error as e:
                print(f"Error saving vandalism page: {e}")
        return """

  #토론이 필요한 사항

  def check_pagina(self, pagina):
    y365, m365 = get_current_year_and_month()
    wiki = self.wiki
    positivo = "{0}/log/{1}-positivo.log".format(
        os.path.dirname(os.path.realpath(__file__)), wiki)
    df_reversas = pd.read_csv(positivo, header=None, delimiter='\t')
    page = df_reversas[5] == pagina
    past = (int(datetime.utcnow().timestamp()) - df_reversas[7]) < (
        60 * 60 * 2)  # 4 horas
    users = df_reversas[page & past][4].nunique()
    rows = df_reversas[page & past]
    if len(rows) < 6 or users < 2:
      return

    tabp = pywikibot.Page(self.site,
                          title='문서 관리 요청/' + y365 + '년' + m365 + '월',
                          ns=4)
    if tabp.get().find('{{{{a|{0}}}}}'.format(pagina)) != -1:
      return
    tpl = "\n" + \
        '{{{{풀기:사:RespicBOT/TABP|페이지={0}|서명=~~~~}}}}'.format(
            pagina)
    tabp.text += "\n" + tpl
    try:
      tabp.save(summary=u'[[{0}]] 문서를 보호 요청함'.format(pagina))
    except:
      pass
    return

  def do_reverse(self, page, user):
    try:
      print('reversa de ' + page.title())

      self.site.rollbackpage(page, user=user)
    except Exception as exp:
      print(exp)
      pass


def main(*args):
  print('main')
  opts = {}
  local_args = pywikibot.handle_args(args)
  for arg in local_args:
    if arg.startswith('-gf:'):
      opts['gf'] = float(arg[4:])
    elif arg.startswith('-dm:'):
      opts['dm'] = float(arg[4:])
    elif arg.startswith('-wiki:'):
      opts['wiki'] = arg[6:]

  site = pywikibot.Site()
  if 'wiki' in opts and opts['wiki'] != 'kowiki':
    lang = opts['wiki'][0:2]
    family = opts['wiki'][2:]
    site = pywikibot.Site(lang, family)

  bot = RespiceBOT(pagegenerators.LiveRCPageGenerator(site), site=site, **opts)
  bot.run()


if __name__ == '__main__':
  print('start')
  main()
