# -*- coding: utf-8 -*
from __future__ import absolute_import, unicode_literals

# 필요한 모듈들을 임포트
from datetime import datetime, timezone, timedelta
import os
import requests
import pandas as pd
import pywikibot
from pywikibot import pagegenerators, Bot

# 기본 임계값 설정
i1 = 0.965 
point = 0

# 현재 연도와 월을 반환하는 함수
def get_current_year_and_month():
    now = datetime.now()
    return now.year, now.month

# 사용자가 익명(비회원, IP 기반) 유저인지 확인하는 함수
def is_anonymous_user(self, username):
  user = pywikibot.User(self.site, username)
  return user.isAnonymous()

# 사용자가 관리자, 기록보호자, 점검자, 점검 면제자, 인터페이스 관리자, 장기 인증된 사용자  그룹인지 확인하는 함수
def is_admin_user(username):
  site = pywikibot.Site()
  try:
    user = pywikibot.User(site, username)
    groups = user.groups()
    admin_groups = {'sysop', 'Bureaucrat', 'Oversighter', 'CheckUser', 'Autopatrolled', 'Interface administrator', 'extendedconfirmed'}
    return any(group in admin_groups for group in groups)
  except pywikibot.NoUsername:
    print(f"The username '{username}' does not exist.")
    return False
  except Exception as e:
    print(f"An error occurred: {e}")
    return False

# 소스의 메인 로봇 클래스 정의
class RespiceBOT(Bot):

    # 초기화 함수, 여러 설정을 초기화
    def __init__(self, generator, site=None, **kwargs):
        super(RespiceBOT, self).__init__(**kwargs)
        self.available_options.update({
            'gf': 0.585, # Good faith 편집인지 판별하는 기준
            'dm': 0.978, # 피해를 주는 편집인지 판별하는 기준
            'wiki': 'kowiki' # 작업 대상 위키
        })

        self.generator = generator
        self.site = site
        if not self.site.logged_in():
            self.site.login()
        self.wiki = "{}{}".format(self.site.lang, str(self.site.family).replace('pedia', ''))

    # 실제 실행 함수, 페이지를 필터링하고 리비전 위험을 검사
    def run(self): 
        global point
        global i1
        i = 0
        print('run')
        for page in filter(self.valid, self.generator):
            try:
                revision, buena_fe, danina, resultado, algorithm = self.check_risk(page)
            except Exception as exp:
                print(exp)
                continue

            if revision is None:
                continue
            kst = timezone(timedelta(hours=9))
            data = [revision, buena_fe, danina, resultado, page._rcinfo.get('user'), page.title(), datetime.now(kst).strftime('%Y%m%d%H%M%S'), int(datetime.now(kst).timestamp()), algorithm]
            # 익명사용자의 편집인 경우 임계값 조정
            if is_anonymous_user(self, page._rcinfo.get('user')):
                  i = 0.977
            # 그룹 검사, 정해져 있는 그룹이 아니면 로깅 수행
            if not is_admin_user(page._rcinfo.get('user')):
                # 포인트가 임계값 이상이면 되돌리기 수행
                if point >= i:
                  print(point)
                  self.do_reverse(self, data) 

    # 페이지가 조건을 만족하는지 확인하는 필터 함수
    def valid(self, page):
        print('valid')
        return (
            page._rcinfo.get('type') == 'edit' and # 편집 유형
            not page._rcinfo.get('bot') and # 봇이 아니어야 함
            page._rcinfo.get('namespace') in {0, 104} and # 이름공간 체크(0:본문)
            page._rcinfo.get('user') != self.site.username() and # 자기자신의 편집 체크
            'mw-rollback' not in list(page.revisions(total=10))[0]['tags'] # 되돌리기 태그로 되돌린 편집이 아닌지 체크
        )

    # 문서의 되돌림 위험성을 검사하는 함수
    def check_risk(self, page):
        global point
        i = i1
        headers = {
            'User-Agent': 'RespiceBOT - an ORES/revertrisk-language-agnostic counter vandalism tool'}
        revision = page._rcinfo.get('revision')
        revision_check = str(revision.get('new'))
        url = 'https://api.wikimedia.org/service/lw/inference/v1/models/revertrisk-language-agnostic:predict'

        # API 요청
        try:
            data = requests.post(url=url, headers=headers, json={"rev_id": revision_check, "lang": self.site.lang}).json()
        except requests.RequestException as e:
            print(f"Error in API request: {e}")
            return None, None, None, None, None

        if 'output' in data and 'probabilities' in data['output']:
            if is_anonymous_user(self, page._rcinfo.get('user')):
              i = 0.977
            point = data['output']['probabilities']['true']
            return revision_check, data['output']['probabilities']['false'], data['output']['probabilities']['true'], \
                data['output']['probabilities']['true'] > i, 'revertrisk-language-agnostic'
        else:
            print("Unexpected API response format")
            return None, None, None, None, None

    def do_reverse(self, page, data):
        try:
            print("log_2")
            page_1 = pywikibot.Page(self.site, title="user:RespiceBOT/ture_log", ns=3)
            page_1.text += "\t"+"[[특:차이/"+str(data[0])+"|"+str(data[0])+"]]"+"\t"+str(data[1])+"\t"+str(data[2])+"\t"+str(data[3])+"\t"+"[[특:기여/"+str(data[4])+"]]"+"\t"+"[["+str(data[5])+"]]"+"\t"+str(data[6])+"\t"+str(data[7])+"<br>"
            summary = "TEST"
            page_1.save(summary=summary)
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

# 스크립트 진입점
if __name__ == '__main__':
    print('start')
    main()
