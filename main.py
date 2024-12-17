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

def how_user_edit(self, username):
    user = pywikibot.User(self.site, username)
    return user.editCount()

def how_old_user(self, username):
  user = pywikibot.User(self.site, username)
  now = datetime.now()
  first_edit = next(user.contributions(total=1, reverse=True))
  first_time = first_edit[2]
  timediff = now - first_time
  return timediff.days

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
            if is_anonymous_user(self, page._rcinfo.get('user')):
              i = 0.985
              print(i)
            if how_old_user(self, page._rcinfo.get('user'))>10:
              i = 0.988
              print(i)
            # 그룹 검사, 정해져 있는 그룹이 아니면 로깅 수행
            if how_user_edit(self, page._rcinfo.get('user'))>100: 
              i = 0.99
              print(i)
            if not is_admin_user(page._rcinfo.get('user')):
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
            page_1 = pywikibot.Page(self.site, title="user:RespiceBOT/true2_log", ns=3)
            page_1.text += "\t"+"[[특:차이/"+str(data[0])+"|"+str(data[0])+"]]"+"\t"+str(data[1])+"\t"+str(data[2])+"\t"+str(data[3])+"\t"+"[[특:기여/"+str(data[4])+"]]"+"\t"+"[["+str(data[5])+"]]"+"\t"+str(data[6])+"\t"+str(data[7])+"\n"
            summary = "[[특:차이/"+str(data[0])+"|"+str(data[0])+"]]" + "[[특:기여/"+str(data[4])+"]]"+"[["+str(data[5])+"]]"
            page_1.save(summary=summary)
            check_user(self, str(data[4]), page) 
        except Exception as exp:
            print(exp)
            pass

def check_user(self, user, page):
    import re
    from datetime import datetime
    wiki = self.wiki
    log_page_title = f"User:RespiceBOT/true2_log"
    log_page = pywikibot.Page(self.site, log_page_title)
    
    try:
        existing_log_content = log_page.text
    except pywikibot.Error:
        existing_log_content = ""
    
    # 로그 파일의 각 줄에서 사용자 이름과 페이지를 추출
    reversion_lines = existing_log_content.split('\n')
    user_reversions = []
    
    for line in reversion_lines:
        match = re.search(r"\[\[특:기여/([^\]]+)\]\]\s*", line)
        if match:
            log_user = match.group(1)  # 사용자 이름
            log_page = match.group(2)  # 페이지 제목
            if log_user == user and log_page == page:
                user_reversions.append(line)
    
    # 리버전 횟수 확인
    if len(user_reversions) >= 2:  # 되돌림 횟수가 2 이상일 경우
        # 익명 사용자인지 확인
        if not pywikibot.User(self.site, user).isAnonymous():
            # 'User:Respice post te/positive log' 페이지에서 사용자 목록 받아오기
            log_page = pywikibot.Page(self.site, "User:Respice post te/positive log")
            log_text = log_page.text
            notification_users = []

            # 문서에서 각 사용자 이름을 추출하여 알림 사용자 목록에 추가
            for line in log_text.splitlines():
                if line.strip() and line[0] != "#":  # 빈 줄이나 주석 제외
                    notification_users.append(line.strip())  # 사용자 이름 추가

            for notify_user in notification_users:
                try:
                    # 알림을 보낼 사용자 토론 페이지 정의
                    talk_page = pywikibot.Page(self.site, f"User talk:{notify_user}")
                    if talk_page.exists():
                        talk_page.text += (
                            f"\n== 알림 ==\n"
                            f"* \n알림 내용: 점검이 필요한 사용자 [[User:{user}]]를 감지함\n"
                            f"* 문서 제목: [[{page}]]\n"
                            f"* 리버전: {len(user_reversions)}\n"
                            f"pywikibot으로 자동화됨. ~~~~"
                        )
                    else:
                        talk_page.text = (
                            f"== 알림 ==\n"
                            f"* 알림 내용: 점검이 필요한 사용자 [[User:{user}]]를 감지함\n"
                            f"* 문서 제목: [[{page}]]\n"
                            f"* 리버전: {len(user_reversions)}\n"
                            f"pywikibot으로 자동화됨. ~~~~"
                        )
                    # 요약과 함께 저장
                    summary = f"점검 필요 알림:{user}"
                    talk_page.save(summary=summary)
                except pywikibot.Error as e:
                    print(f"Error saving talk page for {notify_user}: {e}")

            # 로그 업데이트
            try:
                log_page.text += f"{datetime.now().isoformat()}\t{user}\t{page}\n"
                log_page.save(summary="반복된 되돌림 로깅")
            except pywikibot.Error as e:
                print(f"Error updating log page: {e}")
            
            return


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
